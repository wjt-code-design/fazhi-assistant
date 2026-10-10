"""DB-19 处置「丁」（Owner 2026-10-10 裁「按推荐」）：回落只允许发生在语料根本没有 category 这个键时。

为什么要改：现装行为对三种形状都给「回落取全量」，其中
  S2 = 库里确实带 category 键、但没有你要的那一类 ⇒ 问「行政法」返回「民法」「劳动法」的条文，
       只落一条 warning。这就是执行书 B.4 明令禁止的「用无过滤结果伪装满足真实 category」。
判定语义是实测的（evidence/probe_chroma_key_presence.py，chromadb 0.4.24）：
  缺键的行在 $eq 与 $ne 下一并被排除 ⇒ 「$eq 与 $ne 双双取零而 count>0」等价于「没有任何文档带这个键」。
  实测读数：S1（全不带键）eq/ne 全 0；S2/S3（带键）ne>0。⇒ 该判定与所问值无关，可按集合名缓存。
本文件的替身按上述实测语义实现；末条是负向自证：旧形状对 S2 一定会补发无过滤查询。
"""

from __future__ import annotations

import logging
import types

import pytest
from langchain_core.documents import Document

import retrieval

NOKEY = [
    Document(page_content="民法典第六百七十五条 借款期限", metadata={"source": "民法典", "article": "第六百七十五条"}),
    Document(page_content="劳动合同法第四十七条 经济补偿", metadata={"source": "劳动合同法", "article": "第四十七条"}),
]
WITHKEY = [
    Document(
        page_content="民法典第六百七十五条 借款期限",
        metadata={"source": "民法典", "article": "第六百七十五条", "category": "民法"},
    ),
    Document(
        page_content="劳动合同法第四十七条 经济补偿",
        metadata={"source": "劳动合同法", "article": "第四十七条", "category": "劳动法"},
    ),
]


class FakeChromaCollection:
    """按实测语义复刻 chromadb 0.4.24：metadata 里缺该键的行，$eq 与 $ne 都排除它。"""

    def __init__(self, name, docs):
        self.name = name
        self.docs = docs
        self.get_calls = []

    def count(self):
        return len(self.docs)

    def get(self, where=None, limit=None, include=None):
        self.get_calls.append({"where": where, "limit": limit})
        want = (where or {}).get("category")
        rows = []
        for d in self.docs:
            has = "category" in (d.metadata or {})
            if isinstance(want, dict):
                keep = has and d.metadata.get("category") != want["$ne"]
            else:
                keep = has and d.metadata.get("category") == want
            if keep:
                rows.append(d)
        if limit is not None:
            rows = rows[:limit]
        return {"ids": [str(i) for i in range(len(rows))], "metadatas": [d.metadata for d in rows]}


class FakeVS:
    def __init__(self, docs, name="legal_provisions_cos"):
        self.docs = docs
        self.filters = []
        self._collection = FakeChromaCollection(name, docs)

    def similarity_search_with_score(self, query, k=4, filter=None):
        self.filters.append(filter)
        if filter is None:
            return [(d, 0.5) for d in self.docs[:k]]
        want = filter.get("category")
        if want is None:
            return [(d, 0.5) for d in self.docs[:k]]
        return [(d, 0.5) for d in self.docs if (d.metadata or {}).get("category") == want][:k]


@pytest.fixture(autouse=True)
def _reset_state():
    # 容忍「实现还不存在」：本轮判据要红在行为断言上，不是红在 AttributeError 上。
    seen = getattr(retrieval, "_CATEGORY_MISS_SEEN", None)
    adv = getattr(retrieval, "_CATEGORY_ADVERTISED", None)
    if seen is not None:
        seen.clear()
    if adv is not None:
        adv.clear()
    yield
    if seen is not None:
        seen.clear()
    if adv is not None:
        adv.clear()


def _outcomes(caplog):
    return sorted(
        {
            getattr(r, "category_filter_outcome", "?")
            for r in caplog.records
            if r.getMessage() == "retrieval_category_filter_miss"
        }
    )


def test_S2_library_advertises_category_but_not_this_value_stays_empty():
    """正身：库里带键、问的类不存在 ⇒ 返回零，且不得再发无过滤查询冒充。"""
    vs = FakeVS(WITHKEY)
    retrieval.vectorstore = vs
    got = retrieval.vector_top("行政处罚的设定", n=2, category="行政法")
    contents = [d.page_content for d, _ in got]
    assert contents == [], "库里确实没有该类时应返回零，实际拿到了：" + repr(contents)
    assert vs.filters == [{"category": "行政法"}], "不得为凑出结果而补发无过滤查询：" + repr(vs.filters)


def test_S2_outcome_is_logged_as_no_match_not_fallback(caplog):
    vs = FakeVS(WITHKEY)
    retrieval.vectorstore = vs
    with caplog.at_level(logging.WARNING, logger="legal.retrieval"):
        retrieval.vector_top("行政处罚的设定", n=2, category="行政法")
    assert _outcomes(caplog) == ["filter_no_match_kept_empty"], "归因写错：" + repr(_outcomes(caplog))


