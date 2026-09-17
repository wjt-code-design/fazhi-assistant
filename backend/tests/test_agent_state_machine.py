import json
from typing import Literal

import pytest
from pydantic import BaseModel

from agent.schemas import (
    AgentBudgets,
    AgentStatus,
    LegalAgentState,
    Observation,
    StopDecision,
)
from agent.state_machine import (
    BudgetExceeded,
    DuplicateAction,
    InvalidTransition,
    action_fingerprint,
    register_action,
    register_clarification,
    register_replan,
    transition,
)


class RetrieveLawsInput(BaseModel):
    query: str
    issue_id: str


def test_waiting_user_can_resume_only_to_planning():
    state = LegalAgentState(status=AgentStatus.WAITING_USER)

    assert transition(state, AgentStatus.PLANNING).status is AgentStatus.PLANNING

    with pytest.raises(InvalidTransition):
        transition(state, AgentStatus.DRAFTING)


def test_same_issue_same_tool_same_args_is_blocked():
    state = LegalAgentState()
    request = RetrieveLawsInput(query="时效", issue_id="issue-1")
    state = register_action(state, "issue-1", "retrieve_laws", request)

    with pytest.raises(DuplicateAction):
        register_action(state, "issue-1", "retrieve_laws", request)


def test_action_fingerprint_is_independent_of_argument_order():
    class OrderedInput(BaseModel):
        first: str
        second: int

    class ReorderedInput(BaseModel):
        second: int
        first: str

    assert action_fingerprint("issue-1", "lookup", OrderedInput(first="a", second=1)) == action_fingerprint(
        "issue-1", "lookup", ReorderedInput(second=1, first="a")
    )


@pytest.mark.parametrize(
    ("operation", "budget", "expected_counter"),
    [
        ("transition", AgentBudgets(max_steps=0), "steps"),
        ("action", AgentBudgets(max_tool_calls=0), "tool_calls"),
        ("replan", AgentBudgets(max_replans=0), "replans"),
        ("clarification", AgentBudgets(max_clarifications=0), "clarifications"),
    ],
)
def test_each_configured_budget_exhaustion_is_a_safe_terminal_decision(
    operation: Literal["transition", "action", "replan", "clarification"],
    budget: AgentBudgets,
    expected_counter: str,
):
    state = LegalAgentState(budgets=budget)

    with pytest.raises(BudgetExceeded) as caught:
        if operation == "transition":
            transition(state, AgentStatus.PLANNING)
        elif operation == "action":
            register_action(state, "issue-1", "retrieve_laws", RetrieveLawsInput(query="时效", issue_id="issue-1"))
        elif operation == "replan":
            register_replan(state)
        else:
            register_clarification(state)

    assert isinstance(caught.value.decision, StopDecision)
    assert caught.value.decision.reason == f"budget_exceeded:{expected_counter}"
    assert caught.value.state.status is AgentStatus.STOPPED


def test_duplicate_attempt_budget_is_scoped_per_issue():
    state = LegalAgentState(budgets=AgentBudgets(max_duplicate_attempts_per_issue=0))
    request = RetrieveLawsInput(query="时效", issue_id="issue-1")
    state = register_action(state, "issue-1", "retrieve_laws", request)

    with pytest.raises(BudgetExceeded) as caught:
        register_action(state, "issue-1", "retrieve_laws", request)

    assert caught.value.decision.reason == "budget_exceeded:duplicate_attempts:issue-1"
    assert caught.value.state.duplicate_attempts_by_issue == {"issue-1": 1}


