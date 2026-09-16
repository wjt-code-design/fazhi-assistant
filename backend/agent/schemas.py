"""Typed, serialisable state contracts for legal-agent execution."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    NonNegativeFloat,
    NonNegativeInt,
    SerializeAsAny,
    model_validator,
)

from tools.contracts import ToolName, ToolOutput


class AgentStatus(StrEnum):
    BOOTSTRAPPING = "bootstrapping"
    PLANNING = "planning"
    EXECUTING = "executing"
    EVALUATING = "evaluating"
    WAITING_USER = "waiting_user"
    DRAFTING = "drafting"
    COMPLETED = "completed"
    FAILED = "failed"
    REFUSED = "refused"
    STOPPED = "stopped"


class SourceType(StrEnum):
    USER = "user"
    DOCUMENT = "document"
    STATUTE = "statute"
    CASE = "case"
    TOOL = "tool"
    INFERENCE = "inference"


class LegalValidity(StrEnum):
    EFFECTIVE = "effective"
    SUPERSEDED = "superseded"
    UNKNOWN = "unknown"


class Fact(BaseModel):
    statement: str = Field(min_length=1)
    source: SourceType
    source_ref: str = Field(min_length=1)
    confidence: NonNegativeFloat = Field(le=1)


class UnknownFact(BaseModel):
    statement: str = Field(min_length=1)
    why_outcome_changes: str = Field(min_length=1)


class LegalIssue(BaseModel):
    issue_id: str = Field(min_length=1)
    question: str = Field(min_length=1)
    facts: list[Fact] = Field(default_factory=list)
    unknown_facts: list[UnknownFact] = Field(default_factory=list)


class UncoveredIssue(BaseModel):
    """争点级部分交付（T1，2026-09-16）：completed 终稿未覆盖的争点。

    只含标识与原因码（公开契约的一部分，随 SSE final 事件与历史会话投影出），
    不含异常文本、prompt 或证据原文。
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    issue_id: str = Field(min_length=1)
    reason_code: str = Field(min_length=1)


class Evidence(BaseModel):
    """A frozen citation record, preserving the exact source acquired by a tool."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    evidence_id: str = Field(min_length=1)
    source_id: str = Field(min_length=1)
    source_ref: str = Field(min_length=1)
    source_type: SourceType
    snippet: str = Field(min_length=1)
    legal_validity: LegalValidity
    acquired_at: datetime


class EvidenceConflict(BaseModel):
    """A deterministic conflict edge between canonical evidence records."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    conflict_id: str = Field(min_length=1)
    issue_id: str = Field(min_length=1)
    evidence_ids: tuple[str, ...] = Field(min_length=1)
    critical: bool
    resolved: bool


class Observation(BaseModel):
    """Canonical evidence/tool observation persisted directly in LegalAgentState."""

    model_config = ConfigDict(extra="forbid")

    issue_id: str = Field(min_length=1)
    statement: str = Field(min_length=1)
    evidence_ids: list[str] = Field(default_factory=list)
    confidence: NonNegativeFloat | None = Field(default=None, le=1)
    tool_name: ToolName | None = None
    status: Literal["succeeded", "failed"] = "succeeded"
    output: ToolOutput | None = None
    error_code: (
        Literal[
            "TOOL_TIMEOUT",
            "TOOL_EXECUTION_ERROR",
            "TOOL_CALL_LIMIT_EXCEEDED",
            "TOOL_BUSY",
        ]
        | None
    ) = None
    duration_ms: NonNegativeInt = 0

    @model_validator(mode="after")
    def validate_observation_shape(self) -> Observation:
        if self.tool_name is None:
            if self.confidence is None:
                raise ValueError("evidence observations require confidence")
            if self.output is not None or self.error_code is not None or self.status != "succeeded":
                raise ValueError("evidence observations cannot contain tool result fields")
            if self.duration_ms != 0:
                raise ValueError("evidence observations cannot contain tool duration")
            return self

        if self.confidence is not None:
            raise ValueError("tool observations cannot claim unverified confidence")
        if self.status == "succeeded":
            if self.output is None:
                raise ValueError("successful tool observations require output")
            if self.error_code is not None:
                raise ValueError("successful tool observations cannot contain an error code")
            if self.output.kind != self.tool_name:
                raise ValueError("tool observation output kind must match tool_name")
            return self

        if self.output is not None:
            raise ValueError("failed tool observations cannot contain output")
        if self.error_code is None:
            raise ValueError("failed tool observations require an error code")
        return self


class ToolCallDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["tool_call"] = "tool_call"
    issue_id: str = Field(min_length=1)
    tool_name: str = Field(min_length=1)
    args: SerializeAsAny[BaseModel]


class AskUserDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["ask_user"] = "ask_user"
    question: str = Field(min_length=1)
    unknown_fact: UnknownFact | None = None


class FinishResearchDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["finish_research"] = "finish_research"
    summary: str = Field(min_length=1)


class ReplanDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["replan"] = "replan"
    reason: str = Field(min_length=1)


class StopDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["stop"] = "stop"
    reason: str = Field(min_length=1)


PlanDecision = Annotated[
    ToolCallDecision | AskUserDecision | FinishResearchDecision | ReplanDecision | StopDecision,
    Field(discriminator="kind"),
]


class ClaimCheck(BaseModel):
    claim: str = Field(min_length=1)
    supported: bool
    evidence_ids: list[str] = Field(default_factory=list)
    rationale: str = Field(min_length=1)


class AgentBudgets(BaseModel):
    # 默认值为测试/兜底用；生产由 build_agent_runtime 从 settings 注入（max_steps=20 等）。
    max_steps: NonNegativeInt = 24
    max_tool_calls: NonNegativeInt = 12
    max_replans: NonNegativeInt = 4
    max_clarifications: NonNegativeInt = 3
    max_duplicate_attempts_per_issue: NonNegativeInt = 2
    max_verifier_research_returns: NonNegativeInt = 1


# 争点分解上限的单一数字源（与 runtime 分解器 1–8 上限一致；范围选择以此为界）。
MAX_ISSUES = 8


class LegalAgentState(BaseModel):
    status: AgentStatus = AgentStatus.BOOTSTRAPPING
    budgets: AgentBudgets = Field(default_factory=AgentBudgets)
    steps: NonNegativeInt = 0
    tool_calls: NonNegativeInt = 0
    replans: NonNegativeInt = 0
    clarifications: NonNegativeInt = 0
    verifier_research_returns: NonNegativeInt = 0
    duplicate_attempts_by_issue: dict[str, NonNegativeInt] = Field(default_factory=dict)
    action_fingerprints: set[str] = Field(default_factory=set)
    issues: list[LegalIssue] = Field(default_factory=list)
    # Ticket 1（2026-09-12）：6–8 争点时的范围选择待决状态——仅保存待选择的既有 issue_id，
    # 非空表示等待用户确定性编号选择；合法选择后清空并按原顺序裁剪 issues。
    pending_scope_issue_ids: list[str] = Field(default_factory=list, max_length=MAX_ISSUES)
    # T1（2026-09-16）：争点级部分交付——completed 终稿未覆盖的争点（覆盖信息事实源）。
    # 空 = full；非空 = partial。写入时机：service 在终稿持久化前把局部 uncovered 落入 state，
    # 由 CAS 保存进 run.state_json；历史消息经 Message.agent_run_id 关联读取（旧消息无关联 → unknown）。
    uncovered_issues: list[UncoveredIssue] = Field(default_factory=list, max_length=MAX_ISSUES)
    observations: list[Observation] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    conflicts: list[EvidenceConflict] = Field(default_factory=list)
    claim_checks: list[ClaimCheck] = Field(default_factory=list)
    terminal_decision: StopDecision | None = None

    @model_validator(mode="after")
    def validate_pending_scope_issue_ids(self) -> LegalAgentState:
        if self.pending_scope_issue_ids:
            if len(set(self.pending_scope_issue_ids)) != len(self.pending_scope_issue_ids):
                raise ValueError("pending_scope_issue_ids must be unique")
            known = {issue.issue_id for issue in self.issues}
            if not set(self.pending_scope_issue_ids) <= known:
                raise ValueError("pending_scope_issue_ids must reference existing issues")
        if self.uncovered_issues:
            uncovered_ids = [u.issue_id for u in self.uncovered_issues]
            if len(set(uncovered_ids)) != len(uncovered_ids):
                raise ValueError("uncovered_issues must be unique")
            known = {issue.issue_id for issue in self.issues}
            if not set(uncovered_ids) <= known:
                raise ValueError("uncovered_issues must reference existing issues")
        return self
