"""候选池深度与「返回条数 k」解耦（2026-09-14）——契约测试（全 mock，非 slow）。

背景：报告 `dispatch-output/quality-retrieval-20260914/REPORT.md` §2c 实测——
原实现把候选池上限绑在 k 上（`v[:k] ∪ b[:k] ∪ RRF[:2k]` = 4k），k=4 时池仅 16 条，
金标条文常落 9–20 名 → 进不了池 → rerank 也无从发挥。

本测试钉住 4 条契约（不依赖真实 KB、不调网络）：
1. `settings.retrieval_pool_k = 0` → 每路召回深度 `n = max(k*BM25_K_MULT, 4)`（与历史逐字一致）；
2. `retrieval_pool_k = N > 0` → `n = max(N*BM25_K_MULT, 4)`，候选池变深；
3. 两种情况下 `hybrid_retrieve` 返回条数**仍为 k**（writer payload 不膨胀）；
4. `pool_k` 参与缓存 key —— 改 pool_k 后不会串用旧池深的缓存结果。
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from langchain_core.documents import Document  # noqa: E402

import retrieval  # noqa: E402
from settings import settings  # noqa: E402


def _mk_docs(n: int, tag: str) -> list:
    return [
        (Document(page_content=f"{tag}-{i}", metadata={"source": "民法典", "article": f"第{i}条"}), 1.0)
        for i in range(n)
    ]


def _patch_pipeline(monkeypatch, recorded: list) -> None:
    """把 hybrid_retrieve 的外部依赖全部替换为确定性桩。"""
    monkeypatch.setattr(retrieval.query_understand, "decompose", lambda q: [(q, "original")])

    def _vector_top(query, n, category=None, valid=None):
        recorded.append(("v", n))
        return _mk_docs(n, "v")

    def _bm25_top(query, n, category=None, valid=None):
        recorded.append(("b", n))
        return _mk_docs(n, "b")

    monkeypatch.setattr(retrieval, "vector_top", _vector_top)
    monkeypatch.setattr(retrieval, "bm25_top", _bm25_top)
    # 关 rerank → 走 _cosine_rank；再把它替换为恒等，避免真实嵌入
    monkeypatch.setattr(settings, "rerank_enabled", False)
    monkeypatch.setattr(retrieval, "_cosine_rank", lambda q, docs: docs)
    retrieval.invalidate()  # 清缓存，避免与其它用例串用


def test_pool_k_default_equals_k_and_return_count_unchanged(monkeypatch):
    """契约 1 + 3：默认 0 → 池深=k（历史行为），返回条数=k。"""
    recorded: list = []
    _patch_pipeline(monkeypatch, recorded)
    monkeypatch.setattr(settings, "retrieval_pool_k", 0)

    out = retrieval.hybrid_retrieve("装修公司延期是否构成违约", k=4)

    assert recorded == [("v", 16), ("b", 16)], recorded  # n = max(4*4, 4) = 16
    assert len(out) == 4  # 返回条数仍为 k


def test_pool_k_decoupled_deepens_pool_but_not_return_count(monkeypatch):
    """契约 2 + 3：pool_k=20 → n=max(20*4,4)=80，但返回仍为 k=4。"""
    recorded: list = []
    _patch_pipeline(monkeypatch, recorded)
    monkeypatch.setattr(settings, "retrieval_pool_k", 20)

    out = retrieval.hybrid_retrieve("装修公司延期是否构成违约", k=4)

    assert recorded == [("v", 80), ("b", 80)], recorded
    assert len(out) == 4


def test_pool_k_part_of_cache_key(monkeypatch):
    """契约 4：pool_k 变了必须重算，不能命中旧池深缓存。"""
    recorded: list = []
    _patch_pipeline(monkeypatch, recorded)
    query = "装修公司以材料涨价为由要求增加工程款是否合法有效？"

    monkeypatch.setattr(settings, "retrieval_pool_k", 0)
    retrieval.hybrid_retrieve(query, k=4)
    assert recorded == [("v", 16), ("b", 16)]

    # 同 query、同 k，仅 pool_k 变化 → 必须再次调用召回（池深不同）
    monkeypatch.setattr(settings, "retrieval_pool_k", 20)
    retrieval.hybrid_retrieve(query, k=4)
    assert recorded == [("v", 16), ("b", 16), ("v", 80), ("b", 80)], recorded

    # 完全相同的参数再次调用 → 命中缓存，不再新增召回调用
    retrieval.hybrid_retrieve(query, k=4)
    assert recorded == [("v", 16), ("b", 16), ("v", 80), ("b", 80)], recorded
