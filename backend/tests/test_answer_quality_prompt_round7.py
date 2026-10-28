"""Prompt contract checks only; these do not prove generated answer quality.

This module deliberately imports the pure prompt module, not the application.
The three invariants come from input provenance, conditional reasoning and
claim-to-evidence support, not the particular legal scenarios in the audit.
"""

import pytest

from prompts import AGENT_WRITER_SYSTEM, SYSTEM_BASE


@pytest.mark.parametrize("prompt", [SYSTEM_BASE, AGENT_WRITER_SYSTEM], ids=["fast", "agent"])
def test_unknown_case_facts_are_not_promoted_to_established_facts(prompt):
    assert "不得把常见情形或假设当作本案已确认事实" in prompt
    assert "不得仅凭单一行为认定过错程度或责任比例" in prompt


@pytest.mark.parametrize("prompt", [SYSTEM_BASE, AGENT_WRITER_SYSTEM], ids=["fast", "agent"])
def test_summary_retains_decisive_conditions(prompt):
    assert "保留正文中的适用前提、例外和待确认条件" in prompt


@pytest.mark.parametrize("prompt", [SYSTEM_BASE, AGENT_WRITER_SYSTEM], ids=["fast", "agent"])
def test_citation_requires_support_not_just_a_real_article(prompt):
    assert "核对适用前提与所支持的具体结论" in prompt
    assert "不得仅因条文主题相近就替代所需依据" in prompt


def test_fast_path_does_not_force_nearest_article_when_support_is_missing():
    assert "直接基于上方最相关条文作答并引用条号" not in SYSTEM_BASE
    assert "不把依据不足表述为法律没有规定" in SYSTEM_BASE


def test_agent_preserves_structured_evidence_and_unknown_fact_boundaries():
    assert "顶层字段只有 claims 与 missing_information" in AGENT_WRITER_SYSTEM
    assert "missing_information 只能逐字复制" in AGENT_WRITER_SYSTEM
    assert "不得跨 Issue 引用" in AGENT_WRITER_SYSTEM
    assert "不得新增事实、数字、金额、日期、比例、法律、法条或引用" in AGENT_WRITER_SYSTEM
