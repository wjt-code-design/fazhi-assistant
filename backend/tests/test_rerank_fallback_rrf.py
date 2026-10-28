"""rerank 失败回退契约（2026-10-24 首字优化）。

钉住的契约：rerank 返回 None（超时/配额耗尽/未配置）时，`hybrid_retrieve`
必须直接用已算好的 RRF 序，**不得**调用 `_cosine_rank` 整池重嵌。
背景：实测旧回退把单次问答从 4.7s 劣化到 23.5s——失败路径不能比成功路径慢一个数量级。
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from langchain_core.documents import Document  # noqa: E402

import retrieval  # noqa: E402
from settings import settings  # noqa: E402

Q = "公司拖欠工资并口头解除劳动合同，能否主张经济补偿？"


def _mk_docs(n: int, tag: str) -> list:
    return [
        (Document(page_content=f"{tag}-{i}", metadata={"source": "民法典", "article": f"第{i}条"}), 1.0)
        for i in range(n)
    ]


def test_rerank_none_uses_rrf_without_reembedding(monkeypatch):
    calls = []
    monkeypatch.setattr(retrieval.query_understand, "decompose", lambda q: [(q, "original")])
    monkeypatch.setattr(retrieval, "vector_top", lambda *a, **kw: _mk_docs(4, "v"))
    monkeypatch.setattr(retrieval, "bm25_top", lambda *a, **kw: _mk_docs(4, "b"))
    monkeypatch.setattr(settings, "rerank_enabled", True)
    monkeypatch.setattr(settings, "retrieval_pool_k", 0)
    monkeypatch.setattr(settings, "query_expansion_enabled", False)
    monkeypatch.setattr(retrieval, "_rerank_docs", lambda *a, **kw: calls.append(1) or None)

    def _forbidden(*_a, **_kw):
        raise AssertionError("rerank 返回 None 时不得调用 _cosine_rank 整池重嵌")

    monkeypatch.setattr(retrieval, "_cosine_rank", _forbidden)

    retrieval.invalidate()
    out = retrieval.hybrid_retrieve(Q, k=4)

    assert calls, "测试未真正走到 rerank 分支"
    assert len(out) == 4
