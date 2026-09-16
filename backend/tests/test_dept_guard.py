"""R1/R1b 部门法守卫单测（预注册 dept-law-filter-r1 判据面的代码侧验证）。

覆盖（对齐预注册 §3 测试要求）：
- 民事判域：剔除行政诉讼法/刑事诉讼法条文（C05 实证）
- 冲突指示词 / 零指示 → mixed → 不过滤（保守）
- 实体法永不过滤（民法典/刑法留）
- 空池显式可观测（过滤后可空，不静默）
- R1b：终稿含他域程序法 → 触发 proc_misroute；实体法串台 → 不误报
- 开关关闭 → 零行为变化（短路）
"""

from __future__ import annotations

import pytest
from pydantic import BaseModel

from agent import dept_guard as dg


class _D(BaseModel):
    metadata: dict
    page_content: str = "x"


@pytest.fixture(autouse=True)
def _reset_switches(monkeypatch):
    """每个测试用显式开关；默认关（生产默认 False = 零行为变化）。"""
    monkeypatch.setattr(dg.settings, "agent_proc_misroute_check", False)


def _doc(source: str) -> _D:
    return _D(metadata={"source": source, "article": "第一百二十二条"})


# ---- 判域 ----
def test_domain_of_text_civil():
    assert dg.domain_of_text("民事借款纠纷 起诉条件 需要什么条件") == "civil"


def test_domain_conflict_is_mixed():
    # "诈骗"(criminal) + "借款"(civil) → mixed → 不过滤
    assert dg.domain_of_text("朋友借钱不还 算不算诈骗 该起诉还是报警") is None


def test_domain_zero_hint_is_mixed():
    assert dg.domain_of_text("关于主体资格认定问题") is None


# ---- R1 过滤 ----
def test_r1_filters_foreign_proc_law_civil():
    docs = [_doc("民法典"), _doc("行政诉讼法"), _doc("刑事诉讼法"), _doc("民事诉讼法")]
    kept = dg.filter_docs_by_domain(docs, "civil")
    assert [d.metadata["source"] for d in kept] == ["民法典", "民事诉讼法"]  # 行/刑诉剔，民诉留（civil 域自有）


def test_r1_keeps_entity_law_always():
    docs = [_doc("民法典"), _doc("刑法"), _doc("劳动法")]
    assert len(dg.filter_docs_by_domain(docs, "civil")) == 3  # 实体法永不过滤


def test_r1_can_empty_pool_explicitly():
    # 民事域检索到 2 条行诉法 → 过滤后空池（显式可观测，不静默）
    docs = [_doc("行政诉讼法"), _doc("行政诉讼法")]
    kept = dg.filter_docs_by_domain(docs, "civil")
    assert kept == []


# ---- R1b 终稿串台 ----
def test_r1b_detects_proc_misroute_in_final(monkeypatch):
    monkeypatch.setattr(dg.settings, "agent_proc_misroute_check", True)
    text = "根据《行政诉讼法》第四十九条起诉条件…另见《民法典》第一百八十八条。"
    assert dg.final_draft_proc_misroute(text, "civil") == ["《行政诉讼法》第四十九条"]
    assert dg.check_proc_misroute(text, "civil") is True


def test_r1b_detects_full_name_proc_misroute(monkeypatch):
    # 2026-09-14 深度检查：writer 全称/简称混用（E01 实测两种形态并存），
    # 全称《中华人民共和国行政诉讼法》此前漏检——R1b 红线半失效。
    monkeypatch.setattr(dg.settings, "agent_proc_misroute_check", True)
    text = "参照《中华人民共和国行政诉讼法》第四十九条关于提起诉讼条件的规定。"
    assert dg.final_draft_proc_misroute(text, "civil") == ["《中华人民共和国行政诉讼法》第四十九条"]


def test_r1b_full_name_same_domain_not_false_positive(monkeypatch):
    # 全称本域程序法（中华人民共和国民事诉讼法 in civil）不得误报
    monkeypatch.setattr(dg.settings, "agent_proc_misroute_check", True)
    text = "根据《中华人民共和国民事诉讼法》第一百二十二条,起诉必须有明确的被告。"
    assert dg.final_draft_proc_misroute(text, "civil") == []


def test_r1b_ignores_proc_law_of_same_domain(monkeypatch):
    monkeypatch.setattr(dg.settings, "agent_proc_misroute_check", True)
    text = "根据《民事诉讼法》第一百二十二条起诉。"
    assert dg.final_draft_proc_misroute(text, "civil") == []


def test_r1b_switch_off_is_noop(monkeypatch):
    monkeypatch.setattr(dg.settings, "agent_proc_misroute_check", False)
    # 即使文本有串台，开关关 → False（生产默认不改变既有行为）
    assert dg.check_proc_misroute("《行政诉讼法》第四十九条", "civil") is False


def test_r1b_entity_cross_chapter_not_false_positive(monkeypatch):
    monkeypatch.setattr(dg.settings, "agent_proc_misroute_check", True)
    # C07 型：民法典 694（保证期间）是实体法串章——R1b 不误报（只认专属程序法）
    text = "可参照《民法典》第六百九十四条关于保证期间的规定。"
    assert dg.final_draft_proc_misroute(text, "civil") == []
