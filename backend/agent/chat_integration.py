"""Public SSE projection and atomic final storage for Legal Agent chat.

This module is deliberately independent from ``main.py``. It accepts only
already-normalized Agent results, exposes an allowlisted public event schema,
and owns the compare-and-set that makes final assistant storage idempotent.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import case, func

from models import AgentClaimCheck, AgentRun, AgentStep, Conversation, Message

from .schemas import AgentStatus, ClaimCheck, LegalAgentState, UncoveredIssue
from .state_machine import InvalidTransition, transition
from .verifier import VerificationResult, VerificationVerdict

AgentOutcome = Literal["completed", "clarification", "fallback", "failed"]
CoverageStatus = Literal["full", "partial"]
# 覆盖投影的全量状态域：历史投影（coverage_from_state_json）对 T1 之前的 run 返回
# "unknown"（不得推断 full），比实时结果的 CoverageStatus 多一个状态。
CoverageProjection = Literal["full", "partial", "unknown"]


class AgentFinalizationConflict(RuntimeError):
    """The requested final write is unsafe, foreign, stale, or inconsistent."""


class AgentPublicResult(BaseModel):
    """Minimal application result from which public SSE events are projected."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    outcome: AgentOutcome
    run_id: str | None = Field(default=None, min_length=1)
    conversation_id: int | None = Field(default=None, ge=1)
    state_version: int = Field(ge=0)
    reason_code: str = Field(min_length=1)
    answer: str | None = None
    prompt: str | None = None
    issue_id: str | None = None
    # T1（2026-09-16）：覆盖契约——completed 必须显式携带（full⇔空列表、partial⇔非空）；
    # 其余 outcome 禁止携带。verification=PASS 只表示已交付 claims 通过校验，
    # 覆盖情况由本字段独立表达，不得把 partial 改判为 verification FAIL。
    coverage_status: CoverageStatus | None = None
    uncovered_issues: list[UncoveredIssue] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_outcome_fields(self) -> AgentPublicResult:
        if self.outcome == "completed" and not (self.run_id and self.answer and self.answer.strip()):
            raise ValueError("completed Agent result requires a run and answer")
        if self.outcome == "clarification" and not (
            self.run_id and self.prompt and self.prompt.strip() and self.issue_id and self.issue_id.strip()
        ):
            raise ValueError("clarification Agent result requires prompt and issue_id")
        if self.outcome != "completed" and self.answer is not None:
            raise ValueError("only completed Agent results may contain an answer")
        if self.outcome != "clarification" and (self.prompt is not None or self.issue_id is not None):
            raise ValueError("only clarification Agent results may contain clarification fields")
        if self.outcome == "completed":
            if self.coverage_status is None:
                raise ValueError("completed Agent result requires explicit coverage_status")
            if self.coverage_status == "full" and self.uncovered_issues:
                raise ValueError("full coverage requires an empty uncovered_issues list")
            if self.coverage_status == "partial" and not self.uncovered_issues:
                raise ValueError("partial coverage requires a non-empty uncovered_issues list")
        elif self.coverage_status is not None or self.uncovered_issues:
            raise ValueError("only completed Agent results may carry coverage information")
        return self


def serialize_agent_events(result: AgentPublicResult) -> list[dict[str, object]]:
    """Project a result to declared, privacy-safe Agent SSE events."""

    if result.outcome == "completed":
        assert result.answer is not None and result.run_id is not None
        assert result.coverage_status is not None
        return [
            {"type": "agent_status", "status": "completed"},
            {"type": "verification", "verdict": "PASS"},
            {"type": "token", "content": result.answer},
            {
                "type": "final",
                "run_id": result.run_id,
                "state_version": result.state_version,
                "coverage_status": result.coverage_status,
                "uncovered_issues": [u.model_dump() for u in result.uncovered_issues],
                **({"conversation_id": result.conversation_id} if result.conversation_id is not None else {}),
            },
        ]
    if result.outcome == "clarification":
        assert result.run_id is not None and result.prompt is not None and result.issue_id is not None
        return [
            {"type": "agent_status", "status": "waiting_user"},
            {
                "type": "clarification",
                "run_id": result.run_id,
                "state_version": result.state_version,
                "prompt": result.prompt,
                "issue_id": result.issue_id,
                **({"conversation_id": result.conversation_id} if result.conversation_id is not None else {}),
            },
        ]
    if result.outcome == "fallback":
        return [
            {"type": "agent_status", "status": "degraded"},
            {"type": "restart", "reason_code": result.reason_code},
        ]
    return [
        {"type": "agent_status", "status": "failed"},
        {
            "type": "error",
            "code": result.reason_code,
            "message": "Agent 无法安全完成本次请求。",
        },
    ]


