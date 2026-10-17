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
"""

import logging
from collections.abc import Mapping
from dataclasses import dataclass

import database
import models
import retrieval
import retrieval_core as rc

logger = logging.getLogger("legal.chat")


@dataclass(frozen=True)
class Eligibility:
    allow: bool
    reason: str = ""


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

    拒绝只落归因键 + 候选 id（int），绝不落题干/答案原文（题干可能就是用户问句）。
    """
    verdict = _state_axis(qa_hit, _load_state_safe(qa_hit)) or Eligibility(True, "")
    if not verdict.allow:
        logger.warning(
            "qa_read_eligible_denied reason=%s", verdict.reason, extra={"qa_eligibility_reason": verdict.reason}
        )
    return verdict
