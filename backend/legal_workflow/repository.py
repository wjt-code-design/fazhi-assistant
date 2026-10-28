"""Durable repository operations for user-scoped legal-agent runs."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from typing import TYPE_CHECKING, Any, cast
from uuid import uuid4

from models import AgentEvidence, AgentRun, AgentStep, Conversation

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from .schemas import Evidence, LegalAgentState


@dataclass(frozen=True)
class CheckpointMetadata:
    """Sanitized audit metadata; raw Planner/tool payloads are deliberately absent."""

    decision: str = "state_transition"
    reason_code: str | None = None
    issue_id: str | None = None
    tool_name: str | None = None
    fingerprint: str | None = None
    duration_ms: int | None = None
    result_code: str | None = None
    degraded_reason: str | None = None
    last_error_code: str | None = None
    pending_question: str | None = None


class RunVersionConflict(Exception):
    """Raised when a stale caller attempts to overwrite a newer run state."""

    def __init__(self, run_id: str):
        self.run_id = run_id
        super().__init__(f"Agent run {run_id} has changed; reload it before saving.")


def create_run(
    db: Session,
    *,
    user_id: int,
    conversation_id: int,
    state: LegalAgentState,
    law_as_of: date | None = None,
) -> AgentRun:
    """Create the first durable snapshot for a user-owned agent execution.

    R15-lite（2026-09-18）：`law_as_of` 缺省 None 时落当日（行为逐字不变）；评测/
    灰度通道可显式注入法律版本基准日（如 2021-01-01 民法典分水岭场景），随 run
    持久化并被工具 cutoff/证据有效性判定消费。server-owned：值只能由服务端代码设置。
    边界（R15 绊线，2026-09-18）：缺省落当日意味着**分水岭前事实会得到分水岭后的法**；
    该错答由 `verifier` 的 `law_version_tripwire_check` 拦（默认关）。本函数对 `law_as_of`
    的缺省处理按 docs/handoff-external-harness-20260918.md §2.3 明确锁定，不得改成必填或报错。
    """
    owns_conversation = (
        db.query(Conversation.id)
        .filter(Conversation.id == conversation_id, Conversation.user_id == user_id)
        .one_or_none()
    )
    if owns_conversation is None:
        raise ValueError(f"Conversation {conversation_id} does not belong to user {user_id}.")

    run = AgentRun(
        id=str(uuid4()),
        user_id=user_id,
        conversation_id=conversation_id,
        status=state.status.value,
        state_version=0,
        law_as_of=law_as_of or date.today(),
        state_json=state.model_dump_json(),
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def load_owned_run(db: Session, *, run_id: str, user_id: int, conversation_id: int) -> AgentRun | None:
    """Load a run only when both its user and conversation ownership match.

    V5-01（2026-10-21 第 5 轮只读审查）：除了 id 三元组，还核验**会话的稳定身份**。
    SQLite 数字主键会被复用（max+1）——修复前遗留的孤儿 run 在会话被删、同号新会话
    建立后，仅凭 `conversation_id` 会被重新认领。run 不可能早于它所属会话创建，
    因此 `run.created_at < conversation.created_at` 即说明这是旧会话的残留，拒绝加载。
    该判据同时覆盖升级前已存在于生产库的孤儿行（不依赖本轮删除逻辑是否跑过）。
    """
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
        return None
    conversation = db.get(Conversation, conversation_id)
    if conversation is None or conversation.user_id != user_id:
        return None
    if run.created_at < conversation.created_at:
        return None
    return run


def compare_and_save(
    db: Session,
    *,
    run: AgentRun,
    expected_version: int,
    state: LegalAgentState,
    status: str,
    checkpoint: CheckpointMetadata | None = None,
    new_evidence_by_issue: Mapping[str, Sequence[Evidence]] | None = None,
) -> AgentRun:
    """Persist a state transition atomically, rejecting stale state versions."""
    state_status = state.status.value
    if status != state_status:
        raise ValueError(f"status must match state.status ({state_status}).")

    metadata = checkpoint or CheckpointMetadata()
    run_values: dict[str, object] = {
        "state_json": state.model_dump_json(),
        "status": state_status,
        "state_version": expected_version + 1,
        "updated_at": datetime.utcnow(),
    }
    if checkpoint is not None:
        run_values.update(
            degraded_reason=metadata.degraded_reason,
            last_error_code=metadata.last_error_code,
            pending_question=metadata.pending_question,
        )
    try:
        updated = (
            db.query(AgentRun)
            .filter(AgentRun.id == run.id, AgentRun.state_version == expected_version)
            .update(cast(Any, run_values), synchronize_session=False)
        )
        if updated != 1:
            raise RunVersionConflict(cast(str, run.id))

        db.add(
            AgentStep(
                agent_run_id=run.id,
                state_version=expected_version + 1,
                issue_id=metadata.issue_id,
                decision=metadata.decision,
                reason_code=metadata.reason_code,
                tool_name=metadata.tool_name,
                normalized_input=metadata.fingerprint,
                result_summary=metadata.result_code,
                status=state_status,
                duration_ms=metadata.duration_ms,
                budget_snapshot=state.budgets.model_dump_json(),
            )
        )
        for issue_id, evidence_items in (new_evidence_by_issue or {}).items():
            for evidence in evidence_items:
                db.add(
                    AgentEvidence(
                        agent_run_id=run.id,
                        issue_id=issue_id,
                        source_type=evidence.source_type.value,
                        source_identifier=evidence.source_id,
                        provenance=json.dumps(
                            {
                                "evidence_id": evidence.evidence_id,
                                "source_ref": evidence.source_ref,
                            },
                            ensure_ascii=False,
                            sort_keys=True,
                            separators=(",", ":"),
                        ),
                        snippet=evidence.snippet,
                        legal_validity=evidence.legal_validity.value,
                        law_as_of=run.law_as_of,
                        acquired_at=evidence.acquired_at,
                    )
                )
        db.commit()
    except Exception:
        db.rollback()
        raise
    saved = db.get(AgentRun, run.id)
    if saved is None:
        raise RuntimeError(f"Agent run {run.id} disappeared after save.")
    return saved
