"""W06-C Task 9：摘要来源并集、失效重建、并发拒绝与再次沉淀隔离（H08–H11/H17 的合成控制）。

判据对象是**产品函数**：`memory.compress`、`memory.load_model_context`、`memory._extend_summary`（真实体，
失败路径）。隔离：conftest tmp SQLite + tmp CHROMA_DIR；**不调真实模型**（fake 摘要器观察真实入参）。
日期/游标/来源三者在同一 `commit` 内原子更新，以读取时摘要+游标快照作乐观并发条件。
"""

import json
import os
import sys
import uuid

import pytest
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

import memory  # noqa: E402
import qa_eligibility as qe  # noqa: E402
from models import Conversation, Message, QaCandidate, User  # noqa: E402

ANSWER = "《劳动合同法》第十九条：试用期最长不得超过六个月。"
EVIDENCE = json.dumps([{"source": "中华人民共和国劳动合同法", "article": "第十九条"}], ensure_ascii=False)


class FakeMsg:
    def __init__(self, role, content, qa_provenance=None):
        self.role = role
        self.content = content
        self.qa_provenance = qa_provenance


class FakeLlm:
    def __init__(self, content="合并后的摘要", exc=None):
        self.content = content
        self.exc = exc

    def invoke(self, _msgs):
        if self.exc:
            raise self.exc
        from types import SimpleNamespace

        return SimpleNamespace(content=self.content)


