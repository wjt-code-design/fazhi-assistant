"""Independent, traceable audit evidence contracts for Legal Agent release."""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from scripts.agent_audit_evidence import load_agent_audit_evidence


def _payload() -> dict[str, object]:
    return {
        "schema_version": "legal-agent-agent-audit/v1",
        "release_manifest_sha256": "a" * 64,
        "mode": "agent",
        "reviewer": {"id": "legal-reviewer-001", "role": "independent-legal-reviewer"},
        "reviewed_at": "2026-09-02T10:00:00+08:00",
        "cases": [
            {"id": "case-1", "trace_ref": "trace://case-1", "decision": "pass", "findings": []},
            {"id": "case-2", "trace_ref": "trace://case-2", "decision": "pass", "findings": []},
        ],
    }


def test_agent_audit_evidence_requires_a_named_reviewer_timestamp_and_traceable_per_case_decisions(tmp_path):
    path = tmp_path / "agent-audit.json"
    path.write_text(json.dumps(_payload()), encoding="utf-8")

    audit, _ = load_agent_audit_evidence(path)

    assert audit.reviewer.role == "independent-legal-reviewer"
    assert [case.id for case in audit.cases] == ["case-1", "case-2"]


@pytest.mark.parametrize(
    ("case_update", "error"),
    [
        ({"decision": "pass", "findings": [{"code": "unsupported-claim", "trace_ref": "trace://case-1"}]}, "pass"),
        ({"decision": "finding", "findings": []}, "finding"),
    ],
)
def test_agent_audit_evidence_rejects_incomplete_or_self_contradictory_review_rows(tmp_path, case_update, error):
    path = tmp_path / "agent-audit.json"
    payload = _payload()
    payload["cases"][0].update(case_update)  # type: ignore[index]
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValidationError, match=error):
        load_agent_audit_evidence(path)


@pytest.mark.parametrize("trace_ref", ["C:/Users/33393/case.txt", "trace://case-1?user=123", "trace://案件-1"])
def test_agent_audit_evidence_rejects_non_opaque_trace_references(tmp_path, trace_ref):
    payload = _payload()
    payload["cases"][0]["trace_ref"] = trace_ref  # type: ignore[index]
    path = tmp_path / "agent-audit.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValidationError, match="trace_ref"):
        load_agent_audit_evidence(path)


@pytest.mark.parametrize(
    ("field", "value"),
    [("reviewer.id", "reviewer@example.com"), ("finding.code", "未授权工具调用")],
)
def test_agent_audit_evidence_rejects_non_opaque_reviewer_and_finding_identifiers(tmp_path, field, value):
    payload = _payload()
    if field == "reviewer.id":
        payload["reviewer"]["id"] = value  # type: ignore[index]
    else:
        payload["cases"][0] = {
            "id": "case-1",
            "trace_ref": "trace://case-1",
            "decision": "finding",
            "findings": [{"code": value, "trace_ref": "trace://case-1"}],
        }
    path = tmp_path / "agent-audit.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValidationError):
        load_agent_audit_evidence(path)
