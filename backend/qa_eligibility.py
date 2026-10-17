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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.state_slot = {}


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
        }
    finally:
        db.close()


def _state_axis(meta, state) -> Eligibility | None:
    """§3①②③ 候选状态轴的唯一实现：返回拒绝裁决，或 None（放行/无链不适用）。"""
    cand_id = meta.get("qa_candidate_id") if isinstance(meta, Mapping) else None
    if cand_id is None:
        return None  # 无链：状态轴不适用，交由来源/时效判定
    if not state:
        return Eligibility(False, "state")  # 库挂／找不到行 ⇒ fail-closed
    if state.get("eligibility") in ("revoked", "quarantined"):
        return Eligibility(False, "state")
    if state.get("approval_source") in (None, "unknown"):
        return Eligibility(False, "provenance")  # 未知来源＝不可服务
    return None


def _load_state_safe(qa_hit):
    cand_id = qa_hit.get("qa_candidate_id") if isinstance(qa_hit, Mapping) else None
    try:
        return load_read_state(cand_id) if cand_id is not None else None
    except Exception:  # 库挂与「找不到行」同归 fail-closed：查不动不能算查得过
        logger.warning("qa_read_state_unavailable", extra={"qa_candidate_id": cand_id})
        return None


def _cand_id(hit):
    return hit.get("qa_candidate_id") if isinstance(hit, Mapping) else None


def load_read_state_for(hit):
    """一条 qa_hit 的 SQL 状态：**同一次请求内只读一次**（票 W06-FIX F9/V8，把每请求两条 session 降到一条）。

    有槽（`QaHit`，即真 `search_qa` 出来的那条）⇒ 第一个判定点读一次，其余判定点复用；
    无槽（探针手搓的 plain dict）⇒ 每个判定点自己读一次。两者语义完全一致，只差那次 SELECT。
    复用范围严格限定在**同一个 qa_hit 对象**上，而该对象随 `pre` 活在一次请求里 ⇒
    撤回的可见性不受影响（下一条请求必然重读），也不会出现「今天的读服务昨天撤回前的状态」那种跨请求残留。
    """
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
    verdict = _state_axis(meta, state)
    if verdict is not None:
        return verdict
    if not rc.qa_provenance_verifiable(meta):
        return Eligibility(False, "provenance")
    if not retrieval.qa_citations_in_kb(meta):
        return Eligibility(False, "citation")
    return Eligibility(True, "")


def evaluate_revocation_state(qa_hit) -> Eligibility:
    """读出口用的一站式**状态轴**判定：从 qa_hit 取链 → 装载 SQL 状态（读不到即 fail-closed）→ 出裁决。

    状态装载走 `load_read_state_for`（同一次请求内复用那一次 SELECT，票 W06-FIX F9）。
    拒绝只经 `log_read_denial` 落归因键 + 候选 id（int），绝不落题干/答案原文（题干可能就是用户问句）。
    """
    verdict = _state_axis(qa_hit, load_read_state_for(qa_hit)) or Eligibility(True, "")
    if not verdict.allow:
        log_read_denial(qa_hit, verdict.reason)
    return verdict
