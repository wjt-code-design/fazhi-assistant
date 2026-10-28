"""R15 法律版本适用绊线（2026-09-18/19 批次）。

期望值的独立来源（不是本实现）：
- 分水岭 2021-01-01、普通诉讼时效 3 年、劳动仲裁 1 年 —— `limitation_calc.py:7-15`
  代码级常量段自述的法条依据（《民法典》188/1260、《民法通则》135、《劳动争议调解仲裁法》27），
  与 `backend/domain_rules.py:162-170` 的「民事·诉讼时效 → (民法典, 第一百八十八条)」登记一致
  （该表**接线状态=暂存未接线**，见 `:104-111`；本测试只取其**法条知识**作独立来源，不依赖其接线）；
- 「跨 2021 分水岭拿 today 当基准日必然算错时效」——
  `docs/external-harness-plan-gap-analysis-20260918.md:118`（§五 R15 行：「基准日默认设为今天 →
  跨法修订场景必然错」）与 `:136-137`（T1 = 方案称"最高频最致命"那类 + §六 判断 2）。
"""

from __future__ import annotations

from datetime import date

import pytest

import settings as settings_module
from legal_workflow.limitation_calc import law_version_crosses_watershed
from legal_workflow.verifier import DeterministicVerifier, VerificationVerdict, render_verified
from legal_workflow.writer import EvidenceBoundedWriter
from routing_metrics import is_technical_fallback_reason
from tests.test_phantom_check import SingleClaimGenerator, writer_state

_TIMING_CLAIM = "本案请求权适用《民法典》第一百八十八条，诉讼时效期间为三年。"
_PRE = ["2019年3月5日双方签订借款合同，对方当日未付款"]
_POST = ["2023年8月1日对方拖欠货款"]
_AS_OF_TODAY = date(2026, 9, 18)


def test_pre_watershed_fact_with_post_watershed_baseline_is_conflict():
    assert law_version_crosses_watershed(_TIMING_CLAIM, _PRE, _AS_OF_TODAY) is True


def test_same_side_of_watershed_is_not_conflict():
    assert law_version_crosses_watershed(_TIMING_CLAIM, _POST, _AS_OF_TODAY) is False


def test_injected_pre_watershed_baseline_matches_pre_watershed_fact():
    assert law_version_crosses_watershed(_TIMING_CLAIM, _PRE, date(2020, 6, 1)) is False


def test_missing_baseline_cannot_judge():
    assert law_version_crosses_watershed(_TIMING_CLAIM, _PRE, None) is False


def test_no_parseable_fact_date_does_not_trip():
    """无日期 ≠ 有冲突：拦它会误伤「诉讼时效是几年」这类纯法条陈述（2026-09-18 决策）。"""
    assert law_version_crosses_watershed(_TIMING_CLAIM, ["对方拖欠货款未还"], _AS_OF_TODAY) is False


def test_claim_without_limitation_assertion_does_not_trip():
    assert law_version_crosses_watershed("2019年3月5日的借款到期未还。", _PRE, _AS_OF_TODAY) is False


def test_labor_arbitration_is_outside_the_civil_code_watershed():
    """劳动仲裁时效依据劳调法 27 条（2008 年生效），与民法典分水岭无关。"""
    claim = "仲裁时效为一年，自当事人知道权利被侵害之日起算。"
    assert law_version_crosses_watershed(claim, _PRE, _AS_OF_TODAY) is False


def test_chinese_numeral_dates_are_not_parsed():
    """extract_dates 刻意只认阿拉伯数字日期 → 判不了就不拦（fail-open，模块边界一致）。"""
    assert law_version_crosses_watershed(_TIMING_CLAIM, ["二〇一九年三月五日借款"], _AS_OF_TODAY) is False


# ---- verifier 门（law_version_tripwire_check，默认关）----


def _state_with_pre_watershed_fact():
    """把 writer_state 的事实换成分水岭前（2019），其余结构复用 R12 已验证可用的 fixture。"""
    state = writer_state()
    state.issues[0].facts[0].statement = "2019年3月5日对方拖欠货款"
    return state


def _draft_for(state):
    """`_TIMING_CLAIM` 在现行 verifier（开关关）下实测 PASS——2019 与 2023 两种事实都是，
    正是本门要补的缺口：跨分水岭的错答今天能一路交付（探针见 dispatch 记录）。"""
    result = EvidenceBoundedWriter(SingleClaimGenerator(_TIMING_CLAIM)).render(state)
    assert result.draft is not None, "前置失效：草稿没生成，本组测试需重做"
    return result.draft


def test_tripwire_flag_defaults_off():
    assert settings_module.Settings.model_fields["law_version_tripwire_check"].default is False


