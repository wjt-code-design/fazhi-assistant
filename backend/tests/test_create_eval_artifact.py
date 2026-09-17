import json

import pytest
from pydantic import ValidationError

import scripts.eval_agent as eval_agent
from scripts.check_agent_release import check_agent_release
from scripts.create_eval_artifact import create_frozen_artifact, main
from scripts.eval_agent import freeze_hash, load_cases, load_frozen_artifact_adapter
from scripts.eval_agent import main as evaluate_main
from scripts.release_manifest import load_release_manifest


def _case(case_id: str) -> dict[str, object]:
    return {
        "id": case_id,
        "query": f"问题 {case_id}",
        "issues": ["争议焦点"],
        "critical_facts": ["关键事实"],
        "expected_laws": ["民法典:188"],
        "expected_clarification": None,
        "important_claims": ["结论"],
    }


def _answer(case_id: str) -> dict[str, object]:
    return {
        "id": case_id,
        "answer": {
            "claims": [{"text": "结论", "evidence_ids": ["民法典:188"], "trace_ref": "trace://capture/1"}],
            "detected_issues": ["争议焦点"],
            "trace_ref": "trace://capture/1",
            "latency_ms": 50.0,
            "tool_calls": 1,
        },
    }


def _inputs(tmp_path, *, answers=None):
    cases_path = tmp_path / "cases.json"
    answers_path = tmp_path / "answers.json"
    cases_path.write_text(json.dumps([_case("case-1"), _case("case-2")], ensure_ascii=False), encoding="utf-8")
    payload = {
        "schema_version": "legal-agent-eval-answers/v1",
        "cases": answers or [_answer("case-1"), _answer("case-2")],
    }
    answers_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return cases_path, answers_path


