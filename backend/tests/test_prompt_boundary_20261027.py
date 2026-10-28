"""F2 提示词边界单测（2026-10-27）：定罪类例外 + 禁用表述变体。

只测 prompt 合同文本；不证明生成质量（与 test_answer_quality_prompt_round7 同定位）。
"""

from prompts import AGENT_WRITER_SYSTEM, SYSTEM_BASE


def test_system_base_has_criminal_conviction_boundary():
    assert "刑事定罪问题" in SYSTEM_BASE
    assert "不得以总则条文" in SYSTEM_BASE
    assert "不得援引与案情不符的特别条款" in SYSTEM_BASE


def test_system_base_banlist_covers_process_variants():
    for phrase in (
        "提供条文",
        "检索范围",
        "补充依据",
        "题目要求",
        "本次检索",
        "引用缺失风险",
        "未直接列出",
        "无原文",
        "未在提供条文中",
    ):
        assert phrase in SYSTEM_BASE


def test_agent_writer_still_forbids_free_text_and_process_output():
    assert "不得输出自由文本结论" in AGENT_WRITER_SYSTEM
    assert "提示词" in AGENT_WRITER_SYSTEM
