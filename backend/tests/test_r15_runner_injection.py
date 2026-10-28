"""R15：gate2_runner 的 law_as_of 透传契约 + 对照题集结构契约（2026-09-18）。

只锁"什么时候发这个键"与"题集字段形状对不对"，不发真实 HTTP（零模型调用、零花费）。
契约真源（独立于本实现）：`evals/validate_cases.py:37-40,75,92-99`（字段名单、
required_laws 逐条解包、fact_reveal 单元）与 `backend/scripts/gate5_judge.py:93`
（`int(x[1])` ⇒ 条号必须是 int）。
"""

from __future__ import annotations

import json
from pathlib import Path

import scripts.gate2_runner as runner

_CASE = {
    "id": "W01",
    "initial_question": "2019年3月5日借的钱，现在起诉还有效吗？",
    "domain": "诉讼时效与保证期间",
    "as_of_date": "2026-09-18",
}
_CASES_PATH = Path(__file__).resolve().parents[2] / "evals" / "watershed-cases-r15.json"


def test_payload_carries_law_as_of_when_case_declares_it():
    assert runner._round1_payload(_CASE, no_case_domain=False, no_as_of_date=False)["law_as_of"] == "2026-09-18"


def test_payload_omits_law_as_of_when_case_has_no_as_of_date():
    case = {k: v for k, v in _CASE.items() if k != "as_of_date"}
    assert "law_as_of" not in runner._round1_payload(case, no_case_domain=False, no_as_of_date=False)


def test_no_as_of_date_flag_simulates_production_shape():
    assert "law_as_of" not in runner._round1_payload(_CASE, no_case_domain=False, no_as_of_date=True)


def test_base_fields_unchanged():
    payload = runner._round1_payload(_CASE, no_case_domain=True, no_as_of_date=True)
    assert payload == {"content": _CASE["initial_question"], "no_cache": True, "force_agent": True}


def test_watershed_cases_conform_to_case_schema():
    """题集必须能被 runner + gate5_judge 消费：字段齐、类型对。

    反例即本批初稿：把 round1_facts 写成数组、required_laws 写成中文条号字符串——后者会让
    gate5_judge 的 `int(x[1])` 直接 ValueError 崩判分（评测假红比没评测更坏）。
    """
    doc = json.loads(_CASES_PATH.read_text(encoding="utf-8"))
    assert doc["schema_version"] == "r15-watershed-v1"
    assert len(doc["cases"]) == 2
    for case in doc["cases"]:
        for field in (
            "id",
            "domain",
            "initial_question",
            "round1_facts",
            "round2_facts",
            "required_issues",
            "required_laws",
            "critical_failures",
            "deciding_facts",
            "fact_reveal",
            "as_of_date",
        ):
            assert field in case, f"{case.get('id')}: 缺字段 {field}"
        assert isinstance(case["round1_facts"], str), "round1_facts 必须是 str（v1 契约，非数组）"
        assert runner._case_domain_of(case) == "civil", f"{case['id']}: domain 未映射 ⇒ 不会发 case_domain"
        for entry in case["required_laws"]:
            assert isinstance(entry, list) and len(entry) == 2, "required_laws 条目必须是 [法名, 条号]"
            assert isinstance(entry[0], str) and isinstance(entry[1], int), "条号必须是 int，否则 judge int() 崩"
        for rnd, units in case["fact_reveal"].items():
            assert rnd in ("r1", "r2"), f"{case['id']}: 非法轮次 {rnd}"
            for unit in units:
                assert unit.get("text") and unit.get("keywords"), f"{case['id']}.{rnd}: 单元缺 text/keywords"
    # 对照臂设计：两条只差事实发生日，一侧跨分水岭一侧不跨
    w01, w02 = doc["cases"]
    assert w01["as_of_date"] == w02["as_of_date"]
    assert "2019" in w01["initial_question"] and "2023" in w02["initial_question"]


def test_watershed_fact_reveal_is_consumable_by_runner():
    """题集写了 fact_reveal 不等于投放得到——fid 命名由 `_facts_from_case_set` 决定
    （`r(\\d+)` → `<CASE>-r<轮>-f<序号>`）。这里把"写了但没接上"这类静默失效钉住。"""
    doc = json.loads(_CASES_PATH.read_text(encoding="utf-8"))
    facts = runner._facts_from_case_set({}, doc["cases"])
    assert sorted(facts) == ["W01-r1-f1", "W01-r2-f1", "W02-r1-f1", "W02-r2-f1"]
    assert facts["W01-r1-f1"]["round"] == 1 and facts["W01-r2-f1"]["round"] == 2
    assert "2019" in facts["W01-r1-f1"]["text"] and "2023" in facts["W02-r1-f1"]["text"]
