"""Release-manifest contracts for reproducible Legal Agent evidence."""

from __future__ import annotations

import hashlib
import json

import pytest
from pydantic import ValidationError

from scripts.release_manifest import load_release_manifest, validate_release_dependencies


def _payload() -> dict[str, object]:
    return {
        "schema_version": "legal-agent-release-manifest/v1",
        "release_id": "legal-agent-v1-20260902-001",
        "candidate": {"git_revision": "a" * 40, "build_digest": "sha256:" + "b" * 64},
        "evaluation": {
            "case_set_sha256": "c" * 64,
            "evaluator_name": "legal-agent-deterministic-evaluator",
            "evaluator_version": "1.0.0",
            "rubric_hash": "d" * 64,
            "release_policy_sha256": "e" * 64,
        },
        "knowledge": {
            "corpus_manifest_sha256": "f" * 64,
            "index_manifest_sha256": "0" * 64,
            "jurisdictions": ["CN"],
            "law_as_of": "2026-09-02",
        },
        "runtime": {
            "provider": "test-provider",
            "model": "test-model-2026-09-01",
            "model_snapshot": "snapshot-001",
            "prompt_bundle_sha256": "1" * 64,
            "tool_policy_sha256": "2" * 64,
            "config_sha256": "3" * 64,
        },
        "capture": {
            "protocol_sha256": "4" * 64,
            "retry_policy_sha256": "5" * 64,
            "timeout_seconds": 90,
            "concurrency": 1,
            "cache_policy": "disabled",
            "network_policy": "frozen-knowledge-only",
        },
    }


def test_load_release_manifest_validates_the_complete_reproducibility_boundary(tmp_path):
    path = tmp_path / "release-manifest.json"
    payload = _payload()
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    manifest, sha256 = load_release_manifest(path)

    assert manifest.release_id == "legal-agent-v1-20260902-001"
    assert manifest.candidate.git_revision == "a" * 40
    assert manifest.evaluation.case_set_sha256 == "c" * 64
    assert manifest.knowledge.law_as_of.isoformat() == "2026-09-02"
    assert sha256 == hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.mark.parametrize(
    ("field_path", "value"),
    [
        (("knowledge", "law_as_of"), "2026-02-30"),
        (("capture", "concurrency"), 0),
        (("runtime", "model_snapshot"), ""),
        (("evaluation", "release_policy_sha256"), "not-a-hash"),
    ],
)
def test_load_release_manifest_rejects_invalid_or_incomplete_release_facts(tmp_path, field_path, value):
    path = tmp_path / "release-manifest.json"
    payload = _payload()
    target = payload
    for key in field_path[:-1]:
        target = target[key]  # type: ignore[index]
    target[field_path[-1]] = value  # type: ignore[index]
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(ValidationError):
        load_release_manifest(path)


def test_load_release_manifest_rejects_unknown_fields_instead_of_silently_ignoring_them(tmp_path):
    path = tmp_path / "release-manifest.json"
    payload = _payload()
    payload["unreviewed_override"] = True
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(ValidationError):
        load_release_manifest(path)


def test_release_manifest_rejects_replaced_policy_protocol_or_case_set(tmp_path):
    policy_path = tmp_path / "release-policy.json"
    protocol_path = tmp_path / "capture-protocol.json"
    manifest_path = tmp_path / "release-manifest.json"
    policy = {
        "schema_version": "legal-agent-release-policy/v1",
        "policy_id": "policy-001",
        "scope": "controlled-offline-dual-run",
        "metrics": [
            {
                "name": "safety",
                "unit": "count",
                "direction": "lower-is-better",
                "threshold": "0",
                "aggregation": "sum",
                "minimum_sample_size": 1,
                "observation_window": "one-run",
                "exclusions": [],
                "data_source": "audit",
                "owner": "reviewer",
                "rollback_condition": "any-finding",
            }
        ],
    }
    protocol = {
        "schema_version": "legal-agent-capture-protocol/v1",
        "protocol_id": "protocol-001",
        "case_set_sha256": "c" * 64,
        "modes": ["existing_rag", "agent"],
        "controls": {
            "timeout_seconds": 90,
            "total_timeout_seconds": 90,
            "max_retries": 0,
            "concurrency": 1,
            "cache_policy": "disabled",
            "network_policy": "offline",
            "max_output_tokens": 1,
            "max_tool_calls": 0,
            "retain_failure_rows": True,
        },
    }
    policy_path.write_text(json.dumps(policy), encoding="utf-8")
    protocol_path.write_text(json.dumps(protocol), encoding="utf-8")
    manifest = _payload()
    manifest["evaluation"]["release_policy_sha256"] = hashlib.sha256(policy_path.read_bytes()).hexdigest()  # type: ignore[index]
    manifest["capture"]["protocol_sha256"] = hashlib.sha256(protocol_path.read_bytes()).hexdigest()  # type: ignore[index]
    manifest["capture"]["retry_policy_sha256"] = manifest["capture"]["protocol_sha256"]  # type: ignore[index]
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    validate_release_dependencies(manifest_path, policy_path, protocol_path)

    protocol["case_set_sha256"] = "d" * 64
    protocol_path.write_text(json.dumps(protocol), encoding="utf-8")
    with pytest.raises(ValueError, match="protocol hash"):
        validate_release_dependencies(manifest_path, policy_path, protocol_path)


def test_release_manifest_rejects_unverifiable_retry_policy_hash(tmp_path):
    policy_path = tmp_path / "release-policy.json"
    protocol_path = tmp_path / "capture-protocol.json"
    manifest_path = tmp_path / "release-manifest.json"
    policy = {
        "schema_version": "legal-agent-release-policy/v1",
        "policy_id": "policy-001",
        "scope": "controlled-offline-dual-run",
        "metrics": [
            {
                "name": "safety",
                "unit": "count",
                "direction": "lower-is-better",
                "threshold": "0",
                "aggregation": "sum",
                "minimum_sample_size": 1,
                "observation_window": "one-run",
                "exclusions": [],
                "data_source": "audit",
                "owner": "reviewer",
                "rollback_condition": "any-finding",
            }
        ],
    }
    protocol = {
        "schema_version": "legal-agent-capture-protocol/v1",
        "protocol_id": "protocol-001",
        "case_set_sha256": "c" * 64,
        "modes": ["existing_rag", "agent"],
        "controls": {
            "timeout_seconds": 90,
            "total_timeout_seconds": 90,
            "max_retries": 0,
            "concurrency": 1,
            "cache_policy": "disabled",
            "network_policy": "offline",
            "max_output_tokens": 1,
            "max_tool_calls": 0,
            "retain_failure_rows": True,
        },
    }
    policy_path.write_text(json.dumps(policy), encoding="utf-8")
    protocol_path.write_text(json.dumps(protocol), encoding="utf-8")
    manifest = _payload()
    manifest["evaluation"]["release_policy_sha256"] = hashlib.sha256(policy_path.read_bytes()).hexdigest()  # type: ignore[index]
    manifest["capture"]["protocol_sha256"] = hashlib.sha256(protocol_path.read_bytes()).hexdigest()  # type: ignore[index]
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValueError, match="retry-policy hash"):
        validate_release_dependencies(manifest_path, policy_path, protocol_path)