def encode_sse_event(event: dict[str, object]) -> str:
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


def encode_sse_stream(events: list[dict[str, object]]):
    for event in events:
        yield encode_sse_event(event)
    yield "data: [DONE]\n\n"


def _answer_digest(answer: str) -> str:
    return hashlib.sha256(answer.encode("utf-8")).hexdigest()


def _already_finalized(
    db,
    *,
    run_id: str,
    expected_version: int,
    answer_digest: str,
) -> bool:
    db.expire_all()
    run = db.get(AgentRun, run_id)
    if run is None or run.status != AgentStatus.COMPLETED.value:
        return False
    checkpoint = (
        db.query(AgentStep)
        .filter(
            AgentStep.agent_run_id == run_id,
            AgentStep.state_version == expected_version + 1,
            AgentStep.decision == "finalize",
            AgentStep.result_summary == answer_digest,
        )
        .one_or_none()
    )
    return checkpoint is not None


def persist_agent_final_once(
    db,
    *,
    user_id: int,
    conversation_id: int,
    run_id: str,
    expected_version: int,
    state: LegalAgentState,
    answer: str,
    verification: VerificationResult,
) -> bool:
    """Atomically complete a run, persist ClaimChecks, and write one assistant Message.

    Returns ``True`` for the winning write and ``False`` for an exact idempotent
    replay. Any foreign, stale, or mismatched replay raises rather than guessing.
    """

    normalized_answer = answer.strip()
    if not normalized_answer or state.status is not AgentStatus.DRAFTING:
        raise AgentFinalizationConflict("Agent finalization requires a non-empty DRAFTING result")
    if verification.verdict is not VerificationVerdict.PASS or not verification.claim_checks:
        raise AgentFinalizationConflict("Agent finalization requires a bound PASS verification")

    answer_digest = _answer_digest(normalized_answer)
    run = (
        db.query(AgentRun)
        .filter(
            AgentRun.id == run_id,
            AgentRun.user_id == user_id,
            AgentRun.conversation_id == conversation_id,
        )
        .one_or_none()
    )
    if run is None:
        raise AgentFinalizationConflict("Agent run is not owned by the authenticated request")
    if run.state_version != expected_version or run.status != AgentStatus.DRAFTING.value:
        if _already_finalized(
            db,
            run_id=run_id,
            expected_version=expected_version,
            answer_digest=answer_digest,
        ):
            return False
        raise AgentFinalizationConflict("Agent run changed before finalization")
    try:
        persisted_state = LegalAgentState.model_validate_json(run.state_json)
    except ValueError as exc:
        raise AgentFinalizationConflict("Persisted Agent state is invalid") from exc
    if persisted_state != state:
        raise AgentFinalizationConflict("Finalization state does not match the durable checkpoint")

    claim_checks = [
        ClaimCheck(
            claim=check.claim,
            supported=check.supported,
            evidence_ids=list(check.evidence_ids),
            rationale=check.rationale,
        )
        for check in verification.claim_checks
    ]
    try:
        completed = transition(
            state.model_copy(update={"claim_checks": claim_checks}, deep=True),
            AgentStatus.COMPLETED,
        )
    except InvalidTransition as exc:
        raise AgentFinalizationConflict("Agent state cannot be completed") from exc

    try:
        updated = (
            db.query(AgentRun)
            .filter(
                AgentRun.id == run_id,
                AgentRun.user_id == user_id,
                AgentRun.conversation_id == conversation_id,
                AgentRun.state_version == expected_version,
                AgentRun.status == AgentStatus.DRAFTING.value,
            )
            .update(
                {
                    "state_json": completed.model_dump_json(),
                    "status": AgentStatus.COMPLETED.value,
                    "state_version": expected_version + 1,
                    "pending_question": None,
                    "degraded_reason": None,
                    "last_error_code": None,
                    "updated_at": datetime.utcnow(),
                },
                synchronize_session=False,
            )
        )
        if updated != 1:
            db.rollback()
            if _already_finalized(
                db,
                run_id=run_id,
                expected_version=expected_version,
                answer_digest=answer_digest,
            ):
                return False
            raise AgentFinalizationConflict("Concurrent Agent finalization conflict")

        updated_conversation = (
            db.query(Conversation)
            .filter(Conversation.id == conversation_id, Conversation.user_id == user_id)
            .update(
                {
                    Conversation.message_count: func.coalesce(Conversation.message_count, 0) + 1,
                    Conversation.last_active_at: datetime.utcnow(),
                    Conversation.answer: case(
                        (
                            func.coalesce(Conversation.answer, "") == "",
                            normalized_answer[:2000],
                        ),
                        else_=Conversation.answer,
                    ),
                },
                synchronize_session=False,
            )
        )
        if updated_conversation != 1:
            raise AgentFinalizationConflict("Conversation ownership changed before finalization")
        db.add(
            Message(
                conversation_id=conversation_id,
                role="assistant",
                content=normalized_answer,
                # T1（2026-09-16）：消息关联 run——历史会话经此读取覆盖信息（旧消息 NULL → unknown）
                agent_run_id=run_id,
            )
        )
        db.add(
            AgentStep(
                agent_run_id=run_id,
                state_version=expected_version + 1,
                decision="finalize",
                reason_code="VERIFIED_FINAL_STORED",
                result_summary=answer_digest,
                status=AgentStatus.COMPLETED.value,
                budget_snapshot=completed.budgets.model_dump_json(),
            )
        )
        for check in verification.claim_checks:
            db.add(
                AgentClaimCheck(
                    agent_run_id=run_id,
                    issue_id=None,
                    claim=check.claim,
                    evidence_ids=json.dumps(list(check.evidence_ids), ensure_ascii=False),
                    supported=check.supported,
                    verifier_verdict=verification.verdict.value,
                    rationale=check.rationale,
                )
            )
        db.commit()
        return True
    except AgentFinalizationConflict:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise


