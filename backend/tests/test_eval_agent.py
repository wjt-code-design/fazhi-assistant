import json

import pytest
from pydantic import ValidationError

from scripts.eval_agent import (
    AgentEvalAnswer,
    AgentEvalCase,
    evaluate_case,
    freeze_hash,
    load_cases,
    load_frozen_artifact_adapter,
    load_frozen_artifact_provenance,
    main,
    write_report,
)


def _case() -> AgentEvalCase:
    return AgentEvalCase(
        id="loan-limitations-01",
        query="借款到期后多年未还，是否仍可起诉？",
        issues=["诉讼时效"],
        critical_facts=["还款日期"],
        expected_laws=["民法典:188"],
        expected_clarification="是否约定还款日期",
        important_claims=["可否起诉"],
    )


def _artifact(tmp_path, *, cases_path, mode="agent", freeze_hash_value=None, rows=None):
    frozen_hash = freeze_hash_value or freeze_hash(cases_path.read_bytes())
    payload = {
        "schema_version": "legal-agent-eval-artifact/v1",
        "mode": mode,
        "freeze_hash": frozen_hash,
        "source_git_revision": "2" * 40,
        "source_execution_id": "offline-capture-001",
        "cases": rows
        if rows is not None
        else [
            {
                "id": "loan-limitations-01",
                "answer": {
                    "claims": [
                        {
                            "text": "可否起诉",
                            "evidence_ids": ["民法典:188"],
                            "trace_ref": "trace://agent-run-1/claim-1",
                        }
                    ],
                    "detected_issues": ["诉讼时效"],
                    "clarification": "是否约定还款日期",
                    "trace_ref": "trace://agent-run-1",
                    "latency_ms": 125.0,
                    "tool_calls": 2,
                    "budget_exceeded": False,
                },
            }
        ],
    }
    path = tmp_path / "frozen-artifact.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def test_eval_cases_have_stable_required_fields_and_hash(tmp_path):
    path = tmp_path / "cases.json"
    payload = [_case().model_dump()]
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    cases, frozen_hash = load_cases(path)

    assert cases[0].id == "loan-limitations-01"
    assert len(frozen_hash) == 64
    # v1.1.0（2026-09-06 预注册）：AgentEvalCase 新增 acceptable_clarification_keywords
    # 可选字段（default_factory=list），model_dump 序列化含该键 → 钉值随之更新。
    assert frozen_hash == "06fca4344dc354116aa6b7d3a40d1500e3fd8358e7316ca65cf4fdb4920337ef"


def test_recomputed_artifact_provenance_requires_the_exact_release_boundary(tmp_path):
    cases_path = tmp_path / "cases.json"
    cases_path.write_text(json.dumps([_case().model_dump()], ensure_ascii=False), encoding="utf-8")
    cases, frozen_hash = load_cases(cases_path)
    artifact_path = _artifact(tmp_path, cases_path=cases_path)
    payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    payload["schema_version"] = "legal-agent-eval-artifact/v2"
    payload["release_manifest_sha256"] = "a" * 64
    artifact_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    provenance = load_frozen_artifact_provenance(
        artifact_path,
        mode="agent",
        frozen_hash=frozen_hash,
        release_manifest_sha256="a" * 64,
        case_ids=[case.id for case in cases],
    )

    assert provenance.sha256 == freeze_hash(artifact_path.read_bytes())
    with pytest.raises(ValueError, match="release evidence boundary"):
        load_frozen_artifact_provenance(
            artifact_path,
            mode="agent",
            frozen_hash=frozen_hash,
            release_manifest_sha256="b" * 64,
            case_ids=[case.id for case in cases],
        )


def test_load_cases_rejects_missing_required_field(tmp_path):
    path = tmp_path / "cases.json"
    invalid = _case().model_dump()
    invalid.pop("expected_laws")
    path.write_text(json.dumps([invalid], ensure_ascii=False), encoding="utf-8")

    with pytest.raises(ValidationError):
        load_cases(path)


def test_eval_rejects_untraceable_claim_support():
    result = evaluate_case(_case(), AgentEvalAnswer(claims=[{"text": "可起诉", "evidence_ids": []}]))

    assert result.evidence_coverage == 0.0
    assert result.unsupported_claims == ["可起诉"]


def test_eval_counts_traceable_claim_support_only_once_per_required_claim():
    case = _case().model_copy(update={"important_claims": ["可否起诉", "时效起算"]})
    answer = AgentEvalAnswer(
        claims=[
            {"text": "可否起诉", "evidence_ids": ["民法典:188"]},
            {"text": "时效起算", "evidence_ids": []},
            {"text": "补充说明", "evidence_ids": ["民法典:188"]},
        ]
    )

    result = evaluate_case(case, answer)

    assert result.evidence_coverage == 0.5
    assert result.unsupported_claims == ["时效起算"]


