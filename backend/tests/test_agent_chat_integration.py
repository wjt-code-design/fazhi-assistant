"""Task 10: Agent final storage and fallback boundary integration tests."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from types import SimpleNamespace

import pytest

from agent.repository import create_run
from agent.schemas import (
    AgentStatus,
    ClaimCheck,
    Evidence,
    Fact,
    LegalAgentState,
    LegalIssue,
    LegalValidity,
    Observation,
    SourceType,
)
from agent.verifier import DeterministicVerifier
from agent.writer import DraftAnswer, DraftClaim, derive_claim_id, derive_fact_id
from models import AgentClaimCheck, AgentRun, AgentStep, Conversation, Message, User
from request_bootstrap import RequestBootstrap
from tools.gateway import ToolGateway


def _drafting_state() -> tuple[LegalAgentState, DraftAnswer]:
    fact = Fact(
        statement="借款本金为10000元",
        source=SourceType.DOCUMENT,
        source_ref="document:loan-1",
        confidence=1.0,
    )
    issue = LegalIssue(issue_id="issue-a", question="借款是否应返还", facts=[fact])
    evidence = Evidence(
        evidence_id="evidence-a",
        source_id="statute:civil-code:675",
        source_ref="《民法典》第675条",
        source_type=SourceType.STATUTE,
        snippet="借款本金为10000元，依据《民法典》第675条应按约返还。",
        legal_validity=LegalValidity.EFFECTIVE,
        acquired_at=datetime(2026, 8, 31),
    )
    state = LegalAgentState(
        status=AgentStatus.DRAFTING,
        steps=3,
        issues=[issue],
        evidence=[evidence],
        observations=[
            Observation(
                issue_id="issue-a",
                statement="已取得借款返还规则",
                evidence_ids=["evidence-a"],
                confidence=1.0,
            )
        ],
    )
    fact_id = derive_fact_id("issue-a", fact)
    text = "借款本金为10000元，依据《民法典》第675条应按约返还。"
    claim = DraftClaim(
        claim_id=derive_claim_id("issue-a", text, ["evidence-a"], [fact_id]),
        issue_id="issue-a",
        text=text,
        evidence_ids=("evidence-a",),
        fact_ids=(fact_id,),
        section="conclusion",
    )
    return state, DraftAnswer(conclusion=(claim,))


def _records(db):
    user = User(username="agent-final-owner", password_hash="x")
    db.add(user)
    db.commit()
    conversation = Conversation(user_id=user.id, title="", summary="", message_count=1)
    db.add(conversation)
    db.commit()
    state, draft = _drafting_state()
    run = create_run(db, user_id=user.id, conversation_id=conversation.id, state=state)
    return user, conversation, run, state, draft


def test_final_agent_answer_is_stored_once_with_completed_checkpoint(db):
    from agent.chat_integration import persist_agent_final_once

    user, conversation, run, state, draft = _records(db)
    verification = DeterministicVerifier().verify(state, draft)

    first = persist_agent_final_once(
        db,
        user_id=user.id,
        conversation_id=conversation.id,
        run_id=run.id,
        expected_version=0,
        state=state,
        answer="借款本金为10000元，依据《民法典》第675条应按约返还。",
        verification=verification,
    )
    second = persist_agent_final_once(
        db,
        user_id=user.id,
        conversation_id=conversation.id,
        run_id=run.id,
        expected_version=0,
        state=state,
        answer="借款本金为10000元，依据《民法典》第675条应按约返还。",
        verification=verification,
    )

    assert first is True
    assert second is False
    assert db.query(Message).filter_by(conversation_id=conversation.id, role="assistant").count() == 1
    db.refresh(conversation)
    assert conversation.message_count == 2
    saved = db.get(AgentRun, run.id)
    assert (saved.status, saved.state_version) == ("completed", 1)
    completed = LegalAgentState.model_validate_json(saved.state_json)
    assert completed.status is AgentStatus.COMPLETED
    assert completed.claim_checks == [
        ClaimCheck(
            claim="借款本金为10000元，依据《民法典》第675条应按约返还。",
            supported=True,
            evidence_ids=["evidence-a"],
            rationale="deterministic_verifier_pass",
        )
    ]
    assert db.query(AgentStep).filter_by(agent_run_id=run.id, decision="finalize").count() == 1
    assert db.query(AgentClaimCheck).filter_by(agent_run_id=run.id).count() == 1


def test_final_storage_rejects_foreign_owner_and_does_not_write(db):
    from agent.chat_integration import AgentFinalizationConflict, persist_agent_final_once

    user, conversation, run, state, draft = _records(db)
    verification = DeterministicVerifier().verify(state, draft)

    with pytest.raises(AgentFinalizationConflict):
        persist_agent_final_once(
            db,
            user_id=user.id + 99,
            conversation_id=conversation.id,
            run_id=run.id,
            expected_version=0,
            state=state,
            answer="借款本金为10000元，依据《民法典》第675条应按约返还。",
            verification=verification,
        )

    assert db.query(Message).filter_by(role="assistant").count() == 0
    assert db.get(AgentRun, run.id).status == "drafting"


def test_final_storage_rejects_non_pass_verification(db):
    from agent.chat_integration import AgentFinalizationConflict, persist_agent_final_once
    from agent.verifier import VerificationResult, VerificationVerdict

    user, conversation, run, state, _draft = _records(db)

    with pytest.raises(AgentFinalizationConflict):
        persist_agent_final_once(
            db,
            user_id=user.id,
            conversation_id=conversation.id,
            run_id=run.id,
            expected_version=0,
            state=state,
            answer="不应写入",
            verification=VerificationResult(
                verdict=VerificationVerdict.FAIL_SAFE,
                reason_code="UNSUPPORTED_CLAIM",
            ),
        )

    assert db.query(Message).filter_by(role="assistant").count() == 0


def _bootstrap(conversation_id: int) -> RequestBootstrap:
    query = "公司拖欠工资，应当如何主张权利？"
    return RequestBootstrap(
        conv_id=conversation_id,
        summary="",
        recent=[],
        recent_messages=[],
        image=None,
        user_text=query,
        image_rel=None,
        thumb_rel=None,
        image_description="",
        raw_query=query,
        supplement_text=query,
        intent="legal_query",
        is_exam=False,
        has_options=False,
        contract_mode=False,
        contract_text=None,
        client_truncated=False,
    )


class _AgentTransport:
    def __init__(self, *, issue_payload, planner_payload) -> None:
        self.issue_payload = issue_payload
        self.planner_payload = planner_payload
        self.calls = []

    def invoke(self, messages):
        self.calls.append(messages)
        system = messages[0].content
        if "争点分解器" in system:
            return SimpleNamespace(content=json.dumps(self.issue_payload, ensure_ascii=False))
        if "Planner" in system:
            content = (
                self.planner_payload
                if isinstance(self.planner_payload, str)
                else json.dumps(self.planner_payload, ensure_ascii=False)
            )
            return SimpleNamespace(content=content)
        payload = json.loads(messages[1].content)
        issue = payload["issues"][0]
        evidence_id = issue["evidence"][0]["evidence_id"]
        return SimpleNamespace(
            content=json.dumps(
                {
                    "claims": [
                        {
                            "local_id": "claim-a",
                            "issue_id": issue["issue_id"],
                            "text": "依据《民法典》第675条，应按约处理工资给付争议。",
                            "evidence_ids": [evidence_id],
                            "fact_ids": [],
                            "section": "conclusion",
                        }
                    ],
                    "missing_information": [],
                },
                ensure_ascii=False,
            )
        )


def _settings():
    return SimpleNamespace(
        agent_max_steps=8,
        agent_max_tool_calls=10,
        agent_max_replans=3,
        agent_max_clarifications=2,
        agent_max_verifier_research_returns=1,
    )


def _owner_conversation(db):
    user = User(username=f"agent-service-{db.query(User).count()}", password_hash="x")
    db.add(user)
    db.commit()
    conversation = Conversation(user_id=user.id, title="", summary="", message_count=1)
    db.add(conversation)
    db.commit()
    return user, conversation


def _issue_payload(*, unknown=False):
    return {
        "issues": [
            {
                "question": "拖欠工资时劳动者可以主张哪些权利？",
                "facts": [{"quote": "公司拖欠工资"}],
                "unknown_facts": (
                    [
                        {
                            "statement": "工资支付日是什么？",
                            "why_outcome_changes": "影响拖欠期间的确定。",
                        }
                    ]
                    if unknown
                    else []
                ),
            }
        ]
    }


def _law_gateway(policy_overrides: dict | None = None):
    def retrieve(_context, _args):
        return {
            "kind": "retrieve_laws",
            "statement": "已检索工资给付相关依据。",
            "evidence": [
                {
                    "source_id": "civil-code-675",
                    "source": "民法典",
                    "article": "第675条",
                    "snippet": "依据《民法典》第675条，应按约处理工资给付争议。",
                    "legal_validity": "effective",
                }
            ],
            "retrieval": {"query": "工资给付", "requested_k": 4, "returned_count": 1},
        }

    return ToolGateway(wrapper_overrides={"retrieve_laws": retrieve}, policy_overrides=policy_overrides)


def _law_gateway_with_empty_fanout():
    """V2-G2 适配：对服务端扇出检索（query=issue.question 完整疑问句）返回空证据，
    使会话保持 MISSING_EVIDENCE → replan → planner 决策仍被真正调用（保留全链路验证语义）；
    对 planner 带具体短检索词的调用返回有效证据。"""

    def retrieve(_context, args):
        query = getattr(args, "query", None) or ""
        is_fanout = len(query) > 8 or "？" in query or "?" in query
        if is_fanout:
            return {
                "kind": "retrieve_laws",
                "statement": "检索无有效法条依据。",
                "evidence": [],
                "retrieval": {"query": query, "requested_k": 4, "returned_count": 0},
            }
        return {
            "kind": "retrieve_laws",
            "statement": "已检索工资给付相关依据。",
            "evidence": [
                {
                    "source_id": "civil-code-675",
                    "source": "民法典",
                    "article": "第675条",
                    "snippet": "依据《民法典》第675条，应按约处理工资给付争议。",
                    "legal_validity": "effective",
                }
            ],
            "retrieval": {"query": query, "requested_k": 4, "returned_count": 1},
        }

    return ToolGateway(wrapper_overrides={"retrieve_laws": retrieve})


@dataclass(frozen=True)
class _Final:
    answer: str | None
    reason_code: str


def _finalize(state, draft, verification):
    from agent.verifier import render_verified

    return _Final(answer=render_verified(state, draft, verification), reason_code="READY")


def test_real_agent_service_runs_adapters_controller_gateway_writer_verifier_and_storage(db):
    from agent.service import execute_agent_request

    user, conversation = _owner_conversation(db)
    transport = _AgentTransport(
        issue_payload=_issue_payload(),
        planner_payload={
            "kind": "tool_call",
            "issue_id": "placeholder",
            "tool_name": "retrieve_laws",
            "args": {"query": "工资给付", "k": 4},
        },
    )

    # The Planner must reference the server-derived Issue ID, so obtain it only
    # from the Planner input produced by the real adapter rather than hard-code it.
    original_invoke = transport.invoke

    def dynamic_invoke(messages):
        if "Planner" in messages[0].content:
            planner_input = json.loads(messages[1].content)
            transport.planner_payload["issue_id"] = planner_input["issues"][0]["issue_id"]
        return original_invoke(messages)

    transport.invoke = dynamic_invoke
    result = execute_agent_request(
        db=db,
        user_id=user.id,
        settings=_settings(),
        bootstrap=_bootstrap(conversation.id),
        finalizer=_finalize,
        llm=transport,
        gateway=_law_gateway_with_empty_fanout(),
    )

    assert result.outcome == "completed"
    assert result.answer.startswith("已确认事实：\n")
    assert "可执行建议与风险提示：\n依据《民法典》第675条" in result.answer
    assert result.run_id is not None
    assert db.get(AgentRun, result.run_id).status == "completed"
    assert db.query(Message).filter_by(conversation_id=conversation.id, role="assistant").count() == 1
    assert len(transport.calls) == 3


def test_disconnect_after_verification_keeps_checkpoint_and_writes_no_assistant(db):
    from agent.service import execute_agent_request

    user, conversation = _owner_conversation(db)
    transport = _AgentTransport(
        issue_payload=_issue_payload(),
        planner_payload={
            "kind": "tool_call",
            "issue_id": "placeholder",
            "tool_name": "retrieve_laws",
            "args": {"query": "工资给付", "k": 4},
        },
    )
    original_invoke = transport.invoke

    def dynamic_invoke(messages):
        if "Planner" in messages[0].content:
            planner_input = json.loads(messages[1].content)
            transport.planner_payload["issue_id"] = planner_input["issues"][0]["issue_id"]
        return original_invoke(messages)

    transport.invoke = dynamic_invoke
    finalized = [False]

    def finalizer(state, draft, verification):
        finalized[0] = True
        return _finalize(state, draft, verification)

    result = execute_agent_request(
        db=db,
        user_id=user.id,
        settings=_settings(),
        bootstrap=_bootstrap(conversation.id),
        finalizer=finalizer,
        llm=transport,
        gateway=_law_gateway(),
        cancelled=lambda: finalized[0],
    )

    assert (result.outcome, result.reason_code) == ("failed", "CLIENT_DISCONNECTED")
    assert result.run_id is not None
    assert db.get(AgentRun, result.run_id).status == "drafting"
    assert db.query(AgentStep).filter_by(agent_run_id=result.run_id).count() > 0
    assert db.query(Message).filter_by(conversation_id=conversation.id, role="assistant").count() == 0


def test_real_agent_service_returns_clarification_without_assistant_message(db):
    from agent.service import execute_agent_request

    user, conversation = _owner_conversation(db)
    result = execute_agent_request(
        db=db,
        user_id=user.id,
        settings=_settings(),
        bootstrap=_bootstrap(conversation.id),
        finalizer=_finalize,
        llm=_AgentTransport(
            issue_payload=_issue_payload(unknown=True),
            planner_payload={"kind": "finish_research", "summary": "交给确定性评估"},
        ),
        gateway=_law_gateway(),
    )

    assert result.outcome == "clarification"
    assert result.prompt == "工资支付日是什么？"
    assert result.issue_id is not None
    assert db.query(Message).filter_by(conversation_id=conversation.id, role="assistant").count() == 0


def test_real_agent_service_requests_scope_selection_for_six_issues(db):
    from agent.service import execute_agent_request

    user, conversation = _owner_conversation(db)
    transport = _AgentTransport(
        issue_payload={
            "issues": [
                {"question": f"法律争点{index}的认定标准是什么？", "facts": [], "unknown_facts": []}
                for index in range(1, 7)
            ]
        },
        planner_payload={"kind": "stop", "reason": "范围选择前不得调用 planner"},
    )
    result = execute_agent_request(
        db=db,
        user_id=user.id,
        settings=_settings(),
        bootstrap=_bootstrap(conversation.id),
        finalizer=_finalize,
        llm=transport,
        gateway=_law_gateway(),
    )

    assert result.outcome == "clarification"
    assert result.reason_code == "ISSUE_SCOPE_SELECTION_REQUIRED"
    assert result.issue_id == "scope"
    assert result.prompt is not None
    assert "最多 5 个" in result.prompt
    assert "1. 法律争点1的认定标准是什么？" in result.prompt
    assert result.run_id is not None
    assert result.state_version >= 1
    saved = db.get(AgentRun, result.run_id)
    assert saved.status == "waiting_user"
    persisted = LegalAgentState.model_validate_json(saved.state_json)
    assert len(persisted.pending_scope_issue_ids) == 6
    # 全部 LLM 调用均为争点分解器（含其逐字覆盖 repair 重试）：零 planner/writer/工具调用
    assert transport.calls
    assert all("争点分解器" in messages[0].content for messages in transport.calls)
    assert db.query(Message).filter_by(conversation_id=conversation.id, role="assistant").count() == 0


def test_real_agent_service_resumes_same_run_without_new_user_or_agent_run(db):
    from agent.controller import _DEFAULT_RUN_LOCKS, resume_with_user_fact
    from agent.service import execute_agent_request

    user, conversation = _owner_conversation(db)
    transport = _AgentTransport(
        issue_payload=_issue_payload(unknown=True),
        planner_payload={"kind": "finish_research", "summary": "交给确定性评估"},
    )
    first = execute_agent_request(
        db=db,
        user_id=user.id,
        settings=_settings(),
        bootstrap=_bootstrap(conversation.id),
        finalizer=_finalize,
        llm=transport,
        gateway=_law_gateway(),
    )
    assert first.outcome == "clarification" and first.run_id is not None

    resumed = resume_with_user_fact(
        db=db,
        run_locks=_DEFAULT_RUN_LOCKS,
        run_id=first.run_id,
        expected_version=first.state_version,
        user_id=user.id,
        conversation_id=conversation.id,
        answer="每月5日支付工资",
    )
    transport.planner_payload = {
        "kind": "tool_call",
        "issue_id": "placeholder",
        "tool_name": "retrieve_laws",
        "args": {"query": "工资给付", "k": 4},
    }
    original_invoke = transport.invoke

    def dynamic_invoke(messages):
        if "Planner" in messages[0].content:
            planner_input = json.loads(messages[1].content)
            transport.planner_payload["issue_id"] = planner_input["issues"][0]["issue_id"]
        return original_invoke(messages)

    transport.invoke = dynamic_invoke
    completed = execute_agent_request(
        db=db,
        user_id=user.id,
        settings=_settings(),
        bootstrap=_bootstrap(conversation.id),
        finalizer=_finalize,
        run_id=resumed.run_id,
        llm=transport,
        gateway=_law_gateway(),
    )

    assert completed.outcome == "completed"
    assert completed.run_id == first.run_id
    assert db.query(AgentRun).filter_by(conversation_id=conversation.id).count() == 1
    assert db.query(Message).filter_by(conversation_id=conversation.id, role="user").count() == 0
    assert db.query(Message).filter_by(conversation_id=conversation.id, role="assistant").count() == 1


def test_chat_live_agent_selection_bootstraps_once_and_never_prepares_fast_path(db, monkeypatch):
    from fastapi.testclient import TestClient

    import main
    from agent.chat_integration import AgentPublicResult
    from agent.gate import AgentGateDecision
    from auth import get_current_user

    user, conversation = _owner_conversation(db)
    bootstrap = _bootstrap(conversation.id)
    calls = []
    monkeypatch.setattr(main, "setup_logging", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(main.settings, "agent_enabled", True)
    monkeypatch.setattr(main.settings, "agent_traffic_percent", 100)
    monkeypatch.setattr(main, "_bootstrap_only", lambda *a, **k: calls.append("bootstrap") or bootstrap)
    monkeypatch.setattr(
        main,
        "decide_gate",
        lambda actual: AgentGateDecision(mode="agent_path", complexity="complex", reason_codes=("MULTI_STAGE",)),
    )
    monkeypatch.setattr(
        main,
        "_prepare_fast_path_only",
        lambda actual: pytest.fail("Fast Path must not prepare after Agent selection"),
    )
    monkeypatch.setattr(
        main,
        "execute_agent_request",
        lambda **kwargs: AgentPublicResult(
            outcome="completed",
            run_id="run-live",
            conversation_id=conversation.id,
            state_version=4,
            answer="已验证答案",
            reason_code="READY",
            coverage_status="full",
        ),
    )
    main.app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=user.id)
    try:
        with TestClient(main.app) as client:
            response = client.post(
                "/api/chat",
                json={"content": bootstrap.raw_query, "conversation_id": conversation.id},
            )
    finally:
        main.app.dependency_overrides.clear()

    events = [
        json.loads(line[6:])
        for line in response.text.splitlines()
        if line.startswith("data: ") and line[6:] != "[DONE]"
    ]
    assert response.status_code == 200
    assert calls == ["bootstrap"]
    assert [event["type"] for event in events] == [
        "agent_status",
        "verification",
        "token",
        "final",
    ]
    assert events[-1]["conversation_id"] == conversation.id


def test_forbidden_agent_failure_never_calls_fast_path_fallback(db, monkeypatch):
    from fastapi.testclient import TestClient

    import main
    from agent.chat_integration import AgentPublicResult
    from agent.gate import AgentGateDecision
    from auth import get_current_user

    user, conversation = _owner_conversation(db)
    bootstrap = _bootstrap(conversation.id)
    monkeypatch.setattr(main, "setup_logging", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(main.settings, "agent_enabled", True)
    monkeypatch.setattr(main.settings, "agent_traffic_percent", 100)
    monkeypatch.setattr(main, "_bootstrap_only", lambda *a, **k: bootstrap)
    monkeypatch.setattr(
        main,
        "decide_gate",
        lambda actual: AgentGateDecision(mode="agent_path", complexity="complex", reason_codes=("MULTI_STAGE",)),
    )
    monkeypatch.setattr(
        main,
        "_prepare_fast_path_only",
        lambda actual: pytest.fail("Policy failure must not enter Fast Path"),
    )
    monkeypatch.setattr(
        main,
        "execute_agent_request",
        lambda **kwargs: AgentPublicResult(
            outcome="failed",
            run_id="run-policy",
            conversation_id=conversation.id,
            state_version=2,
            reason_code="PLANNER_POLICY_VIOLATION",
        ),
    )
    main.app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=user.id)
    try:
        with TestClient(main.app) as client:
            response = client.post(
                "/api/chat",
                json={"content": bootstrap.raw_query, "conversation_id": conversation.id},
            )
    finally:
        main.app.dependency_overrides.clear()

    assert '"type": "error"' in response.text
    assert "PLANNER_POLICY_VIOLATION" in response.text
    assert '"type": "restart"' not in response.text


def test_fallback_to_fast_path_requires_allowlist_and_prepares_same_bootstrap_once(monkeypatch):
    import main

    bootstrap = _bootstrap(17)
    prepared = {"conv_id": 17}
    calls = []
    monkeypatch.setattr(
        main,
        "_prepare_fast_path_only",
        lambda actual: calls.append(actual) or prepared,
    )

    assert main.fallback_to_fast_path(bootstrap, "TOOL_TIMEOUT") is prepared
    assert prepared["agent_fallback_reason"] == "TOOL_TIMEOUT"
    assert calls == [bootstrap]
    with pytest.raises(ValueError, match="not eligible"):
        main.fallback_to_fast_path(bootstrap, "PLANNER_POLICY_VIOLATION")
    assert calls == [bootstrap]


@pytest.mark.parametrize(
    ("planner_payload", "expected_outcome", "expected_reason"),
    [
        ("not-json", "fallback", "PLANNER_PARSE_ERROR"),
        (
            {"kind": "stop", "reason": "done", "budgets": {"max_steps": 999}},
            "failed",
            "PLANNER_POLICY_VIOLATION",
        ),
    ],
)
def test_real_agent_service_allows_only_technical_planner_fallback(
    db, planner_payload, expected_outcome, expected_reason
):
    from agent.service import execute_agent_request

    user, conversation = _owner_conversation(db)
    result = execute_agent_request(
        db=db,
        user_id=user.id,
        settings=_settings(),
        bootstrap=_bootstrap(conversation.id),
        finalizer=_finalize,
        llm=_AgentTransport(issue_payload=_issue_payload(), planner_payload=planner_payload),
        gateway=_law_gateway_with_empty_fanout(),
    )

    assert (result.outcome, result.reason_code) == (expected_outcome, expected_reason)
    assert db.query(Message).filter_by(conversation_id=conversation.id, role="assistant").count() == 0


def test_malformed_issue_output_fails_closed_without_fast_fallback(db):
    from agent.service import execute_agent_request

    user, conversation = _owner_conversation(db)
    result = execute_agent_request(
        db=db,
        user_id=user.id,
        settings=_settings(),
        bootstrap=_bootstrap(conversation.id),
        finalizer=_finalize,
        llm=_AgentTransport(issue_payload={"issues": []}, planner_payload={"kind": "stop", "reason": "unused"}),
        gateway=_law_gateway(),
    )

    assert (result.outcome, result.reason_code) == ("failed", "ISSUE_DECOMPOSITION_INVALID")
    assert db.query(AgentRun).filter_by(conversation_id=conversation.id).count() == 0
    assert db.query(Message).filter_by(conversation_id=conversation.id, role="assistant").count() == 0


@pytest.mark.parametrize(
    ("failure", "expected_outcome", "expected_reason"),
    [
        (ValueError("invalid runtime wiring"), "failed", "AGENT_EXECUTION_FAILURE"),
        ("unavailable", "fallback", "TOOL_UNAVAILABLE"),
    ],
)
def test_runtime_construction_only_falls_back_for_named_unavailability(
    db, monkeypatch, failure, expected_outcome, expected_reason
):
    import agent.service as service
    from agent.runtime import RuntimeUnavailable

    user, conversation = _owner_conversation(db)
    raised = RuntimeUnavailable("no configured model") if failure == "unavailable" else failure
    monkeypatch.setattr(service, "build_agent_runtime", lambda **kwargs: (_ for _ in ()).throw(raised))

    result = service.execute_agent_request(
        db=db,
        user_id=user.id,
        settings=_settings(),
        bootstrap=_bootstrap(conversation.id),
        finalizer=_finalize,
    )

    assert (result.outcome, result.reason_code) == (expected_outcome, expected_reason)


# ---------------------------------------------------------------------------
# T2（2026-09-09）：回喂预算持久化及版本传递——真实持久化路径集成测试。
# 注：2026-09-12 Ticket 2 删除 coverage 回喂循环后，该组已改写为串行 writer 语义
# （`_SerialWriterTransport`），"attempt 持久化"相关旧断言随循环删除。
# ---------------------------------------------------------------------------


def _two_issue_payload() -> dict:
    """两个争点，事实均确认（无 unknown_facts，不触发澄清）。

    facts quote 必须是用户请求原文的逐字片段（build_initial_agent_state 校验），
    因此配套 _two_issue_bootstrap 提供包含两个片段的 raw_query。
    """
    return {
        "issues": [
            {
                "question": "借款到期后应当如何返还？",
                "facts": [{"quote": "借款本金为一万元，约定到期返还"}],
                "unknown_facts": [],
            },
            {
                "question": "拖欠的工资应当如何支付？",
                "facts": [{"quote": "公司拖欠工资"}],
                "unknown_facts": [],
            },
        ]
    }


def _two_issue_bootstrap(conversation_id: int) -> RequestBootstrap:
    query = "借款本金为一万元，约定到期返还，且公司拖欠工资，应当如何主张权利？"
    return RequestBootstrap(
        conv_id=conversation_id,
        summary="",
        recent=[],
        recent_messages=[],
        image=None,
        user_text=query,
        image_rel=None,
        thumb_rel=None,
        image_description="",
        raw_query=query,
        supplement_text=query,
        intent="legal_query",
        is_exam=False,
        has_options=False,
        contract_mode=False,
        contract_text=None,
        client_truncated=False,
    )


class _TwoIssueLawGateway:
    """扇出检索替身：按 query 关键词返回各争点专属的生效成文法证据。"""

    def __init__(self) -> None:
        self.queries: list[str] = []

    def retrieve(self, _context, args):
        query = getattr(args, "query", "") or ""
        self.queries.append(query)
        if "借款" in query:
            evidence = {
                "source_id": "civil-code-675",
                "source": "民法典",
                "article": "第675条",
                "snippet": "依据《民法典》第675条，借款人应当按照约定的期限返还借款。",
                "legal_validity": "effective",
            }
        else:
            evidence = {
                "source_id": "labor-law-50",
                "source": "劳动法",
                "article": "第50条",
                "snippet": "依据《劳动法》第50条，工资应当以货币形式按月支付给劳动者本人。",
                "legal_validity": "effective",
            }
        return {
            "kind": "retrieve_laws",
            "statement": "已检索相关依据。",
            "evidence": [evidence],
            "retrieval": {"query": query, "requested_k": 4, "returned_count": 1},
        }

    def as_gateway(self) -> ToolGateway:
        return ToolGateway(wrapper_overrides={"retrieve_laws": self.retrieve})


class _SerialWriterTransport:
    """脚本替身（Ticket 2 串行 writer）：每次 writer 渲染只收到一个争点的单争点 payload。

    issue_id/evidence_id 均从实际输入 payload 提取（服务端生成，不猜测）。
    mode（负例注入，均只影响指定争点的响应）：
    - "complete"：每个争点绑定自身证据（全链路成功路径）；
    - "invalid_evidence_last"：最后一个争点引用不存在的证据 ID → writer UNKNOWN_EVIDENCE_ID；
    - "overconfident_last"：最后一个争点 claim 含过度自信表述 → verifier REWRITE（首次非 PASS
      即终态失败，不再有第二轮 writer）。
    """

    def __init__(self, issue_payload: dict, *, mode: str = "complete") -> None:
        self.issue_payload = issue_payload
        self.mode = mode
        self.calls: list[tuple[str, int]] = []

    def invoke(self, messages):
        system = messages[0].content
        if "争点分解器" in system:
            self.calls.append(("issue", len(messages)))
            return SimpleNamespace(content=json.dumps(self.issue_payload, ensure_ascii=False))
        if "Planner" in system:
            self.calls.append(("planner", len(messages)))
            return SimpleNamespace(
                content=json.dumps({"kind": "finish_research", "summary": "扇出检索已完成"}, ensure_ascii=False)
            )
        payload = json.loads(messages[1].content)
        assert len(payload["issues"]) == 1, "Ticket 2：writer 每次只接收一个争点"
        issue = payload["issues"][0]
        writer_index = len([kind for kind, _ in self.calls if kind.startswith("writer")])
        self.calls.append(("writer", len(messages)))
        evidence = issue["evidence"][0]
        source, _, article = evidence["source_ref"].partition("#")
        evidence_ids = [evidence["evidence_id"]]
        text = f"依据《{source}》{article}，应当依法履行相应义务。"
        total_issues = len(self.issue_payload["issues"])
        if self.mode == "invalid_evidence_all":
            # 负例注入：**所有**争点都引用不存在的证据 ID（测"全部失败仍整轮失败"分支）
            evidence_ids = ["ev-ghost-does-not-exist"]
            text = "引用不存在的证据，应当被 writer 拒绝。"
        elif self.mode == "invalid_evidence_last" and writer_index == total_issues - 1:
            # 负例注入：最后一个争点引用不存在的证据 ID → UNKNOWN_EVIDENCE_ID
            evidence_ids = ["ev-ghost-does-not-exist"]
            text = "引用不存在的证据，应当被 writer 拒绝。"
        if self.mode == "overconfident_last" and writer_index == total_issues - 1:
            text = f"依据《{source}》{article}，一定应当依法履行相应义务。"
        claims = [
            {
                "local_id": f"claim-{issue['issue_id']}",
                "issue_id": issue["issue_id"],
                "text": text,
                "evidence_ids": evidence_ids,
                "fact_ids": [],
                "section": "conclusion",
            }
        ]
        return SimpleNamespace(content=json.dumps({"claims": claims, "missing_information": []}, ensure_ascii=False))


def test_serial_writer_completes_two_issues_with_one_call_each(db):
    """Ticket 2：两个争点各自一次有效生成 → 合并 PASS → 终稿落盘。

    验收：DB COMPLETED、assistant 恰一条、writer 恰两次（逐争点、无回喂第二轮）、
    无 coverage_rewrite_attempt 检查点（回喂循环已删除）、verifier_research_returns 保持 0。
    T1（2026-09-16）：全争点成功 ⇒ completed + coverage=full（结果、state、消息关联三处一致）。
    """
    from agent.service import execute_agent_request

    user, conversation = _owner_conversation(db)
    transport = _SerialWriterTransport(_two_issue_payload())
    result = execute_agent_request(
        db=db,
        user_id=user.id,
        settings=_settings(),
        bootstrap=_two_issue_bootstrap(conversation.id),
        finalizer=_finalize,
        llm=transport,
        gateway=_TwoIssueLawGateway().as_gateway(),
    )

    assert result.outcome == "completed", f"unexpected failure: {result.reason_code}"
    assert result.run_id is not None
    # T1：全争点成功 ⇒ full + 空列表（AgentPublicResult 契约）
    assert result.coverage_status == "full"
    assert result.uncovered_issues == []
    stored_run = db.get(AgentRun, result.run_id)
    assert stored_run.status == "completed"
    reloaded = LegalAgentState.model_validate_json(stored_run.state_json)
    assert reloaded.verifier_research_returns == 0
    # T1：completed 的 run.state_json 是覆盖信息事实源（full 也要落盘，历史重载可判）
    assert reloaded.uncovered_issues == []
    # A6 脆弱点锁固：full 判定依赖 state_json 显式含 uncovered_issues 键（而非默认值推断）——
    # 若未来序列化改为 exclude_defaults，此断言会失败并暴露"full 退化为 unknown"的静默回归
    assert '"uncovered_issues"' in stored_run.state_json
    # T1：assistant 消息关联 run（历史重载用）
    stored_message = db.query(Message).filter_by(conversation_id=conversation.id, role="assistant").one()
    assert stored_message.agent_run_id == result.run_id
    writer_calls = [kind for kind, _ in transport.calls if kind == "writer"]
    assert writer_calls == ["writer", "writer"]
    assert db.query(AgentStep).filter_by(agent_run_id=result.run_id, decision="coverage_rewrite_attempt").count() == 0


def test_with_uncovered_notice_passthrough_and_listing():
    """未覆盖说明（纯函数）：无未覆盖 ⇒ 正文逐字不变；有 ⇒ 显式列出争点与原因码。"""
    from types import SimpleNamespace as NS

    from agent.service import _with_uncovered_notice

    state = NS(issues=[NS(issue_id="i1", question="甲争点？"), NS(issue_id="i2", question="乙争点？")])
    assert _with_uncovered_notice("正文结论。", [], state) == "正文结论。"
    out = _with_uncovered_notice("正文结论。", [("i2", "UNKNOWN_EVIDENCE_ID")], state)
    assert out.startswith("正文结论。")
    assert "乙争点？" in out and "UNKNOWN_EVIDENCE_ID" in out and "未能覆盖的争点" in out


def test_partial_delivery_delivers_remaining_issues_when_one_fails(db):
    """争点级部分交付（2026-09-15，开关默认关）——开关**开**时：

    最后一个争点 writer 校验失败（UNKNOWN_EVIDENCE_ID）**不再让整轮失败**：
    - 该争点记为未覆盖，其余争点照常渲染并交付（outcome=completed）；
    - 终稿**显式列出**未覆盖争点及原因（防静默降级，§4.2「不跳过问题」）；
    - writer 对**全部**争点各调用一次（不再首个失败即停）。
    """
    from agent.service import execute_agent_request
    from models import AgentRun

    user, conversation = _owner_conversation(db)
    transport = _SerialWriterTransport(_two_issue_payload(), mode="invalid_evidence_last")
    settings_stub = _settings()
    settings_stub.agent_partial_delivery_enabled = True  # 本测试的被测开关
    result = execute_agent_request(
        db=db,
        user_id=user.id,
        settings=settings_stub,
        bootstrap=_two_issue_bootstrap(conversation.id),
        finalizer=_finalize,
        llm=transport,
        gateway=_TwoIssueLawGateway().as_gateway(),
    )

    stored_run = db.get(AgentRun, result.run_id)
    assert stored_run.status == "completed"
    assert [k for k, _ in transport.calls if k == "writer"] == ["writer", "writer"]
    answer = result.answer or ""
    assert "未能覆盖的争点" in answer
    assert "UNKNOWN_EVIDENCE_ID" in answer
    # T1（2026-09-16）：部分交付 ⇒ coverage=partial + 未覆盖列表（结果、state、消息关联三处一致）
    reloaded = LegalAgentState.model_validate_json(stored_run.state_json)
    assert result.coverage_status == "partial"
    assert [(u.issue_id, u.reason_code) for u in result.uncovered_issues] == [
        (u.issue_id, u.reason_code) for u in reloaded.uncovered_issues
    ]
    # 未覆盖的恰是最后一个争点（invalid_evidence_last），且列表保持原争点顺序、引用既有 issue_id
    assert [(u.issue_id, u.reason_code) for u in reloaded.uncovered_issues] == [
        (reloaded.issues[1].issue_id, "UNKNOWN_EVIDENCE_ID")
    ]
    stored_message = db.query(Message).filter_by(conversation_id=conversation.id, role="assistant").one()
    assert stored_message.agent_run_id == result.run_id


def test_partial_delivery_all_failed_still_fails(db):
    """开关开但**全部**争点都失败 ⇒ 仍整轮失败（无内容可交付，不得伪造"部分交付"）。

    同时验证：失败**不中断**渲染（两个争点都被调用过）——与 fail-fast 的调用序列不同。
    """
    from agent.service import execute_agent_request

    user, conversation = _owner_conversation(db)
    transport = _SerialWriterTransport(_two_issue_payload(), mode="invalid_evidence_all")
    settings_stub = _settings()
    settings_stub.agent_partial_delivery_enabled = True
    result = execute_agent_request(
        db=db,
        user_id=user.id,
        settings=settings_stub,
        bootstrap=_two_issue_bootstrap(conversation.id),
        finalizer=_finalize,
        llm=transport,
        gateway=_TwoIssueLawGateway().as_gateway(),
    )

    assert result.outcome == "failed"
    # 保留**首个**失败争点的原因码（与开关关闭时的首个失败口径一致）
    assert result.reason_code == "UNKNOWN_EVIDENCE_ID"
    # T1：失败结果不携带覆盖信息；且不得生成 completed assistant 消息
    assert result.coverage_status is None
    assert result.uncovered_issues == []
    assert db.query(Message).filter_by(conversation_id=conversation.id, role="assistant").count() == 0
    # 两个争点都被渲染过（不是首个失败即停）
    assert [k for k, _ in transport.calls if k == "writer"] == ["writer", "writer"]


def test_partial_delivery_off_keeps_fail_fast(db):
    """开关**关**（默认）：最后一个争点失败 ⇒ 整轮失败，行为与既有 fail-fast 完全一致。"""
    from agent.service import execute_agent_request

    user, conversation = _owner_conversation(db)
    transport = _SerialWriterTransport(_two_issue_payload(), mode="invalid_evidence_last")
    result = execute_agent_request(
        db=db,
        user_id=user.id,
        settings=_settings(),  # 不带该字段 ⇒ getattr 兜底为关
        bootstrap=_two_issue_bootstrap(conversation.id),
        finalizer=_finalize,
        llm=transport,
        gateway=_TwoIssueLawGateway().as_gateway(),
    )

    assert result.outcome == "failed"
    assert result.reason_code == "UNKNOWN_EVIDENCE_ID"
    # 首个失败即停：最后一个争点失败 ⇒ writer 恰好被调用到该争点为止
    assert [k for k, _ in transport.calls if k == "writer"] == ["writer", "writer"]


def test_conversation_history_coverage_projection_full_partial_unknown(db, monkeypatch):
    """T1（2026-09-16）历史重载：GET /api/conversations/{id} 的覆盖投影契约。

    - Agent assistant 消息（消息关联 run，run state_json 含结构化覆盖）→ full / partial；
    - 旧消息（无 agent_run_id 关联）→ **unknown**，不得推断为 full（A5）；
    - 用户消息不适用覆盖 → None；
    - real-time SSE 与历史 API 看到同一覆盖结果（A6 的历史侧）。
    """
    from types import SimpleNamespace

    from fastapi.testclient import TestClient

    import main
    from agent.service import execute_agent_request
    from auth import get_current_user

    user, conversation = _owner_conversation(db)

    # full：两争点全成功
    full_result = execute_agent_request(
        db=db,
        user_id=user.id,
        settings=_settings(),
        bootstrap=_two_issue_bootstrap(conversation.id),
        finalizer=_finalize,
        llm=_SerialWriterTransport(_two_issue_payload()),
        gateway=_TwoIssueLawGateway().as_gateway(),
    )
    assert full_result.coverage_status == "full"

    # partial：最后争点失败（部分交付开关开）
    partial_settings = _settings()
    partial_settings.agent_partial_delivery_enabled = True
    partial_result = execute_agent_request(
        db=db,
        user_id=user.id,
        settings=partial_settings,
        bootstrap=_two_issue_bootstrap(conversation.id),
        finalizer=_finalize,
        llm=_SerialWriterTransport(_two_issue_payload(), mode="invalid_evidence_last"),
        gateway=_TwoIssueLawGateway().as_gateway(),
    )
    assert partial_result.coverage_status == "partial"

    # 旧形态：无 run 关联的 assistant 消息（T1 之前落库的历史消息）
    db.add(Message(conversation_id=conversation.id, role="assistant", content="旧 RAG 回答"))
    # 用户消息：覆盖投影不适用
    db.add(Message(conversation_id=conversation.id, role="user", content="用户提问"))
    db.commit()

    monkeypatch.setattr(main, "setup_logging", lambda *_args, **_kwargs: None)
    main.app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=user.id)
    try:
        with TestClient(main.app) as client:
            response = client.get(f"/api/conversations/{conversation.id}")
    finally:
        main.app.dependency_overrides.clear()

    assert response.status_code == 200
    msgs = response.json()["messages"]
    by_content = {m["content"]: m for m in msgs}
    full_msg = by_content[full_result.answer]
    partial_msg = by_content[partial_result.answer]
    legacy_msg = by_content["旧 RAG 回答"]
    user_msg = by_content["用户提问"]

    assert full_msg["coverage_status"] == "full"
    assert full_msg["uncovered_issues"] == []
    assert partial_msg["coverage_status"] == "partial"
    assert partial_msg["uncovered_issues"] == [
        {"issue_id": u.issue_id, "reason_code": u.reason_code} for u in partial_result.uncovered_issues
    ]
    # A5：旧消息 unknown，不推断 full
    assert legacy_msg["coverage_status"] == "unknown"
    assert legacy_msg["uncovered_issues"] == []
    assert user_msg["coverage_status"] is None


def test_coverage_gate_terminal_failure_logs_per_issue_binding_facts(db, caplog):
    """首次 verifier 非 PASS 即终态失败（不触发第二轮 writer），且仍留逐争点可归因诊断。

    动机（2026-09-12 H3 C01 付费运行无法归因）：终态只落 verdict 与原因码。此断言锁住
    逐争点记录（claim 数与生效成文法绑定数）的可区分性；Ticket 2 后"无 claim"场景由
    writer 的 ISSUE_CLAIMS_MISSING 前置拦截，此处覆盖"有 claim 未超限但含过度自信表述"
    （REWRITE）→ 合并后首次 verify 非 PASS → 终态失败。
    """
    import logging as _logging

    from agent.service import execute_agent_request

    user, conversation = _owner_conversation(db)
    transport = _SerialWriterTransport(_two_issue_payload(), mode="overconfident_last")
    with caplog.at_level(_logging.INFO, logger="legal.agent"):
        result = execute_agent_request(
            db=db,
            user_id=user.id,
            settings=_settings(),
            bootstrap=_two_issue_bootstrap(conversation.id),
            finalizer=_finalize,
            llm=transport,
            gateway=_TwoIssueLawGateway().as_gateway(),
        )

    assert result.outcome == "failed"
    assert result.reason_code == "OVERCONFIDENT_WORDING"
    # 不触发第二轮 writer：每争点恰一次生成
    assert [kind for kind, _ in transport.calls if kind == "writer"] == ["writer", "writer"]
    records = [r for r in caplog.records if getattr(r, "agent_coverage_issues", None) is not None]
    assert records, "覆盖率/终稿验证失败必须留下 agent_coverage_issues 诊断，否则失败不可归因"
    facts = records[-1].agent_coverage_issues
    assert len(facts) == 2, "必须是逐争点的记录"
    assert all(row["claims"] >= 1 for row in facts)
    assert all(row["claims_bound_effective_statute"] >= 1 for row in facts)
    assert getattr(records[-1], "agent_coverage_gap_count", None) == 0
    assert getattr(records[-1], "agent_issue_count", None) == 2
    assert db.query(Message).filter_by(conversation_id=conversation.id, role="assistant").count() == 0


def test_coverage_gate_diagnostic_field_is_registered_in_log_whitelist():
    """白名单回归：诊断字段未登记会被 JSON formatter 静默丢弃（同 V2-T8 的教训）。"""
    from observability import _ACCOUNT_FIELDS

    assert "agent_coverage_issues" in _ACCOUNT_FIELDS


def test_serial_writer_invalid_evidence_fails_fast_without_assistant(db):
    """最后一个争点引用不存在证据 ID → writer FAIL_SAFE 立即失败；无 assistant、无回喂。"""
    from agent.service import execute_agent_request

    user, conversation = _owner_conversation(db)
    transport = _SerialWriterTransport(_two_issue_payload(), mode="invalid_evidence_last")
    result = execute_agent_request(
        db=db,
        user_id=user.id,
        settings=_settings(),
        bootstrap=_two_issue_bootstrap(conversation.id),
        finalizer=_finalize,
        llm=transport,
        gateway=_TwoIssueLawGateway().as_gateway(),
    )

    assert (result.outcome, result.reason_code) == ("failed", "UNKNOWN_EVIDENCE_ID")
    # 第一个争点成功 + 第二个争点失败即停：恰两次 writer 调用，无第二轮/回喂
    assert [kind for kind, _ in transport.calls if kind == "writer"] == ["writer", "writer"]
    assert db.query(Message).filter_by(conversation_id=conversation.id, role="assistant").count() == 0
    stored_run = db.get(AgentRun, result.run_id)
    assert stored_run.status == "failed"
    assert stored_run.last_error_code == "UNKNOWN_EVIDENCE_ID"
    failure_step = db.query(AgentStep).filter_by(agent_run_id=result.run_id, decision="failure").one_or_none()
    assert failure_step is not None
    assert failure_step.reason_code == "UNKNOWN_EVIDENCE_ID"
    # Ticket 2：stage 带出失败争点
    assert ":UNKNOWN_EVIDENCE_ID" in (failure_step.result_summary or "")
    reloaded = LegalAgentState.model_validate_json(stored_run.state_json)
    assert reloaded.verifier_research_returns == 0
    assert db.query(AgentStep).filter_by(agent_run_id=result.run_id, decision="coverage_rewrite_attempt").count() == 0


def test_verifier_crash_on_first_verification_reports_technical_failure(db, monkeypatch):
    """首次 verify 异常 → 技术失败（技术 fallback 白名单），无第二轮 writer。"""
    from agent.service import execute_agent_request
    from agent.verifier import DeterministicVerifier

    def flaky_verify(self, state, draft):
        raise RuntimeError("simulated verifier crash")

    monkeypatch.setattr(DeterministicVerifier, "verify", flaky_verify)
    user, conversation = _owner_conversation(db)
    transport = _SerialWriterTransport(_two_issue_payload())
    result = execute_agent_request(
        db=db,
        user_id=user.id,
        settings=_settings(),
        bootstrap=_two_issue_bootstrap(conversation.id),
        finalizer=_finalize,
        llm=transport,
        gateway=_TwoIssueLawGateway().as_gateway(),
    )

    # VERIFIER_TECHNICAL_FAILURE 按既有 routing_metrics 分类为技术 fallback（与原实现同码同函数）
    assert (result.outcome, result.reason_code) == ("fallback", "VERIFIER_TECHNICAL_FAILURE")
    stored_run = db.get(AgentRun, result.run_id)
    assert stored_run.status == "failed"
    assert stored_run.last_error_code == "VERIFIER_TECHNICAL_FAILURE"
    assert [kind for kind, _ in transport.calls if kind == "writer"] == ["writer", "writer"]
    assert db.query(Message).filter_by(conversation_id=conversation.id, role="assistant").count() == 0


def test_disconnect_between_issues_stops_serial_writer_without_assistant(db):
    """第 N 个争点渲染前取消 → CLIENT_DISCONNECTED；后续争点不再调用，无 assistant 写入。"""
    from agent.service import execute_agent_request

    user, conversation = _owner_conversation(db)
    transport = _SerialWriterTransport(_two_issue_payload())
    original_invoke = transport.invoke

    def invoke_then_disconnect(messages):
        response = original_invoke(messages)
        if transport.calls[-1][0] == "writer":
            disconnected[0] = True  # 第一个争点 writer 完成后断连（第二个争点调用之前）
        return response

    disconnected = [False]
    transport.invoke = invoke_then_disconnect
    result = execute_agent_request(
        db=db,
        user_id=user.id,
        settings=_settings(),
        bootstrap=_two_issue_bootstrap(conversation.id),
        finalizer=_finalize,
        llm=transport,
        gateway=_TwoIssueLawGateway().as_gateway(),
        cancelled=lambda: disconnected[0],
    )

    assert (result.outcome, result.reason_code) == ("failed", "CLIENT_DISCONNECTED")
    assert [kind for kind, _ in transport.calls if kind == "writer"] == ["writer"]
    assert db.query(Message).filter_by(conversation_id=conversation.id, role="assistant").count() == 0
    reloaded = LegalAgentState.model_validate_json(db.get(AgentRun, result.run_id).state_json)
    assert reloaded.verifier_research_returns == 0


def test_agent_request_rejects_foreign_run_without_state_writes(db):
    """跨用户 run_id → OWNERSHIP_FAILURE 且零状态写入（所有权约束在 service 边界生效）。"""
    from agent.service import execute_agent_request

    owner, owner_conversation = _owner_conversation(db)
    transport = _SerialWriterTransport(_two_issue_payload())
    first = execute_agent_request(
        db=db,
        user_id=owner.id,
        settings=_settings(),
        bootstrap=_two_issue_bootstrap(owner_conversation.id),
        finalizer=_finalize,
        llm=transport,
        gateway=_TwoIssueLawGateway().as_gateway(),
    )
    assert first.outcome == "completed"
    completed_run = db.get(AgentRun, first.run_id)
    completed_state_json = completed_run.state_json
    completed_version = completed_run.state_version

    stranger, stranger_conversation = _owner_conversation(db)
    replay = execute_agent_request(
        db=db,
        user_id=stranger.id,
        settings=_settings(),
        bootstrap=_two_issue_bootstrap(stranger_conversation.id),
        finalizer=_finalize,
        run_id=first.run_id,
        llm=transport,
        gateway=_TwoIssueLawGateway().as_gateway(),
    )

    assert (replay.outcome, replay.reason_code) == ("failed", "OWNERSHIP_FAILURE")
    assert db.query(Message).filter_by(conversation_id=stranger_conversation.id, role="assistant").count() == 0
    final_run = db.get(AgentRun, first.run_id)
    assert (final_run.state_json, final_run.state_version) == (completed_state_json, completed_version)


def test_overconfident_rewrite_verdict_persisted_as_unimplemented(db):
    """verifier REWRITE → 首次非 PASS 即终态失败，FAILED 终态与 verdict 阶段落盘（Ticket 2）。"""
    from agent.service import execute_agent_request

    user, conversation = _owner_conversation(db)
    transport = _SerialWriterTransport(_two_issue_payload(), mode="overconfident_last")
    result = execute_agent_request(
        db=db,
        user_id=user.id,
        settings=_settings(),
        bootstrap=_two_issue_bootstrap(conversation.id),
        finalizer=_finalize,
        llm=transport,
        gateway=_TwoIssueLawGateway().as_gateway(),
    )

    assert (result.outcome, result.reason_code) == ("failed", "OVERCONFIDENT_WORDING")
    # 每争点恰一次生成（最后一个争点的过度自信表述在合并后由 verifier 拦截）：
    # 不进回喂循环，无 attempt checkpoint
    assert [kind for kind, _ in transport.calls if kind.startswith("writer")] == ["writer", "writer"]
    assert db.query(AgentStep).filter_by(agent_run_id=result.run_id, decision="coverage_rewrite_attempt").count() == 0
    stored_run = db.get(AgentRun, result.run_id)
    assert stored_run.status == "failed"
    assert stored_run.last_error_code == "OVERCONFIDENT_WORDING"
    failure_step = db.query(AgentStep).filter_by(agent_run_id=result.run_id, decision="failure").one_or_none()
    assert failure_step is not None
    assert failure_step.reason_code == "OVERCONFIDENT_WORDING"
    assert failure_step.result_summary == "VERIFIER:REWRITE"
    reloaded = LegalAgentState.model_validate_json(stored_run.state_json)
    assert reloaded.status is AgentStatus.FAILED
    assert reloaded.verifier_research_returns == 0  # 未消耗回喂预算
    assert result.state_version == stored_run.state_version
    assert db.query(Message).filter_by(conversation_id=conversation.id, role="assistant").count() == 0


@pytest.mark.parametrize("conflict", [False, True])
def test_failure_persistence_reports_storage_error_or_conflict(db, monkeypatch, caplog, conflict):
    """保存失败公开报告真实故障，保留预算及并发赢家，日志不泄露异常原文。"""
    import agent.service as service
    from agent.service import execute_agent_request
    from observability import _JsonFormatter

    real_compare_and_save = service.compare_and_save
    winner_versions = []

    def failing_on_failed_state(*args, **kwargs):
        if kwargs.get("state") is not None and kwargs["state"].status is AgentStatus.FAILED:
            if not conflict:
                raise OSError("secret-database-credentials")
            winner = LegalAgentState.model_validate_json(kwargs["run"].state_json)
            real_compare_and_save(
                args[0],
                run=kwargs["run"],
                expected_version=kwargs["expected_version"],
                state=winner,
                status=winner.status.value,
            )
            winner_versions.append(kwargs["expected_version"] + 1)
        return real_compare_and_save(*args, **kwargs)

    monkeypatch.setattr(service, "compare_and_save", failing_on_failed_state)
    user, conversation = _owner_conversation(db)
    transport = _SerialWriterTransport(_two_issue_payload(), mode="invalid_evidence_last")
    result = execute_agent_request(
        db=db,
        user_id=user.id,
        settings=_settings(),
        bootstrap=_two_issue_bootstrap(conversation.id),
        finalizer=_finalize,
        llm=transport,
        gateway=_TwoIssueLawGateway().as_gateway(),
    )

    expected = "AGENT_FINALIZATION_CONFLICT" if conflict else "AGENT_STORAGE_FAILURE"
    assert (result.outcome, result.reason_code) == ("failed", expected)
    stored_run = db.get(AgentRun, result.run_id)
    assert stored_run.status == "drafting"  # FAILED 未落盘，不伪报已落盘
    reloaded = LegalAgentState.model_validate_json(stored_run.state_json)
    assert reloaded.verifier_research_returns == 0  # Ticket 2：无回喂 attempt，预算不动
    assert db.query(AgentStep).filter_by(agent_run_id=result.run_id, decision="coverage_rewrite_attempt").count() == 0
    assert db.query(AgentStep).filter_by(agent_run_id=result.run_id, decision="failure").count() == 0
    assert db.query(Message).filter_by(conversation_id=conversation.id, role="assistant").count() == 0
    assert stored_run.state_version == (winner_versions[0] if conflict else result.state_version)
    if conflict:
        assert result.state_version + 1 == stored_run.state_version
    records = [record for record in caplog.records if record.getMessage() == "agent_failure_persistence_failed"]
    assert len(records) == 1
    logged = _JsonFormatter().format(records[0])
    assert "UNKNOWN_EVIDENCE_ID" in logged
    assert "WRITER:" in logged
    assert expected in logged
    assert "secret-database-credentials" not in logged


@pytest.mark.parametrize("feedback_first", [False, True])
def test_planner_transport_error_is_not_retried_as_bad_output(db, feedback_first):
    from agent.service import execute_agent_request

    class UnavailablePlanner(_SerialWriterTransport):
        def invoke(self, messages):
            if "Planner" in messages[0].content:
                self.calls.append(("planner", len(messages)))
                if feedback_first and sum(kind == "planner" for kind, _ in self.calls) == 1:
                    return SimpleNamespace(content='{"kind":"invalid-decision"}')
                raise TimeoutError("secret-provider-details")
            return super().invoke(messages)

    def no_laws(_context, args):
        return {
            "kind": "retrieve_laws",
            "statement": "未命中依据",
            "evidence": [],
            "retrieval": {"query": args.query, "requested_k": 4, "returned_count": 0},
        }

    user, conversation = _owner_conversation(db)
    transport = UnavailablePlanner(_two_issue_payload())
    result = execute_agent_request(
        db=db,
        user_id=user.id,
        settings=_settings(),
        bootstrap=_two_issue_bootstrap(conversation.id),
        finalizer=_finalize,
        llm=transport,
        gateway=ToolGateway(wrapper_overrides={"retrieve_laws": no_laws}),
    )
    assert sum(kind == "planner" for kind, _ in transport.calls) == (2 if feedback_first else 1)
    assert result.reason_code == "AGENT_EXECUTION_FAILURE"
    stored = db.get(AgentRun, result.run_id)
    assert stored.status == "failed"
    assert stored.last_error_code == "AGENT_EXECUTION_FAILURE"
    assert result.state_version == stored.state_version
    assert db.query(Message).filter_by(conversation_id=conversation.id, role="assistant").count() == 0


def test_service_rejects_controller_snapshot_replaced_before_reload(db, monkeypatch):
    from agent.controller import AgentController
    from agent.repository import compare_and_save, load_owned_run
    from agent.service import execute_agent_request

    real_run = AgentController.run
    winner_json = []

    def run_then_advance(self, run_id, bootstrap):
        original = real_run(self, run_id, bootstrap)
        saved = load_owned_run(db, run_id=run_id, user_id=user.id, conversation_id=conversation.id)
        winner = original.state.model_copy(update={"verifier_research_returns": 1})
        compare_and_save(db, run=saved, expected_version=saved.state_version, state=winner, status=winner.status.value)
        winner_json.append(winner.model_dump_json())
        return original

    monkeypatch.setattr(AgentController, "run", run_then_advance)
    user, conversation = _owner_conversation(db)
    transport = _SerialWriterTransport(_two_issue_payload(), mode="invalid_evidence_last")
    result = execute_agent_request(
        db=db,
        user_id=user.id,
        settings=_settings(),
        bootstrap=_two_issue_bootstrap(conversation.id),
        finalizer=_finalize,
        llm=transport,
        gateway=_TwoIssueLawGateway().as_gateway(),
    )
    assert result.reason_code == "AGENT_FINALIZATION_CONFLICT"
    stored = db.get(AgentRun, result.run_id)
    assert stored.state_json == winner_json[0]
    assert result.state_version == stored.state_version
    assert not any(kind.startswith("writer") for kind, _ in transport.calls)
    assert db.query(Message).filter_by(conversation_id=conversation.id, role="assistant").count() == 0


_MULTI_ISSUE_QUERY = "公司拖欠工资且未签合同，现在要解除劳动关系，能否主张补偿"
# 8 条供 8 争点回归用（每条都必须是 raw_query 的逐字片段）；前 4 条被既有 4 争点测试按索引使用。
_MULTI_ISSUE_QUOTES = [
    "公司拖欠工资",
    "未签合同",
    "解除劳动关系",
    "主张补偿",
    "现在要解除劳动关系",
    "公司拖欠工资且未签合同",
    "劳动关系",
    "能否主张补偿",
]


def _multi_issue_bootstrap(conversation_id: int) -> RequestBootstrap:
    return RequestBootstrap(
        conv_id=conversation_id,
        summary="",
        recent=[],
        recent_messages=[],
        image=None,
        user_text=_MULTI_ISSUE_QUERY,
        image_rel=None,
        thumb_rel=None,
        image_description="",
        raw_query=_MULTI_ISSUE_QUERY,
        supplement_text=_MULTI_ISSUE_QUERY,
        intent="legal_query",
        is_exam=False,
        has_options=False,
        contract_mode=False,
        contract_text=None,
        client_truncated=False,
    )


def _multi_issue_payload(n_issues: int) -> dict:
    """n 个 issue，每个都带 unknown_facts（fact.quote 必须是 raw_query 原文片段）。"""
    return {
        "issues": [
            {
                "question": f"争点{i}的法律依据是什么？",
                "facts": [{"quote": _MULTI_ISSUE_QUOTES[i]}],
                "unknown_facts": [{"statement": f"缺失事实{i}", "why_outcome_changes": f"影响争点{i}的结论"}],
            }
            for i in range(n_issues)
        ]
    }


class _MultiIssueTransport:
    """多 issue 假 transport：issue 分解返回 n 个 issue；planner 交确定性评估；draft 返回合法 claims。

    `planner_call_limit`：**护栏**（2026-09-10 自审补）。补检索若退化为无界重入，
    planner 会被反复调用——若不设上限，测试表现为**挂死**（实测 >300s 未返回、段错误），
    在 CI 里既慢又难定位。设上限后，无界循环必然撞上护栏 → 抛出带计数的断言错误，
    使测试**快速、带信息地变红**，而不是超时挂死。默认 50 远高于合法路径用量（实测 0）。
    """

    def __init__(self, n_issues: int, planner_call_limit: int = 50) -> None:
        self.issue_payload = _multi_issue_payload(n_issues)
        self.n_issues = n_issues
        self.planner_calls = 0  # 供终止性断言用（不得空转）
        self.planner_call_limit = planner_call_limit

    def invoke(self, messages):
        system = messages[0].content
        if "争点分解器" in system:
            return SimpleNamespace(content=json.dumps(self.issue_payload, ensure_ascii=False))
        if "Planner" in system:
            self.planner_calls += 1
            assert self.planner_calls <= self.planner_call_limit, (
                f"planner 被调用 {self.planner_calls} 次，超护栏 {self.planner_call_limit}"
                " —— 补检索疑似无界重入（不是挂死在超时里，是护栏主动报错）"
            )
            return SimpleNamespace(content=json.dumps({"kind": "finish_research", "summary": "交给确定性评估"}))
        # draft 渲染：为每个 issue 产出一条绑定其证据的 claim
        payload = json.loads(messages[1].content)
        claims = []
        for issue in payload["issues"]:
            evidence_ids = [e["evidence_id"] for e in issue.get("evidence", [])]
            if not evidence_ids:
                continue
            claims.append(
                {
                    "local_id": f"claim-{issue['issue_id'][:8]}",
                    "issue_id": issue["issue_id"],
                    "text": "依据《民法典》第675条处理。",
                    "evidence_ids": evidence_ids[:1],
                    "fact_ids": [],
                    "section": "conclusion",
                }
            )
        return SimpleNamespace(content=json.dumps({"claims": claims, "missing_information": []}, ensure_ascii=False))


def test_clarify_budget_exhaustion_must_not_skip_unretrieved_issues(db):
    """回归（2026-09-10 实测复现，对照线上 probe-15 C01 现场）：

    缺陷：扇出每轮只推进一步、被澄清 return 打断；而 `_handle_evaluation` 的
    CLARIFY_BUDGET_EXHAUSTED 分支无条件转 DRAFTING、**不检查是否还有 issue 从未检索**。
    当 issue 数 > 澄清预算 + 1 时，尾部 issue 必然漏检 → 进 DRAFTING 时无证据绑定 →
    verifier 判 EVIDENCE_COVERAGE_DEFICIENT → 回喂被拒 → agent 失败、用户拿到空终稿。

    正确行为：转入 DRAFTING 之前必须保证每个 issue 都至少有过一次成功检索
    （与 `_deterministic_finish_gate` 闸门 B 的 `_every_issue_has_evidence` 口径一致）。
    """
    from agent.controller import _DEFAULT_RUN_LOCKS, resume_with_user_fact
    from agent.service import execute_agent_request

    n_issues = 4  # > max_clarifications(2) + 1
    user = User(username="skip-issue-owner", password_hash="x")
    db.add(user)
    db.commit()
    conversation = Conversation(user_id=user.id, title="", summary="", message_count=1)
    db.add(conversation)
    db.commit()

    transport = _MultiIssueTransport(n_issues)
    gateway = _law_gateway()
    settings = SimpleNamespace(
        agent_max_steps=16,
        agent_max_tool_calls=10,
        agent_max_replans=3,
        agent_max_clarifications=2,
        agent_max_verifier_research_returns=1,
    )

    run_id: str | None = None
    version: int | None = None
    for turn in range(1, 9):
        if run_id is None:
            result = execute_agent_request(
                db=db,
                user_id=user.id,
                settings=settings,
                bootstrap=_multi_issue_bootstrap(conversation.id),
                finalizer=_finalize,
                llm=transport,
                gateway=gateway,
            )
        else:
            resumed = resume_with_user_fact(
                db=db,
                run_locks=_DEFAULT_RUN_LOCKS,
                run_id=run_id,
                expected_version=version,
                user_id=user.id,
                conversation_id=conversation.id,
                answer=f"事实补充：第{turn}轮",
            )
            version = resumed.new_state_version
            result = execute_agent_request(
                db=db,
                user_id=user.id,
                settings=settings,
                bootstrap=_multi_issue_bootstrap(conversation.id),
                finalizer=_finalize,
                llm=transport,
                gateway=gateway,
                run_id=run_id,  # 必须复用同一 run（真实服务端由 chat 接口传入）
            )
        if result.run_id:
            run_id = result.run_id
        if result.state_version is not None:
            version = result.state_version
        if result.outcome != "clarification":
            break

    run = db.get(AgentRun, run_id)
    state = LegalAgentState.model_validate_json(run.state_json)
    retrieved = {obs.issue_id for obs in state.observations if obs.status == "succeeded" and obs.evidence_ids}
    missing = [issue.issue_id for issue in state.issues if issue.issue_id not in retrieved]
    assert not missing, (
        f"转入 {state.status} 时仍有 issue 从未被检索：{missing}；"
        f"clarifications={state.clarifications}/{state.budgets.max_clarifications}"
    )


def test_five_issue_decomposition_reaches_drafting_within_step_budget(db):
    """回归（2026-09-12 真实付费运行复现：run numattr-q38-c01-20260912-01）：

    缺陷：planner 规划出 5 个争点时，澄清用满 2 轮后需 backfill 补 2 个争点。
    每次 backfill 占 1 个检查点、每次检索占 2 个，bootstrap 1 个、澄清 2×2 个
    → 1+8+4+2 = 15/16，第 5 个争点的检索发起时 steps=14，
    撞上 `controller.py:603` 的 `steps+3 > max_steps`（14+3=17>16）
    → `budget_exceeded:step_preflight` → stopped → 技术失败回落 Fast Path。
    **确定性发生，与模型无关**（这是第 4 轮付费运行的真实终态）。

    用户 2026-09-12 授权把 AGENT_MAX_STEPS 16→20（产品参数，非证据/校验红线；
    与 8→16 的先例同类——上一次也是因"澄清耗尽步数"获批上调）。
    本测试锁死：5 争点场景必须能走到起草并落盘终稿，不得再因步数提前停止。
    """
    from agent.controller import _DEFAULT_RUN_LOCKS, resume_with_user_fact
    from agent.service import execute_agent_request

    n_issues = 5
    user = User(username="five-issue-owner", password_hash="x")
    db.add(user)
    db.commit()
    conversation = Conversation(user_id=user.id, title="", summary="", message_count=1)
    db.add(conversation)
    db.commit()

    transport = _MultiIssueTransport(n_issues)
    gateway = _law_gateway()
    settings = SimpleNamespace(
        agent_max_steps=20,  # 用户 2026-09-12 授权值（原 16 对 5 争点必挂，见上）
        agent_max_tool_calls=10,
        agent_max_replans=3,
        agent_max_clarifications=2,
        agent_max_verifier_research_returns=1,
    )

    run_id: str | None = None
    version: int | None = None
    result = None
    for turn in range(1, 9):
        if run_id is None:
            result = execute_agent_request(
                db=db,
                user_id=user.id,
                settings=settings,
                bootstrap=_multi_issue_bootstrap(conversation.id),
                finalizer=_finalize,
                llm=transport,
                gateway=gateway,
            )
        else:
            resumed = resume_with_user_fact(
                db=db,
                run_locks=_DEFAULT_RUN_LOCKS,
                run_id=run_id,
                expected_version=version,
                user_id=user.id,
                conversation_id=conversation.id,
                answer=f"事实补充：第{turn}轮",
            )
            version = resumed.new_state_version
            result = execute_agent_request(
                db=db,
                user_id=user.id,
                settings=settings,
                bootstrap=_multi_issue_bootstrap(conversation.id),
                finalizer=_finalize,
                llm=transport,
                gateway=gateway,
                run_id=run_id,  # 必须复用同一 run（真实服务端由 chat 接口传入）
            )
        if result.run_id:
            run_id = result.run_id
        if result.state_version is not None:
            version = result.state_version
        if result.outcome != "clarification":
            break

    assert result is not None
    assert result.outcome != "failed" or result.reason_code != "AGENT_BUDGET_EXCEEDED", (
        "5 争点场景不得再因步数预算提前停止（这是本次上调 AGENT_MAX_STEPS 要消除的缺陷）"
    )
    run = db.get(AgentRun, run_id)
    state = LegalAgentState.model_validate_json(run.state_json)
    assert state.terminal_decision is None or "budget_exceeded" not in str(state.terminal_decision), (
        f"终态决策不得是预算耗尽：{state.terminal_decision}"
    )
    retrieved = {obs.issue_id for obs in state.observations if obs.status == "succeeded" and obs.evidence_ids}
    missing = [issue.issue_id for issue in state.issues if issue.issue_id not in retrieved]
    assert not missing, f"仍有 issue 从未被检索：{missing}"


def test_eight_issue_decomposition_batch_reaches_drafting_within_20(db):
    """T1b 真·批量检索目标（2026-09-12，批量已实现、本测试转绿）；Ticket 1 适配（同日）：

    8 争点现在会先触发范围选择澄清（ISSUE_SCOPE_SELECTION_REQUIRED，产品约束：一次
    运行最多处理 5 个）。本测试先以合法编号选择前 5 个，再验证批量检索的步数经济学：
    C-1b（逐争点扇出 + 暂缓澄清）实测 8 争点 19/20 步停、检索 6/8——每争点 3 步
    （EXECUTING+EVALUATING+转回 PLANNING）是状态机 `EVALUATING→仅PLANNING` 决定的结构性成本。
    真·批量检索：一个 EXECUTING 周期内连发全部未检索争点的 retrieve_laws、一次 EVALUATING
    收齐，步数与 N 解耦。

    依赖：产品网关 retrieve_laws `max_calls_per_run` 已 6→10（5 争点需 5 次检索，见
    tools/gateway.py _POLICIES）；本测试用产品默认值，不再 override。
    """
    from agent.controller import _DEFAULT_RUN_LOCKS, resume_with_user_fact
    from agent.service import execute_agent_request

    n_issues = 8
    user = User(username="batch-eight-owner", password_hash="x")
    db.add(user)
    db.commit()
    conversation = Conversation(user_id=user.id, title="", summary="", message_count=1)
    db.add(conversation)
    db.commit()

    transport = _MultiIssueTransport(n_issues)
    gateway = _law_gateway()
    settings = SimpleNamespace(
        agent_max_steps=20,
        agent_max_tool_calls=10,
        agent_max_replans=3,
        agent_max_clarifications=2,
        agent_max_verifier_research_returns=1,
    )

    run_id: str | None = None
    version: int | None = None
    result = None
    for turn in range(1, 9):
        if run_id is None:
            result = execute_agent_request(
                db=db,
                user_id=user.id,
                settings=settings,
                bootstrap=_multi_issue_bootstrap(conversation.id),
                finalizer=_finalize,
                llm=transport,
                gateway=gateway,
            )
        else:
            answer = (
                "1,2,3,4,5"  # 范围选择：确定性编号选择前 5 个（Ticket 1 新产品约束）
                if result.outcome == "clarification" and result.reason_code == "ISSUE_SCOPE_SELECTION_REQUIRED"
                else f"事实补充：第{turn}轮"
            )
            resumed = resume_with_user_fact(
                db=db,
                run_locks=_DEFAULT_RUN_LOCKS,
                run_id=run_id,
                expected_version=version,
                user_id=user.id,
                conversation_id=conversation.id,
                answer=answer,
            )
            version = resumed.new_state_version
            result = execute_agent_request(
                db=db,
                user_id=user.id,
                settings=settings,
                bootstrap=_multi_issue_bootstrap(conversation.id),
                finalizer=_finalize,
                llm=transport,
                gateway=gateway,
                run_id=run_id,  # 必须复用同一 run（真实服务端由 chat 接口传入）
            )
        if result.run_id:
            run_id = result.run_id
        if result.state_version is not None:
            version = result.state_version
        if result.outcome != "clarification":
            break

    assert result is not None
    run = db.get(AgentRun, run_id)
    state = LegalAgentState.model_validate_json(run.state_json)
    assert "budget_exceeded" not in str(state.terminal_decision), (
        f"8 争点批量检索后不得因步数预算停止（terminal_decision={state.terminal_decision}，"
        f"steps={state.steps}/{state.budgets.max_steps}）"
    )
    retrieved = {obs.issue_id for obs in state.observations if obs.status == "succeeded" and obs.evidence_ids}
    missing = [issue.issue_id for issue in state.issues if issue.issue_id not in retrieved]
    assert not missing, f"仍有 issue 从未被检索：{missing}"
    assert state.status in {AgentStatus.DRAFTING, AgentStatus.COMPLETED}, (
        f"8 争点批量检索后应抵达起草/完成：status={state.status}"
    )


def _all_empty_gateway():
    """所有检索一律返回空证据（含 planner 短查询）→ 每个 issue 永远拿不到证据。

    用于验证补检索的**终止性**：补齐动作不能因"永远没有证据"而无界重试。
    """

    def retrieve(_context, args):
        query = getattr(args, "query", None) or ""
        return {
            "kind": "retrieve_laws",
            "statement": "检索无有效法条依据。",
            "evidence": [],
            "retrieval": {"query": query, "requested_k": 4, "returned_count": 0},
        }

    return ToolGateway(wrapper_overrides={"retrieve_laws": retrieve})


def test_backfill_retrieval_terminates_when_retriever_returns_no_evidence(db):
    """回归（2026-09-10 边界自审，锁死终止性）：

    上一版补检索修复（以 `_every_issue_has_evidence` 为循环条件）在"检索器持续返回
    空命中"时**不收敛**：该函数恒为 False → `_handle_evaluation` 的 backfill 分支被
    无限重入 → 单轮实测 297 次 planner 调用、300 次评估，终态停在**非终态** planning，
    仅靠 step 预算被迫中断（把"快速确定性失败"劣化成"长时间空转 + 非终态"）。

    本测试锁死正确语义：每个缺证据 issue 都已**发起过**检索后，补检索必须让路，
    run 必须抵达**终态**且 planner 调用次数有界（不得空转）。
    """
    from agent.controller import _DEFAULT_RUN_LOCKS, resume_with_user_fact
    from agent.service import execute_agent_request

    n_issues = 4
    user = User(username="backfill-terminate-owner", password_hash="x")
    db.add(user)
    db.commit()
    conversation = Conversation(user_id=user.id, title="", summary="", message_count=1)
    db.add(conversation)
    db.commit()

    transport = _MultiIssueTransport(n_issues)
    settings = SimpleNamespace(
        # 预算 16→20（2026-09-12，C-1b）：扇出不再被澄清中途打断——空命中场景下 4 个 issue
        # 全部先检索完（每争点 3 步：EXECUTING+EVALUATING+暂缓转回 PLANNING）才进入澄清，
        # 步数经济学从"先澄清+backfill"变为"先扇出再澄清"，16 步不够（实测 turn3 恢复时
        # BudgetExceeded→ResumeRunConflict）。20 与产品当前默认一致；本测试锁的是**终止性
        # 不变式**（抵达终态、planner 有界、每 issue 已尝试），不锁 16 这个历史数值。
        agent_max_steps=20,
        agent_max_tool_calls=10,
        agent_max_replans=3,
        agent_max_clarifications=2,
        agent_max_verifier_research_returns=1,
    )

    run_id: str | None = None
    version: int | None = None
    for turn in range(1, 9):
        if run_id is None:
            result = execute_agent_request(
                db=db,
                user_id=user.id,
                settings=settings,
                bootstrap=_multi_issue_bootstrap(conversation.id),
                finalizer=_finalize,
                llm=transport,
                gateway=_all_empty_gateway(),
            )
        else:
            resumed = resume_with_user_fact(
                db=db,
                run_locks=_DEFAULT_RUN_LOCKS,
                run_id=run_id,
                expected_version=version,
                user_id=user.id,
                conversation_id=conversation.id,
                answer=f"事实补充：第{turn}轮",
            )
            version = resumed.new_state_version
            result = execute_agent_request(
                db=db,
                user_id=user.id,
                settings=settings,
                bootstrap=_multi_issue_bootstrap(conversation.id),
                finalizer=_finalize,
                llm=transport,
                gateway=_all_empty_gateway(),
                run_id=run_id,
            )
        if result.run_id:
            run_id = result.run_id
        if result.state_version is not None:
            version = result.state_version
        if result.outcome != "clarification":
            break

    run = db.get(AgentRun, run_id)
    state = LegalAgentState.model_validate_json(run.state_json)

    # 1) 必须抵达终态（不得停在 planning 这类"仍在推进"的状态）
    assert state.status in {
        AgentStatus.FAILED,
        AgentStatus.DRAFTING,
        AgentStatus.COMPLETED,
        AgentStatus.REFUSED,
        AgentStatus.STOPPED,
    }, f"补检索未收敛：终态停在非终态 {state.status}"

    # 2) planner 调用必须有界（每个 issue 至多补一次检索，不允许空转）
    assert transport.planner_calls <= n_issues + 1, (
        f"planner 被空转调用 {transport.planner_calls} 次（上限 {n_issues + 1}）—— 补检索存在无界重入"
    )

    # 3) 终止依据：每个 issue 都留下过 retrieve_laws 动作指纹（试过了，不是没试）
    from agent.state_machine import action_fingerprint
    from tools.contracts import RetrieveLawsInput

    for issue in state.issues:
        attempted = any(
            fp == action_fingerprint(issue.issue_id, "retrieve_laws", RetrieveLawsInput(query=issue.question, k=4))
            for fp in state.action_fingerprints
        )
        assert attempted, f"issue {issue.issue_id} 从未发起过检索，补检索提前放弃"
