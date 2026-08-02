"""阶段6 测试：结构化切分（纯函数，fixture 为合成测试文本）。"""

import os

import chunking as C

FIXTURE = os.path.join(os.path.dirname(__file__), "..", "..", "data", "sample_laws", "sample_law.txt")

EXPECTED_ARTICLES = {"第一条", "第二条", "第三条", "第四条", "第五条", "第五条之一", "第一〇一条", "第100条", "第六条"}


def _load() -> str:
    return open(FIXTURE, encoding="utf-8").read()


def _chunks() -> list:
    return C.split_law_document(_load())


def test_article_coverage_exactly_once():
    """正文每条条号恰好进入 chunk 元数据；目录条目不被识别为条文。"""
    chunks = _chunks()
    articles = [c.meta.get("article", "") for c in chunks]
    found = {a for a in articles if a}
    assert found == EXPECTED_ARTICLES, f"条号覆盖不完整：{found ^ EXPECTED_ARTICLES}"
    # 目录条目（立法目的与依据 / 适用范围）不得成为条文
    assert not any("立法目的与依据" in c.page_content for c in chunks), "目录条目不应进入内容"


def test_toc_skipped():
    chunks = _chunks()
    joined = "\n".join(c.page_content for c in chunks)
    assert "目  录" not in joined
    assert "第一章 总则" in joined  # 正文章节标题仍在（作为前缀）


def test_chapter_prefix_injected():
    chunks = _chunks()
    fifth = [c for c in chunks if c.meta.get("article") == "第五条"]
    assert fifth and all("第二章 分则" in c.page_content for c in fifth)
    last = [c for c in chunks if c.meta.get("article") == "第六条"]
    assert last and all("附则" in c.page_content for c in last)


def test_variants_recognized():
    chunks = _chunks()
    arts = {c.meta.get("article", "") for c in chunks}
    assert "第一〇一条" in arts  # 汉字〇
    assert "第100条" in arts  # 阿拉伯数字
    assert "第五条之一" in arts  # 条之一


def test_midline_citation_not_split():
    """正文行中「第十九条的适用」不得触发新条号边界。"""
    chunks = _chunks()
    assert not any(c.meta.get("article") == "第十九条" for c in chunks)


def test_long_article_sentence_split():
    """超长条句切：多条 chunk 共享同一条号，且每条不超过句切上限+前缀。"""
    chunks = _chunks()
    third = [c for c in chunks if c.meta.get("article") == "第三条"]
    assert len(third) >= 2, "超长条应被句切为多个 chunk"
    assert all(c.meta["article"] == "第三条" for c in third)
    assert all(len(c.page_content) <= 700 for c in third)


def test_article_has_headline_kept():
    """条号头行保留在内容中（BM25 条号查询的精确匹配载荷）。"""
    chunks = _chunks()
    second = [c for c in chunks if c.meta.get("article") == "第二条"][0]
    assert "第二条 本条例适用于" in second.page_content  # 条号头行保留（章节前缀在前）


def test_fallback_paragraph_without_articles():
    """全文无条号 → 回退段落切分，meta 无 article。"""
    text = "这是一段没有条号结构的备忘录。\n\n它包含多个段落，用于验证降级切分路径。\n\n第三个段落。"
    chunks = C.split_law_document(text)
    assert chunks and all(c.meta.get("article", "") == "" for c in chunks)
    assert sum(len(c.page_content) for c in chunks) == len(text)


def test_toc_only_short_entries_falls_back():
    """只有目录式短条目（如「第一条 立法目的」）的文本 → 全部丢弃后回退段落切分。"""
    text = "第一章 总则\n第一条 立法目的\n第二条 适用范围"
    chunks = C.split_law_document(text)
    assert chunks and all(not c.meta.get("article") for c in chunks)


def test_split_article_text_basic_and_long():
    short = C.split_article_text("依法成立的合同受法律保护。", article="第八条")
    assert len(short) == 1 and short[0].meta["article"] == "第八条"
    long_body = "第" + "一段。" + "第二段；" * 300
    long = C.split_article_text(long_body, article="第九条", chapter="第二章 分则")
    assert len(long) >= 2 and all(c.meta["article"] == "第九条" for c in long)
    assert all("第二章 分则" in c.page_content for c in long)


def test_empty_input():
    assert C.split_law_document("") == []
    assert C.split_law_document("   ") == []
    assert C.split_article_text("") == []
