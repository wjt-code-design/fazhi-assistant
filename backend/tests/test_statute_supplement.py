"""要件法条确定性补充（`domain_rules.statute_supplement_docs`）的单元测试。

只测**判定/去重/表完整性**逻辑（monkeypatch `_lookup_all`，不依赖 KB/向量库）；
表内法条是否真实存在于知识库，由 `scripts/verify_supplement_coverage.py`（KB 级验证）单独把关。

背景：独立审计显示 57 个评测 required 法条实例中 68% 根本未进入证据，而 writer 对证据内
法条渲染 0 失误 ⇒ 注入点在检索侧。本表的映射依据是**法律领域知识**，与评测题集独立；
泛化由冻结的留出集 `holdout-cases-v1.json` 验收（判据：留出题 HIT 率 ≥ 题集 − 10pp）。
"""

from __future__ import annotations

import pytest

import domain_rules


def _capture_lookup(monkeypatch) -> list[list[tuple[str, str]]]:
    calls: list[list[tuple[str, str]]] = []

    def fake_lookup(specs: list[tuple[str, str]]):
        calls.append(list(specs))
        return [f"DOC::{s}#{a}" for s, a in specs]

    monkeypatch.setattr(domain_rules, "_lookup_all", fake_lookup)
    return calls


def _specs_of(monkeypatch, text: str) -> list[tuple[str, str]]:
    calls = _capture_lookup(monkeypatch)
    domain_rules.statute_supplement_docs(text)
    return calls[-1] if calls else []


def test_labor_dismissal_maps_core_articles(monkeypatch):
    specs = _specs_of(monkeypatch, "公司把我辞退了，说不给补偿，我该怎么办")
    got = {(s, a) for s, a in specs}
    assert ("劳动合同法", "第八十七条") in got, "违法解除二倍补偿是本场景的核心要件"
    assert ("劳动合同法", "第四十六条") in got and ("劳动合同法", "第四十七条") in got
    assert all(s == "劳动合同法" for s, _ in specs)


def test_statute_of_limitation_and_loan_both_fire(monkeypatch):
    """借时效问题同时命中「诉讼时效」与「借款」两个域，两域条文都应进入。"""
    specs = _specs_of(monkeypatch, "借款2021年到期，现在起诉是不是过诉讼时效了")
    got = {(s, a) for s, a in specs}
    assert ("民法典", "第一百八十八条") in got  # 时效域
    assert ("民法典", "第一百九十五条") in got
    assert ("民法典", "第六百七十五条") in got  # 借款域
    assert ("民法典", "第六百八十条") in got


def test_rental_maps_repair_duty(monkeypatch):
    specs = _specs_of(monkeypatch, "房东不修水管，泡坏了我的家具，押金也不退")
    got = {(s, a) for s, a in specs}
    assert ("民法典", "第七百一十二条") in got
    assert ("民法典", "第七百一十三条") in got
    assert ("民法典", "第五百七十七条") in got


def test_deposit_maps_penalty_rule(monkeypatch):
    specs = _specs_of(monkeypatch, "卖家收了定金之后不发货")
    got = {(s, a) for s, a in specs}
    assert {("民法典", "第五百八十六条"), ("民法典", "第五百八十七条"), ("民法典", "第五百八十八条")} <= got


def test_consumer_fraud_delegates_to_existing_mapping(monkeypatch):
    """消费欺诈复用既有 `CONSUMER_FRAUD_DOCS_SPEC`（不建第二套真源）。"""
    specs = _specs_of(monkeypatch, "商家发假货欺诈消费者，还不肯退款")
    assert ("消费者权益保护法", "第五十五条") in {(s, a) for s, a in specs}


def test_unrelated_text_injects_nothing(monkeypatch):
    calls = _capture_lookup(monkeypatch)
    assert domain_rules.statute_supplement_docs("今天天气怎么样") == []
    assert domain_rules.statute_supplement_docs("") == []
    assert calls == [], "无命中时不得发起任何 KB 查找"


def test_dedup_overlapping_domains(monkeypatch):
    """「租赁」与「违约」两域都含民法典577 —— 同一条文只注入一次。"""
    specs = _specs_of(monkeypatch, "租房期间房东违约，还不修漏水")
    fifties = [a for s, a in specs if s == "民法典" and a == "第五百七十七条"]
    assert len(fifties) == 1, f"民法典577 应去重为一条，实际 {len(fifties)}"


def test_table_integrity_and_no_degenerate_keywords():
    """守卫 CC_KEYWORDS 的防退化教训：禁止单字/泛词触发（会退化为"全部命中"）。"""
    for keywords, table in domain_rules._STATUTE_SUPPLEMENT_TABLE:
        assert keywords, "关键词组不得为空"
        for k in keywords:
            assert len(k) >= 2, f"触发词 {k!r} 过短（单字触发会退化）"
        assert table, "关键词组必须配条文表"
        for source, article in table:
            assert source and article, f"条目不完整: {(source, article)}"
            assert article.startswith("第") and article.endswith("条"), f"条文格式应为「第…条」: {(source, article)}"


@pytest.mark.slow
def test_all_supplement_articles_exist_in_kb():
    """KB 级验证（需真实 chroma 索引，故标 slow）：表内每条 (source, article) 必须能精确查到。

    若查不到，`_lookup_all` 会**静默返回空** ⇒ 补充悄悄失效、且没有任何报错 —— 这比报错更危险。
    """
    pairs = [(source, article) for _, table in domain_rules._STATUTE_SUPPLEMENT_TABLE for source, article in table]
    pairs += [(s, a) for s, a in domain_rules.CONSUMER_FRAUD_DOCS_SPEC]
    missing = [f"{s}#{a}" for s, a in pairs if not domain_rules._lookup_all([(s, a)])]
    assert not missing, f"以下法条在知识库中不存在（注入会静默失效）: {missing}"
