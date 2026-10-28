"""filter_sources_by_citation 单测：参考条文按答复实际引用过滤。

覆盖：命中子集保持 sources 原顺序、归一匹配（中文/阿拉伯条号、法名简称）、
答复未引在库条文时返回空（不拿全量凑数）、库外引用天然排除。
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from retrieval import filter_sources_by_citation  # noqa: E402

SOURCES = [
    {"source": "民事诉讼法", "article": "第二十一条"},
    {"source": "民事诉讼法", "article": "第六十七条"},
    {"source": "刑事诉讼法", "article": "第五十一条"},
    {"source": "民法典", "article": "第五百八十七条"},
]


def test_keeps_only_cited_and_preserves_order():
    ans = "依据《民事诉讼法》第67条与《民法典》第五百八十七条，……"
    out = filter_sources_by_citation(ans, SOURCES)
    # 未引的 21 条（管辖）与刑诉 51 被滤掉；保留的按 sources 原序（检索序即相关序）
    assert [s["article"] for s in out] == ["第六十七条", "第五百八十七条"]


def test_cross_law_same_article_not_confused():
    ans = "依据《民事诉讼法》第六十七条"  # 只引民诉 67
    out = filter_sources_by_citation(ans, SOURCES)
    assert [s["article"] for s in out] == ["第六十七条"]
    assert not any(s["source"] == "刑事诉讼法" for s in out)


def test_returns_empty_when_nothing_cited():
    assert filter_sources_by_citation("这是一个没有法条引用的回答。", SOURCES) == []
    assert filter_sources_by_citation("", SOURCES) == []


def test_out_of_kb_citation_yields_empty():
    ans = "依据《公司法》第一百条"  # 不在 SOURCES 内
    assert filter_sources_by_citation(ans, SOURCES) == []


def test_empty_sources():
    assert filter_sources_by_citation("依据《民法典》第五百八十七条", []) == []


def test_duplicate_entries_deduped():
    """场景组+检索都命中同一条时只保留首次（线上实测 K01 曾重复下发 67）。"""
    dup = SOURCES + [{"source": "民事诉讼法", "article": "第六十七条"}]
    out = filter_sources_by_citation("依据《民事诉讼法》第六十七条", dup)
    assert [s["article"] for s in out] == ["第六十七条"]


def test_real_world_burden_of_proof_case():
    """真实场景：27 条上下文，答复只引 5 条（其余为刑诉/行政法/管辖执行章噪音）。"""
    noisy = SOURCES + [
        {"source": "行政诉讼法", "article": "第三十八条"},
        {"source": "行政复议法", "article": "第四十四条"},
        {"source": "民事诉讼法", "article": "第一百五十七条"},
    ]
    ans = (
        "根据《民事诉讼法》第六十七条，当事人对自己提出的主张，有责任提供证据。"
        "《民事诉讼法》第六十八条要求及时提供证据。"
        "《民诉法解释》第九十一条、第九十二条进一步明确举证责任分配。"
    )
    out = filter_sources_by_citation(ans, noisy)
    assert len(out) == 1 and out[0]["article"] == "第六十七条"
    assert not any(s["source"] in ("行政诉讼法", "行政复议法") for s in out)
