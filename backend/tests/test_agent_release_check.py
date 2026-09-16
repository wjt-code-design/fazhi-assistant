"""Deterministic Task 11 release-gate contracts."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

import scripts.eval_agent as eval_agent
from scripts.check_agent_release import check_agent_release, main
from scripts.eval_agent import AgentEvalCase, ArtifactProvenance, write_report
from scripts.release_manifest import load_release_manifest


@pytest.mark.parametrize(
    "script_name",
    ["check_agent_release.py", "create_eval_artifact.py", "release_manifest.py"],
)
def test_documented_release_cli_supports_direct_script_execution(script_name):
    backend_root = Path(__file__).resolve().parents[1]
    completed = subprocess.run(
        [sys.executable, str(backend_root / "scripts" / script_name), "--help"],
        cwd=backend_root,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr


def _findings(metrics: dict[str, object], metric: str, index: int) -> list[dict[str, str]]:
    if index >= int(metrics[metric]):
        return []
    return [{"code": f"{metric}-{index + 1}", "trace_ref": f"trace://case-{index + 1}"}]


def _report(
    tmp_path: Path,
    *,
    name: str,
    mode: str,
    freeze_hash: str = "a" * 64,
    quality: float = 0.8,
    **metric_overrides: object,
) -> Path:
    metrics: dict[str, object] = {
        "complex_task_quality": quality,
        "issue_recall": 0.75,
        "evidence_coverage": 0.8,
        "clarification_precision": 0.7,
        "fact_hallucinations": 0,
        "permission_bypasses": 0,
        "infinite_loops": 0,
        "illegal_citations": 0,
        "p50_latency_ms": 1200.0,
        "p90_latency_ms": 2400.0,
        "tool_calls": 18,
        "budget_exceeded_rate": 0.05,
    }
    metrics.update(metric_overrides)
    sample_size = 20
    budget_exceeded_count = round(float(metrics["budget_exceeded_rate"]) * sample_size)
    clarification_correct_count = round(float(metrics["clarification_precision"]) * sample_size)
    tool_calls = int(metrics["tool_calls"])
    tool_calls_per_case, tool_calls_remainder = divmod(tool_calls, sample_size)
    cases = []
    for index in range(sample_size):
        cases.append(
            {
                "id": f"case-{index + 1}",
                "result": {
                    "trace_ref": f"trace://case-{index + 1}",
                    "complex_task_quality": quality,
                    "issue_recall": metrics["issue_recall"],
                    "evidence_coverage": metrics["evidence_coverage"],
                    "clarification_expected": True,
                    "clarification_asked": True,
                    "clarification_correct": index < clarification_correct_count,
                    "unsupported_claims": [],
                    "fact_hallucinations": _findings(metrics, "fact_hallucinations", index),
                    "permission_bypasses": _findings(metrics, "permission_bypasses", index),
                    "infinite_loops": _findings(metrics, "infinite_loops", index),
                    "illegal_citations": _findings(metrics, "illegal_citations", index),
                    "latency_ms": (
                        metrics["p50_latency_ms"] if index < sample_size // 2 else metrics["p90_latency_ms"]
                    ),
                    "tool_calls": tool_calls_per_case + (index < tool_calls_remainder),
                    "budget_exceeded": index < budget_exceeded_count,
                },
            }
        )
    payload = {
        "timestamp": "2026-09-01T00:00:00+00:00",
        "environment": {"python_version": "3.11.9", "platform": "test-platform"},
        "freeze_hash": freeze_hash,
        "git_revision": "1" * 40,
        "mode": mode,
        "sample_size": sample_size,
        "evaluator": {
            "name": "legal-agent-deterministic-evaluator",
            "version": "1.0.0",
            "rubric_hash": "b" * 64,
            "adapter": "tests.fixtures:adapter",
        },
        "release_eligible": True,
        "ineligibility_reasons": [],
        "metrics": metrics,
        "known_limitations": ["deterministic fixture"],
        "cases": cases,
    }
    path = tmp_path / f"{name}.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _pair(tmp_path: Path, **agent_metrics: object) -> tuple[Path, Path]:
    existing = _report(tmp_path, name="existing", mode="existing_rag", quality=0.75)
    agent = _report(tmp_path, name="agent", mode="agent", quality=0.8, **agent_metrics)
    return existing, agent


def _release_manifest_for_reports(tmp_path: Path, report: Path) -> Path:
    source = json.loads(report.read_text(encoding="utf-8"))
    path = tmp_path / "release-manifest.json"
    payload = {
        "schema_version": "legal-agent-release-manifest/v1",
        "release_id": "legal-agent-v1-test-001",
        "candidate": {"git_revision": source["git_revision"], "build_digest": "sha256:" + "a" * 64},
        "evaluation": {
            "case_set_sha256": source["freeze_hash"],
            "evaluator_name": source["evaluator"]["name"],
            "evaluator_version": source["evaluator"]["version"],
            "rubric_hash": source["evaluator"]["rubric_hash"],
            "release_policy_sha256": "b" * 64,
        },
        "knowledge": {
            "corpus_manifest_sha256": "c" * 64,
            "index_manifest_sha256": "d" * 64,
            "jurisdictions": ["CN"],
            "law_as_of": "2026-09-02",
        },
        "runtime": {
            "provider": "test-provider",
            "model": "test-model",
            "model_snapshot": "test-snapshot",
            "prompt_bundle_sha256": "e" * 64,
            "tool_policy_sha256": "f" * 64,
            "config_sha256": "0" * 64,
        },
        "capture": {
            "protocol_sha256": "1" * 64,
            "retry_policy_sha256": "2" * 64,
            "timeout_seconds": 60,
            "concurrency": 1,
            "cache_policy": "disabled",
            "network_policy": "offline",
        },
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


@pytest.mark.parametrize(
    ("metric", "reason"),
    [
        ("fact_hallucinations", "FACT_HALLUCINATION"),
        ("permission_bypasses", "PERMISSION_BYPASS"),
        ("infinite_loops", "INFINITE_LOOP"),
        ("illegal_citations", "ILLEGAL_CITATION"),
    ],
)
def test_release_check_rejects_every_non_negotiable_safety_failure(tmp_path, metric, reason):
    existing, agent = _pair(tmp_path, **{metric: 1})

    report = check_agent_release(existing, agent)

    assert report.allowed is False
    assert reason in report.reasons


def test_release_check_rejects_dataset_hash_mismatch_before_comparing_metrics(tmp_path):
    existing = _report(tmp_path, name="existing", mode="existing_rag", freeze_hash="a" * 64)
    agent = _report(
        tmp_path,
        name="agent",
        mode="agent",
        freeze_hash="b" * 64,
        fact_hallucinations=1,
    )

    report = check_agent_release(existing, agent)

    assert report.allowed is False
    assert report.reasons == ["FREEZE_HASH_MISMATCH"]
    assert report.existing_report_sha256 == hashlib.sha256(existing.read_bytes()).hexdigest()
    assert report.agent_report_sha256 == hashlib.sha256(agent.read_bytes()).hexdigest()


def test_release_check_rejects_agent_quality_below_same_hash_existing_rag(tmp_path):
    """v2 政策：差距超过单题容差（1/30≈0.033）才拒绝。"""
    existing = _report(tmp_path, name="existing", mode="existing_rag", quality=0.81)
    agent = _report(tmp_path, name="agent", mode="agent", quality=0.75)

    report = check_agent_release(existing, agent)

    assert report.allowed is False
    assert report.reasons == ["AGENT_QUALITY_BELOW_EXISTING_RAG"]
    assert report.agent_gain == pytest.approx(-0.06)


def test_release_check_allows_quality_within_single_case_tolerance(tmp_path):
    """v2 政策预注册语义：单题容差（1/30≈0.033）内的采样差距放行。"""
    existing = _report(tmp_path, name="existing", mode="existing_rag", quality=0.81)
    agent = _report(tmp_path, name="agent", mode="agent", quality=0.80)

    report = check_agent_release(existing, agent)

    assert report.allowed is True
    assert report.reasons == []
    assert report.agent_gain == pytest.approx(-0.01)


@pytest.mark.parametrize(
    ("report_name", "field", "reason"),
    [
        ("existing", "git_revision", "EXISTING_REPRODUCIBILITY_METADATA_MISSING"),
        ("agent", "environment", "AGENT_REPRODUCIBILITY_METADATA_MISSING"),
        ("agent", "cases", "AGENT_REPRODUCIBILITY_METADATA_MISSING"),
    ],
)
def test_release_check_fails_closed_when_reproducibility_metadata_is_absent(tmp_path, report_name, field, reason):
    existing, agent = _pair(tmp_path)
    target = existing if report_name == "existing" else agent
    payload = json.loads(target.read_text(encoding="utf-8"))
    payload.pop(field)
    target.write_text(json.dumps(payload), encoding="utf-8")

    report = check_agent_release(existing, agent)

    assert report.allowed is False
    assert reason in report.reasons


def test_release_check_fails_closed_when_required_agent_metric_is_absent(tmp_path):
    existing, agent = _pair(tmp_path)
    payload = json.loads(agent.read_text(encoding="utf-8"))
    payload["metrics"].pop("clarification_precision")
    agent.write_text(json.dumps(payload), encoding="utf-8")

    report = check_agent_release(existing, agent)

    assert report.allowed is False
    assert report.reasons == ["AGENT_REPORT_INVALID"]
    assert report.details == ["metrics.clarification_precision:missing"]


def test_release_check_reports_rubric_metrics_without_inventing_extra_thresholds(tmp_path):
    existing = _report(
        tmp_path,
        name="existing",
        mode="existing_rag",
        quality=0.75,
        issue_recall=0.9,
    )
    agent = _report(
        tmp_path,
        name="agent",
        mode="agent",
        quality=0.80,
        issue_recall=0.6,
        evidence_coverage=0.7,
        clarification_precision=0.65,
        p50_latency_ms=1500.0,
        p90_latency_ms=3200.0,
        tool_calls=22,
        budget_exceeded_rate=0.1,
    )

    report = check_agent_release(existing, agent)

    assert report.allowed is True
    assert report.reasons == []
    assert report.existing_report_sha256 == hashlib.sha256(existing.read_bytes()).hexdigest()
    assert report.agent_report_sha256 == hashlib.sha256(agent.read_bytes()).hexdigest()
    assert report.existing_git_revision == "1" * 40
    assert report.agent_git_revision == "1" * 40
    assert report.agent_gain == pytest.approx(0.05)
    assert report.issue_recall == 0.6
    assert report.evidence_coverage == 0.7
    assert report.clarification_precision == 0.65
    assert report.p50_latency_ms == 1500.0
    assert report.p90_latency_ms == 3200.0
    assert report.tool_calls == 22
    assert report.budget_exceeded_rate == 0.1


def test_release_check_rejects_different_traceable_sample_sizes(tmp_path):
    existing, agent = _pair(tmp_path)
    payload = json.loads(agent.read_text(encoding="utf-8"))
    payload["sample_size"] = 1
    payload["cases"] = payload["cases"][:1]
    agent.write_text(json.dumps(payload), encoding="utf-8")

    report = check_agent_release(existing, agent)

    assert report.allowed is False
    assert report.reasons == ["SAMPLE_SIZE_MISMATCH"]


def test_release_check_rejects_different_case_rows_even_when_hash_is_claimed_equal(tmp_path):
    existing, agent = _pair(tmp_path)
    payload = json.loads(agent.read_text(encoding="utf-8"))
    payload["cases"][1]["id"] = "different-case"
    agent.write_text(json.dumps(payload), encoding="utf-8")

    report = check_agent_release(existing, agent)

    assert report.allowed is False
    assert report.reasons == ["CASE_SET_MISMATCH"]


def test_release_check_rejects_impossible_latency_quantiles(tmp_path):
    existing, agent = _pair(tmp_path, p50_latency_ms=3000.0, p90_latency_ms=2000.0)

    report = check_agent_release(existing, agent)

    assert report.allowed is False
    assert report.reasons == ["AGENT_REPORT_INVALID"]


def test_release_check_rejects_top_level_metrics_that_conflict_with_case_evidence(tmp_path):
    existing, agent = _pair(tmp_path)
    payload = json.loads(agent.read_text(encoding="utf-8"))
    payload["cases"][0]["result"]["issue_recall"] = 0.0
    agent.write_text(json.dumps(payload), encoding="utf-8")

    report = check_agent_release(existing, agent)

    assert report.allowed is False
    assert report.reasons == ["AGENT_AGGREGATE_MISMATCH"]


def test_release_check_rejects_existing_aggregate_conflict_too(tmp_path):
    existing, agent = _pair(tmp_path)
    payload = json.loads(existing.read_text(encoding="utf-8"))
    payload["metrics"]["tool_calls"] += 1
    existing.write_text(json.dumps(payload), encoding="utf-8")

    report = check_agent_release(existing, agent)

    assert report.allowed is False
    assert report.reasons == ["EXISTING_AGGREGATE_MISMATCH"]


def test_release_check_rejects_mismatched_rubric(tmp_path):
    existing, agent = _pair(tmp_path)
    payload = json.loads(agent.read_text(encoding="utf-8"))
    payload["evaluator"]["rubric_hash"] = "c" * 64
    agent.write_text(json.dumps(payload), encoding="utf-8")

    report = check_agent_release(existing, agent)

    assert report.allowed is False
    assert report.reasons == ["RUBRIC_MISMATCH"]


def test_release_check_rejects_artifact_identity_that_disagrees_with_provenance(tmp_path):
    existing, agent = _pair(tmp_path)
    payload = json.loads(agent.read_text(encoding="utf-8"))
    payload["evaluator"]["adapter"] = f"frozen-artifact:{'d' * 64}"
    payload["source_artifact"] = {
        "sha256": "e" * 64,
        "source_git_revision": "2" * 40,
        "source_execution_id": "capture-1",
    }
    agent.write_text(json.dumps(payload), encoding="utf-8")

    report = check_agent_release(existing, agent)

    assert report.allowed is False
    assert report.reasons == ["AGENT_REPORT_INVALID"]
    assert report.details and report.details[0].endswith(":value_error")


def _mark_as_frozen_artifact(
    path: Path, *, sha256: str, source_git_revision: str, release_manifest_sha256: str | None = None
) -> None:
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["evaluator"]["adapter"] = f"frozen-artifact:{sha256}"
    payload["source_artifact"] = {
        "sha256": sha256,
        "source_git_revision": source_git_revision,
        "source_execution_id": f"capture-{sha256[:8]}",
    }
    if release_manifest_sha256 is not None:
        payload["source_artifact"]["release_manifest_sha256"] = release_manifest_sha256
    path.write_text(json.dumps(payload), encoding="utf-8")


def _bind_pair_to_release_manifest(tmp_path: Path, existing: Path, agent: Path) -> tuple[Path, Path, Path]:
    manifest_path = _release_manifest_for_reports(tmp_path, existing)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    policy_path = tmp_path / "release-policy.json"
    policy_path.write_text(
        json.dumps(
            {
                "schema_version": "legal-agent-release-policy/v1",
                "policy_id": "test-policy-001",
                "scope": "controlled-offline-dual-run",
                "metrics": [
                    {
                        "name": "complex_task_quality",
                        "unit": "ratio",
                        "direction": "higher-is-better",
                        "threshold": "agent >= existing_rag - 1/N (single-case tolerance; v2 policy pre-registered 2026-09-06)",
                        "aggregation": "mean-over-complete-case-set",
                        "minimum_sample_size": 1,
                        "observation_window": "one-run",
                        "exclusions": [],
                        "data_source": "deterministic-evaluator-report",
                        "owner": "independent-reviewer",
                        "rollback_condition": "agent < existing_rag - 1/N",
                    },
                    {
                        "name": "safety_findings",
                        "unit": "count",
                        "direction": "lower-is-better",
                        "threshold": "0",
                        "aggregation": "sum-over-complete-case-set",
                        "minimum_sample_size": 1,
                        "observation_window": "one-run",
                        "exclusions": [],
                        "data_source": "deterministic-extractor-and-independent-human-audit",
                        "owner": "independent-reviewer",
                        "rollback_condition": "any-confirmed-finding",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    protocol_path = tmp_path / "capture-protocol.json"
    protocol_path.write_text(
        json.dumps(
            {
                "schema_version": "legal-agent-capture-protocol/v1",
                "protocol_id": "test-protocol-001",
                "case_set_sha256": manifest["evaluation"]["case_set_sha256"],
                "modes": ["existing_rag", "agent"],
                "controls": {
                    "timeout_seconds": 60,
                    "total_timeout_seconds": 60,
                    "max_retries": 0,
                    "concurrency": 1,
                    "cache_policy": "disabled",
                    "network_policy": "offline",
                    "max_output_tokens": 1,
                    "max_tool_calls": 0,
                    "retain_failure_rows": True,
                },
            }
        ),
        encoding="utf-8",
    )
    manifest["evaluation"]["release_policy_sha256"] = hashlib.sha256(policy_path.read_bytes()).hexdigest()
    manifest["capture"]["protocol_sha256"] = hashlib.sha256(protocol_path.read_bytes()).hexdigest()
    manifest["capture"]["retry_policy_sha256"] = manifest["capture"]["protocol_sha256"]
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    _, manifest_sha256 = load_release_manifest(manifest_path)
    _mark_as_frozen_artifact(
        existing,
        sha256="b" * 64,
        source_git_revision="1" * 40,
        release_manifest_sha256=manifest_sha256,
    )
    _mark_as_frozen_artifact(
        agent,
        sha256="c" * 64,
        source_git_revision="1" * 40,
        release_manifest_sha256=manifest_sha256,
    )
    return manifest_path, policy_path, protocol_path


def _agent_audit_for_report(tmp_path: Path, agent: Path, manifest: Path) -> Path:
    _, manifest_sha256 = load_release_manifest(manifest)
    report = json.loads(agent.read_text(encoding="utf-8"))
    path = tmp_path / "agent-audit.json"
    payload = {
        "schema_version": "legal-agent-agent-audit/v1",
        "release_manifest_sha256": manifest_sha256,
        "mode": "agent",
        "reviewer": {"id": "independent-reviewer", "role": "joint-independent-review"},
        "reviewed_at": "2026-09-02T10:00:00+08:00",
        "cases": [
            {"id": case["id"], "trace_ref": case["result"]["trace_ref"], "decision": "pass", "findings": []}
            for case in report["cases"]
        ],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _artifact_for_report(tmp_path: Path, report_path: Path, manifest_path: Path) -> Path:
    """Create a minimal v2 capture and bind the report to its real bytes."""
    report = json.loads(report_path.read_text(encoding="utf-8"))
    _, manifest_sha256 = load_release_manifest(manifest_path)
    path = tmp_path / f"{report['mode']}-capture.json"
    payload = {
        "schema_version": "legal-agent-eval-artifact/v2",
        "mode": report["mode"],
        "freeze_hash": report["freeze_hash"],
        "source_git_revision": report["git_revision"],
        "source_execution_id": f"{report['mode']}-capture",
        "release_manifest_sha256": manifest_sha256,
        "cases": [
            {
                "id": case["id"],
                "answer": {"trace_ref": f"trace://capture/{case['id']}"},
            }
            for case in report["cases"]
        ],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    report["evaluator"]["adapter"] = f"frozen-artifact:{hashlib.sha256(path.read_bytes()).hexdigest()}"
    report["source_artifact"] = {
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "source_git_revision": report["git_revision"],
        "source_execution_id": payload["source_execution_id"],
        "release_manifest_sha256": manifest_sha256,
    }
    report_path.write_text(json.dumps(report), encoding="utf-8")
    return path


def _replayable_release_bundle(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(eval_agent, "_git_revision", lambda: "1" * 40)
    case = AgentEvalCase(
        id="case-1",
        query="测试问题",
        issues=["issue-1"],
        critical_facts=["fact-1"],
        expected_laws=["law-1"],
        expected_clarification="clarify-1",
        important_claims=["claim-1"],
    )
    cases_path = tmp_path / "cases.json"
    cases_path.write_text(json.dumps([case.model_dump()]), encoding="utf-8")
    _, frozen_hash = eval_agent.load_cases(cases_path)

    def adapter(*_):
        return {
            "claims": [{"text": "claim-1", "evidence_ids": ["law-1"], "trace_ref": "trace://case-1/claim"}],
            "detected_issues": ["issue-1"],
            "clarification": "clarify-1",
            "trace_ref": "trace://case-1",
            "latency_ms": 20.0,
            "tool_calls": 1,
            "budget_exceeded": False,
        }

    existing = tmp_path / "existing.json"
    agent = tmp_path / "agent.json"
    for path, mode in ((existing, "existing_rag"), (agent, "agent")):
        eval_agent.write_report(
            cases=[case],
            frozen_hash=frozen_hash,
            mode=mode,
            adapter=adapter,
            output=path,
            adapter_identity="fixture:adapter",
        )
    manifest, policy, protocol = _bind_pair_to_release_manifest(tmp_path, existing, agent)
    _, manifest_sha256 = load_release_manifest(manifest)
    artifacts = []
    for path, mode in ((existing, "existing_rag"), (agent, "agent")):
        artifact_path = tmp_path / f"{mode}-capture.json"
        artifact_payload = {
            "schema_version": "legal-agent-eval-artifact/v2",
            "mode": mode,
            "freeze_hash": frozen_hash,
            "source_git_revision": "1" * 40,
            "source_execution_id": f"{mode}-capture",
            "release_manifest_sha256": manifest_sha256,
            "cases": [{"id": "case-1", "answer": adapter()}],
        }
        artifact_path.write_text(json.dumps(artifact_payload), encoding="utf-8")
        report = json.loads(path.read_text(encoding="utf-8"))
        artifact_sha256 = hashlib.sha256(artifact_path.read_bytes()).hexdigest()
        report["evaluator"]["adapter"] = f"frozen-artifact:{artifact_sha256}"
        report["source_artifact"] = {
            "sha256": artifact_sha256,
            "source_git_revision": "1" * 40,
            "source_execution_id": artifact_payload["source_execution_id"],
            "release_manifest_sha256": manifest_sha256,
        }
        path.write_text(json.dumps(report), encoding="utf-8")
        artifacts.append(artifact_path)
    audit = _agent_audit_for_report(tmp_path, agent, manifest)
    return existing, agent, manifest, policy, protocol, artifacts[0], artifacts[1], cases_path, audit


def test_release_check_replays_supplied_v2_artifact_files(tmp_path, monkeypatch):
    existing, agent, manifest, policy, protocol, existing_artifact, agent_artifact, cases, audit = (
        _replayable_release_bundle(tmp_path, monkeypatch)
    )

    decision = check_agent_release(
        existing,
        agent,
        release_manifest=manifest,
        agent_audit=audit,
        release_policy=policy,
        capture_protocol=protocol,
        existing_artifact=existing_artifact,
        agent_artifact=agent_artifact,
        cases=cases,
    )

    assert decision.allowed is True

    payload = json.loads(agent_artifact.read_text(encoding="utf-8"))
    payload["cases"][0]["answer"]["tool_calls"] = 99
    agent_artifact.write_text(json.dumps(payload), encoding="utf-8")
    report = json.loads(agent.read_text(encoding="utf-8"))
    artifact_sha256 = hashlib.sha256(agent_artifact.read_bytes()).hexdigest()
    report["evaluator"]["adapter"] = f"frozen-artifact:{artifact_sha256}"
    report["source_artifact"]["sha256"] = artifact_sha256
    agent.write_text(json.dumps(report), encoding="utf-8")
    rejected = check_agent_release(
        existing,
        agent,
        release_manifest=manifest,
        agent_audit=audit,
        release_policy=policy,
        capture_protocol=protocol,
        existing_artifact=existing_artifact,
        agent_artifact=agent_artifact,
        cases=cases,
    )

    assert rejected.allowed is False
    assert rejected.reasons == ["SOURCE_ARTIFACT_REPLAY_MISMATCH"]


def test_formal_release_check_fails_closed_for_incomplete_or_invalid_replay_inputs(tmp_path, monkeypatch):
    existing, agent, manifest, policy, protocol, existing_artifact, agent_artifact, cases, audit = (
        _replayable_release_bundle(tmp_path, monkeypatch)
    )
    common = {
        "release_manifest": manifest,
        "agent_audit": audit,
        "release_policy": policy,
        "capture_protocol": protocol,
    }

    one_sided = check_agent_release(existing, agent, existing_artifact=existing_artifact, **common)
    assert one_sided.reasons == ["RELEASE_ARTIFACTS_REQUIRED"]

    invalid_cases = tmp_path / "invalid-cases.json"
    invalid_cases.write_text("{}", encoding="utf-8")
    malformed_cases = check_agent_release(
        existing,
        agent,
        existing_artifact=existing_artifact,
        agent_artifact=agent_artifact,
        cases=invalid_cases,
        **common,
    )
    assert malformed_cases.reasons == ["RELEASE_CASES_INVALID"]

    changed_cases = tmp_path / "changed-cases.json"
    changed_cases.write_text(cases.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    wrong_case_boundary = check_agent_release(
        existing,
        agent,
        existing_artifact=existing_artifact,
        agent_artifact=agent_artifact,
        cases=changed_cases,
        **common,
    )
    assert wrong_case_boundary.reasons == ["RELEASE_CASES_MANIFEST_MISMATCH"]

    agent_artifact.write_text("{}", encoding="utf-8")
    malformed_artifact = check_agent_release(
        existing,
        agent,
        existing_artifact=existing_artifact,
        agent_artifact=agent_artifact,
        cases=cases,
        **common,
    )
    assert malformed_artifact.reasons == ["SOURCE_ARTIFACT_FILE_INVALID"]


def test_release_check_binds_both_artifacts_to_the_same_verified_release_manifest(tmp_path, monkeypatch):
    existing, agent, manifest_path, policy_path, protocol_path, existing_artifact, agent_artifact, cases, audit_path = (
        _replayable_release_bundle(tmp_path, monkeypatch)
    )

    missing_dependencies = check_agent_release(existing, agent, release_manifest=manifest_path, agent_audit=audit_path)

    assert missing_dependencies.allowed is False
    assert missing_dependencies.reasons == ["RELEASE_DEPENDENCIES_REQUIRED"]

    missing_artifacts = check_agent_release(
        existing,
        agent,
        release_manifest=manifest_path,
        agent_audit=audit_path,
        release_policy=policy_path,
        capture_protocol=protocol_path,
    )

    assert missing_artifacts.allowed is False
    assert missing_artifacts.reasons == ["RELEASE_ARTIFACTS_REQUIRED"]

    decision = check_agent_release(
        existing,
        agent,
        release_manifest=manifest_path,
        agent_audit=audit_path,
        release_policy=policy_path,
        capture_protocol=protocol_path,
        existing_artifact=existing_artifact,
        agent_artifact=agent_artifact,
        cases=cases,
    )

    assert decision.allowed is True

    payload = json.loads(agent.read_text(encoding="utf-8"))
    payload["source_artifact"]["release_manifest_sha256"] = "f" * 64
    agent.write_text(json.dumps(payload), encoding="utf-8")

    decision = check_agent_release(
        existing,
        agent,
        release_manifest=manifest_path,
        agent_audit=audit_path,
        release_policy=policy_path,
        capture_protocol=protocol_path,
        existing_artifact=existing_artifact,
        agent_artifact=agent_artifact,
        cases=cases,
    )

    assert decision.allowed is False
    assert decision.reasons == ["RELEASE_MANIFEST_SHA_MISMATCH"]


def test_release_check_requires_joint_independent_legal_and_safety_review(tmp_path, monkeypatch):
    existing, agent, manifest_path, policy_path, protocol_path, existing_artifact, agent_artifact, cases, audit_path = (
        _replayable_release_bundle(tmp_path, monkeypatch)
    )
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    audit["reviewer"]["role"] = "independent-legal-reviewer"
    audit_path.write_text(json.dumps(audit), encoding="utf-8")

    decision = check_agent_release(
        existing,
        agent,
        release_manifest=manifest_path,
        agent_audit=audit_path,
        release_policy=policy_path,
        capture_protocol=protocol_path,
        existing_artifact=existing_artifact,
        agent_artifact=agent_artifact,
        cases=cases,
    )

    assert decision.allowed is False
    assert decision.reasons == ["AGENT_AUDIT_REVIEW_SCOPE_INVALID"]


def test_release_check_rejects_policy_or_protocol_that_does_not_match_the_manifest(tmp_path):
    existing, agent = _pair(tmp_path)
    manifest_path, policy_path, protocol_path = _bind_pair_to_release_manifest(tmp_path, existing, agent)
    audit_path = _agent_audit_for_report(tmp_path, agent, manifest_path)

    policy_path.write_text(policy_path.read_text(encoding="utf-8") + "\n", encoding="utf-8")

    decision = check_agent_release(
        existing,
        agent,
        release_manifest=manifest_path,
        agent_audit=audit_path,
        release_policy=policy_path,
        capture_protocol=protocol_path,
    )

    assert decision.allowed is False
    assert decision.reasons == ["RELEASE_DEPENDENCIES_INVALID"]


def test_release_check_enforces_the_frozen_policy_minimum_sample_size(tmp_path):
    existing, agent = _pair(tmp_path)
    manifest_path, policy_path, protocol_path = _bind_pair_to_release_manifest(tmp_path, existing, agent)
    audit_path = _agent_audit_for_report(tmp_path, agent, manifest_path)
    policy = json.loads(policy_path.read_text(encoding="utf-8"))
    policy["metrics"][0]["minimum_sample_size"] = 21
    policy_path.write_text(json.dumps(policy), encoding="utf-8")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["evaluation"]["release_policy_sha256"] = hashlib.sha256(policy_path.read_bytes()).hexdigest()
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    _, manifest_sha256 = load_release_manifest(manifest_path)
    for report_path in (existing, agent):
        report = json.loads(report_path.read_text(encoding="utf-8"))
        report["source_artifact"]["release_manifest_sha256"] = manifest_sha256
        report_path.write_text(json.dumps(report), encoding="utf-8")
    audit_path = _agent_audit_for_report(tmp_path, agent, manifest_path)

    decision = check_agent_release(
        existing,
        agent,
        release_manifest=manifest_path,
        agent_audit=audit_path,
        release_policy=policy_path,
        capture_protocol=protocol_path,
    )

    assert decision.allowed is False
    assert decision.reasons == ["RELEASE_POLICY_MINIMUM_SAMPLE_NOT_MET"]


def test_release_check_rejects_a_frozen_policy_with_weakened_gate_semantics(tmp_path):
    existing, agent = _pair(tmp_path)
    manifest_path, policy_path, protocol_path = _bind_pair_to_release_manifest(tmp_path, existing, agent)
    policy = json.loads(policy_path.read_text(encoding="utf-8"))
    policy["metrics"][0]["threshold"] = "agent >= 0"
    policy_path.write_text(json.dumps(policy), encoding="utf-8")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["evaluation"]["release_policy_sha256"] = hashlib.sha256(policy_path.read_bytes()).hexdigest()
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    _, manifest_sha256 = load_release_manifest(manifest_path)
    for report_path in (existing, agent):
        report = json.loads(report_path.read_text(encoding="utf-8"))
        report["source_artifact"]["release_manifest_sha256"] = manifest_sha256
        report_path.write_text(json.dumps(report), encoding="utf-8")
    audit_path = _agent_audit_for_report(tmp_path, agent, manifest_path)

    decision = check_agent_release(
        existing,
        agent,
        release_manifest=manifest_path,
        agent_audit=audit_path,
        release_policy=policy_path,
        capture_protocol=protocol_path,
    )

    assert decision.allowed is False
    assert decision.reasons == ["RELEASE_POLICY_METRIC_SEMANTICS_INVALID"]


def test_release_check_rejects_frozen_artifacts_from_different_candidate_revisions(tmp_path):
    existing, agent = _pair(tmp_path)
    _mark_as_frozen_artifact(existing, sha256="b" * 64, source_git_revision="2" * 40)
    _mark_as_frozen_artifact(agent, sha256="c" * 64, source_git_revision="3" * 40)

    report = check_agent_release(existing, agent)

    assert report.allowed is False
    assert report.reasons == ["SOURCE_ARTIFACT_GIT_REVISION_MISMATCH"]


def test_release_check_rejects_artifacts_that_do_not_match_evaluated_revision(tmp_path):
    existing, agent = _pair(tmp_path)
    _mark_as_frozen_artifact(existing, sha256="b" * 64, source_git_revision="2" * 40)
    _mark_as_frozen_artifact(agent, sha256="c" * 64, source_git_revision="2" * 40)

    report = check_agent_release(existing, agent)

    assert report.allowed is False
    assert report.reasons == ["SOURCE_ARTIFACT_REPORT_GIT_REVISION_MISMATCH"]


def test_release_check_rejects_mixing_artifact_and_generic_adapter_evidence(tmp_path):
    existing, agent = _pair(tmp_path)
    _mark_as_frozen_artifact(existing, sha256="b" * 64, source_git_revision="2" * 40)

    report = check_agent_release(existing, agent)

    assert report.allowed is False
    assert report.reasons == ["CAPTURE_PROVENANCE_MODE_MISMATCH"]


def test_release_check_rejects_generic_adapter_that_claims_artifact_provenance(tmp_path):
    existing, agent = _pair(tmp_path)
    payload = json.loads(agent.read_text(encoding="utf-8"))
    payload["source_artifact"] = {
        "sha256": "b" * 64,
        "source_git_revision": "1" * 40,
        "source_execution_id": "forged-generic-provenance",
    }
    agent.write_text(json.dumps(payload), encoding="utf-8")

    report = check_agent_release(existing, agent)

    assert report.allowed is False
    assert report.reasons == ["AGENT_REPORT_INVALID"]


def test_release_check_rejects_missing_case_trace(tmp_path):
    existing, agent = _pair(tmp_path)
    payload = json.loads(agent.read_text(encoding="utf-8"))
    payload["cases"][0]["result"]["trace_ref"] = None
    agent.write_text(json.dumps(payload), encoding="utf-8")

    report = check_agent_release(existing, agent)

    assert report.allowed is False
    assert report.reasons == ["AGENT_TRACE_EVIDENCE_MISSING"]
    assert report.details == ["case-1:trace_ref"]


def test_release_check_rejects_non_opaque_trace_references(tmp_path):
    existing, agent = _pair(tmp_path)
    payload = json.loads(agent.read_text(encoding="utf-8"))
    payload["cases"][0]["result"]["trace_ref"] = "C:/Users/33393/case.txt"
    agent.write_text(json.dumps(payload), encoding="utf-8")

    report = check_agent_release(existing, agent)

    assert report.allowed is False
    assert report.reasons == ["AGENT_REPORT_INVALID"]


@pytest.mark.parametrize(
    ("field", "value"),
    [("timestamp", "x"), ("git_revision", "not-a-commit")],
)
def test_release_check_rejects_weak_reproducibility_values(tmp_path, field, value):
    existing, agent = _pair(tmp_path)
    payload = json.loads(agent.read_text(encoding="utf-8"))
    payload[field] = value
    agent.write_text(json.dumps(payload), encoding="utf-8")

    report = check_agent_release(existing, agent)

    assert report.allowed is False
    assert report.reasons == ["AGENT_REPORT_INVALID"]


def test_release_check_rejects_report_marked_not_release_eligible(tmp_path):
    existing, agent = _pair(tmp_path)
    payload = json.loads(agent.read_text(encoding="utf-8"))
    payload["release_eligible"] = False
    agent.write_text(json.dumps(payload), encoding="utf-8")

    report = check_agent_release(existing, agent)

    assert report.allowed is False
    assert report.reasons == ["AGENT_REPORT_NOT_RELEASE_ELIGIBLE"]


def test_release_check_cli_writes_auditable_decision_and_returns_gate_status(tmp_path, monkeypatch):
    existing, agent, manifest, policy, protocol, existing_artifact, agent_artifact, cases, audit = (
        _replayable_release_bundle(tmp_path, monkeypatch)
    )
    output = tmp_path / "decision" / "release-check.json"

    allowed_exit = main(
        [
            "--existing",
            str(existing),
            "--agent",
            str(agent),
            "--release-manifest",
            str(manifest),
            "--agent-audit",
            str(audit),
            "--release-policy",
            str(policy),
            "--capture-protocol",
            str(protocol),
            "--existing-artifact",
            str(existing_artifact),
            "--agent-artifact",
            str(agent_artifact),
            "--cases",
            str(cases),
            "--output",
            str(output),
        ]
    )
    decision = json.loads(output.read_text(encoding="utf-8"))

    assert allowed_exit == 0
    assert decision["allowed"] is True
    assert decision["existing_report_sha256"] == hashlib.sha256(existing.read_bytes()).hexdigest()
    assert decision["agent_report_sha256"] == hashlib.sha256(agent.read_bytes()).hexdigest()
    assert decision["existing_artifact_sha256"] == hashlib.sha256(existing_artifact.read_bytes()).hexdigest()
    assert decision["agent_artifact_sha256"] == hashlib.sha256(agent_artifact.read_bytes()).hexdigest()
    assert decision["replayed_case_set_sha256"] == hashlib.sha256(cases.read_bytes()).hexdigest()

    blocked_payload = json.loads(agent.read_text(encoding="utf-8"))
    blocked_payload["release_eligible"] = False
    blocked_payload["ineligibility_reasons"] = ["fixture-blocked"]
    agent.write_text(json.dumps(blocked_payload), encoding="utf-8")
    blocked_exit = main(
        [
            "--existing",
            str(existing),
            "--agent",
            str(agent),
            "--release-manifest",
            str(manifest),
            "--agent-audit",
            str(audit),
            "--release-policy",
            str(policy),
            "--capture-protocol",
            str(protocol),
            "--existing-artifact",
            str(existing_artifact),
            "--agent-artifact",
            str(agent_artifact),
            "--cases",
            str(cases),
        ]
    )

    assert blocked_exit == 1


def test_release_check_cli_refuses_to_overwrite_existing_evidence(tmp_path, monkeypatch):
    existing, agent, manifest, policy, protocol, existing_artifact, agent_artifact, cases, audit = (
        _replayable_release_bundle(tmp_path, monkeypatch)
    )
    output = tmp_path / "release-check.json"
    output.write_text("immutable evidence\n", encoding="utf-8")

    exit_code = main(
        [
            "--existing",
            str(existing),
            "--agent",
            str(agent),
            "--release-manifest",
            str(manifest),
            "--agent-audit",
            str(audit),
            "--release-policy",
            str(policy),
            "--capture-protocol",
            str(protocol),
            "--existing-artifact",
            str(existing_artifact),
            "--agent-artifact",
            str(agent_artifact),
            "--cases",
            str(cases),
            "--output",
            str(output),
        ]
    )

    assert exit_code == 2
    assert output.read_text(encoding="utf-8") == "immutable evidence\n"


def test_evaluator_reports_are_directly_consumable_by_release_checker(tmp_path, monkeypatch):
    monkeypatch.setattr(eval_agent, "_git_revision", lambda: "2" * 40)
    case = AgentEvalCase(
        id="case-1",
        query="是否仍可起诉？",
        issues=["诉讼时效"],
        critical_facts=["还款日期"],
        expected_laws=["民法典:188"],
        expected_clarification="是否约定还款日期",
        important_claims=["可否起诉"],
    )

    def adapter(*_):
        return {
            "claims": [
                {
                    "text": "可否起诉",
                    "evidence_ids": ["民法典:188"],
                    "trace_ref": "trace://case-1/claim-1",
                }
            ],
            "detected_issues": ["诉讼时效"],
            "clarification": "是否约定还款日期",
            "trace_ref": "trace://case-1",
            "latency_ms": 50.0,
            "tool_calls": 1,
            "budget_exceeded": False,
        }

    existing = tmp_path / "existing.json"
    agent = tmp_path / "agent.json"
    existing_artifact = ArtifactProvenance(
        sha256="b" * 64,
        source_git_revision="2" * 40,
        source_execution_id="existing-capture",
    )
    agent_artifact = ArtifactProvenance(
        sha256="c" * 64,
        source_git_revision="2" * 40,
        source_execution_id="agent-capture",
    )
    write_report(
        cases=[case],
        frozen_hash="a" * 64,
        mode="existing_rag",
        adapter=adapter,
        adapter_identity=f"frozen-artifact:{existing_artifact.sha256}",
        artifact_provenance=existing_artifact,
        output=existing,
    )
    write_report(
        cases=[case],
        frozen_hash="a" * 64,
        mode="agent",
        adapter=adapter,
        adapter_identity=f"frozen-artifact:{agent_artifact.sha256}",
        artifact_provenance=agent_artifact,
        output=agent,
    )

    decision = check_agent_release(existing, agent)

    assert decision.allowed is True
    from scripts.eval_agent import EVALUATOR_VERSION as _EV

    assert decision.evaluator_version == _EV  # 透传当前评估器版本（v1.1.0 预注册后随动）
    assert decision.rubric_hash
