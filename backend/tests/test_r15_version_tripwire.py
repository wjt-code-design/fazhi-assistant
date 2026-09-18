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

from agent.limitation_calc import law_version_crosses_watershed

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
