"""V2-T1（2026-09-09）：R1–R12 复核 sidecar 校验与聚合的测试。

合成正例仅证明聚合逻辑可达（同材料可重算），不构成产品成功证明（教学手册第六课）。
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from scripts.review_sidecar import (
    REQUIRED_REVIEW_RULES,
    ReviewEntry,
    ReviewSidecar,
    aggregate_review,
    aggregate_run,
    validate_sidecar,
)

_SHA = "a" * 64
_RUN = "gate2-run-gate5-dev-run-11"


def _review(
    rule: str,
    *,
    status: str = "PASS",
    reviewer: str = "独立复核者-甲",
    refs=None,
    reason: str = "逐 claim 对照证据核实",
):
    return ReviewEntry(
        rule=rule,
        status=status,
        reviewer=reviewer,
        evidence_refs=list(refs) if refs is not None else ["mechanical_diagnostics.R2=true"],
        reason=reason,
    )


def _full_sidecar(**overrides) -> ReviewSidecar:
    reviews = [
        _review("R1_primary_facts_first_round", refs=["final_text.section1", "frozen-cases C02 事实清单"]),
        _review("R2_specific_prompt"),
        _review("R3_no_repeat"),
        _review("R4_correction_handling", refs=["session.correction_exchange"]),
        _review("R5_max_two_rounds"),
        _review("R6_six_sections_header"),
        _review("R6_content_match", refs=["final_text.full", "six-section mapping"]),
        _review("R7_all_required_issues", refs=["required_issues_hit_mech", "final_text.sections"]),
        _review("R8_required_statutes", refs=["required_statute_hits"]),
        _review("R9_claim_evidence_binding", refs=["claim_evidence_bindings", "claim texts vs snippets"]),
        _review("R10_no_unconfirmed_as_fact", refs=["final_text claims vs unknown_facts"]),
        _review("R11_actionable_advice", refs=["final_text.advice"]),
        _review("R12_redlines"),
    ]
    payload = {"schema_version": 1, "run_id": _RUN, "sessions_sha256": _SHA, "case_id": "C02", "reviews": reviews}
    payload.update(overrides)
    return ReviewSidecar.model_validate(payload)


def test_synthetic_complete_positive_review_reaches_reviewed_closure():
    """合成完整正例 → REVIEWED_CLOSURE（仅证明聚合器可达，不算产品成功）。"""
    result = aggregate_review(_full_sidecar(), expected_run_id=_RUN, expected_sessions_sha256=_SHA)
    assert result["verdict"] == "REVIEWED_CLOSURE"
    assert result["problems"] == []


def test_required_rule_set_has_thirteen_items_with_r6_subitems():
    """必需规则集 = R1–R12 + R6 复合子项；不能只数 12 行。"""
    assert len(REQUIRED_REVIEW_RULES) == 13
    assert {"R6_six_sections_header", "R6_content_match"}.issubset(REQUIRED_REVIEW_RULES)


def test_missing_required_rule_is_pending_not_closure():
    sidecar = _full_sidecar()
    sidecar.reviews = [r for r in sidecar.reviews if r.rule != "R7_all_required_issues"]
    result = aggregate_review(sidecar)
    assert result["verdict"] == "PENDING_REVIEW"
    assert "missing required review rule: R7_all_required_issues" in result["problems"]


def test_duplicate_rule_rejected():
    sidecar = _full_sidecar()
    sidecar.reviews.append(_review("R2_specific_prompt"))
    problems = validate_sidecar(sidecar)
    assert "duplicate review rule: R2_specific_prompt x2" in problems
    assert aggregate_review(sidecar)["verdict"] == "INVALID"


def test_unknown_rule_rejected():
    sidecar = _full_sidecar()
    sidecar.reviews.append(_review("R13_made_up"))
    assert aggregate_review(sidecar)["verdict"] == "INVALID"


def test_run_id_mismatch_is_invalid():
    result = aggregate_review(_full_sidecar(), expected_run_id="gate2-run-other")
    assert result["verdict"] == "INVALID"
    assert any("run_id mismatch" in p for p in result["problems"])


def test_sessions_sha256_mismatch_is_invalid():
    result = aggregate_review(_full_sidecar(), expected_sessions_sha256="b" * 64)
    assert result["verdict"] == "INVALID"
    assert any("sessions_sha256 mismatch" in p for p in result["problems"])


def test_placeholder_sha256_rejected():
    sidecar = _full_sidecar(sessions_sha256="待填实际哈希")
    assert aggregate_review(sidecar)["verdict"] == "INVALID"


def test_placeholder_run_id_rejected():
    sidecar = _full_sidecar(run_id="待填真实 run")
    assert aggregate_review(sidecar)["verdict"] == "INVALID"


def test_explicit_fail_is_failed_even_if_everything_else_passes():
    sidecar = _full_sidecar()
    sidecar.reviews[0] = _review(
        "R1_primary_facts_first_round", status="FAIL", refs=["final_text.section1"], reason="首段未先列已确认事实"
    )
    result = aggregate_review(sidecar)
    assert result["verdict"] == "FAILED"
    assert result["failed_rules"] == ["R1_primary_facts_first_round"]


def test_review_status_is_pending_not_closure():
    sidecar = _full_sidecar()
    sidecar.reviews[7] = _review("R7_all_required_issues", status="REVIEW", reason="尚未取得逐 issue 支撑证据")
    result = aggregate_review(sidecar)
    assert result["verdict"] == "PENDING_REVIEW"
    assert "R7_all_required_issues" in result["pending_rules"]


def test_placeholder_reviewer_is_pending():
    sidecar = _full_sidecar()
    sidecar.reviews[9] = _review("R9_claim_evidence_binding", reviewer="待填独立复核者")
    result = aggregate_review(sidecar)
    assert result["verdict"] == "PENDING_REVIEW"
    assert "R9_claim_evidence_binding" in result["pending_rules"]


def test_pass_without_evidence_refs_is_pending():
    sidecar = _full_sidecar()
    sidecar.reviews[10] = _review("R10_no_unconfirmed_as_fact", refs=[])
    assert aggregate_review(sidecar)["verdict"] == "PENDING_REVIEW"


def test_pass_with_placeholder_evidence_ref_is_pending():
    sidecar = _full_sidecar()
    sidecar.reviews[11] = _review("R11_actionable_advice", refs=["待填证据"])
    assert aggregate_review(sidecar)["verdict"] == "PENDING_REVIEW"


def test_run_level_aggregation_requires_all_cases_closure():
    positive = aggregate_review(_full_sidecar(), expected_run_id=_RUN, expected_sessions_sha256=_SHA)
    pending_sidecar = _full_sidecar()
    pending_sidecar.reviews[3] = _review("R4_correction_handling", status="REVIEW", reason="未决")
    pending = aggregate_review(pending_sidecar)
    failed_sidecar = _full_sidecar()
    failed_sidecar.reviews[0] = _review("R1_primary_facts_first_round", status="FAIL", reason="x")
    failed = aggregate_review(failed_sidecar)

    assert aggregate_run([positive, dict(pending)])["verdict"] == "PENDING_REVIEW"
    assert aggregate_run([positive, dict(failed)])["verdict"] == "FAILED"
    assert aggregate_run([positive, positive])["verdict"] == "REVIEWED_CLOSURE"
    assert aggregate_run([])["verdict"] == "PENDING_REVIEW"  # 无证据不通过


def test_sidecar_rejects_unknown_extra_fields():
    with pytest.raises(ValidationError):
        ReviewSidecar.model_validate(
            {
                "schema_version": 1,
                "run_id": _RUN,
                "sessions_sha256": _SHA,
                "case_id": "C02",
                "reviews": [_review("R2_specific_prompt").model_dump()],
                "auto_passed": True,  # 不允许任何"自动通过"旁路字段
            }
        )


def test_required_rules_match_frozen_judge_verdict_keys():
    """T1 审查修复（AST 哨兵）：REQUIRED_REVIEW_RULES 必须与冻结 judge 的
    full_case_verdict 字面量键（R 规则键）一致——judge 改名时本测试红，提醒同步，
    不触碰冻结 judge 文件本身（不 import、不执行其逻辑）。"""
    import ast
    from pathlib import Path

    judge_src = Path(__file__).resolve().parents[1] / "scripts" / "gate5_judge.py"
    tree = ast.parse(judge_src.read_text(encoding="utf-8"))
    verdict_keys: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Dict):
            target_names = {t.id for t in node.targets if isinstance(t, ast.Name)}
            if "verdict" in target_names:
                for key_node in node.value.keys:
                    assert isinstance(key_node, ast.Constant) and isinstance(key_node.value, str)
                    if key_node.value.startswith("R") and key_node.value[1:2].isdigit():
                        verdict_keys.add(key_node.value)
    assert len(verdict_keys) == 13, f"judge verdict R-keys: {sorted(verdict_keys)}"
    assert verdict_keys == set(REQUIRED_REVIEW_RULES)