def test_eval_requires_expected_law_as_primary_evidence():
    case = _case()
    answer = AgentEvalAnswer(
        claims=[
            {"text": "可否起诉", "evidence_ids": ["x"]},
            {"text": "空证据", "evidence_ids": []},
            {"text": "合法证据", "evidence_ids": ["民法典:188"]},
        ]
    )

    result = evaluate_case(case, answer)

    assert result.evidence_coverage == 0.0
    assert result.unsupported_claims == ["可否起诉", "空证据"]

    valid_result = evaluate_case(case, AgentEvalAnswer(claims=[{"text": "可否起诉", "evidence_ids": ["民法典:188"]}]))
    assert valid_result.evidence_coverage == 1.0
    assert valid_result.unsupported_claims == []


def test_report_includes_reproducible_execution_environment(tmp_path):
    output = tmp_path / "report.json"

    report = write_report(
        cases=[_case()],
        frozen_hash="a" * 64,
        mode="existing_rag",
        adapter=lambda *_: {"claims": []},
        output=output,
    )

    persisted = json.loads(output.read_text(encoding="utf-8"))
    assert report["environment"] == persisted["environment"]
    assert report["environment"]["python_version"]
    assert report["environment"]["platform"]


def test_report_with_adapter_contains_versioned_recomputable_case_evidence(tmp_path):
    output = tmp_path / "report.json"

    report = write_report(
        cases=[_case()],
        frozen_hash="a" * 64,
        mode="agent",
        adapter=lambda *_: {
            "claims": [
                {
                    "text": "可否起诉",
                    "evidence_ids": ["民法典:188"],
                    "trace_ref": "trace://run-1/claim-1",
                }
            ],
            "detected_issues": ["诉讼时效"],
            "clarification": "是否约定还款日期",
            "trace_ref": "trace://run-1",
            "latency_ms": 125.0,
            "tool_calls": 2,
            "budget_exceeded": False,
        },
        output=output,
    )

    assert report["release_eligible"] is True
    assert report["evaluator"]["name"] == "legal-agent-deterministic-evaluator"
    assert report["evaluator"]["version"]
    assert len(report["evaluator"]["rubric_hash"]) == 64
    assert report["metrics"]["complex_task_quality"] == 1.0
    assert report["metrics"]["issue_recall"] == 1.0
    assert report["metrics"]["clarification_precision"] == 1.0
    assert report["metrics"]["tool_calls"] == 2
    assert report["cases"][0]["result"]["trace_ref"] == "trace://run-1"


