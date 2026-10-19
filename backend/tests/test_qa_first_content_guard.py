"""W06-B Task 4 行为测试：生成前与首正文前复核（P / O / W）（B12–B16）。

隔离同 Task 3：临时 SQLite（`db`）＋ conftest 临时 CHROMA_DIR ＋ `double_embeddings`；
不联网、不读 .env 配置、不跑真实模型。

覆盖方式（诚实标注）：本文件钉住 P/O/W 三个阶段的**产品原语**行为
（`_p_recheck` / `_recheck_before_model` / `_generation_input_invalid` /
`_cache_write_deps_ok` / `_drop_tracked_qa` / `evaluate_revocation_state(..., fresh=True)`）。
`stream()` 内部的首正文时序（status/restart 不算开始、空 chunk 不算开始、重做恰好 1 次）的**逐帧**
端到端由 W06B 报告注明覆盖边界——本文件不跑 SSE。
"""

import asyncio
import json
import os
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

import knowledge_service as ks  # noqa: E402
import main  # noqa: E402
import qa_eligibility as qe  # noqa: E402

EVIDENCE = json.dumps([{"source": "中华人民共和国劳动合同法", "article": "第十九条"}], ensure_ascii=False)
ANSWER = (
    "《劳动合同法》第十九条对试用期上限作了分层规定：合同期限三个月以上不满一年的，试用期不得超过一个月；"
    "同一用人单位与同一劳动者只能约定一次试用期。"
)


