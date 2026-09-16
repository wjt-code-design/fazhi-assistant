"""Task 10: privacy-safe Agent SSE projection contracts."""

from __future__ import annotations

import json

import pytest


def test_completed_agent_events_use_only_declared_types_and_hide_internal_payloads():
    from agent.chat_integration import AgentPublicResult, serialize_agent_events

    result = AgentPublicResult(
        outcome="completed",
        run_id="run-1",
        conversation_id=17,
        state_version=7,
        answer="有证据约束的结论。",
        reason_code="READY",
        coverage_status="full",
    )

    events = serialize_agent_events(result)

    assert [event["type"] for event in events] == [
        "agent_status",
        "verification",
        "token",
        "final",
    ]
    assert events[-1] == {
        "type": "final",
        "run_id": "run-1",
        "state_version": 7,
        "conversation_id": 17,
        "coverage_status": "full",
        "uncovered_issues": [],
    }
    serialized = json.dumps(events, ensure_ascii=False)
    for private in (
        "system_prompt",
        "planner_output",
        "tool_args",
        "state_json",
        "chain_of_thought",
        "why_outcome_changes",
    ):
        assert private not in serialized


def test_partial_final_event_carries_coverage_and_keeps_event_order():
    """T1（2026-09-16）：partial 终稿的 final 事件携带结构化覆盖；事件顺序与既有四段不变。"""
    from agent.chat_integration import AgentPublicResult, serialize_agent_events
    from agent.schemas import UncoveredIssue

    result = AgentPublicResult(
        outcome="completed",
        run_id="run-p",
        conversation_id=18,
        state_version=9,
        answer="已交付争点的结论。",
        reason_code="READY",
        coverage_status="partial",
        uncovered_issues=[UncoveredIssue(issue_id="issue-x", reason_code="UNKNOWN_EVIDENCE_ID")],
    )

    events = serialize_agent_events(result)

    assert [event["type"] for event in events] == ["agent_status", "verification", "token", "final"]
    # verification 仍为 PASS：它只表示"已交付 claims 通过校验"，覆盖由独立字段表达（A1/A3）
    assert events[1] == {"type": "verification", "verdict": "PASS"}
    assert events[-1] == {
        "type": "final",
        "run_id": "run-p",
        "state_version": 9,
        "conversation_id": 18,
        "coverage_status": "partial",
        "uncovered_issues": [{"issue_id": "issue-x", "reason_code": "UNKNOWN_EVIDENCE_ID"}],
    }


def test_coverage_contract_validation():
    """T1 覆盖契约校验：completed 必须显式带覆盖；full⇔空列表；partial⇔非空；非 completed 禁带。"""
    from pydantic import ValidationError

    from agent.chat_integration import AgentPublicResult
    from agent.schemas import UncoveredIssue

    # completed 缺覆盖 → 拒绝（不得静默推断 full）
    with pytest.raises(ValidationError):
        AgentPublicResult(
            outcome="completed",
            run_id="run-1",
            state_version=1,
            answer="结论。",
            reason_code="READY",
        )
    # full 但列表非空 → 拒绝
    with pytest.raises(ValidationError):
        AgentPublicResult(
            outcome="completed",
            run_id="run-1",
            state_version=1,
            answer="结论。",
            reason_code="READY",
            coverage_status="full",
            uncovered_issues=[UncoveredIssue(issue_id="i", reason_code="X")],
        )
    # partial 但列表为空 → 拒绝
    with pytest.raises(ValidationError):
        AgentPublicResult(
            outcome="completed",
            run_id="run-1",
            state_version=1,
            answer="结论。",
            reason_code="READY",
            coverage_status="partial",
        )
    # 非 completed 带覆盖 → 拒绝
    with pytest.raises(ValidationError):
        AgentPublicResult(
            outcome="clarification",
            run_id="run-2",
            state_version=1,
            prompt="补充事实？",
            issue_id="issue-a",
            reason_code="MISSING_FACT",
            coverage_status="full",
        )


def test_clarification_event_is_minimal_and_contains_no_evaluator_rationale():
    from agent.chat_integration import AgentPublicResult, serialize_agent_events

    events = serialize_agent_events(
        AgentPublicResult(
            outcome="clarification",
            run_id="run-2",
            conversation_id=17,
            state_version=3,
            prompt="是否约定还款日期？",
            issue_id="issue-a",
            reason_code="MISSING_FACT",
        )
    )

    assert [event["type"] for event in events] == ["agent_status", "clarification"]
    assert events[-1] == {
        "type": "clarification",
        "run_id": "run-2",
        "state_version": 3,
        "prompt": "是否约定还款日期？",
        "issue_id": "issue-a",
        "conversation_id": 17,
    }


@pytest.mark.parametrize("outcome", ["fallback", "failed"])
def test_non_final_outcomes_never_emit_token_or_final(outcome):
    from agent.chat_integration import AgentPublicResult, serialize_agent_events

    result = AgentPublicResult(
        outcome=outcome,
        run_id="run-3",
        state_version=2,
        reason_code="TOOL_TIMEOUT" if outcome == "fallback" else "PLANNER_POLICY_VIOLATION",
    )

    events = serialize_agent_events(result)

    assert not {"token", "final"}.intersection(event["type"] for event in events)
    serialized = json.dumps(events, ensure_ascii=False)
    assert "Traceback" not in serialized
    assert "planner_output" not in serialized.lower()


def test_sse_encoder_has_one_data_record_per_event_and_done_is_explicit():
    from agent.chat_integration import encode_sse_event, encode_sse_stream

    event = {"type": "agent_status", "status": "planning"}
    assert encode_sse_event(event) == 'data: {"type": "agent_status", "status": "planning"}\n\n'
    frames = list(encode_sse_stream([event]))
    assert frames == [encode_sse_event(event), "data: [DONE]\n\n"]
