"""QA 读取资格唯一真源（票 W06-IMPL §3）。

全仓只这一处把「一条语料记录的候选状态」判出来；读出口只把数据送进来、把裁决读出来，
不许再各拼一份 `eligibility`/`approval_source` 的形状（§4 项 4 的 AST 守卫钉这条）。

判据**分键不分门**（同一记录在两出口回同一个 reason 键）：
① 带链却读不到 SQL 行（库挂／找不到行）⇒ fail-closed，reason=state；
② eligibility ∈ {revoked, quarantined} ⇒ 拒，reason=state；
③ approval_source 为 unknown/NULL（未知来源＝不可服务，C03 形状 P）⇒ 拒，reason=provenance；
④ 复用既有 `qa_provenance_verifiable`／`qa_citations_in_kb` 两个判据本体（`qa_read_eligible` 全判据），
   不在出口里重抄一份解析/查库循环。

保留的放行面：**没有候选链**（`qa_candidate_id` 缺失）的语料记录，状态轴不适用 ⇒ 仍由来源/时效判定。
「缺链 ⇒ fail-closed」只对**带链**记录生效（带链却读不到＝数据损坏，必须拒）；这是
`test_qa_provenance_guard.py`／`test_qa_citation_gate_symmetry.py` 两条对照腿钉死的放行面，不许打掉。

注入出口（`main._build_messages`）只咨询**状态轴**（撤回/审批来源/缺链 fail-closed）：
来源可校验与引用在库两条判定仍在产生处（`request_bootstrap.prepare_fast_path`）做一次，
注入出口不重复扫库——否则每个带 qa_hit 的请求都多一次 Chroma 读，也会把未打桩的注入对照腿打死。

票 W06-FIX（2026-10-17）两条就地修正：
① F3/V2：合成判据从「零生产调用者」变成**产生处的唯一入口**——`prepare_fast_path` 现在调
   `qa_read_eligible`（一次判全：状态轴→来源→引用），不再自己写一遍排序。
   两排序不一致这条由 `tests/test_qa_read_eligibility.py::test_producer_and_direct_return_exit_report_the_same_reason`
   钉住（同一条记录在产生处与直返出口必须回同一个 reason）。
② F9/V8：一次带 QA 命中的请求原先开两条 `SessionLocal()`（两个出口各一条），现在状态装载走
   `load_read_state_for` 的请求内复用（`QaHit.state_slot`）⇒ 一条。判据是**计数替身**，不是读代码。
"""

import hashlib
import json
import logging
from collections.abc import Mapping
from dataclasses import dataclass

import database
import models
import retrieval
import retrieval_core as rc

logger = logging.getLogger("legal.chat")

# 拒绝读数里**两道门各自的既有布尔键**（票 AUTH-A／票 W1 在册口径：分键不分门）。
# 合成一键就只知道「语料被拦了」而不知道是哪道门在衰减，所以这两键继续由**产生处**落，
# 出口侧只落 `qa_eligibility_reason`（同一次拒绝在两处各留一次读数会让计数翻倍 ⇒ 见 `log_read_denial` 的形参）。
_GATE_BOOLEAN = {"provenance": "qa_provenance_refused", "citation": "qa_citation_refused"}


@dataclass(frozen=True)
class Eligibility:
    allow: bool
    reason: str = ""


@dataclass(frozen=True)
class QaDependency:
    """**不可变** QA 依赖快照（票 W06-B §4.1）：生成实际用到的 QA 记录的冻结值。

    只含进程内部核对用的字段——`candidate_id`（SQL 主键）、`vector_doc_id`（链映射）、
    `eligibility_version`（资格版本）与 `record_digest`（question/answer/evidence 的确定性摘要）。
    摘要**只在进程内部核对**，绝不落日志/报告（题干可能就是用户问句，答案/证据属 AUTH-3 禁项）。
    不携带可变 `QaHit`/`state_slot`，也不从答案引用反推依赖。
    """

    candidate_id: int
    vector_doc_id: str
    eligibility_version: int
    record_digest: str


