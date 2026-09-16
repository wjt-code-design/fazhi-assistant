from datetime import datetime

import pytest

from agent.evaluator import EvaluationOutcome, EvidenceEvaluator
from agent.schemas import (
    Evidence,
    EvidenceConflict,
    LegalAgentState,
    LegalIssue,
    LegalValidity,
    Observation,
    SourceType,
    UnknownFact,
)


def evidence(
    evidence_id: str,
    *,
    source_type: SourceType = SourceType.STATUTE,
    validity: LegalValidity = LegalValidity.EFFECTIVE,
    snippet: str = "法条内容",
) -> Evidence:
    return Evidence(
        evidence_id=evidence_id,
        source_id=f"external-{evidence_id}",
        source_ref="中华人民共和国民法典#第一条",
        source_type=source_type,
        snippet=snippet,
        legal_validity=validity,
        acquired_at=datetime(2026, 8, 30, 8, 0),
    )


def issue(issue_id: str, *, unknowns: list[UnknownFact] | None = None) -> LegalIssue:
    return LegalIssue(issue_id=issue_id, question=f"{issue_id} question", unknown_facts=unknowns or [])


def linked_observation(issue_id: str, evidence_id: str, *, statement: str = "任意措辞") -> Observation:
    return Observation(
        issue_id=issue_id,
        statement=statement,
        evidence_ids=[evidence_id],
        confidence=1,
    )


def test_evaluation_outcomes_serialize_as_stable_machine_codes():
    assert [outcome.value for outcome in EvaluationOutcome] == [
        "SUFFICIENT",
        "MISSING_FACT",
        "MISSING_EVIDENCE",
        "CONFLICT",
        "FAIL_SAFE",
    ]


def test_two_issue_state_is_sufficient_only_when_each_issue_links_effective_statute():
    state = LegalAgentState(
        issues=[issue("issue-b"), issue("issue-a")],
        evidence=[evidence("ev-a"), evidence("ev-b")],
        observations=[linked_observation("issue-a", "ev-a"), linked_observation("issue-b", "ev-b")],
    )

    result = EvidenceEvaluator().evaluate(state)

    assert result.outcome is EvaluationOutcome.SUFFICIENT
    assert result.reason_code == "ALL_ISSUES_GROUNDED"
    assert result.issue_id is None
    assert result.clarification is None


@pytest.mark.parametrize(
    ("candidate", "expected_reason"),
    [
        (None, "MISSING_EFFECTIVE_STATUTE"),
        (evidence("ev", validity=LegalValidity.UNKNOWN), "MISSING_EFFECTIVE_STATUTE"),
        (evidence("ev", validity=LegalValidity.SUPERSEDED), "MISSING_EFFECTIVE_STATUTE"),
        (evidence("ev", source_type=SourceType.CASE), "MISSING_EFFECTIVE_STATUTE"),
    ],
)
def test_missing_unknown_superseded_or_nonstatute_evidence_is_insufficient(candidate, expected_reason):
    evidence_items = [] if candidate is None else [candidate]
    observation_items = [] if candidate is None else [linked_observation("issue-a", "ev")]
    state = LegalAgentState(issues=[issue("issue-a")], evidence=evidence_items, observations=observation_items)

    result = EvidenceEvaluator().evaluate(state)

    assert result.outcome is EvaluationOutcome.MISSING_EVIDENCE
    assert result.reason_code == expected_reason
    assert result.issue_id == "issue-a"


def test_global_evidence_does_not_cover_an_unlinked_second_issue():
    state = LegalAgentState(
        issues=[issue("issue-a"), issue("issue-b")],
        evidence=[evidence("ev")],
        observations=[linked_observation("issue-a", "ev")],
    )

    result = EvidenceEvaluator().evaluate(state)

    assert result.outcome is EvaluationOutcome.MISSING_EVIDENCE
    assert result.issue_id == "issue-b"


def test_first_unknown_fact_is_selected_by_stable_issue_and_fact_order():
    state = LegalAgentState(
        issues=[
            issue(
                "issue-b",
                unknowns=[UnknownFact(statement="z fact", why_outcome_changes="changes b")],
            ),
            issue(
                "issue-a",
                unknowns=[
                    UnknownFact(statement="z fact", why_outcome_changes="changes z"),
                    UnknownFact(statement="a fact", why_outcome_changes="changes a"),
                ],
            ),
        ]
    )

    result = EvidenceEvaluator().evaluate(state)

    assert result.outcome is EvaluationOutcome.MISSING_FACT
    assert result.reason_code == "OUTCOME_CHANGING_FACT_UNKNOWN"
    assert result.issue_id == "issue-a"
    assert result.clarification == UnknownFact(statement="a fact", why_outcome_changes="changes a")


@pytest.mark.parametrize(
    ("critical", "resolved", "expected"),
    [
        (True, False, EvaluationOutcome.CONFLICT),
        (True, True, EvaluationOutcome.SUFFICIENT),
        (False, False, EvaluationOutcome.SUFFICIENT),
    ],
)
def test_only_unresolved_critical_conflict_blocks_sufficiency(critical, resolved, expected):
    state = LegalAgentState(
        issues=[issue("issue-a")],
        evidence=[evidence("ev-a"), evidence("ev-b")],
        observations=[linked_observation("issue-a", "ev-a")],
        conflicts=[
            EvidenceConflict(
                conflict_id="conflict-1",
                issue_id="issue-a",
                evidence_ids=("ev-a", "ev-b"),
                critical=critical,
                resolved=resolved,
            )
        ],
    )

    result = EvidenceEvaluator().evaluate(state)

    assert result.outcome is expected


@pytest.mark.parametrize(
    "state",
    [
        LegalAgentState(),
        LegalAgentState(
            issues=[issue("issue-a")],
            evidence=[evidence("ev")],
            observations=[linked_observation("issue-a", "dangling")],
        ),
        LegalAgentState(
            issues=[issue("issue-a")],
            evidence=[evidence("ev")],
            observations=[linked_observation("unknown-issue", "ev")],
        ),
        LegalAgentState(
            issues=[issue("issue-a")],
            evidence=[evidence("ev")],
            conflicts=[
                EvidenceConflict(
                    conflict_id="c",
                    issue_id="unknown-issue",
                    evidence_ids=("ev",),
                    critical=True,
                    resolved=False,
                )
            ],
        ),
        LegalAgentState(
            issues=[issue("issue-a")],
            evidence=[evidence("ev")],
            conflicts=[
                EvidenceConflict(
                    conflict_id="c",
                    issue_id="issue-a",
                    evidence_ids=("missing",),
                    critical=True,
                    resolved=False,
                )
            ],
        ),
        LegalAgentState(
            issues=[issue("issue-a")],
            evidence=[evidence("same", snippet="one"), evidence("same", snippet="two")],
        ),
    ],
)
def test_structural_integrity_failures_fail_safe(state):
    result = EvidenceEvaluator().evaluate(state)

    assert result.outcome is EvaluationOutcome.FAIL_SAFE
    assert result.reason_code.startswith("INTEGRITY_")


def test_evaluation_is_invariant_to_observation_prose():
    base = LegalAgentState(
        issues=[issue("issue-a")],
        evidence=[evidence("ev")],
        observations=[linked_observation("issue-a", "ev", statement="一定胜诉")],
    )
    changed = base.model_copy(update={"observations": [linked_observation("issue-a", "ev", statement="可能没有把握")]})

    assert EvidenceEvaluator().evaluate(base) == EvidenceEvaluator().evaluate(changed)