def _approved_dep(db, question):
    doc_id = uuid.uuid4().hex
    row = QaCandidate(
        question=question,
        answer=ANSWER,
        grounded_score=0.9,
        evidence=EVIDENCE,
        status="approved",
        approval_source="human",
        vector_doc_id=doc_id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    dep = qe.QaDependency(
        row.id, doc_id, int(row.eligibility_version or 1), qe._record_digest(row.question, row.answer, row.evidence)
    )
    return row, dep


def _conv(db, **kwargs):
    user = User(username=f"sum-{uuid.uuid4().hex[:8]}", password_hash="x")
    db.add(user)
    db.flush()
    defaults = {"user_id": user.id, "title": "", "summary": "", "summary_upto": 0, "message_count": 20}
    defaults.update(kwargs)
    conv = Conversation(**defaults)
    db.add(conv)
    db.commit()
    db.refresh(conv)
    return conv


def _prov_text(dep):
    return qe.serialize_provenance(qe.Provenance(True, (dep,), ()))


def _session_factory(db):
    return sessionmaker(bind=db.get_bind(), autoflush=False, autocommit=False)


# ==================== H08：摘要来源并集（含旧摘要 + 本批） ====================


def test_compress_unions_batch_and_existing_summary_provenance(db, monkeypatch):
    _row_g, dep_g = _approved_dep(db, "摘要并集题：G 还在吗？")
    _row_j, dep_j = _approved_dep(db, "摘要并集题：J 还在吗？")
    conv = _conv(db, summary="旧摘要（含 G）", summary_provenance=_prov_text(dep_g))
    batch = [
        FakeMsg("user", "新问题", None),
        FakeMsg("assistant", "回答 J", _prov_text(dep_j)),
    ]
    monkeypatch.setattr(memory, "_gap_messages", lambda db, conv: batch)

    assert memory.compress(db, conv, FakeLlm("合并后的新摘要")) is True
    prov = qe.parse_provenance(conv.summary_provenance)
    assert prov is not None and prov.complete
    ids = {dep.candidate_id for dep in prov.qa_dependencies}
    assert ids == {dep_g.candidate_id, dep_j.candidate_id}, "新摘要必须同时覆盖旧摘要 G 与本批 J"
    assert conv.summary == "合并后的新摘要"
    assert conv.summary_upto == 20 - memory.RECENT_K


def test_compress_unknown_assistant_in_batch_propagates_unknown(db, monkeypatch):
    _row_g, dep_g = _approved_dep(db, "摘要未知题：未追溯助手？")
    conv = _conv(db, summary="", summary_provenance=None)
    batch = [FakeMsg("user", "问题", None), FakeMsg("assistant", "未追溯旧结论", None)]
    monkeypatch.setattr(memory, "_gap_messages", lambda db, conv: batch)
    assert memory.compress(db, conv, FakeLlm("摘要")) is True
    assert conv.summary_provenance is None, "未追溯助手进批次 ⇒ 摘要来源未知，不得签空集"


def test_compress_unknown_existing_summary_not_fed_as_existing(db, monkeypatch):
    """L9：来源未知（NULL）的旧摘要**不作为 existing 输入**喂压缩器（与 H07/投影一致），
    本次新摘要来源只反映**实际喂入**的本批（已知 ⇒ 可签完整空）；旧 summary 文本被新摘要覆盖属既有语义。"""
    conv = _conv(db, summary="来源未知旧摘要", summary_provenance=None)
    captured = {}
    real_extend = memory._extend_summary

    def spy(llm, existing, batch):
        captured["existing"] = existing
        return real_extend(llm, existing, batch)

    monkeypatch.setattr(memory, "_extend_summary", spy)
    monkeypatch.setattr(memory, "_gap_messages", lambda db, conv: [FakeMsg("user", "问题", None)])
    assert memory.compress(db, conv, FakeLlm("摘要")) is True
    assert captured["existing"] == "", "来源未知的旧摘要仍被喂进压缩器（L9 未修）"
    prov = qe.parse_provenance(conv.summary_provenance)
    assert prov is not None and prov.complete and prov.qa_dependencies == (), "来源只应反映实际喂入的本批"


# ==================== H09：失效旧摘要不再喂入 existing ====================


def test_compress_does_not_feed_revoked_existing_summary(db, monkeypatch):
    row_g, dep_g = _approved_dep(db, "失效摘要题：旧摘要还喂吗？")
    conv = _conv(db, summary="旧摘要（含 G）", summary_provenance=_prov_text(dep_g))
    row_g.eligibility = "revoked"
    db.commit()

    captured = {}
    real_extend = memory._extend_summary

    def spy(llm, existing, batch):
        captured["existing"] = existing
        return real_extend(llm, existing, batch)

    monkeypatch.setattr(memory, "_extend_summary", spy)
    monkeypatch.setattr(memory, "_gap_messages", lambda db, conv: [FakeMsg("user", "问题", None)])
    assert memory.compress(db, conv, FakeLlm("重建摘要")) is True
    assert captured["existing"] == "", "已失效旧摘要不得作为 existing 再次喂入压缩器（H09）"
    # 重建后来源不再含失效 G
    prov = qe.parse_provenance(conv.summary_provenance)
    assert prov is not None and all(d.candidate_id != row_g.id for d in prov.qa_dependencies)


# ==================== H10：并发（另一压缩抢先提交）拒绝过时产物 ====================


def test_compress_rejects_stale_snapshot_when_another_writer_commits(db, monkeypatch):
    conv = _conv(db, summary="原始摘要", summary_upto=0, message_count=20)
    sf = _session_factory(db)

    def racing(llm, existing, batch):
        other = sf()
        try:
            other.query(Conversation).filter(Conversation.id == conv.id).update(
                {"summary": "别的事物提交的新摘要", "summary_upto": 7}, synchronize_session=False
            )
            other.commit()
        finally:
            other.close()
        return "本轮过时摘要"

    monkeypatch.setattr(memory, "_extend_summary", racing)
    monkeypatch.setattr(memory, "_gap_messages", lambda db, conv: [FakeMsg("user", "问题", None)])
    assert memory.compress(db, conv, FakeLlm()) is False, "过时快照必须被拒，不得覆盖较新安全摘要"

    fresh = db.get(Conversation, conv.id)
    db.refresh(fresh)
    assert fresh.summary == "别的事物提交的新摘要"
    assert fresh.summary_upto == 7


# ==================== H11：摘要器失败不推进游标/不覆盖来源 ====================


def test_compress_llm_failure_does_not_advance_cursor_or_provenance(db, monkeypatch):
    _row_g, dep_g = _approved_dep(db, "失败题：摘要器挂了会怎样？")
    conv = _conv(db, summary="旧摘要", summary_upto=3, summary_provenance=_prov_text(dep_g))
    monkeypatch.setattr(memory, "_gap_messages", lambda db, conv: [FakeMsg("user", "x")])
    assert memory.compress(db, conv, FakeLlm(exc=RuntimeError("模型不可用"))) is False
    fresh = db.get(Conversation, conv.id)
    db.refresh(fresh)
    assert fresh.summary == "旧摘要" and fresh.summary_upto == 3
    assert fresh.summary_provenance == _prov_text(dep_g)


# ==================== H02：失效摘要不进模型上下文，UI 原文保留 ====================


def test_revoked_summary_is_excluded_from_model_context_but_kept_for_ui(db):
    row_g, dep_g = _approved_dep(db, "摘要投影题：旧摘要该进模型吗？")
    conv = _conv(db, summary="含 G 的旧摘要", summary_provenance=_prov_text(dep_g))
    db.add(Message(conversation_id=conv.id, role="user", content="用户事实", qa_provenance=None))
    db.commit()

    # 未撤回：摘要可用
    ctx = memory.load_model_context(db, conv)
    assert ctx.summary == "含 G 的旧摘要" and ctx.summary_usable is True

    row_g.eligibility = "revoked"
    db.commit()
    ctx2 = memory.load_model_context(db, conv)
    assert ctx2.summary_usable is False
    assert ctx2.summary == "", "失效摘要不得进入模型上下文（H02）"
    # UI 保留原文与游标
    _summary, ui = memory.load_context(db, conv)
    fresh = db.get(Conversation, conv.id)
    db.refresh(fresh)
    assert fresh.summary == "含 G 的旧摘要"


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