def coverage_from_state_json(state_json: str) -> tuple[CoverageProjection, list[dict[str, str]]]:
    """T1（2026-09-16）历史覆盖投影（纯函数）：从 run.state_json 读结构化覆盖信息。

    返回 (coverage_status, uncovered_issues)：
    - state_json 缺 `uncovered_issues` 键（T1 之前的历史 run）→ ("unknown", [])——不得推断 full；
    - 键存在：空列表 → "full"，非空 → "partial"（条目只保留 issue_id/reason_code）。
    损坏 JSON 一律 unknown（确定性，不抛异常——历史读取不得因脏数据 500）。
    """
    try:
        data = json.loads(state_json)
    except ValueError:
        return "unknown", []
    if not isinstance(data, dict) or "uncovered_issues" not in data:
        return "unknown", []
    raw = data.get("uncovered_issues")
    items = [
        {"issue_id": str(item["issue_id"]), "reason_code": str(item["reason_code"])}
        for item in (raw or [])
        if isinstance(item, dict) and item.get("issue_id") and item.get("reason_code")
    ]
    return ("partial" if items else "full"), items


__all__ = [
    "AgentFinalizationConflict",
    "AgentPublicResult",
    "coverage_from_state_json",
    "encode_sse_event",
    "encode_sse_stream",
    "persist_agent_final_once",
    "serialize_agent_events",
]
