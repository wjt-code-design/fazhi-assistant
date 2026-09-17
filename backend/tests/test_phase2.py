from types import SimpleNamespace

import pydantic
from langchain_core.documents import Document

import curation
import retrieval_core as rc
from schemas import ChatIn


# ---------- 受控沉淀判定 ----------
def test_curation_requires_all_conditions():
    good = "根据《劳动合同法》第十九条，试用期最长不得超过六个月，三年以上合同适用。"
    assert curation.should_curate(0.8, good) is True
    assert curation.should_curate(0.3, good) is False  # 低分
    assert curation.should_curate(0.9, "试用期最长六个月，未引用法条。") is False  # 无引用
    assert curation.should_curate(0.9, "根据《劳动合同法》第十九条。") is False  # 太短
    assert curation.should_curate(0.9, "") is False


# ---------- RRF 融合 ----------
def test_rrf_fuses_shared_higher():
    s = rc.rrf([["a", "b"], ["b", "c"]])
    assert s["b"] > s["a"] and s["b"] > s["c"]
    assert abs(s["a"] - 1 / 61) < 1e-9
    assert abs(s["c"] - 1 / 62) < 1e-9


def test_rrf_empty():
    assert rc.rrf([]) == {}


# ---------- 分词 ----------
def test_tokenize_filters_whitespace():
    toks = rc.tokenize("  劳动合同法  第十九条 ")
    assert "第十九条" in toks and all(t.strip() for t in toks)
    assert rc.tokenize("") == []


# ---------- LRU ----------
def test_lru_evicts_oldest():
    cache = rc.LRU(2)
    cache.put("a", 1)
    cache.put("b", 2)
    assert cache.get("a") == 1
    cache.put("c", 3)  # 淘汰 b
    assert cache.get("b") is None and cache.get("c") == 3 and len(cache) == 2


# ---------- BM25（非退化语料） ----------
def test_bm25_ranks_matching_first_and_positive():
    docs = [
        Document(page_content="试用期 不得超过 六个月"),
        Document(page_content="诉讼时效 为 三年"),
        Document(page_content="退货 七日 无理由"),
    ]
    bm = rc.build_bm25(docs)
    top = rc.bm25_top(bm, docs, "试用期", 3)
    assert top[0][0].page_content.startswith("试用期")
    assert top[0][1] > 0  # 3 条语料命中 1 条，IDF>0


def test_bm25_category_filter():
    docs = [
        Document(page_content="试用期 六个月", metadata={"category": "劳动法"}),
        Document(page_content="试用期 工资", metadata={"category": "民法"}),
        Document(page_content="退货 七日", metadata={"category": "消费法"}),
    ]
    bm = rc.build_bm25(docs)
    top = rc.bm25_top(bm, docs, "试用期", 3, category="民法")
    assert top and all(d.metadata["category"] == "民法" for d, _ in top)


# ---------- schemas ----------
def test_chatin_flexible_and_maxlen():
    assert ChatIn(content="hi").content == "hi"
    assert ChatIn(image="data:image/png;base64,xxx").image is not None
    assert ChatIn().content is None
    try:
        ChatIn(content="x" * 12001)  # 上限 4000→12000（2026-08-06 合同评估，契约容量）
    except pydantic.ValidationError:
        pass
    else:
        raise AssertionError("应拒绝超长 content")


# ---------- memory 双阈值（纯逻辑） ----------
def test_needs_compress_dual_threshold():
    from memory import char_count, needs_compress

    recent = [SimpleNamespace(content="a" * 100) for _ in range(6)]
    assert needs_compress(SimpleNamespace(message_count=5, summary=""), recent) is False
    assert needs_compress(SimpleNamespace(message_count=13, summary=""), recent) is True  # 轮次触发
    assert needs_compress(SimpleNamespace(message_count=8, summary="s" * 6000), recent) is True  # 字符触发
    assert needs_compress(SimpleNamespace(message_count=8, summary="s" * 1000), recent) is False
    assert char_count("abc", recent) == 603


# ---------- 空答多配置重试（假链，不调真实 API） ----------
def test_stream_with_retry_empty_then_content():
    import asyncio

    from rag_chain import stream_with_retry

    calls = {"n": 0}

    class FakeChain:
        async def astream(self, _messages):
            calls["n"] += 1
            if calls["n"] == 1:
                yield ""  # 第一次：空生成
                yield ""
            else:
                yield "答"
                yield "案"

    async def collect():
        return [p async for p in stream_with_retry(lambda _i, _d: FakeChain(), [], [(False, 0.0), (True, 0.5)])]

    assert asyncio.run(collect()) == ["答", "案"]
    assert calls["n"] == 2  # 空答后确实重试了第二次


def test_stream_with_retry_all_empty_returns_nothing():
    import asyncio

    from rag_chain import stream_with_retry

    class FakeChain:
        async def astream(self, _messages):
            yield ""

    async def collect():
        return [p async for p in stream_with_retry(lambda _i, _d: FakeChain(), [], [(False, 0.0), (True, 0.5)])]

    assert asyncio.run(collect()) == []


# ---------- 剥除 thinking 模型内联 <think> 块 ----------
def test_clean_answer_strips_think_blocks():
    from rag_chain import clean_answer

    assert clean_answer("<think>先分析一下。</think>答案是六个月。") == "答案是六个月。"
    assert clean_answer("答案是六个月。") == "答案是六个月。"
    assert clean_answer("<think>\n用户想要试用期时长\n</think>回答：六个月") == "回答：六个月"
    assert clean_answer("") == ""