class QaHit(dict):
    """`knowledge_service.search_qa` 的返回形状：普通 dict ＋ 一个**请求内**共享的 SQL 状态槽。

    为什么把槽挂在对象上而不是加一个键（票 W06-FIX F9/V8）：
    ① 加键会打穿「`result["qa_hit"] == 手搓 dict`」这一族既有判据（产生处的接缝用例就长这样）；
    ② 状态槽是**一次请求的生命周期**属性，不是语料内容，把它做成键等于把 SQL 读数混进向量 payload；
    ③ 挂在对象上还有一层安全含义：`dict(hit, ...)` 派生出的 plain dict **拿不到槽** ⇒
       评测探针/改链路的对照腿仍走「各自自查」的老路径，不会因为缓存而读到别人塞的状态。

    所以：**有槽 ⇒ 一次 SELECT 服务一次请求里的三个判定点；没槽 ⇒ 每个判定点自己读一次**
    （语义完全相同，只是不省那次读）。槽随 `pre` 一起被回收，不存在跨请求残留。
    """

    state_slot: dict
    doc_link: dict

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.state_slot = {}
        self.doc_link = {}
        self.doc_id: str | None = None


def _select_candidate_id_by_doc_id(doc_id):
    """按向量 doc id 回查候选行 id：**只发一条 SELECT，走 `vector_doc_id` 上的索引**。

    查不到返回 None（＝这条语料确实没有候选行，仍按来源/时效判定）；查不动**照抛**，
    由 `resolve_chain` 归成 fail-closed——「库挂了」绝不能被读成「没有链所以放行」。
    """
    db = database.SessionLocal()
    try:
        row = db.query(models.QaCandidate.id).filter(models.QaCandidate.vector_doc_id == str(doc_id)).first()
        return int(row[0]) if row is not None else None
    finally:
        db.close()


def resolve_chain(hit):
    """解析一条读出口记录的候选链，返回 `(cand_id, lookup_failed)`（票 C20 形状①）。

    顺序：① 向量 metadata 里那份链（快路径，新写入都有）；② 没有就用 `doc_id` 回查 SQL。
    ⇒ 链的**权威存放处**从此是 SQL（`qa_candidates.vector_doc_id`），向量 metadata 那份只是省一次读；
      这也修掉了 C03=P 落地时留着的那个洞：回填只写 SQL，而读出口只看 metadata ⇒ 已签的
      "未核订存量退出直返"在现网一条也没发生（实测 279 题 277 → 277，`linked` 两次都是 0）。
    回查异常 ⇒ `(None, True)` ⇒ 判据按 fail-closed 拒（reason=state）。
    同一条 hit 只查一次（结果记在 `doc_link` 槽里，三出口共用）。
    手搓的 plain dict 两个槽都没有 ⇒ 与改前逐字同行为（接缝判据不受影响）。
    """
    cand_id = hit.get("qa_candidate_id") if isinstance(hit, Mapping) else None
    if cand_id is not None:
        return cand_id, False
    doc_id = getattr(hit, "doc_id", None)
    if not doc_id:
        return None, False
    memo = getattr(hit, "doc_link", None)
    if isinstance(memo, dict) and memo:
        return memo.get("id"), bool(memo.get("failed"))
    try:
        found = _select_candidate_id_by_doc_id(doc_id)
        failed = False
    except Exception:
        logger.warning("qa_chain_lookup_failed", extra={"qa_eligibility_reason": "state"})
        found, failed = None, True
    if isinstance(memo, dict):
        memo.update({"id": found, "failed": failed})
    return found, failed


def resolve_candidate_id(hit):
    """只要链 id 的对外读法（忽略回查失败位）；判据内部一律用 `resolve_chain`。"""
    return resolve_chain(hit)[0]


def _as_meta(meta_or_doc_id) -> Mapping:
    """判据入参可为向量 metadata（Mapping）或向量 doc id（str，就地取回 metadata）。"""
    if isinstance(meta_or_doc_id, Mapping):
        return meta_or_doc_id
    doc_id = str(meta_or_doc_id)
    from knowledge_service import _qa_store  # 局部导入：仅在按 doc id 取数时碰 QA 集合，避免加载期纠缠

    data = _qa_store._collection.get(ids=[doc_id], include=["metadatas"])
    metas = data.get("metadatas") or []
    return metas[0] if metas and metas[0] else {}