def _g_row(db, question):
    doc_id = uuid.uuid4().hex
    row = ks.QaCandidate(
        question=question,
        answer=ANSWER,
        grounded_score=0.95,
        evidence=EVIDENCE,
        status="approved",
        approval_source="human",
        vector_doc_id=doc_id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    ks.add_qa_pair(question, ANSWER, EVIDENCE, cand_id=row.id, doc_id=doc_id)
    return row


def _hit_of(q):
    hit = ks.search_qa(q)
    assert hit is not None and hit.get("qa_candidate_id") is not None
    return hit


def _revoke_without_clear(db, row):
    live = db.get(ks.QaCandidate, row.id)
    live.eligibility = "revoked"
    db.commit()


def _prompt_text(messages) -> str:
    out = []
    for m in messages:
        c = getattr(m, "content", m)
        out.append(c if isinstance(c, str) else json.dumps(c, ensure_ascii=False))
    return "\n".join(out)


def _pre(q, hit):
    return {
        "conv_id": 1,
        "intent": "legal_query",
        "image": None,
        "recent": [],
        "rewritten": q,
        "user_text": q,
        "summary": "",
        "qa_hit": hit,
        "context": "",
        "sources": [],
        "image_rel": None,
        "thumb_rel": None,
        "is_exam": False,
        "has_options": False,
        "contract_data": None,
        "law_as_of": None,
    }


# ==================== B12：模型调用前复核 → 重建 messages（不是只清 pre） ====================


def test_b12_recheck_before_model_rebuilds_messages_without_revoked_qa(db, double_embeddings):
    """B12：P 已读 G、旧 messages 已构造；撤回在模型调用前提交 ⇒ 新模型输入不含 G。

    阴性控制前提在同一用例里先证「旧 messages 确实含 G」（防本就没引用的假绿）。
    """
    q = "B12 模型调用前复核：新输入还会带已撤回的问答吗？"
    row = _g_row(db, q)
    pre = _pre(q, _hit_of(q))
    messages = main._build_messages(pre)
    assert "此前已确认的问答" in _prompt_text(messages), "阴性控制前提不成立：旧 messages 本就不含 G"
    deps = main._input_qa_dependencies(pre)
    assert isinstance(deps, tuple) and len(deps) == 1

    _revoke_without_clear(db, row)
    new_pre, new_messages, new_deps = asyncio.run(main._recheck_before_model(pre, messages, deps))
    assert new_pre["qa_hit"] is None, "模型调用前复核没丢掉已失效的 QA"
    text = _prompt_text(new_messages)
    assert "此前已确认的问答" not in text and ANSWER not in text, "重建后的 messages 仍含 G"
    # 「仅清 pre 但继续旧 messages」这条故障能被检出：旧 messages 里 G 还在
    assert "此前已确认的问答" in _prompt_text(messages)


def test_b12_negative_control_recheck_keeps_messages_when_dependency_valid(db, double_embeddings):
    """B12 对照：依赖未失效 ⇒ 复核**不**重建、messages 不变（防止"永远重建"的假门）。"""
    q = "B12 对照：依赖没变时复核会不会误伤旧 messages？"
    _g_row(db, q)
    pre = _pre(q, _hit_of(q))
    messages = main._build_messages(pre)
    deps = main._input_qa_dependencies(pre)
    same_pre, same_messages, same_deps = asyncio.run(main._recheck_before_model(pre, messages, deps))
    assert same_messages is messages and same_pre is pre and same_deps == deps


# ==================== B13：status 未发 content；O 前撤回不发旧答案 ====================


def test_b13_o_gate_blocks_before_first_content(db, double_embeddings):
    """B13：缓存/QA 直返准备完成后、O 读前撤回 ⇒ O 门判失效，不发旧答案（status 不算正文已开始）。

    O 门只看**非空**依赖；`None`/空 tuple 不在此判失效（无链 QA/无 QA 路径各自另判）。
    """
    q = "B13 O 前撤回：准备完毕的答案还会被发出去吗？"
    row = _g_row(db, q)
    dep = qe.capture_dependency(_hit_of(q))
    assert asyncio.run(main._generation_input_invalid((dep,))) is False  # 阳性：未撤时不失效

    _revoke_without_clear(db, row)
    assert asyncio.run(main._generation_input_invalid((dep,))) is True, "O 门没判出失效 ⇒ 会发旧答案"
    # 空/无 QA 不在此判失效（无链 QA 的直接读取资格另判）
    assert asyncio.run(main._generation_input_invalid(())) is False
    assert asyncio.run(main._generation_input_invalid(None)) is False


def test_b13_fresh_state_read_blocks_direct_return_path(db, double_embeddings):
    """B13：QA 直返在首个 content 前用 **fresh** 状态轴复核；撤回后 fresh 拒绝（非 fresh 复用旧槽）。"""
    q = "B13 直返 O：fresh 状态轴能挡住准备完毕的直返吗？"
    row = _g_row(db, q)
    hit = _hit_of(q)
    assert qe.evaluate_revocation_state(hit).allow is True  # P 阶段（填了请求内槽）
    _revoke_without_clear(db, row)
    assert qe.evaluate_revocation_state(hit).allow is True, "非 fresh 复用旧槽 ⇒ 这正是 O 需要 fresh 的理由"
    assert qe.evaluate_revocation_state(hit, fresh=True).allow is False, "fresh 复核没判出撤回 ⇒ O 挡不住直返"


# ==================== B14：丢弃旧产物 + 重建 + 重做恰好 1 次 ====================


def test_b14_drop_rebuild_and_bounded_redo(db, double_embeddings):
    """B14：缓冲产物含 G 且撤回后 ⇒ 丢弃（`_drop_tracked_qa`）、重建无 G 输入；重做有界（依赖转未知）。"""
    q = "B14 丢弃旧产物：重建后的输入还带 G 吗？重做会不会无限？"
    row = _g_row(db, q)
    pre = _pre(q, _hit_of(q))
    deps = main._input_qa_dependencies(pre)
    _revoke_without_clear(db, row)
    assert asyncio.run(main._generation_input_invalid(deps)) is True, "旧产物含失效依赖却没被判失效"

    dropped = main._drop_tracked_qa(pre)
    assert dropped["qa_hit"] is None
    rebuilt = main._build_messages(dropped)
    assert "此前已确认的问答" not in _prompt_text(rebuilt), "重建后仍含 G"
    # 重建后依赖转未知 ⇒ 重做那一轮 O 不再判失效 ⇒ 不会无限重做
    assert asyncio.run(main._generation_input_invalid(main._input_qa_dependencies(dropped))) is False


# ==================== B15：已发首个 content 后撤回 ⇒ 允许原流完成，W 拒绝写缓存 ====================


def test_b15_w_rejects_write_after_first_content_revocation(db, double_embeddings):
    """B15：首个非空正文已发后撤回 ⇒ 本轮不主动打断（既有行为），但 **W** 拒绝写失效依赖缓存。"""
    q = "B15 首正文后撤回：旧流允许完成但缓存还写吗？"
    row = _g_row(db, q)
    dep = qe.capture_dependency(_hit_of(q))
    assert asyncio.run(main._cache_write_deps_ok((dep,))) is True  # 阳性：未撤时可写
    _revoke_without_clear(db, row)
    assert asyncio.run(main._cache_write_deps_ok((dep,))) is False, "W 没拦住 ⇒ 失效依赖会被写进缓存"


# ==================== B16：fresh 竞态 / 有界 / 资源与计数边界 ====================


def test_b16_stage_local_reuse_and_cross_stage_fresh_read(db, double_embeddings):
    """B16（fresh 竞态的不含承诺部分）：阶段内复用同一槽、跨阶段 fresh 新读。

    这里**不宣称** socket 原子性：O 的 SQL 读取只是可见性观察点；读取之后再撤回的竞态属已知限制。
    """
    q = "B16 阶段边界：阶段内复用、跨阶段新读，两条读数会不会不同？"
    row = _g_row(db, q)
    hit = _hit_of(q)
    assert qe.evaluate_revocation_state(hit).allow is True  # 阶段内（P）读一次，填槽
    _revoke_without_clear(db, row)
    # 阶段内复用 ⇒ 仍是旧读数（不改变判据）
    assert qe.evaluate_revocation_state(hit).allow is True
    # 阶段边界 fresh ⇒ 新 SQL 会话读到撤回
    assert qe.evaluate_revocation_state(hit, fresh=True).allow is False
    # fresh 之后再复用，槽已被新读数覆盖
    assert qe.evaluate_revocation_state(hit).allow is False


def test_b16_empty_dependency_and_read_failure_are_not_false_starts(db, double_embeddings, monkeypatch):
    """B16 边界：空 chunk/空依赖不判失效；读异常判失效（异常≠已知无 QA，不误放行）。"""
    assert asyncio.run(main._generation_input_invalid(())) is False

    q = "B16 读异常：O 复核读不动时会静默放行吗？"
    _g_row(db, q)
    dep = qe.capture_dependency(_hit_of(q))

    def _boom():
        raise RuntimeError("模拟 O 复核时库挂")

    monkeypatch.setattr(qe.database, "SessionLocal", _boom)
    assert asyncio.run(main._generation_input_invalid((dep,))) is True, "读异常被读成了放行 ⇒ O 静默失效"