def _release_manifest(tmp_path, cases_path, *, revision="a" * 40):
    path = tmp_path / "release-manifest.json"
    payload = {
        "schema_version": "legal-agent-release-manifest/v1",
        "release_id": "legal-agent-v1-test-001",
        "candidate": {"git_revision": revision, "build_digest": "sha256:" + "b" * 64},
        "evaluation": {
            "case_set_sha256": freeze_hash(cases_path.read_bytes()),
            "evaluator_name": "legal-agent-deterministic-evaluator",
            "evaluator_version": "1.0.0",
            "rubric_hash": "c" * 64,
            "release_policy_sha256": "d" * 64,
        },
        "knowledge": {
            "corpus_manifest_sha256": "e" * 64,
            "index_manifest_sha256": "f" * 64,
            "jurisdictions": ["CN"],
            "law_as_of": "2026-09-02",
        },
        "runtime": {
            "provider": "test-provider",
            "model": "test-model",
            "model_snapshot": "test-snapshot",
            "prompt_bundle_sha256": "0" * 64,
            "tool_policy_sha256": "1" * 64,
            "config_sha256": "2" * 64,
        },
        "capture": {
            "protocol_sha256": "3" * 64,
            "retry_policy_sha256": "4" * 64,
            "timeout_seconds": 60,
            "concurrency": 1,
            "cache_policy": "disabled",
            "network_policy": "offline",
        },
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_create_frozen_artifact_preserves_case_order_and_is_readable_by_evaluator(tmp_path):
    cases_path, answers_path = _inputs(tmp_path)
    output = tmp_path / "agent-capture.json"

    artifact = create_frozen_artifact(
        cases_path=cases_path,
        answers_path=answers_path,
        mode="agent",
        source_git_revision="a" * 40,
        source_execution_id="offline-capture-20260902",
        output=output,
    )

    assert artifact.freeze_hash == freeze_hash(cases_path.read_bytes())
    assert [row.id for row in artifact.cases] == ["case-1", "case-2"]
    persisted = json.loads(output.read_text(encoding="utf-8"))
    assert persisted["source_execution_id"] == "offline-capture-20260902"
    cases, frozen_hash = load_cases(cases_path)
    adapter, _ = load_frozen_artifact_adapter(output, cases=cases, frozen_hash=frozen_hash, mode="agent")
    assert adapter(cases[0], "agent").claims[0].text == "结论"


def test_create_frozen_artifact_binds_a_verified_release_manifest_to_new_capture_evidence(tmp_path):
    cases_path, answers_path = _inputs(tmp_path)
    manifest_path = _release_manifest(tmp_path, cases_path)
    _, manifest_sha256 = load_release_manifest(manifest_path)
    output = tmp_path / "agent-capture.json"

    artifact = create_frozen_artifact(
        cases_path=cases_path,
        answers_path=answers_path,
        mode="agent",
        source_git_revision="a" * 40,
        source_execution_id="offline-capture-20260902",
        release_manifest=manifest_path,
        output=output,
    )

    assert artifact.schema_version == "legal-agent-eval-artifact/v2"
    assert artifact.release_manifest_sha256 == manifest_sha256


def test_create_frozen_artifact_rejects_a_manifest_for_a_different_candidate_or_case_set(tmp_path):
    cases_path, answers_path = _inputs(tmp_path)
    manifest_path = _release_manifest(tmp_path, cases_path, revision="b" * 40)

    with pytest.raises(ValueError, match="candidate revision"):
        create_frozen_artifact(
            cases_path=cases_path,
            answers_path=answers_path,
            mode="agent",
            source_git_revision="a" * 40,
            source_execution_id="offline-capture-20260902",
            release_manifest=manifest_path,
            output=tmp_path / "agent-capture.json",
        )


@pytest.mark.parametrize(
    "answers",
    [
        [_answer("case-1")],
        [_answer("case-2"), _answer("case-1")],
        [_answer("case-1"), _answer("case-1")],
    ],
)
def test_create_frozen_artifact_rejects_missing_reordered_or_duplicate_case_rows(tmp_path, answers):
    cases_path, answers_path = _inputs(tmp_path, answers=answers)

    with pytest.raises(ValueError, match="case ids do not match"):
        create_frozen_artifact(
            cases_path=cases_path,
            answers_path=answers_path,
            mode="agent",
            source_git_revision="a" * 40,
            source_execution_id="offline-capture-20260902",
            output=tmp_path / "agent-capture.json",
        )


def test_create_frozen_artifact_rejects_unknown_capture_fields_instead_of_storing_identity_data(tmp_path):
    cases_path, answers_path = _inputs(tmp_path)
    payload = json.loads(answers_path.read_text(encoding="utf-8"))
    payload["cases"][0]["conversation_id"] = "user-conversation-123"
    answers_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(ValidationError):
        create_frozen_artifact(
            cases_path=cases_path,
            answers_path=answers_path,
            mode="agent",
            source_git_revision="a" * 40,
            source_execution_id="offline-capture-20260902",
            output=tmp_path / "agent-capture.json",
        )


def test_create_frozen_artifact_rejects_stringified_answer_metrics(tmp_path):
    cases_path, answers_path = _inputs(tmp_path)
    payload = json.loads(answers_path.read_text(encoding="utf-8"))
    payload["cases"][0]["answer"]["latency_ms"] = "50.0"
    payload["cases"][0]["answer"]["tool_calls"] = "1"
    payload["cases"][0]["answer"]["budget_exceeded"] = "false"
    answers_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(ValidationError):
        create_frozen_artifact(
            cases_path=cases_path,
            answers_path=answers_path,
            mode="agent",
            source_git_revision="a" * 40,
            source_execution_id="offline-capture-20260902",
            output=tmp_path / "agent-capture.json",
        )


def test_create_frozen_artifact_refuses_to_overwrite_existing_evidence(tmp_path):
    cases_path, answers_path = _inputs(tmp_path)
    manifest_path = _release_manifest(tmp_path, cases_path)
    output = tmp_path / "agent-capture.json"
    output.write_text("immutable evidence\n", encoding="utf-8")

    exit_code = main(
        [
            "--mode",
            "agent",
            "--cases",
            str(cases_path),
            "--answers",
            str(answers_path),
            "--source-git-revision",
            "a" * 40,
            "--source-execution-id",
            "offline-capture-20260902",
            "--release-manifest",
            str(manifest_path),
            "--output",
            str(output),
        ]
    )

    assert exit_code == 2
    assert output.read_text(encoding="utf-8") == "immutable evidence\n"


def test_artifact_cli_requires_policy_and_protocol_before_creating_any_evidence(tmp_path):
    cases_path, answers_path = _inputs(tmp_path)
    manifest_path = _release_manifest(tmp_path, cases_path)
    output = tmp_path / "agent-capture.json"

    exit_code = main(
        [
            "--mode",
            "agent",
            "--cases",
            str(cases_path),
            "--answers",
            str(answers_path),
            "--source-git-revision",
            "a" * 40,
            "--source-execution-id",
            "capture-001",
            "--release-manifest",
            str(manifest_path),
            "--output",
            str(output),
        ]
    )

    assert exit_code == 2
    assert not output.exists()


def test_create_frozen_artifact_rejects_invalid_provenance_before_writing(tmp_path):
    cases_path, answers_path = _inputs(tmp_path)

    with pytest.raises(ValidationError):
        create_frozen_artifact(
            cases_path=cases_path,
            answers_path=answers_path,
            mode="agent",
            source_git_revision="not-a-commit",
            source_execution_id="\n",
            output=tmp_path / "agent-capture.json",
        )


@pytest.mark.parametrize("source_execution_id", ["C:/Users/33393/capture.json", "capture?user=123", "采集-001"])
def test_create_frozen_artifact_rejects_non_opaque_execution_ids(tmp_path, source_execution_id):
    cases_path, answers_path = _inputs(tmp_path)

    with pytest.raises(ValidationError, match="source_execution_id"):
        create_frozen_artifact(
            cases_path=cases_path,
            answers_path=answers_path,
            mode="agent",
            source_git_revision="a" * 40,
            source_execution_id=source_execution_id,
            output=tmp_path / "agent-capture.json",
        )


def test_offline_artifacts_flow_through_evaluator_and_release_checker(tmp_path, monkeypatch):
    monkeypatch.setattr(eval_agent, "_git_revision", lambda: "2" * 40)
    cases_path, agent_answers_path = _inputs(tmp_path)
    existing_answers_path = tmp_path / "existing-answers.json"
    existing_answers_path.write_bytes(agent_answers_path.read_bytes())
    existing_artifact = tmp_path / "existing-capture.json"
    agent_artifact = tmp_path / "agent-capture.json"
    existing_report = tmp_path / "existing-report.json"
    agent_report = tmp_path / "agent-report.json"

    create_frozen_artifact(
        cases_path=cases_path,
        answers_path=existing_answers_path,
        mode="existing_rag",
        source_git_revision="2" * 40,
        source_execution_id="offline-existing-rag-capture",
        output=existing_artifact,
    )
    create_frozen_artifact(
        cases_path=cases_path,
        answers_path=agent_answers_path,
        mode="agent",
        source_git_revision="2" * 40,
        source_execution_id="offline-agent-capture",
        output=agent_artifact,
    )

    assert (
        evaluate_main(
            [
                "--mode",
                "existing_rag",
                "--cases",
                str(cases_path),
                "--artifact",
                str(existing_artifact),
                "--output",
                str(existing_report),
            ]
        )
        == 0
    )
    assert (
        evaluate_main(
            [
                "--mode",
                "agent",
                "--cases",
                str(cases_path),
                "--artifact",
                str(agent_artifact),
                "--output",
                str(agent_report),
            ]
        )
        == 0
    )

    decision = check_agent_release(existing_report, agent_report)

    assert decision.allowed is True
    assert decision.sample_size == 2
    assert decision.reasons == []
