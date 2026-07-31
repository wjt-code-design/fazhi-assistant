"""检索纯逻辑：分词 / LRU / RRF 融合 / BM25 / 重排回落。

只依赖 stdlib + jieba + rank_bm25 + langchain_core 的 Document 类型，不加载嵌入模型/向量库，
因此可被单元测试快速覆盖。重排模型加载与向量检索在 retrieval.py。
"""
import threading
from collections import OrderedDict
from typing import Dict, List, Optional, Tuple

import jieba
from rank_bm25 import BM25Okapi
from langchain_core.documents import Document

RRF_K = 60


def tokenize(text: str) -> List[str]:
    """中文分词（jieba），过滤空白与纯空白片段。"""
    return [t for t in jieba.cut(text or "") if t and t.strip()]


class LRU:
    """线程安全的简单 LRU 缓存（用于检索结果缓存）。"""

    def __init__(self, maxsize: int = 256):
        self._d: "OrderedDict[tuple, object]" = OrderedDict()
        self._max = maxsize
        self._lock = threading.Lock()

    def get(self, key):
        with self._lock:
            if key in self._d:
                self._d.move_to_end(key)
                return self._d[key]
        return None

    def put(self, key, value) -> None:
        with self._lock:
            self._d[key] = value
            self._d.move_to_end(key)
            while len(self._d) > self._max:
                self._d.popitem(last=False)

    def clear(self) -> None:
        with self._lock:
            self._d.clear()

    def __len__(self) -> int:
        with self._lock:
            return len(self._d)


def rrf(rankings: List[List[str]], k: int = RRF_K) -> Dict[str, float]:
    """Reciprocal Rank Fusion。rankings=多个按相关性排序的 doc-id 列表；返回 id->融合分。纯函数。"""
    scores: Dict[str, float] = {}
    for ranking in rankings:
        for rank, doc_id in enumerate(ranking):
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank + 1)
    return scores


def build_bm25(docs: List[Document]) -> Optional[BM25Okapi]:
    if not docs:
        return None
    return BM25Okapi([tokenize(d.page_content) for d in docs])


def bm25_top(
    bm25: BM25Okapi, docs: List[Document], query: str, n: int, category: Optional[str] = None
) -> List[Tuple[Document, float]]:
    scores = bm25.get_scores(tokenize(query))
    order = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
    out: List[Tuple[Document, float]] = []
    for i in order:
        d = docs[i]
        if category and d.metadata.get("category") != category:
            continue
        out.append((d, float(scores[i])))
        if len(out) >= n:
            break
    return out


def rerank(query: str, docs: List[Document], enabled: bool = False, model=None) -> List[Document]:
    """重排接口。未启用或未加载模型时原样返回（安全回落，保证不破坏现有检索）。

    启用且模型就绪时的接法（占位，模型加载在 retrieval.py 完成后再填充）：
        pairs = [[query, d.page_content] for d in docs]
        scores = model.compute_score(pairs)
        docs = [d for _, d in sorted(zip(scores, docs), key=lambda x: x[0], reverse=True)]
    """
    if not enabled or model is None or not docs:
        return docs
    return docs
