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
    db: Session, *, user_id: int, conversation_id: int, state: LegalAgentState
) -> AgentRun:
    """Create the first durable snapshot for a user-owned agent execution."""
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
        law_as_of=date.today(),
        state_json=state.model_dump_json(),
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def load_owned_run(
    db: Session, *, run_id: str, user_id: int, conversation_id: int
) -> AgentRun | None:
    """Load a run only when both its user and conversation ownership match."""
    return (
        db.query(AgentRun)
        .filter(
            AgentRun.id == run_id,
            AgentRun.user_id == user_id,
            AgentRun.conversation_id == conversation_id,
        )
        .one_or_none()
    )


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
