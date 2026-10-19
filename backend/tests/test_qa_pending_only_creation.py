"""W06-P0：暂停自动批准（C03=P 的写侧落实）——新契约 P01–P04。

Owner 已裁 C03=P 正文包含「暂停自动批准，高分只入待审」。而当前 create_candidate 在
grounded_score >= AUTO_CURATE_THRESHOLD 时仍 status='approved' 并 add_qa_pair 写 QA 向量
（knowledge_service.py）。本票把写侧改为「高分/低分一律 pending」，人工 decide_candidate(approved)
是唯一的向量写入与 human 来源入口；不靠调整 0.89 阈值假装暂停。

改前应**先红**：P01/P04 因高分自动 approved＋写向量而失败；改后应全绿。
隔离：只用 db（tmp_path 临时 SQLite）+ double_embeddings（确定性伪向量）+ conftest 的临时 CHROMA_DIR。
不碰真实 app.db、真实语料与真权重。
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import knowledge_service as ks  # noqa: E402
import retrieval  # noqa: E402

# 可校验引用（rc.cited_articles 认 JSON list[{source,article}] 形状）
EVIDENCE = json.dumps([{"source": "中华人民共和国劳动合同法", "article": "第十九条"}], ensure_ascii=False)
ANSWER = (
    "《劳动合同法》第十九条对试用期上限作了分层规定：合同期限三个月以上不满一年的，试用期不得超过一个月；"
    "同一用人单位与同一劳动者只能约定一次试用期。"
)


def _vector_docs() -> set[str]:
    """向量侧（临时集合）当前全部 question 文档，用于证明"没写向量"。"""
    data = ks._qa_store._collection.get(include=["documents"])
    return {str(d).strip() for d in (data.get("documents") or [])}


def test_p01_high_score_creates_pending_without_vector_write(monkeypatch, db, double_embeddings):
    """P01：score=0.95、证据有效 ⇒ status=pending、向量 add 调用数=0、不自签 approved/human。"""
    writes: list = []
    monkeypatch.setattr(ks, "add_qa_pair", lambda *a, **k: writes.append(a[:1]))
    monkeypatch.setattr(retrieval, "invalidate", lambda: None)

    q = "P01：劳动合同约定的试用期上限应当如何确定？"
    row = ks.create_candidate(db, q, ANSWER, 0.95, EVIDENCE)

    assert row.status == "pending", f"高分仍被自动 approved ⇒ C03=P 写侧未落实：status={row.status}"
    assert writes == [], f"高分候选写了 QA 向量 ⇒ 自动收录未暂停：{writes}"
    assert row.vector_doc_id is None, f"高分候选带了向量链：{row.vector_doc_id}"
    assert row.approval_source != "auto_by_score_inferred", "高分仍自签机器批准"
    assert row.approval_source != "human", "高分仍自签人工批准"


def test_p02_low_and_zero_are_pending_and_manual_approve_forms_servable(monkeypatch, db, double_embeddings):
    """P02：0.55/0 分别创建 ⇒ 均 pending 且正常字段保留；明确人工采纳后才形成 human/资格链与向量。"""
    monkeypatch.setattr(retrieval, "invalidate", lambda: None)

    q_low, q_zero = "P02 低分：试用期工资下限？", "P02 零分：无关反馈纠错？"
    low = ks.create_candidate(db, q_low, ANSWER, 0.55, EVIDENCE)
    zero = ks.create_candidate(db, q_zero, ANSWER, 0.0, "feedback:down")

    assert low.status == "pending" and zero.status == "pending"
    # 正常字段保留（不因暂停批准而丢分数/证据）
    assert abs(float(low.grounded_score) - 0.55) < 1e-9 and low.evidence == EVIDENCE
    assert abs(float(zero.grounded_score) - 0.0) < 1e-9

    before = _vector_docs()
    assert q_low not in before, "待审候选不该进向量侧"
    ks.decide_candidate(db, low.id, "approved")
    assert low.status == "approved" and low.approval_source == "human"
    assert low.vector_doc_id, "人工采纳后应有向量链"
    assert q_low in _vector_docs(), "人工采纳后应写入向量侧"


def test_p03_reject_pending_is_not_served_and_manual_path_is_fail_closed(monkeypatch, db, double_embeddings):
    """P03：拒绝待审项 ⇒ 不服务；人工采纳链的异常 fail-closed，不退回自动发布。"""
    monkeypatch.setattr(retrieval, "invalidate", lambda: None)

    q = "P03：用人单位能否只约定试用期而不签劳动合同？"
    row = ks.create_candidate(db, q, ANSWER, 0.95, EVIDENCE)
    ks.decide_candidate(db, row.id, "rejected")
    assert row.status == "rejected" and row.eligibility == "revoked"
    assert q not in _vector_docs(), "被拒绝的待审项不应进向量侧"

    # 人工采纳链异常：写向量抛错必须显式上抛（fail-closed），不得静默改走自动发布
    q2 = "P03 乙：人工采纳时向量写入失败不该自动发布。"
    row2 = ks.create_candidate(db, q2, ANSWER, 0.95, EVIDENCE)

    def _boom(*_a, **_k):
        raise RuntimeError("synthetic vector write failure")

    monkeypatch.setattr(ks, "add_qa_pair", _boom)
    raised = False
    try:
        ks.decide_candidate(db, row2.id, "approved")
    except RuntimeError:
        raised = True
    assert raised, "人工采纳写向量失败被吞掉 ⇒ 不是 fail-closed"
    assert row2.status != "approved" or row2.vector_doc_id is None, "失败却被当成已发布"


def test_p04_high_score_is_not_served_by_the_real_store_and_manual_approve_is(monkeypatch, db, double_embeddings):
    """P04：走真实 _qa_store——高分候选不被 search_qa 读到；人工采纳后才读到（端到端写侧闭环）。"""
    monkeypatch.setattr(retrieval, "invalidate", lambda: None)

    q = "P04：真实向量集合上，高分候选在人工采纳前是否可见？"
    row = ks.create_candidate(db, q, ANSWER, 0.95, EVIDENCE)
    hit_before = ks.search_qa(q)
    assert hit_before is None, "高分自动收录把记录直接放进了可服务向量集合 ⇒ 写侧未暂停"

    ks.decide_candidate(db, row.id, "approved")
    hit_after = ks.search_qa(q)
    assert hit_after is not None and hit_after["answer"] == ANSWER, "人工采纳后未进入可服务集合"
