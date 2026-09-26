"""S0 时效未知显式化：`retrieval_core.time_validity_state` 的判据与"不动检索集"这条边界。

背景（票组 `docs/h1-law-version-collision-tickets-20260926.md` §S0）：现网语料 10266/10266 条
`effective_from` 为空串且 `status='现行'`（该 status 是上传路径的默认值，没人核过）⇒
`is_valid_by_time` 对每一条都走 fail-open。本模块不是收紧判据，而是把"我们有没有资格这样断言"
变成一个可被答案层/门禁消费的状态。
"""

import retrieval_core as rc


def test_state_unknown_when_no_dates_but_predicate_still_passes():
    """无日期 ⇒ unknown，而谓词**照旧放行**：这条同时钉住"标出来"与"没改检索集"两件事。"""
    meta = {"status": "现行"}
    assert rc.time_validity_state(meta) == "unknown"
    assert rc.is_valid_by_time(meta, "2026-08-01") is True


def test_state_verified_when_effective_from_present_for_current_version():
    assert rc.time_validity_state({"status": "现行", "effective_from": "2021-01-01"}) == "verified"


def test_state_requires_termination_date_for_finished_versions():
    """已废止/已修改 只有起始日 ⇒ 无法证明它在查询日已终止，仍算 unknown。"""
    assert rc.time_validity_state({"status": "已废止", "effective_from": "1999-10-01"}) == "unknown"
    assert (
        rc.time_validity_state({"status": "已废止", "effective_from": "1999-10-01", "effective_to": "2020-12-31"})
        == "verified"
    )
    assert rc.time_validity_state({"status": "已修改", "effective_from": "2018-01-01"}) == "unknown"


def test_state_unknown_for_unverified_status_even_with_dates():
    """`未验证` 是"没人替这条断言背过书"的状态 ⇒ 有日期也不等于时效已核。"""
    assert rc.time_validity_state({"status": "未验证", "effective_from": "2021-01-01"}) == "unknown"


def test_state_tolerates_missing_and_blank_fields():
    assert rc.time_validity_state({}) == "unknown"
    assert rc.time_validity_state({"status": "", "effective_from": "  ", "effective_to": ""}) == "unknown"


def test_state_never_narrows_the_retrieval_set():
    """S0 的边界：状态函数只做标注，**不得**成为新的过滤条件。

    取一组"unknown 但谓词在该日确实有效"的元数据，逐条要求谓词仍返回 True ⇒
    谁把 `未验证`/`unknown` 塞进 is_valid_by_time 的排除分支，这里立刻红。
    """
    unknown_but_valid = [
        {"status": "现行"},
        {"status": "现行", "effective_from": "", "effective_to": ""},
        {"status": "未验证", "effective_from": "2008-05-01"},
        {"status": "已修改", "effective_from": "2018-01-01"},
    ]
    for meta in unknown_but_valid:
        assert rc.time_validity_state(meta) == "unknown", meta
        assert rc.is_valid_by_time(meta, "2026-08-01") is True, meta
