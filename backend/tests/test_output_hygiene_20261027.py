"""F3/F4 输出卫生单测（2026-10-27）：内部话术删除 + 结论矛盾检测。

样本取自 2026-10-27 故意伤害/教唆犯事故答案原文。
"""

import output_normalize as on

AUDIT_BAD = (
    "依据《刑法》第十四条、第二百三十四条（虽未直接列出234条全文，但第289条及常识指向该罪名体系，"
    "此处需严格依据提供条文，若仅依提供条文，存在引用缺失风险，但根据《刑法》第十三条犯罪定义及"
    "第十四条故意规定，结合“一级伤残”即重伤结果，可推导定性；注：题目要求严格依据提供条文，"
    "提供条文中无第二百三十四条原文，但有第二百八十九条提及依照二百三十四条定罪，"
    "故可间接引用或说明需结合具体罪名条文）。"
)


def test_strip_internal_notes_removes_audit_parenthetical():
    out = on.strip_internal_notes(AUDIT_BAD)
    for phrase in ("提供条文", "引用缺失", "题目要求", "检索范围", "未直接列出"):
        assert phrase not in out
    assert "第二百三十四条" in out  # 正文引用保留


def test_strip_internal_notes_removes_meta_sentences():
    text = (
        "王五构成故意伤害罪。"
        "最大风险：需提供《刑法》第二百三十四条原文以确证量刑档次。"
        "补充依据（未在本次检索范围内，条文存在于法律库）"
    )
    out = on.strip_internal_notes(text)
    for phrase in ("需提供", "检索范围", "补充依据", "条文存在于法律库"):
        assert phrase not in out
    assert "王五构成故意伤害罪" in out


def test_strip_internal_notes_keeps_clean_legal_text():
    text = "《刑法》第二百三十四条规定，故意伤害他人身体的，处三年以下有期徒刑、拘役或者管制。"
    assert on.strip_internal_notes(text) == text


def test_strip_internal_notes_is_idempotent():
    once = on.strip_internal_notes(AUDIT_BAD)
    assert on.strip_internal_notes(once) == once


def test_has_internal_notes():
    assert on.has_internal_notes(AUDIT_BAD)
    assert not on.has_internal_notes("《刑法》第二百三十四条规定故意伤害罪的处刑。")


def test_detect_conclusion_contradiction_flags_negated_relied_article():
    text = "依据《刑法》第十四条、第二百三十四条（未直接列出234条全文）。"
    issues = on.detect_conclusion_contradiction(text)
    assert any("234" in item or "二百三十四" in item for item in issues)


def test_detect_conclusion_contradiction_ignores_clean_text():
    text = "依据《刑法》第二百三十四条，王五构成故意伤害罪；第二百三十四条为现行有效条文。"
    assert on.detect_conclusion_contradiction(text) == []


def test_detect_contradiction_across_sentences():
    """事故形态：前句"依据 234"，后句"234 未提供"——跨句也必须命中。"""
    text = "依据《刑法》第二百三十四条，构成故意伤害罪。第二百三十四条未提供全文。"
    assert on.detect_conclusion_contradiction(text) == ["234"]


def test_detect_contradiction_mixed_numerals():
    """条号必须归一为数字：中文条号与阿拉伯条号指向同一条。"""
    text = "依据《刑法》第二百三十四条。未提供第234条全文。"
    assert on.detect_conclusion_contradiction(text) == ["234"]


def test_detect_contradiction_ignores_normal_negation():
    """正常表述不得误报：'未包含精神损害' 不是对 584 条的缺失声明。"""
    text = "根据《民法典》第五百八十四条，可得利益损失未包含精神损害。"
    assert on.detect_conclusion_contradiction(text) == []


def test_detect_contradiction_pronoun_reference():
    """代词指代（该条）才回看前句，且必须指向'依据'句。"""
    text = "依据《刑法》第二百三十四条。但未提供该条全文。"
    assert on.detect_conclusion_contradiction(text) == ["234"]


def test_detect_contradiction_only_nearest_article():
    """同一小句列了多个条号时，否定只指向最近的那一条（事故句不得误伤第14条）。"""
    text = "依据《刑法》第十四条、第二百三十四条（虽未直接列出234条全文，但可推导）。"
    assert on.detect_conclusion_contradiction(text) == ["234"]


def test_contradiction_note_survives_stripers():
    """F4 提示不得被两个清理器删掉（否则用户什么也看不到）。"""
    text = "依据《刑法》第二百三十四条，构成故意伤害罪。" + on.CONTRADICTION_NOTE
    assert on.CONTRADICTION_NOTE.strip() in on.strip_internal_notes(text)
    assert on.CONTRADICTION_NOTE.strip() in on.strip_unprovided_notes(text, lambda source: True)