def test_S1_library_without_the_key_still_falls_back(caplog):
    """现网形状不许回归：库里根本没有该键 ⇒ 仍回落一次，归因记成「这个维度不可过滤」。"""
    vs = FakeVS(NOKEY)
    retrieval.vectorstore = vs
    with caplog.at_level(logging.WARNING, logger="legal.retrieval"):
        got = retrieval.vector_top("经济补偿", n=2, category="行政法")
    assert [d.page_content for d, _ in got] == [d.page_content for d in NOKEY[:2]]
    assert vs.filters == [{"category": "行政法"}, None], "应只补发一次无过滤：" + repr(vs.filters)
    assert _outcomes(caplog) == ["filter_unsupported_fell_back"], "归因写错：" + repr(_outcomes(caplog))


def test_S3_requested_category_present_queries_once_only():
    vs = FakeVS(WITHKEY)
    retrieval.vectorstore = vs
    got = retrieval.vector_top("经济补偿", n=2, category="劳动法")
    assert [d.page_content for d, _ in got] == ["劳动合同法第四十七条 经济补偿"]
    assert vs.filters == [{"category": "劳动法"}], "命中路径不该有第二次查询：" + repr(vs.filters)


def test_bm25_side_shares_the_same_verdict(monkeypatch):
    """BM25 的 category 是 Python 谓词，判「键存不存在」必须与向量侧同结论：带键而值不匹配 ⇒ 零结果。"""
    calls = []

    def spy(model, docs, query, n, category=None, valid=None):
        calls.append(category)
        if category is None:
            return []
        return [(d, 1.0) for d in docs if (d.metadata or {}).get("category") == category][:n]

    monkeypatch.setattr(retrieval.rc, "bm25_top", spy)
    monkeypatch.setattr(retrieval, "_ensure_bm25", lambda: (types.SimpleNamespace(model="stub"), WITHKEY))
    out = retrieval.bm25_top("行政处罚的设定", n=2, category="行政法")
    assert [d.page_content for d, _ in out] == [], "BM25 侧同样不得跨类冒充：" + repr([d.page_content for d, _ in out])
    assert calls == ["行政法"], "不该为凑结果再跑一次无 category 的检索：" + repr(calls)


def test_grounded_top_score_does_not_borrow_other_categories():
    vs = FakeVS(WITHKEY)
    retrieval.vectorstore = vs
    score = retrieval.grounded_top_score("行政处罚的设定", category="行政法")
    assert score == 0.0, "带键而类不存在时沉淀打分必须是 0，拿到：" + repr(score)
    assert vs.filters == [{"category": "行政法"}], "打分侧也不许补发无过滤查询：" + repr(vs.filters)


def test_presence_verdict_cached_and_cleared_on_invalidate():
    vs = FakeVS(WITHKEY)
    retrieval.vectorstore = vs
    assert retrieval._corpus_advertises_category(vs) is True
    probes = len(vs._collection.get_calls)
    assert probes >= 1, "判定应当真的去问集合，而不是恒真"
    assert retrieval._corpus_advertises_category(vs) is True
    assert len(vs._collection.get_calls) == probes, "同一集合的判定不该每次重探"
    retrieval.invalidate()
    assert getattr(retrieval, "_CATEGORY_ADVERTISED", None) == {}, "invalidate() 必须清判定缓存"
    vs2 = FakeVS(NOKEY)
    assert retrieval._corpus_advertises_category(vs2) is False, "S1 形状必须判成不带这个维度"


def test_probe_unavailable_keeps_the_old_shape():
    """没有 _collection 出口（含别处的替身）时不许变成「不回落的硬失败」。"""
    vs = FakeVS(NOKEY)
    del vs._collection
    retrieval.vectorstore = vs
    got = retrieval.vector_top("经济补偿", n=2, category="行政法")
    assert [d.page_content for d, _ in got] == [d.page_content for d in NOKEY[:2]], "探针不可用时应维持回落"
    assert vs.filters == [{"category": "行政法"}, None]


def test_legacy_always_fallback_shape_cannot_pass_S2():
    """负向自证：改前的逻辑对 S2 必补发无过滤查询 ⇒ 若这条「过」了说明判据对象是空的。"""
    probes = []

    class LegacyShape:
        def __init__(self, docs):
            self.docs = docs
            self.filters = []

        def similarity_search_with_score(self, query, k=4, filter=None):
            self.filters.append(filter)
            if filter is None:
                return [(d, 0.5) for d in self.docs[:k]]
            want = filter.get("category")
            hits = [(d, 0.5) for d in self.docs if (d.metadata or {}).get("category") == want]
            if not hits and want:
                probes.append("legacy_fallback")
                hits = [(d, 0.5) for d in self.docs[:k]]
            return hits[:k]

    legacy = LegacyShape(WITHKEY)
    out = legacy.similarity_search_with_score("行政处罚的设定", k=2, filter={"category": "行政法"})
    assert probes == ["legacy_fallback"], "旧形状若不再兜底，这条负控就没咬住任何东西"
    assert [d.page_content for d, _ in out] == [d.page_content for d in WITHKEY[:2]], "旧形状确实把跨类内容当了答案"
