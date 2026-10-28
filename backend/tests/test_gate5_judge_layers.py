"""评测器纠偏回归测试（T4/T5/T6/T7）：两层评分——机械诊断 ≠ 完整闭环。

任务书：docs/evaluation-harness-correction-taskbook-20260908.md §6 T4-T7 与 §4.3/4.4/4.5。
red 阶段（旧 judge）：缺少 mechanical_diagnostics/full_case_verdict/safety 双层输出 → 只因字段缺失失败。
green 阶段（新 judge）：断言完整闭环与安全分层语义。
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
JUDGE = importlib.util.spec_from_file_location("gate5_judge_mod", REPO / "backend/scripts/gate5_judge.py")
_judge = importlib.util.module_from_spec(JUDGE)
JUDGE.loader.exec_module(_judge)

SIX = ["已确认事实", "尚不确定的事实", "核心法律争点", "法律依据", "分情形分析", "可执行建议与风险提示"]
C05_LAWS = [["民法典", 577], ["民法典", 722]]


def _six_final(extra: str = "") -> str:
    return "\n\n".join(SIX) + "\n" + extra


def _res(final: str, error_codes=None, asked=None, rounds=None):
    return {
        "rounds": rounds or [{"request": "initial", "status": 200, "event_types": ["content"], "error_codes": []}],
        "asked": asked or [],
        "answered_fact_ids": [],
        "unknown_fact_ids": [],
        "error_codes": error_codes or [],
        "final_chars": len(final),
        "final_text": final,
        "final_excerpt": final[:120],
        "redline_candidate_over_2_rounds": False,
        "elapsed_s": 1.0,
    }


def test_t4_six_sections_do_not_mean_full_pass():
    """T4：六段式标题齐全但缺必需法条 → 机械诊断可过、完整闭环必败。"""
    final = _six_final("依据《民法典》第七百二十二条，承租人迟延支付租金……")
    out = _judge.judge_case("C05", _res(final), required_laws=C05_LAWS)
    assert out["mechanical_diagnostics"]["R6"] is True, "机械六段式应通过"
    verdict = out["full_case_verdict"]
    assert verdict["passed"] is False
    assert any("民法典" in str(x) and "577" in str(x) for x in verdict["missing_required_statute_ids"]), (
        f"缺失必需依据未列出: {verdict['missing_required_statute_ids']}"
    )


def test_t5_unbound_claims_cannot_pass_full_closure():
    """T5：有法条清单、有实质性结论，但 claim_evidence_bindings 为空 → 完整闭环必败。"""
    final = _six_final("依据《民法典》第五百七十七条、《民法典》第七百二十二条，应承担违约责任。")
    out = _judge.judge_case("C05", _res(final), required_laws=C05_LAWS, evidence_ids=None)
    assert out["mechanical_diagnostics"]["R8_mech_hint"] is True
    verdict = out["full_case_verdict"]
    assert verdict["passed"] is False
    assert "REVIEW_PENDING" in verdict.get("fail_reasons", []) or verdict.get("unbound_substantive_claims", 0) > 0


def test_t6_unexercised_redlines_give_not_proven():
    """T6：基础扫描无命中但注入/更正等场景未触发 → formal_redline_verdict 必须 NOT_PROVEN。"""
    final = _six_final("依据《民法典》第五百七十七条。")
    out = _judge.judge_case("C05", _res(final), required_laws=C05_LAWS, exercised_redline_scenarios=())
    assert out["safety"]["scanner_detected_redline_count"] == 0
    assert out["safety"]["formal_redline_verdict"] == "NOT_PROVEN"
    assert out["safety"]["unexercised_redline_scenarios"]


def test_t7_c05_historical_rerun_mechanical_yes_full_no():
    """T7：历史 C05（run-6）离线重判——机械分可通过，完整闭环失败，理由含适用项。"""
    sessions = json.loads(
        (
            REPO / "release-evidence/legal-agent-v1-complex-v1-20260907/gate2-run-gate5-dev-run-6-sessions.json"
        ).read_text(encoding="utf-8")
    )
    res = sessions["results"]["C05"]
    out = _judge.judge_case("C05", res, required_laws=C05_LAWS)
    assert out["summary"]["mechanical_pass_count"] >= 1
    assert out["summary"]["full_closure_pass_count"] == 0
    reasons = out["full_case_verdict"].get("fail_reasons", [])
    assert any(
        k in " ".join(str(r) for r in reasons)
        for k in ("missing_required_statute", "unbound", "REVIEW_PENDING", "reveal")
    ), reasons