def test_cli_without_adapter_writes_plumbing_report_that_cannot_pass_release(tmp_path):
    cases = tmp_path / "cases.json"
    output = tmp_path / "report.json"
    cases.write_text(json.dumps([_case().model_dump()], ensure_ascii=False), encoding="utf-8")

    exit_code = main(["--mode", "agent", "--cases", str(cases), "--output", str(output)])
    report = json.loads(output.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert report["release_eligible"] is False
    assert "NO_ADAPTER" in report["ineligibility_reasons"]


def test_cli_refuses_to_overwrite_existing_evaluation_evidence(tmp_path):
    cases = tmp_path / "cases.json"
    output = tmp_path / "report.json"
    cases.write_text(json.dumps([_case().model_dump()], ensure_ascii=False), encoding="utf-8")
    output.write_text("immutable evidence\n", encoding="utf-8")

    exit_code = main(["--mode", "agent", "--cases", str(cases), "--output", str(output)])

    assert exit_code == 2
    assert output.read_text(encoding="utf-8") == "immutable evidence\n"


def test_cli_evaluates_only_same_hash_frozen_artifact_and_records_source_provenance(tmp_path):
    cases_path = tmp_path / "cases.json"
    output = tmp_path / "report.json"
    cases_path.write_text(json.dumps([_case().model_dump()], ensure_ascii=False), encoding="utf-8")
    artifact = _artifact(tmp_path, cases_path=cases_path)

    exit_code = main(
        [
            "--mode",
            "agent",
            "--cases",
            str(cases_path),
            "--artifact",
            str(artifact),
            "--output",
            str(output),
        ]
    )
    report = json.loads(output.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert report["release_eligible"] is True
    assert report["evaluator"]["adapter"].startswith("frozen-artifact:")
    assert report["source_artifact"] == {
        "sha256": freeze_hash(artifact.read_bytes()),
        "source_git_revision": "2" * 40,
        "source_execution_id": "offline-capture-001",
    }


@pytest.mark.parametrize(
    ("mode", "freeze_hash_value", "expected_message"),
    [
        ("existing_rag", None, "mode does not match"),
        ("agent", "f" * 64, "freeze_hash does not match"),
    ],
)
def test_frozen_artifact_adapter_rejects_cross_mode_or_cross_dataset_evidence(
    tmp_path, mode, freeze_hash_value, expected_message
):
    cases_path = tmp_path / "cases.json"
    cases_path.write_text(json.dumps([_case().model_dump()], ensure_ascii=False), encoding="utf-8")
    cases, frozen_hash = load_cases(cases_path)
    artifact = _artifact(tmp_path, cases_path=cases_path, mode=mode, freeze_hash_value=freeze_hash_value)

    with pytest.raises(ValueError, match=expected_message):
        load_frozen_artifact_adapter(artifact, cases=cases, frozen_hash=frozen_hash, mode="agent")


def test_frozen_artifact_adapter_rejects_missing_or_duplicate_case_evidence(tmp_path):
    cases_path = tmp_path / "cases.json"
    cases_path.write_text(json.dumps([_case().model_dump()], ensure_ascii=False), encoding="utf-8")
    cases, frozen_hash = load_cases(cases_path)
    artifact = _artifact(tmp_path, cases_path=cases_path, rows=[])

    with pytest.raises(ValueError, match="case ids do not match"):
        load_frozen_artifact_adapter(artifact, cases=cases, frozen_hash=frozen_hash, mode="agent")

    duplicate = _artifact(
        tmp_path,
        cases_path=cases_path,
        rows=[
            {"id": "loan-limitations-01", "answer": {}},
            {"id": "loan-limitations-01", "answer": {}},
        ],
    )
    with pytest.raises(ValidationError, match="case identifiers must be unique"):
        load_frozen_artifact_adapter(duplicate, cases=cases, frozen_hash=frozen_hash, mode="agent")


def test_loaded_frozen_artifact_cannot_be_reused_under_a_different_mode(tmp_path):
    cases_path = tmp_path / "cases.json"
    cases_path.write_text(json.dumps([_case().model_dump()], ensure_ascii=False), encoding="utf-8")
    cases, frozen_hash = load_cases(cases_path)
    artifact = _artifact(tmp_path, cases_path=cases_path)
    adapter, _ = load_frozen_artifact_adapter(artifact, cases=cases, frozen_hash=frozen_hash, mode="agent")

    with pytest.raises(ValueError, match="mode does not match"):
        adapter(cases[0], "existing_rag")


def test_frozen_artifact_rejects_unsafe_execution_identifier(tmp_path):
    cases_path = tmp_path / "cases.json"
    cases_path.write_text(json.dumps([_case().model_dump()], ensure_ascii=False), encoding="utf-8")
    cases, frozen_hash = load_cases(cases_path)
    artifact = _artifact(tmp_path, cases_path=cases_path)
    payload = json.loads(artifact.read_text(encoding="utf-8"))
    payload["source_execution_id"] = "capture-1\nforged-log-entry"
    artifact.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(ValidationError):
        load_frozen_artifact_adapter(artifact, cases=cases, frozen_hash=frozen_hash, mode="agent")


def test_clarification_matching_v1_1_accepts_curated_keyword_paraphrase():
    """v1.1.0：合法改述性反问经人工策展关键词判定合格（预注册语义）。"""
    from scripts.eval_agent import AgentEvalCase, _clarification_matches

    case = AgentEvalCase(
        id="c1",
        query="q",
        issues=["i"],
        critical_facts=["是否存在催收或承认债务"],
        expected_laws=["民法典:188"],
        expected_clarification="借条是否约定还款日期，之后是否催收或对方承认债务？",
        important_claims=["是否可能超过诉讼时效"],
        acceptable_clarification_keywords=["主张过权利", "催收"],
    )
    # 逐字匹配（原语义保持）
    assert _clarification_matches(case, " 借条是否约定还款日期，之后是否催收或对方承认债务？ ") is True
    # 合法改述：不含预期原文但命中策展关键词
    assert _clarification_matches(case, "债权人是否在2021年至2024年期间向债务人主张过权利") is True
    # 关键词未命中且非逐字 → 不合格
    assert _clarification_matches(case, "合同签订地点在哪里") is False
    # 未反问 → 不合格
    assert _clarification_matches(case, None) is False
    # 无策展关键词的题回退为仅逐字
    bare = case.model_copy(update={"acceptable_clarification_keywords": []})
    assert _clarification_matches(bare, "债权人向债务人主张过权利") is False


def test_v1_2_expect_clarification_case_rewards_correct_ask():
    """v1.2.0 预注册语义：期望反问题正确反问 → 该题满分 1.0；
    反问错/不问 → 按答案内容质量给部分分。
    （旧 v1.1 口径下正确反问只得 mean(recall,coverage,1)/3 < 1.0，此测试本会红。）"""
    from scripts.eval_agent import AgentEvalAnswer, AgentEvalCase, evaluate_case

    case = AgentEvalCase(
        id="c1",
        query="q",
        issues=["时效"],
        critical_facts=["催收"],
        expected_laws=["民法典:188"],
        expected_clarification="是否催收过？",
        important_claims=["是否超过诉讼时效"],
        acceptable_clarification_keywords=["催收", "主张过权利"],
    )
    correct_ask = AgentEvalAnswer(claims=[], clarification="债权人是否催收或主张过权利？")
    no_ask = AgentEvalAnswer(claims=[], clarification=None)
    wrong_ask = AgentEvalAnswer(claims=[], clarification="今天天气如何？")

    assert evaluate_case(case, correct_ask).complex_task_quality == 1.0
    no_ask_result = evaluate_case(case, no_ask)
    assert no_ask_result.complex_task_quality == 0.0  # 空答案 → recall/coverage 均 0
    wrong_ask_result = evaluate_case(case, wrong_ask)
    assert wrong_ask_result.complex_task_quality == 0.0