def load_read_state(cand_id):
    """按候选 id 取回 SQL 状态 dict；找不到行／未接线返回 None（由判据 fail-closed）。

    会话即时开关，读的是 `database.SessionLocal`（测试 fixture 把它换到 tmp 引擎），
    所以读出口不依赖调用方持有的 session，也不为此产生跨层反向依赖。
    """
    if cand_id is None:
        return None
    db = database.SessionLocal()
    try:
        row = db.get(models.QaCandidate, cand_id)
        if row is None:
            return None
        return {
            "eligibility": row.eligibility,
            "approval_source": row.approval_source,
            "status": row.status,
            "vector_doc_id": row.vector_doc_id,
            # W06-C §5.1：派生 QA 的来源包（NULL=旧来源未知）。状态轴据此复核**传递依赖**。
            "qa_provenance": row.qa_provenance,
        }
    finally:
        db.close()


def _state_axis(meta, state) -> Eligibility | None:
    """§3①②③ 候选状态轴的唯一实现：返回拒绝裁决，或 None（放行/无链不适用）。

    票 C20（形状①）：链不再只认 metadata 那一份拷贝——`resolve_chain` 在缺键时按 doc id 回查 SQL。
    手搓的 plain dict 没有 `doc_id` 属性 ⇒ 走的路径与改前逐字相同。
    """
    cand_id, lookup_failed = resolve_chain(meta)
    if cand_id is None:
        # 回查失败（库挂）与「带链却读不到行」同归 fail-closed；真的没有链才谈"状态轴不适用"
        return Eligibility(False, "state") if lookup_failed else None
    if not state:
        return Eligibility(False, "state")  # 库挂／找不到行 ⇒ fail-closed
    if state.get("eligibility") in ("revoked", "quarantined"):
        return Eligibility(False, "state")
    if state.get("approval_source") in (None, "unknown"):
        return Eligibility(False, "provenance")  # 未知来源＝不可服务
    # W06-C §5.1：派生 QA 的**传递依赖**复核——从失效祖先生成的新 candidate 不得借新 id 绕过撤回。
    # 仅当该行真带了来源包（qa_provenance 非 NULL）时才多开一次复核会话；旧行 NULL 不受影响。
    prov = parse_provenance(state.get("qa_provenance"))
    if prov is not None:
        deps = dependencies_for_reuse(prov)
        if deps is None or not validate_dependencies(deps).allow:
            return Eligibility(False, "ancestor")
    return None


def _cand_id(hit):
    """链的解析口（metadata 快路径 → doc id 回查），全仓只有 `resolve_chain` 这一份。"""
    return resolve_chain(hit)[0] if isinstance(hit, Mapping) else None


def _load_state_safe(qa_hit):
    """状态装载的唯一入口：链由 `_cand_id` 解析，不在这里再读一遍 metadata 键。"""
    cand_id = _cand_id(qa_hit)
    try:
        return load_read_state(cand_id) if cand_id is not None else None
    except Exception:  # 库挂与「找不到行」同归 fail-closed：查不动不能算查得过
        logger.warning("qa_read_state_unavailable", extra={"qa_candidate_id": cand_id})
        return None


def load_read_state_for(hit, *, fresh: bool = False):
    """一条 qa_hit 的 SQL 状态：**同一次请求内只读一次**（票 W06-FIX F9/V8，把每请求两条 session 降到一条）。

    有槽（`QaHit`，即真 `search_qa` 出来的那条）⇒ 第一个判定点读一次，其余判定点复用；
    无槽（探针手搓的 plain dict）⇒ 每个判定点自己读一次。两者语义完全一致，只差那次 SELECT。
    复用范围严格限定在**同一个 qa_hit 对象**上，而该对象随 `pre` 活在一次请求里 ⇒
    撤回的可见性不受影响（下一条请求必然重读），也不会出现「今天的读服务昨天撤回前的状态」那种跨请求残留。

    票 W06-B §4.2：`fresh=True` 时**先清掉该 hit 的状态槽与链记忆**再重读（等价于开一条新 SQL 会话、
    不复用早期 ORM 读数）——阶段边界（P/O/W）与缓存命中后的复核走这条；阶段内仍可复用（默认 False）。
    """
    if fresh:
        slot = getattr(hit, "state_slot", None)
        if isinstance(slot, dict):
            slot.clear()
        link = getattr(hit, "doc_link", None)
        if isinstance(link, dict):
            link.clear()
        cand_id = _cand_id(hit)
        if cand_id is None:
            return None
        return _load_state_safe(hit)
    cand_id = _cand_id(hit)
    if cand_id is None:
        return None
    memo = getattr(hit, "state_slot", None)
    if not isinstance(memo, dict):
        return _load_state_safe(hit)
    if cand_id not in memo:
        memo[cand_id] = _load_state_safe(hit)
    return memo[cand_id]