def test_duplicate_action_exposes_updated_state_until_per_issue_limit_is_exhausted():
    state = LegalAgentState(budgets=AgentBudgets(max_duplicate_attempts_per_issue=2))
    request = RetrieveLawsInput(query="时效", issue_id="issue-1")
    state = register_action(state, "issue-1", "retrieve_laws", request)

    for expected_attempts in (1, 2):
        with pytest.raises(DuplicateAction) as caught:
            register_action(state, "issue-1", "retrieve_laws", request)
        state = caught.value.state
        assert state.duplicate_attempts_by_issue == {"issue-1": expected_attempts}

    with pytest.raises(BudgetExceeded) as caught:
        register_action(state, "issue-1", "retrieve_laws", request)

    assert caught.value.state.duplicate_attempts_by_issue == {"issue-1": 3}


def test_plan_decisions_are_discriminated_and_tool_calls_keep_typed_args():
    from agent.schemas import ToolCallDecision

    decision = ToolCallDecision(
        kind="tool_call",
        issue_id="issue-1",
        tool_name="retrieve_laws",
        args=RetrieveLawsInput(query="时效", issue_id="issue-1"),
    )

    assert decision.args.query == "时效"
    assert decision.model_dump(mode="json")["args"] == {"query": "时效", "issue_id": "issue-1"}


def test_legacy_evidence_observation_shape_remains_state_compatible():
    observation = Observation(
        issue_id="issue-1",
        statement="该事实由证据支持",
        evidence_ids=["evidence-1"],
        confidence=0.8,
    )

    restored = LegalAgentState.model_validate_json(
        LegalAgentState(observations=[observation]).model_dump_json()
    ).observations[0]

    assert restored == observation
    assert restored.tool_name is None
    assert restored.output is None


@pytest.mark.parametrize(
    "invalid_payload",
    [
        {
            "issue_id": "issue-1",
            "statement": "missing output",
            "tool_name": "retrieve_laws",
            "status": "succeeded",
        },
        {
            "issue_id": "issue-1",
            "statement": "missing error",
            "tool_name": "retrieve_laws",
            "status": "failed",
        },
        {
            "issue_id": "issue-1",
            "statement": "failed with output",
            "tool_name": "retrieve_laws",
            "status": "failed",
            "error_code": "TOOL_TIMEOUT",
            "output": {
                "kind": "retrieve_laws",
                "statement": "late",
                "evidence": [],
                "retrieval": None,
            },
        },
        {
            "issue_id": "issue-1",
            "statement": "success with error",
            "tool_name": "retrieve_laws",
            "status": "succeeded",
            "error_code": "TOOL_TIMEOUT",
            "output": {
                "kind": "retrieve_laws",
                "statement": "ok",
                "evidence": [],
                "retrieval": None,
            },
        },
        {
            "issue_id": "issue-1",
            "statement": "mismatched output",
            "tool_name": "lookup_article",
            "status": "succeeded",
            "output": {
                "kind": "retrieve_laws",
                "statement": "wrong tool",
                "evidence": [],
                "retrieval": None,
            },
        },
        {
            "issue_id": "issue-1",
            "statement": "tool output without tool name",
            "confidence": 0.8,
            "output": {
                "kind": "retrieve_laws",
                "statement": "orphan",
                "evidence": [],
                "retrieval": None,
            },
        },
        {
            "issue_id": "issue-1",
            "statement": "tool error without tool name",
            "confidence": 0.8,
            "status": "failed",
            "error_code": "TOOL_TIMEOUT",
        },
        {
            "issue_id": "issue-1",
            "statement": "legacy evidence lacks confidence",
        },
        {
            "issue_id": "issue-1",
            "statement": "tool observation fabricates confidence",
            "confidence": 0.5,
            "tool_name": "retrieve_laws",
            "status": "succeeded",
            "output": {
                "kind": "retrieve_laws",
                "statement": "ok",
                "evidence": [],
                "retrieval": None,
            },
        },
    ],
)
def test_observation_rejects_cross_field_invariants_from_python_and_json(invalid_payload):
    with pytest.raises(ValueError):
        Observation.model_validate(invalid_payload)
    with pytest.raises(ValueError):
        Observation.model_validate_json(json.dumps(invalid_payload, ensure_ascii=False))
