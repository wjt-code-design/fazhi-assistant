"""W06-C Task 8：同一安全投影贯穿 request_bootstrap 与 tools.memory（H01/H12/H14/H15 的合成控制）。

判据对象是**产品链**：`request_bootstrap.bootstrap_request`（默认投影 `memory.load_model_context_bootstrap`）、
`tools.memory.retrieve_memory`、`memory.load_context`（UI/审计，必须保留原文）。
隔离：conftest tmp SQLite + tmp CHROMA_DIR；不读真实会话/实库，不联网。Agent 工具内部来源字段为 **exclude**
（不进模型可见输出），其"恢复/Observation 重放"链在本票 **NOT_RUN**（见报告）。
"""

import json
import os
import sys
import uuid
from datetime import date

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

import memory  # noqa: E402
import qa_eligibility as qe  # noqa: E402
import request_bootstrap  # noqa: E402
import tools.memory as memory_tool  # noqa: E402
from models import Conversation, Message, QaCandidate, User  # noqa: E402
from tools.contracts import (  # noqa: E402
    RetrieveMemoryInput,
    RetrieveMemoryOutput,
    ToolAuthorizationError,
    ToolContext,
)

ANSWER = "《劳动合同法》第十九条：试用期最长不得超过六个月。"
EVIDENCE = json.dumps([{"source": "中华人民共和国劳动合同法", "article": "第十九条"}], ensure_ascii=False)


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


def _seed(db, *messages, **conv_kw):
    from datetime import datetime, timedelta

    user = User(username=f"revoc-{uuid.uuid4().hex[:8]}", password_hash="x")
    db.add(user)
    db.flush()
    conv = Conversation(user_id=user.id, title="", summary="", message_count=len(messages), **conv_kw)
    db.add(conv)
    db.flush()
    base = datetime(2026, 1, 1)
    for i, (role, content, prov) in enumerate(messages):
        db.add(
            Message(
                conversation_id=conv.id,
                role=role,
                content=content,
                qa_provenance=prov,
                created_at=base + timedelta(seconds=i),
            )
        )
    db.commit()
    db.refresh(conv)
    return user, conv


def _bootstrap_deps(load_context):
    values = {
        "session_factory": None,  # 由调用处补
        "load_context": load_context,
        "validate_image": lambda image: None,
        "persist_image": lambda image: (None, None),
        "cleanup_persisted_image": lambda rel, thumb: None,
        "describe_image": lambda image, text: "",
        "classify_intent": lambda query: "legal_query",
        "is_exam_question": lambda query: False,
        "has_exam_options": lambda query: False,
        "is_contract_review": lambda query: False,
        "contract_trigger_reason": lambda query: None,
        "feature_multi_analyze": False,
        "contract_conversations": set(),
        "contract_reviewed_conversations": set(),
        "is_contract_exit": lambda query: False,
    }
    return values


# ==================== H01/H15：bootstrap 序列化消费同一投影 ====================


def test_bootstrap_recent_excludes_revoked_assistant_but_ui_keeps_it(db, monkeypatch):
    row, dep = _approved_dep(db, "bootstrap 投影题：这条结论该进模型吗？")
    prov_text = qe.serialize_provenance(qe.Provenance(True, (dep,), ()))
    user, conv = _seed(db, ("user", "用户事实", None), ("assistant", "旧法律结论（G）", prov_text))
    row.eligibility = "revoked"
    db.commit()

    from sqlalchemy.orm import sessionmaker

    sf = sessionmaker(bind=db.get_bind(), autoflush=False, autocommit=False)
    # 默认投影（model 侧）
    deps = _bootstrap_deps(memory.load_model_context_bootstrap)
    deps["session_factory"] = sf
    bs = request_bootstrap.bootstrap_request(
        user.id, conv.id, "那下一步呢", None, False, _deps=request_bootstrap.BootstrapDependencies(**deps)
    )
    contents = [m["content"] for m in bs.recent]
    assert "旧法律结论（G）" not in contents, "已知失效助手结论不得进模型序列化历史"
    assert "用户事实" in contents

    # UI/审计默认接口仍返回原文
    _summary, ui = memory.load_context(db, conv)
    assert "旧法律结论（G）" in [m.content for m in ui]


def test_bootstrap_default_deps_use_the_projection(monkeypatch):
    """接线面：`_default_bootstrap_dependencies` 的 load_context 必须绑到投影，而不是旧的原文接口。"""
    deps = request_bootstrap._default_bootstrap_dependencies()
    assert deps.load_context is memory.load_model_context_bootstrap
    assert deps.load_context is not memory.load_context


# ==================== H12/H14：tools.memory 读同一投影 + 越权先拒 ====================


def test_tools_memory_drops_revoked_assistant_and_reports_internal_provenance(db):
    row, dep = _approved_dep(db, "工具投影题：记忆里这条结论可复用吗？")
    prov_text = qe.serialize_provenance(qe.Provenance(True, (dep,), ()))
    user, conv = _seed(db, ("user", "用户事实", None), ("assistant", "旧法律结论（G）", prov_text))
    context = ToolContext(user_id=user.id, conversation_id=conv.id, run_id="r-1", law_as_of=date(2026, 10, 1))

    # 未撤回：工具读到两条，内部来源可解析
    out = memory_tool.retrieve_memory(context, RetrieveMemoryInput(limit=10))
    assert [m.content for m in out.messages] == ["用户事实", "旧法律结论（G）"]
    assert out.provenance is not None and dep in qe.parse_provenance(out.provenance).qa_dependencies
    # 内部来源字段不进模型可见输出（exclude=True）
    assert "provenance" not in out.model_dump()

    # 撤回：工具剔除失效助手，用户事实保留
    row.eligibility = "revoked"
    db.commit()
    out2 = memory_tool.retrieve_memory(context, RetrieveMemoryInput(limit=10))
    assert [m.content for m in out2.messages] == ["用户事实"]