def log_read_denial(hit, reason: str, *, with_gate_boolean: bool = False) -> None:
    """拒绝留痕的**唯一落点**（票 W06-FIX F10/V10）。

    改前这条只落 `qa_eligibility_reason`，而 `:114` 的注释与 `observability.py:170-172` 都写着
    「落归因键 + 候选行 id」⇒ 注释与字节不一致，归因指不到行。现在**两键一起落**：
    `qa_eligibility_reason`（state|provenance|citation）＋ `qa_candidate_id`（int，无链记录为 None ⇒
    JSON formatter 不写这个键，那条记录该看的读数是 `qa_write_unlinked`）。
    两键都是枚举/整数，不含题干与答案原文（AUTH-3 日志不落原文）。
    `with_gate_boolean` 只给产生处用（保住 `qa_provenance_refused`/`qa_citation_refused` 两个在册读数
    不被合成一键）；出口侧默认不落，否则一次拒绝在两个地方各计一次，指标就虚高了。
    """
    extra = {"qa_eligibility_reason": reason, "qa_candidate_id": _cand_id(hit)}
    if with_gate_boolean:
        gate = _GATE_BOOLEAN.get(reason)
        if gate:
            extra[gate] = True
    logger.warning("qa_read_eligible_denied reason=%s", reason, extra=extra)


def qa_read_eligible(meta_or_doc_id, state) -> Eligibility:
    """全判据（状态轴 + 来源可校验 + 引用在库）——单点真源，供一次性判定的调用方使用。"""
    meta = _as_meta(meta_or_doc_id)
    if not isinstance(meta_or_doc_id, Mapping) and meta.get("qa_candidate_id") is None:
        meta = dict(meta)  # 只在"按 doc id 调用"这一支复制一份；其余路径拿到的仍是同一份 Mapping
        try:
            meta["qa_candidate_id"] = _select_candidate_id_by_doc_id(str(meta_or_doc_id))
        except Exception:  # 与 `_state_axis` 同一个 fail-closed 口径：查不动不等于没有链
            logger.warning("qa_chain_lookup_failed", extra={"qa_eligibility_reason": "state"})
            return Eligibility(False, "state")
    verdict = _state_axis(meta, state)
    if verdict is not None:
        return verdict
    if not rc.qa_provenance_verifiable(meta):
        return Eligibility(False, "provenance")
    if not retrieval.qa_citations_in_kb(meta):
        return Eligibility(False, "citation")
    return Eligibility(True, "")


def evaluate_revocation_state(qa_hit, *, fresh: bool = False) -> Eligibility:
    """读出口用的一站式**状态轴**判定：从 qa_hit 取链 → 装载 SQL 状态（读不到即 fail-closed）→ 出裁决。

    状态装载走 `load_read_state_for`（同一次请求内复用那一次 SELECT，票 W06-FIX F9）。
    拒绝只经 `log_read_denial` 落归因键 + 候选 id（int），绝不落题干/答案原文（题干可能就是用户问句）。

    票 W06-B §4.2：`fresh=True` 传给 `load_read_state_for` ⇒ 清槽后新读（阶段边界复核用）。
    """
    verdict = _state_axis(qa_hit, load_read_state_for(qa_hit, fresh=fresh)) or Eligibility(True, "")
    if not verdict.allow:
        log_read_denial(qa_hit, verdict.reason)
    return verdict


# ==================== W06-B：不可变 QA 依赖快照与缓存读守 ====================
# §4.1：`None`＝依赖未知（不读/不写可复用缓存）；空 `tuple`＝该次完整构造输入**已确认没有使用 QA**；
# 非空 tuple＝完整 QA 依赖。摘要只在进程内部核对，绝不落日志/报告（题干即用户问句，答案/证据禁项）。


