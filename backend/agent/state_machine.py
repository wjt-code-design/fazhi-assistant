"""Deterministic state transitions and per-run action budgets."""

from __future__ import annotations

import hashlib
import json

from pydantic import BaseModel

from .schemas import AgentStatus, LegalAgentState, StopDecision

ALLOWED: dict[AgentStatus, set[AgentStatus]] = {
    AgentStatus.BOOTSTRAPPING: {AgentStatus.PLANNING, AgentStatus.FAILED, AgentStatus.REFUSED},
    AgentStatus.PLANNING: {AgentStatus.EXECUTING, AgentStatus.WAITING_USER, AgentStatus.DRAFTING, AgentStatus.FAILED},
    AgentStatus.EXECUTING: {AgentStatus.EVALUATING, AgentStatus.FAILED},
    AgentStatus.EVALUATING: {AgentStatus.PLANNING, AgentStatus.WAITING_USER, AgentStatus.DRAFTING, AgentStatus.FAILED},
    AgentStatus.WAITING_USER: {AgentStatus.PLANNING, AgentStatus.FAILED, AgentStatus.REFUSED},
    AgentStatus.DRAFTING: {AgentStatus.COMPLETED, AgentStatus.WAITING_USER, AgentStatus.FAILED},
}


class InvalidTransition(ValueError):
    pass


class DuplicateAction(ValueError):
    """A duplicate request whose incremented per-issue state must be persisted."""

    def __init__(self, state: LegalAgentState, issue_id: str, tool_name: str) -> None:
        self.state = state
        super().__init__(f"duplicate action for issue {issue_id}: {tool_name}")


class BudgetExceeded(RuntimeError):
    def __init__(self, state: LegalAgentState, reason: str) -> None:
        self.decision = StopDecision(reason=f"budget_exceeded:{reason}")
        self.state = state.model_copy(
            update={"status": AgentStatus.STOPPED, "terminal_decision": self.decision}
        )
        super().__init__(self.decision.reason)


def action_fingerprint(issue_id: str, tool_name: str, args: BaseModel) -> str:
    canonical = json.dumps(args.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(f"{issue_id}|{tool_name}|{canonical}".encode()).hexdigest()


def _limit(state: LegalAgentState, counter: str, attempted_value: int, maximum: int) -> None:
    if attempted_value > maximum:
        raise BudgetExceeded(state.model_copy(update={counter: attempted_value}), counter)


def transition(state: LegalAgentState, target: AgentStatus) -> LegalAgentState:
    if target not in ALLOWED.get(state.status, set()):
        raise InvalidTransition(f"cannot transition from {state.status.value} to {target.value}")
    next_steps = state.steps + 1
    _limit(state, "steps", next_steps, state.budgets.max_steps)
    return state.model_copy(update={"status": target, "steps": next_steps})


def register_action(state: LegalAgentState, issue_id: str, tool_name: str, args: BaseModel) -> LegalAgentState:
    fingerprint = action_fingerprint(issue_id, tool_name, args)
    if fingerprint in state.action_fingerprints:
        attempts = state.duplicate_attempts_by_issue.get(issue_id, 0) + 1
        attempted_state = state.model_copy(
            update={"duplicate_attempts_by_issue": {**state.duplicate_attempts_by_issue, issue_id: attempts}}
        )
        if attempts > state.budgets.max_duplicate_attempts_per_issue:
            raise BudgetExceeded(attempted_state, f"duplicate_attempts:{issue_id}")
        raise DuplicateAction(attempted_state, issue_id, tool_name)

    next_tool_calls = state.tool_calls + 1
    _limit(state, "tool_calls", next_tool_calls, state.budgets.max_tool_calls)
    return state.model_copy(
        update={
            "tool_calls": next_tool_calls,
            "action_fingerprints": state.action_fingerprints | {fingerprint},
        }
    )


def register_replan(state: LegalAgentState) -> LegalAgentState:
    next_replans = state.replans + 1
    _limit(state, "replans", next_replans, state.budgets.max_replans)
    return state.model_copy(update={"replans": next_replans})


def register_clarification(state: LegalAgentState) -> LegalAgentState:
    next_clarifications = state.clarifications + 1
    _limit(state, "clarifications", next_clarifications, state.budgets.max_clarifications)
    return state.model_copy(update={"clarifications": next_clarifications})