def test_tools_memory_rejects_foreign_conversation_before_reading(db):
    _row, _dep = _approved_dep(db, "越权题：能不能读别人的会话？")
    _owner, conv = _seed(db, ("user", "别人的事实", None))
    other = User(username=f"other-{uuid.uuid4().hex[:8]}", password_hash="x")
    db.add(other)
    db.commit()
    context = ToolContext(user_id=other.id, conversation_id=conv.id, run_id="r-2", law_as_of=date(2026, 10, 1))
    with pytest.raises(ToolAuthorizationError):
        memory_tool.retrieve_memory(context, RetrieveMemoryInput())


# ==================== H14：持久 Observation 重放 / 旧 run 恢复的交模型前复核 ====================


def test_gateway_captures_tool_output_provenance_onto_observation(db):
    """接线面：工具输出的内部来源包被接到持久 Observation 上（否则重放无从复核）。"""
    from agent.schemas import ToolCallDecision
    from tools.gateway import ToolGateway

    _row, dep = _approved_dep(db, "H14 网关题：来源包会被接到观察上吗？")
    prov = qe.serialize_provenance(qe.Provenance(True, (dep,), ()))
    out = RetrieveMemoryOutput(statement="读取到 1 条会话记忆。", summary="", messages=[], provenance=prov)
    gateway = ToolGateway(wrapper_overrides={"retrieve_memory": lambda *_: out})
    context = ToolContext(user_id=1, conversation_id=1, run_id="r-1", law_as_of=date(2026, 10, 1))
    obs = gateway.execute(
        context, ToolCallDecision(issue_id="issue-a", tool_name="retrieve_memory", args=RetrieveMemoryInput())
    )
    assert obs.qa_provenance == prov


def test_planner_payload_skips_revoked_observation_across_persisted_roundtrip(db):
    """H14：交模型前的 planner payload——**撤回来源的观察不再交模型**，有效/未知仍保留。

    走 state_json 持久化 round-trip，代表"旧 run 恢复"与新工具返回消费的是**同一投影**
    （不是只过滤新工具返回值）。未知来源按 H07 未裁处理：保留、但不被当成可信。
    """
    from types import SimpleNamespace

    from agent.runtime import _planner_payload
    from agent.schemas import LegalAgentState, Observation

    _row_ok, dep_ok = _approved_dep(db, "H14 有效题")
    row_rev, dep_rev = _approved_dep(db, "H14 撤回题")
    row_rev.eligibility = "revoked"
    db.commit()
    prov_ok = qe.serialize_provenance(qe.Provenance(True, (dep_ok,), ()))
    prov_rev = qe.serialize_provenance(qe.Provenance(True, (dep_rev,), ()))

    def _obs(issue, prov):
        out = RetrieveMemoryOutput(statement=f"记忆 {issue}", summary="", messages=[], provenance=prov)
        return Observation(
            issue_id=issue,
            tool_name="retrieve_memory",
            status="succeeded",
            statement=f"记忆 {issue}",
            output=out,
            qa_provenance=prov,
        )

    state = LegalAgentState(observations=[_obs("i-ok", prov_ok), _obs("i-rev", prov_rev), _obs("i-unknown", None)])
    restored = LegalAgentState.model_validate_json(state.model_dump_json())  # 模拟旧 run 恢复
    payload = _planner_payload(restored, SimpleNamespace(raw_query="q"))
    issue_ids = [item["issue_id"] for item in payload["observations"]]
    assert issue_ids == ["i-ok", "i-unknown"], "已撤回来源的观察仍被交模型（H14 未接线）或未知被误删"


def test_h07_unknown_history_not_handed_as_trusted_but_user_facts_kept(db):
    """H07 合成多轮（Owner 已裁）：旧 assistant 来源未知 + 用户短追问「那下一步呢」⇒
    模型侧不把该未知结论作为已确认依据（序列化历史剔除），用户事实保留；UI 原文仍在。
    """
    from sqlalchemy.orm import sessionmaker

    user, conv = _seed(db, ("user", "用户事实：合同三个月", None), ("assistant", "未追溯旧结论", None))
    sf = sessionmaker(bind=db.get_bind(), autoflush=False, autocommit=False)
    deps = _bootstrap_deps(memory.load_model_context_bootstrap)
    deps["session_factory"] = sf
    bs = request_bootstrap.bootstrap_request(
        user.id, conv.id, "那下一步呢", None, False, _deps=request_bootstrap.BootstrapDependencies(**deps)
    )
    contents = [m["content"] for m in bs.recent]
    assert "未追溯旧结论" not in contents, "未知来源旧结论被当作已确认依据交给模型（H07 未实施）"
    assert "用户事实：合同三个月" in contents, "用户事实不得被字符串误删"
    _s, ui = memory.load_context(db, conv)
    assert "未追溯旧结论" in [m.content for m in ui], "UI/原文必须保留"


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