# 记录摘要的**内部格式版本**：L10（设计 §5.1）要求摘要覆盖来源包与 schema 版本，
# 只哈希 question/answer/evidence 不能检出"祖先来源包变化"。改了编码即等同换格式 ⇒ 旧缓存保守 miss。
_RECORD_DIGEST_SCHEMA_VERSION = 1


def _record_digest(question, answer, evidence, qa_provenance=None) -> str:
    """SQL 记录的确定性内部摘要（不落盘/不落日志）。

    L10（设计 §5.1）：纳入**来源包 + 其 schema 版本**——只哈希 question/answer/evidence 时，
    "祖先来源包变了"（撤回/新增依赖）检不出来，旧"已核"快照会被复用。字段顺序固定；来源包为
    NULL/空串时与旧口径同值（旧行不受影响），有来源包时摘要随其变化。
    """
    payload = json.dumps(
        [
            _RECORD_DIGEST_SCHEMA_VERSION,
            str(question or ""),
            str(answer or ""),
            str(evidence or ""),
            str(qa_provenance or ""),
        ],
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _hit_matches_row(row, hit) -> bool:
    """核 SQL 记录内容与选中 hit 一致（题干/答案/证据三字段逐字）。不一致 ⇒ 不做依赖快照。"""
    if not isinstance(hit, Mapping):
        return False
    return (
        str(getattr(row, "question", "") or "") == str(hit.get("question") or "")
        and str(getattr(row, "answer", "") or "") == str(hit.get("answer") or "")
        and str(getattr(row, "evidence", "") or "") == str(hit.get("evidence") or "")
    )


def capture_dependency(hit) -> QaDependency | None:
    """从一条**实际参与生成**的 hit 收集不可变依赖快照；拿不到可靠 SQL 身份 ⇒ None。

    收集时（§4.1）核 SQL 记录内容与选中 hit 一致、链映射一致，再保存冻结值。SQL 没有
    `law_as_of_basis` ⇒ 不把 created_at/eligibility_version 冒充法律版本（本函数根本不碰它们）。
    无可靠身份（无链、行不存在、内容不一致、链映射不一致、读取异常）一律 None（＝依赖未知）。
    """
    cand_id = _cand_id(hit)
    if cand_id is None:
        return None
    db = None
    try:
        db = database.SessionLocal()
        row = db.get(models.QaCandidate, cand_id)
        if row is None:
            return None
        doc_id = getattr(hit, "doc_id", None)
        if doc_id and row.vector_doc_id and str(doc_id) != str(row.vector_doc_id):
            return None
        if not _hit_matches_row(row, hit):
            return None
        return QaDependency(
            candidate_id=int(cand_id),
            vector_doc_id=str(row.vector_doc_id or ""),
            eligibility_version=int(row.eligibility_version or 1),
            record_digest=_record_digest(row.question, row.answer, row.evidence, getattr(row, "qa_provenance", None)),
        )
    except Exception:  # 库挂/查不动 ⇒ 依赖未知（不读/不写可复用缓存），绝不留原文
        logger.warning("qa_dependency_capture_failed", extra={"qa_candidate_id": cand_id})
        return None
    finally:
        if db is not None:
            db.close()


def _validate_one(db, dep: QaDependency) -> Eligibility:
    """单条依赖在**新 SQL 会话**上的复核：任一撤回/隔离/丢行/映射变化/版本变化/内容变化 ⇒ 拒绝。"""
    row = db.get(models.QaCandidate, dep.candidate_id)
    if row is None:
        return Eligibility(False, "missing")  # 丢行
    if row.eligibility in ("revoked", "quarantined"):
        return Eligibility(False, "state")  # 撤回/隔离
    if row.approval_source in (None, "unknown"):
        return Eligibility(False, "provenance")  # 未知来源
    if str(row.vector_doc_id or "") != str(dep.vector_doc_id):
        return Eligibility(False, "identity")  # 链映射变化
    if int(row.eligibility_version or 1) != int(dep.eligibility_version):
        return Eligibility(False, "version")  # 版本变化
    if _record_digest(row.question, row.answer, row.evidence, getattr(row, "qa_provenance", None)) != dep.record_digest:
        return Eligibility(False, "content")  # 记录内容或来源包（祖先）变化
    return Eligibility(True, "")


def validate_dependencies(deps) -> Eligibility:
    """复核一份不可变依赖快照（票 W06-B §4.1）：`None`＝依赖未知 ⇒ 不服务；空 tuple ⇒ 放行；非空逐条核。

    用**新的 SQL 会话**装一次，逐条核状态/身份/版本/内容；任一变化或读取异常 ⇒ miss。
    本函数由调用方投进线程池执行（fast-path 业务代码不得在主线程直接读同步 SQL）。
    """
    if deps is None:
        return Eligibility(False, "unknown")  # 依赖未知 ⇒ 不读/不写可复用缓存
    if not deps:
        return Eligibility(True, "")  # 已确认没有使用 QA
    db = None
    try:
        db = database.SessionLocal()
        for dep in deps:
            verdict = _validate_one(db, dep)
            if not verdict.allow:
                return verdict
    except Exception:  # 读取异常（含开会话失败）⇒ 不放行（异常≠已知无 QA）
        logger.warning("qa_dependency_validate_failed")
        return Eligibility(False, "unreadable")
    finally:
        if db is not None:
            db.close()
    return Eligibility(True, "")


# ==================== W06-C：来源包（Provenance envelope，§5.1）====================
# 消息 / 摘要 / 派生 QA 的**真实传递来源**。外层带 schema_version、complete 及依赖集合，
# 依赖类型**复用** W06-B 的 `QaDependency`；序列化/解析/签发只有本模块这一处入口（单一真源）。
PROVENANCE_SCHEMA_VERSION = 1
# 依赖/输入 id 的容量上限：超限**保守判未知**，绝不截断后仍称完整（§4.1/§5.1）。
MAX_QA_DEPENDENCIES = 64
MAX_INPUT_MESSAGE_IDS = 64


@dataclass(frozen=True)
class Provenance:
    """一条历史消息 / 摘要 / 派生 QA 的真实来源包（票 W06-C §5.1）。

    - `complete=True, qa_dependencies=()`：真实输入已证明**没有** QA 祖先；
    - `complete=True, qa_dependencies=[...]`：完整传递依赖；
    - `complete=False` / 坏 JSON / 未来未支持 schema 版本：来源未知
      （`parse_provenance` 返回 `None` 或 `dependencies_for_reuse` 返回 `None`），**绝不等价于无 QA 依赖**。

    列上的 `NULL`（`None`）＝旧来源未知——与"空依赖"是两种状态，`build_provenance` 里禁止互相代换。
    """

    complete: bool
    qa_dependencies: tuple[QaDependency, ...] = ()
    input_message_ids: tuple[int, ...] = ()
    schema_version: int = PROVENANCE_SCHEMA_VERSION


def _dep_payload(dep: QaDependency) -> dict:
    return {
        "candidate_id": int(dep.candidate_id),
        "vector_doc_id": str(dep.vector_doc_id),
        "eligibility_version": int(dep.eligibility_version),
        "record_digest": str(dep.record_digest),
    }


def _dep_from_payload(item) -> QaDependency | None:
    if not isinstance(item, dict):
        return None
    try:
        cid = item["candidate_id"]
        vdid = item["vector_doc_id"]
        ev = item["eligibility_version"]
        rd = item["record_digest"]
    except KeyError:
        return None
    if isinstance(cid, bool) or not isinstance(cid, int):
        return None
    if not isinstance(vdid, str) or not isinstance(rd, str):
        return None
    if isinstance(ev, bool) or not isinstance(ev, int):
        return None
    return QaDependency(int(cid), vdid, int(ev), rd)


def serialize_provenance(prov: Provenance) -> str:
    """来源包的**唯一序列化入口**（字段顺序固定、确定性 JSON）。"""
    payload = {
        "schema_version": int(prov.schema_version),
        "complete": bool(prov.complete),
        "qa_dependencies": [_dep_payload(d) for d in prov.qa_dependencies],
        "input_message_ids": [int(i) for i in prov.input_message_ids],
    }
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def parse_provenance(text) -> Provenance | None:
    """来源包的**唯一解析入口**。`None`/空串/坏 JSON/未来 schema/坏元素/超容量 ⇒ `None`（来源未知）。

    未知是保守的一侧：调用方不得把它降成"已知空依赖"。
    """
    if text is None or text == "":
        return None
    try:
        data = json.loads(text)
    except (ValueError, TypeError):
        return None
    if not isinstance(data, dict):
        return None
    schema_version = data.get("schema_version")
    if isinstance(schema_version, bool) or not isinstance(schema_version, int):
        return None
    if schema_version != PROVENANCE_SCHEMA_VERSION:
        return None  # 未来未支持的 schema 版本 ⇒ 来源未知，不作可信空集
    complete = data.get("complete")
    if not isinstance(complete, bool):
        return None
    raw_deps = data.get("qa_dependencies")
    if not isinstance(raw_deps, list):
        return None
    deps: list[QaDependency] = []
    for item in raw_deps:
        dep = _dep_from_payload(item)
        if dep is None:
            return None
        deps.append(dep)
    raw_ids = data.get("input_message_ids", [])
    if not isinstance(raw_ids, list):
        return None
    if any(isinstance(item, bool) or not isinstance(item, int) for item in raw_ids):
        return None
    if len(deps) > MAX_QA_DEPENDENCIES or len(raw_ids) > MAX_INPUT_MESSAGE_IDS:
        return None  # 容量超限 ⇒ 不许截断后仍称完整
    return Provenance(
        complete=complete,
        qa_dependencies=tuple(deps),
        input_message_ids=tuple(int(i) for i in raw_ids),
        schema_version=schema_version,
    )


def build_provenance(qa_dependencies, ancestors=(), input_message_ids=()) -> Provenance | None:
    """**唯一签发入口**：为一份生成 / 摘要 / 派生输入签发来源包。

    - `qa_dependencies`：本次实际使用的 QA 依赖（tuple）或 `None`（未知）；
    - `ancestors`：本次实际复用的历史消息 / 摘要 / 工具结果来源包；任一为 `None`（未知）或
      `complete=False` ⇒ 整体未知（未知祖先**传播未知**），不把未知/不完整当可信空集；
    - 依赖按 (candidate_id, vector_doc_id, eligibility_version, record_digest) 去重；容量超限 ⇒ 未知。
    """
    if qa_dependencies is None:
        return None  # 本次 QA 使用情况未知 ⇒ 整体未知
    deps: list[QaDependency] = list(qa_dependencies)
    ids: list[int] = [int(i) for i in input_message_ids]
    for ancestor in ancestors:
        if ancestor is None:
            return None  # 未知祖先 ⇒ 传播未知，绝不降成空集
        if not ancestor.complete:
            return None  # 不完整祖先包不作可信输入
        deps.extend(ancestor.qa_dependencies)
        ids.extend(ancestor.input_message_ids)
    seen = set()
    unique: list[QaDependency] = []
    for dep in deps:
        key = (dep.candidate_id, dep.vector_doc_id, dep.eligibility_version, dep.record_digest)
        if key in seen:
            continue
        seen.add(key)
        unique.append(dep)
    unique_ids = sorted({int(i) for i in ids})
    if len(unique) > MAX_QA_DEPENDENCIES or len(unique_ids) > MAX_INPUT_MESSAGE_IDS:
        return None  # 容量耗尽：保守判未知，不截断后谎称完整
    return Provenance(complete=True, qa_dependencies=tuple(unique), input_message_ids=tuple(unique_ids))


def dependencies_for_reuse(prov: Provenance | None):
    """把来源包还原成**可复核的依赖快照**给复用方：`None`＝来源未知（不是空集）；否则依赖元组。"""
    if prov is None or not prov.complete:
        return None
    return tuple(prov.qa_dependencies)


def provenance_state(prov: Provenance | None) -> Eligibility:
    """来源包复用前的状态：未知(False,'unknown') / 已知空(True) / 非空且逐条复核通过(True)。

    复核走 `validate_dependencies`（新 SQL 会话）。**未知不在此判"失效"**——H07（旧未知来源输入规则）
    未裁前，调用方按各路径既有行为处理，既不把未知当可信空集，也不静默全量屏蔽。
    """
    deps = dependencies_for_reuse(prov)
    if deps is None:
        return Eligibility(False, "unknown")
    return validate_dependencies(deps)


def has_self_reference(prov: Provenance | None, candidate_id: int) -> bool:
    """派生来源自引用检查：来源包里含 candidate_id 自身 ⇒ True（调用方据此拒签发，防借新 id 洗白）。"""
    if prov is None:
        return False
    return any(dep.candidate_id == int(candidate_id) for dep in prov.qa_dependencies)
