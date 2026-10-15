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


# 不计步的"记账边"（DB-15 / 报告 B-01+B-47）：**扩集合是一次产品决定**，
# 判据只有一条——该边是否发起模型或工具调用。加了边就等于加了预算，等于削弱防循环上界，
# 所以这里逐条注明各自的替代上界在哪。`tests/test_agent_budget_terminal_edges.py` 钉住本集合。
FREE_STEP_EDGES: frozenset[tuple[AgentStatus, AgentStatus]] = frozenset(
    {
        # 落库终稿：COMPLETED 无出边（见 ALLOWED），只会发生一次，无需预算约束。
        (AgentStatus.DRAFTING, AgentStatus.COMPLETED),
        # 接受用户对自己追问的回答：轮数由 register_clarification / max_clarifications 单独封顶。
        (AgentStatus.WAITING_USER, AgentStatus.PLANNING),
    }
)


class DuplicateAction(ValueError):
    """A duplicate request whose incremented per-issue state must be persisted."""

    def __init__(self, state: LegalAgentState, issue_id: str, tool_name: str) -> None:
        self.state = state
        super().__init__(f"duplicate action for issue {issue_id}: {tool_name}")


class BudgetExceeded(RuntimeError):
    def __init__(self, state: LegalAgentState, reason: str) -> None:
        self.decision = StopDecision(reason=f"budget_exceeded:{reason}")
        self.state = state.model_copy(update={"status": AgentStatus.STOPPED, "terminal_decision": self.decision})
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
    # DB-15（2026-10-09，审查报告 B-01/B-47）：两条"不发起任何模型/工具调用"的记账边不计步。
    # 改前每条边都 +1，而 `steps + 3 > max_steps` 那两处预检只挡**工具**路径，挡不住 1 步边
    # ⇒ 状态可以合法地停在 `steps == max_steps` 上，此后
    #   ① DRAFTING→COMPLETED：已 PASS 校验的终稿在落库瞬间被自己的预算炸掉（B-01，实测四腿）；
    #   ② WAITING_USER→PLANNING：用户对追问的回答被拒（409），该 run **永久不可恢复**（B-47，真数据 16/47）。
    # 免计费不等于不设界：越界仍由 `_limit` fail-closed；而这两条边各自的循环上界另有真源——
    # 澄清轮数由 `register_clarification`/`max_clarifications` 钉，终稿只发生一次（COMPLETED 无出边）。
    charge = 0 if (state.status, target) in FREE_STEP_EDGES else 1
    next_steps = state.steps + charge
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
