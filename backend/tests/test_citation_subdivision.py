"""款项级引用解析与校验测试（2026-10-25，G1）。

背景：113 题把《企业破产法》第八十七条**第二款**第一项写成**第一款**第一项，
旧的条级解析器只看「第八十七条」，永远判正常。本组测试锁定款/项解析与存在性校验。
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))

from citation_check import (  # noqa: E402
    article_structure,
    extract_citation_refs,
    extract_citations,
    validate_subdivision,
)

ART87 = """第八章　重　　整
第八十七条　部分表决组未通过重整计划草案的，债务人或者管理人可以同未通过重整计划草案的表决组协商。该表决组可以在协商后再表决一次。
未通过重整计划草案的表决组拒绝再次表决或者再次表决仍未通过重整计划草案，但重整计划草案符合下列条件的，债务人或者管理人可以申请人民法院批准重整计划草案：
（一）按照重整计划草案，本法第八十二条第一款第一项所列债权就该特定财产将获得全额清偿。
（二）按照重整计划草案，本法第八十二条第一款第二项、第三项所列债权将获得全额清偿。
"""


def test_extract_ref_with_paragraph_and_item():
    refs = extract_citation_refs("根据《企业破产法》第八十七条第一款第一项，可以申请批准。")
    assert ("企业破产法", 87, 1, 1) in refs


def test_extract_ref_article_only():
    refs = extract_citation_refs("依据《民法典》第六百五十八条，可以撤销。")
    assert ("民法典", 658, None, None) in refs


def test_extract_ref_paragraph_only():
    refs = extract_citation_refs("《企业破产法》第八十七条第二款规定了强制批准条件。")
    assert ("企业破产法", 87, 2, None) in refs


def test_extract_ref_item_without_paragraph():
    refs = extract_citation_refs("《企业破产法》第八十七条第一项。")
    assert ("企业破产法", 87, None, 1) in refs


def test_extract_refs_do_not_cross_book_title():
    text = "《宪法》第十二条、《民法典》第二百五十八条与《刑法》第三百九十六条。"
    refs = extract_citation_refs(text)
    assert ("宪法", 12, None, None) in refs
    assert ("民法典", 258, None, None) in refs
    assert ("刑法", 396, None, None) in refs
    assert ("宪法", 396, None, None) not in refs


def test_article_level_extraction_unchanged():
    # 条级指标必须与改造前一致，避免冻结基线不可比
    text = "《民法典》第六百五十八条及《刑法》第三百九十六条第二款第一项。"
    assert extract_citations(text) == {("民法典", 658), ("刑法", 396)}


def test_article_structure_splits_paragraphs_and_items():
    paras = article_structure(ART87)
    assert paras is not None and len(paras) == 2
    assert paras[0]["items"] == []
    assert paras[1]["items"] == [1, 2]


def test_validate_detects_wrong_paragraph():
    # 113 的原始错误：第一款下没有项
    assert validate_subdivision(ART87, 1, 1) is False


def test_validate_accepts_correct_subdivision():
    assert validate_subdivision(ART87, 2, 1) is True


def test_validate_rejects_out_of_range_paragraph():
    assert validate_subdivision(ART87, 3, None) is False


def test_validate_returns_none_without_subdivision():
    assert validate_subdivision(ART87, None, None) is None


def test_validate_returns_none_when_article_not_parseable():
    assert validate_subdivision("（无条文原文）", 1, 1) is None