def test_verifier_flag_off_leaves_cross_watershed_draft_passing(monkeypatch: pytest.MonkeyPatch):
    """默认关：同一条 draft 照常通过（行为逐字不变，基线安全）。"""
    monkeypatch.setattr(settings_module.settings, "law_version_tripwire_check", False)
    state = _state_with_pre_watershed_fact()
    verdict = DeterministicVerifier().verify(state, _draft_for(state), law_as_of=_AS_OF_TODAY)
    assert verdict.verdict is VerificationVerdict.PASS


def test_verifier_flag_on_blocks_cross_watershed_draft(monkeypatch: pytest.MonkeyPatch):
    """开关开 + 2019 事实 + today 基准 + claim 断言民事时效结论 → 终态拒答。"""
    monkeypatch.setattr(settings_module.settings, "law_version_tripwire_check", True)
    state = _state_with_pre_watershed_fact()
    verdict = DeterministicVerifier().verify(state, _draft_for(state), law_as_of=_AS_OF_TODAY)
    assert verdict.verdict is VerificationVerdict.FAIL_SAFE
    assert verdict.reason_code == "LAW_VERSION_WATERSHED_MISMATCH"
    # 可归因：失败路径必须带出**被判定的那句原文**（2026-09-19 真实运行臂暴露：不带 draft/state 时
    # 线上日志只剩 verdict=FAIL_SAFE，分不清哪句按旧年份答了新时代的法）。
    # 刻意不逐字比对 claim：writer 会把全角逗号归一成半角（实测 '，'→','），逐字比会测到归一化上。
    assert len(verdict.claim_checks) == 1
    caught = verdict.claim_checks[0]
    assert caught.supported is False
    assert caught.rationale == "LAW_VERSION_WATERSHED_MISMATCH"
    assert "诉讼时效" in caught.claim and "第一百八十八条" in caught.claim


def test_verifier_flag_on_keeps_post_watershed_draft_passing(monkeypatch: pytest.MonkeyPatch):
    """同开关下 2023 事实必须放行——防修成"一律拦"。"""
    monkeypatch.setattr(settings_module.settings, "law_version_tripwire_check", True)
    state = writer_state()
    verdict = DeterministicVerifier().verify(state, _draft_for(state), law_as_of=_AS_OF_TODAY)
    assert verdict.verdict is VerificationVerdict.PASS


def test_verifier_flag_on_without_baseline_fails_as_wiring_error(monkeypatch: pytest.MonkeyPatch):
    """接线自检：开关开而 law_as_of 没透传 ⇒ 绊线会静默失效，宁可显式失败。"""
    monkeypatch.setattr(settings_module.settings, "law_version_tripwire_check", True)
    state = writer_state()
    verdict = DeterministicVerifier().verify(state, _draft_for(state))
    assert verdict.verdict is VerificationVerdict.FAIL_SAFE
    assert verdict.reason_code == "LAW_TRIPWIRE_NOT_WIRED"


def test_pass_result_carries_the_baseline_date(monkeypatch: pytest.MonkeyPatch):
    """F1 修复的一半：PASS 结果必须带上基准日，供 render_verified 的二次验证复用。"""
    monkeypatch.setattr(settings_module.settings, "law_version_tripwire_check", True)
    state = writer_state()
    verdict = DeterministicVerifier().verify(state, _draft_for(state), law_as_of=_AS_OF_TODAY)
    assert verdict.verdict is VerificationVerdict.PASS
    assert verdict.law_as_of == _AS_OF_TODAY


def test_render_verified_reveals_with_tripwire_on(monkeypatch: pytest.MonkeyPatch):
    """F1 的正题：`render_verified` 内部会**再跑一次 verify**（verifier.py:226，经
    main.py:878 走生产链路）。它若不复用首轮基准日，二次验证就命中
    LAW_TRIPWIRE_NOT_WIRED ⇒ 整轮交付 None，用户看到的是 VERIFIER_NOT_PASS，
    绊线原因码永远浮不上来。这条测试就是那道接线的看门狗。"""
    monkeypatch.setattr(settings_module.settings, "law_version_tripwire_check", True)
    state = writer_state()
    draft = _draft_for(state)
    verdict = DeterministicVerifier().verify(state, draft, law_as_of=_AS_OF_TODAY)
    assert verdict.verdict is VerificationVerdict.PASS, "前置失效：本轮就没通过，本测试需重做"
    assert render_verified(state, draft, verdict) is not None


def test_new_reason_codes_are_not_technical_fallbacks():
    """两个新理由码必须留在业务失败侧：落进 TECHNICAL_FALLBACK_REASON_CODES 会把
    "明确拒答"变成"静默降级到快速通道"（service._failure_or_fallback 的分支）。"""
    assert not is_technical_fallback_reason("LAW_VERSION_WATERSHED_MISMATCH")
    assert not is_technical_fallback_reason("LAW_TRIPWIRE_NOT_WIRED")
