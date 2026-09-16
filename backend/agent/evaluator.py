"""Pure, deterministic evaluation of structured legal-agent evidence state."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict

from .schemas import LegalAgentState, LegalValidity, SourceType, UnknownFact


class EvaluationOutcome(StrEnum):
    SUFFICIENT = "SUFFICIENT"
    MISSING_FACT = "MISSING_FACT"
    MISSING_EVIDENCE = "MISSING_EVIDENCE"
    CONFLICT = "CONFLICT"
    FAIL_SAFE = "FAIL_SAFE"


EvaluationReason = Literal[
    "ALL_ISSUES_GROUNDED",
    "OUTCOME_CHANGING_FACT_UNKNOWN",
    "MISSING_EFFECTIVE_STATUTE",
    "UNRESOLVED_CRITICAL_CONFLICT",
    "INTEGRITY_NO_ISSUES",
    "INTEGRITY_DUPLICATE_ISSUE_ID",
    "INTEGRITY_DIVERGENT_EVIDENCE_ID",
    "INTEGRITY_DANGLING_EVIDENCE_LINK",
    "INTEGRITY_UNKNOWN_OBSERVATION_ISSUE",
    "INTEGRITY_UNKNOWN_CONFLICT_ISSUE",
    "INTEGRITY_UNKNOWN_CONFLICT_EVIDENCE",
]


class EvaluationDecision(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    outcome: EvaluationOutcome
    reason_code: EvaluationReason
    issue_id: str | None = None
    clarification: UnknownFact | None = None


class EvidenceEvaluator:
    """Evaluate only typed links and flags; never infer from prose or confidence."""

    def evaluate(self, state: LegalAgentState) -> EvaluationDecision:
        integrity_failure = self._integrity_failure(state)
        if integrity_failure is not None:
            return integrity_failure

        for conflict in sorted(state.conflicts, key=lambda item: (item.issue_id, item.conflict_id)):
            if conflict.critical and not conflict.resolved:
                return EvaluationDecision(
                    outcome=EvaluationOutcome.CONFLICT,
                    reason_code="UNRESOLVED_CRITICAL_CONFLICT",
                    issue_id=conflict.issue_id,
                )

        for issue in sorted(state.issues, key=lambda item: item.issue_id):
            if issue.unknown_facts:
                unknown = min(
                    issue.unknown_facts,
                    key=lambda item: (item.statement, item.why_outcome_changes),
                )
                return EvaluationDecision(
                    outcome=EvaluationOutcome.MISSING_FACT,
                    reason_code="OUTCOME_CHANGING_FACT_UNKNOWN",
                    issue_id=issue.issue_id,
                    clarification=unknown,
                )

        evidence_by_id = {item.evidence_id: item for item in state.evidence}
        linked_by_issue: dict[str, set[str]] = {item.issue_id: set() for item in state.issues}
        for observation in state.observations:
            if observation.status == "succeeded":
                linked_by_issue[observation.issue_id].update(observation.evidence_ids)
        for issue in sorted(state.issues, key=lambda item: item.issue_id):
            has_effective_statute = any(
                evidence_by_id[evidence_id].source_type is SourceType.STATUTE
                and evidence_by_id[evidence_id].legal_validity is LegalValidity.EFFECTIVE
                for evidence_id in linked_by_issue[issue.issue_id]
            )
            if not has_effective_statute:
                return EvaluationDecision(
                    outcome=EvaluationOutcome.MISSING_EVIDENCE,
                    reason_code="MISSING_EFFECTIVE_STATUTE",
                    issue_id=issue.issue_id,
                )

        return EvaluationDecision(
            outcome=EvaluationOutcome.SUFFICIENT,
            reason_code="ALL_ISSUES_GROUNDED",
        )

    @staticmethod
    def _integrity_failure(state: LegalAgentState) -> EvaluationDecision | None:
        if not state.issues:
            return EvaluationDecision(
                outcome=EvaluationOutcome.FAIL_SAFE,
                reason_code="INTEGRITY_NO_ISSUES",
            )
        issue_ids = [item.issue_id for item in state.issues]
        if len(issue_ids) != len(set(issue_ids)):
            return EvaluationDecision(
                outcome=EvaluationOutcome.FAIL_SAFE,
                reason_code="INTEGRITY_DUPLICATE_ISSUE_ID",
            )

        evidence_payload_by_id: dict[str, dict[str, object]] = {}
        for evidence in state.evidence:
            payload = evidence.model_dump(mode="json")
            existing = evidence_payload_by_id.get(evidence.evidence_id)
            if existing is not None and existing != payload:
                return EvaluationDecision(
                    outcome=EvaluationOutcome.FAIL_SAFE,
                    reason_code="INTEGRITY_DIVERGENT_EVIDENCE_ID",
                )
            evidence_payload_by_id[evidence.evidence_id] = payload
        evidence_ids = set(evidence_payload_by_id)
        known_issues = set(issue_ids)

        for observation in state.observations:
            if observation.issue_id not in known_issues:
                return EvaluationDecision(
                    outcome=EvaluationOutcome.FAIL_SAFE,
                    reason_code="INTEGRITY_UNKNOWN_OBSERVATION_ISSUE",
                    issue_id=observation.issue_id,
                )
            if not set(observation.evidence_ids).issubset(evidence_ids):
                return EvaluationDecision(
                    outcome=EvaluationOutcome.FAIL_SAFE,
                    reason_code="INTEGRITY_DANGLING_EVIDENCE_LINK",
                    issue_id=observation.issue_id,
                )

        for conflict in state.conflicts:
            if conflict.issue_id not in known_issues:
                return EvaluationDecision(
                    outcome=EvaluationOutcome.FAIL_SAFE,
                    reason_code="INTEGRITY_UNKNOWN_CONFLICT_ISSUE",
                    issue_id=conflict.issue_id,
                )
            if not set(conflict.evidence_ids).issubset(evidence_ids):
                return EvaluationDecision(
                    outcome=EvaluationOutcome.FAIL_SAFE,
                    reason_code="INTEGRITY_UNKNOWN_CONFLICT_EVIDENCE",
                    issue_id=conflict.issue_id,
                )
        return None
