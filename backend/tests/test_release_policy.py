"""Predeclared Legal Agent release-policy contracts."""

from __future__ import annotations

import hashlib
import json

import pytest
from pydantic import ValidationError

from scripts.release_policy import load_release_policy


def _payload() -> dict[str, object]:
    return {
        "schema_version": "legal-agent-release-policy/v1",
        "policy_id": "legal-agent-v1-20260902-001",
        "scope": "controlled-offline-dual-run",
        "metrics": [
            {
                "name": "complex_task_quality",
                "unit": "ratio",
                "direction": "higher-is-better",
                "threshold": "agent >= existing_rag",
                "aggregation": "mean-over-complete-case-set",
                "minimum_sample_size": 20,
                "observation_window": "one-complete-frozen-run-per-mode",
                "exclusions": [],
                "data_source": "deterministic-evaluator-report",
                "owner": "release-approver",
                "rollback_condition": "agent < existing_rag",
            },
            {
                "name": "safety_findings",
                "unit": "count",
                "direction": "lower-is-better",
                "threshold": "0",
                "aggregation": "sum-over-complete-case-set",
                "minimum_sample_size": 20,
                "observation_window": "one-complete-frozen-run-per-mode",
                "exclusions": [],
                "data_source": "independent-human-audit",
                "owner": "legal-reviewer",
                "rollback_condition": "any-confirmed-finding",
            },
        ],
    }


def test_load_release_policy_requires_reproducible_metric_owners_and_rollback_rules(tmp_path):
    path = tmp_path / "release-policy.json"
    payload = _payload()
    path.write_text(json.dumps(payload), encoding="utf-8")

    policy, sha256 = load_release_policy(path)

    assert policy.scope == "controlled-offline-dual-run"
    assert [metric.name for metric in policy.metrics] == ["complex_task_quality", "safety_findings"]
    assert sha256 == hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("minimum_sample_size", 0),
        ("owner", ""),
        ("rollback_condition", ""),
    ],
)
def test_load_release_policy_rejects_metrics_that_cannot_drive_a_release_decision(tmp_path, field, value):
    path = tmp_path / "release-policy.json"
    payload = _payload()
    payload["metrics"][0][field] = value  # type: ignore[index]
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValidationError):
        load_release_policy(path)


def test_load_release_policy_rejects_duplicate_metric_names_and_unknown_fields(tmp_path):
    path = tmp_path / "release-policy.json"
    payload = _payload()
    duplicate = dict(payload["metrics"][0])  # type: ignore[index]
    payload["metrics"].append(duplicate)  # type: ignore[index]
    payload["unreviewed_override"] = True
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValidationError):
        load_release_policy(path)
