"""DB-16（2026-10-09，审查报告 B-05）：`category` 过滤落空时必须回落无过滤并留痕。

为什么这是缺陷而不是"库里没有就不给"：
- 现网两个条文集合的 metadata **没有 `category` 键**（实测各 10,266 行、每行 8 键，报告 §12.6）；
- Chroma 0.4.24 对"缺失键"的 `$eq` **排除该行**，`$ne` 同样排除（实测九腿，报告 §12.3）⇒ 没有逃生门；
- BM25 侧的过滤是 Python 谓词 `retrieval_core.py:228`，而 `_ensure_bm25` 的文档取自**同一个**
  `_collection.get()` ⇒ 两个池一起清零；
- Planner 系统提示词此前**明写「category 可选」**（`agent/runtime.py:85`，本轮已删）
  ⇒ 模型是被邀请传它的，不是它自己乱想；
- 改前**零日志**：Agent 只看到 MISSING_EVIDENCE，运维把"系统过滤不了"读成"库里没这条法"
  （09-26 那次把 rerank 降权误读成召回缺口，就是同一类误诊）。

本文件的替身**按实测到的 Chroma 语义**实现（缺键 ⇒ 过滤取零），不是按我希望的语义。
"""

from __future__ import annotations

import logging

import pytest
from langchain_core.documents import Document

import retrieval

DOCS = [
    (
        Document(
            page_content="民法典第六百七十五条 借款期限", metadata={"source": "民法典", "article": "第六百七十五条"}
        ),
        0.1,
    ),
    (
        Document(
            page_content="民法典第五百七十七条 违约责任", metadata={"source": "民法典", "article": "第五百七十七条"}
        ),
        0.2,
    ),
    (
        Document(
            page_content="劳动合同法第四十七条 经济补偿", metadata={"source": "劳动合同法", "article": "第四十七条"}
        ),
        0.3,
    ),
]


class _FakeVectorstore:
    """复刻 §12.3 实测到的语义：**没有任何文档带该键** ⇒ 带 category 的 where 取零，无过滤取全量。"""

    def __init__(self) -> None:
        self.filters: list[dict | None] = []

    def similarity_search_with_score(self, query: str, k: int = 4, filter: dict | None = None):
        self.filters.append(filter)
        if filter is None:
            return list(DOCS)[:k]
        # 库里没有 `category` 键 ⇒ Chroma 把每一行都排除（LEG-7 的实测结果）
        if "category" in filter:
            return []
        return list(DOCS)[:k]


@pytest.fixture()
def fake_vs(monkeypatch):
    vs = _FakeVectorstore()
    monkeypatch.setattr(retrieval, "vectorstore", vs)
    return vs


@pytest.fixture(autouse=True)
def _reset_seen():
    retrieval._CATEGORY_MISS_SEEN.clear()
    yield
    retrieval._CATEGORY_MISS_SEEN.clear()


def test_vector_top_falls_back_when_category_filters_everything_out(fake_vs):
    got = retrieval.vector_top("借款期限", n=2, category="民法")
    assert [d.page_content for d, _ in got] == [d.page_content for d, _ in DOCS[:2]], "回落后应拿到无过滤的结果"
    assert fake_vs.filters == [{"category": "民法"}, None], f"应先带过滤、再回落一次无过滤：{fake_vs.filters}"


def test_vector_top_without_category_does_not_double_query(fake_vs):
    """控制腿（防回落变成无条件重查）：category=None 时**只查一次**，行为与改前逐字一致。"""
    retrieval.vector_top("借款期限", n=2, category=None)
    assert fake_vs.filters == [None]


def test_category_miss_is_logged_once_per_value_with_attribution(fake_vs, caplog):
    """回落必须留痕，且同值不刷屏（否则过载时日志被自己淹掉）。"""
    with caplog.at_level(logging.WARNING, logger="legal.retrieval"):
        retrieval.vector_top("借款期限", n=2, category="民法")
        retrieval.vector_top("违约责任", n=2, category="民法")
        retrieval.vector_top("经济补偿", n=2, category="劳动法")
    hits = [r for r in caplog.records if r.getMessage() == "retrieval_category_filter_miss"]
    assert len(hits) == 2, f"每个 category 值各记一次：{[getattr(r, 'category_filter_value', None) for r in hits]}"
    assert {r.category_filter_value for r in hits} == {"民法", "劳动法"}
    assert {r.category_filter_stage for r in hits} == {"vector_top"}


def test_bm25_top_falls_back_when_no_document_carries_the_category(monkeypatch):
    docs = [d for d, _ in DOCS]
    model = retrieval.rc.build_bm25(docs)
    monkeypatch.setattr(retrieval, "_ensure_bm25", lambda: (model, docs))
    got = retrieval.bm25_top("经济补偿", n=2, category="民法")
    assert got, "BM25 侧也必须回落，否则候选池仍被单边清零"
    assert all(d.page_content for d, _ in got)


def test_grounded_top_score_does_not_return_zero_for_an_unfilterable_category(monkeypatch, fake_vs):
    """沉淀打分侧同一形状：改前带 category 直接 0.0 ⇒ 该题**永不进待审队列**且无人知晓。"""
    monkeypatch.setattr(retrieval, "_collection_is_cosine", lambda: True)
    score = retrieval.grounded_top_score("借款期限", category="民法")
    assert score > 0.0, f"回落之后应拿到非零分，实得 {score}"
    assert fake_vs.filters == [{"category": "民法"}, None]


def test_planner_prompt_no_longer_invites_the_category_argument():
    """邀请面必须关掉：提示词里那句「category 可选」是这条链的起点（报告 §12.3 第 1 步）。"""
    from legal_workflow.runtime import _PLANNER_SYSTEM_PROMPT

    assert "category 可选" not in _PLANNER_SYSTEM_PROMPT
    assert '"k":4' in _PLANNER_SYSTEM_PROMPT, "提示词的其他工具说明不能被顺手删掉"


def test_invalidate_resets_the_miss_log_suppression(fake_vs, caplog):
    """知识增删（`invalidate()`）后必须允许重新留痕（2026-10-09 复核轮 B 路补）。

    抑制器的原话是"同一 (stage, category) 每进程只 warn 一次"。若不随 `invalidate()` 清，
    写侧改过 `category`（或换了一批数据）之后的**第二轮同类异常永远不会再进日志**——
    抑制器反过来把可归因性吃掉了。本腿钉的是"清完后能再 warn 一次"，两半都要：
    先证第一轮的第二次调用确实静默（否则这条腿测不到抑制器），再证 invalidate 之后重新出声。
    """
    with caplog.at_level(logging.WARNING, logger="legal.retrieval"):
        retrieval.vector_top("借款期限", n=2, category="民法")
        retrieval.vector_top("违约责任", n=2, category="民法")
        assert len([r for r in caplog.records if r.getMessage() == "retrieval_category_filter_miss"]) == 1, (
            "抑制器在工作"
        )

        retrieval.invalidate()
        retrieval.vector_top("经济补偿", n=2, category="民法")
    hits = [r for r in caplog.records if r.getMessage() == "retrieval_category_filter_miss"]
    assert len(hits) == 2, f"invalidate() 后应能重新留痕一次，实得 {len(hits)} 条"
