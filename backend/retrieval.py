"""检索编排：向量 + BM25(jieba) 经 RRF 融合 + 结果缓存 + 重排回落。

- HYBRID=1（默认）：向量与 BM25 双路召回 + RRF 融合；对中文法律条号/专有名词的精确匹配是语义检索的短板，BM25 补齐。
- RETRIEVAL_RERANK=1（默认关）：重排接口已就绪，模型加载与启用在此开关后填充；关闭时安全回落为原顺序。
- 检索结果按 (mode,query,category,k) 做 LRU 缓存；知识增删时调 invalidate() 失效。
- BM25 索引惰性构建并缓存；增删知识后 invalidate() 重建。
"""
import math
import os
import threading
from typing import List, Optional, Tuple

from langchain_core.documents import Document

from rag_chain import vectorstore, embeddings
import retrieval_core as rc

from settings import settings

RETRIEVAL_RERANK = settings.feature_rerank
HYBRID = settings.feature_hybrid
BM25_K_MULT = 2

_cache = rc.LRU()
_bm25_lock = threading.Lock()
_bm25 = None
_bm25_docs: List[Document] = []


def invalidate() -> None:
    """知识增删后调用：清空 BM25 索引与结果缓存。"""
    global _bm25, _bm25_docs
    with _bm25_lock:
        _bm25 = None
        _bm25_docs = []
    _cache.clear()


def _ensure_bm25() -> None:
    global _bm25, _bm25_docs
    with _bm25_lock:
        if _bm25 is not None:
            return
        data = vectorstore._collection.get(include=["documents", "metadatas"])
        docs = [
            Document(
                page_content=data["documents"][i],
                metadata=(data["metadatas"][i] if data["metadatas"] else {}),
            )
            for i in range(len(data["ids"]))
        ]
        _bm25 = rc.build_bm25(docs)
        _bm25_docs = docs


def _cos(a, b) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(x * x for x in b)) or 1.0
    return dot / (na * nb)


def vector_top(query: str, n: int, category: Optional[str] = None) -> List[Tuple[Document, float]]:
    filt = {"category": category} if category else None
    res = vectorstore.similarity_search_with_score(query, k=n, filter=filt)
    return [(d, float(s)) for d, s in res]


def _doc_id(d: Document) -> str:
    # 无稳定外部 id 时以内容作融合 key（chunk 内容唯一）
    return d.page_content


def bm25_top(query: str, n: int, category: Optional[str] = None) -> List[Tuple[Document, float]]:
    _ensure_bm25()
    if _bm25 is None:
        return []
    return rc.bm25_top(_bm25, _bm25_docs, query, n, category)


def hybrid_retrieve(query: str, k: int = 4, category: Optional[str] = None) -> List[Document]:
    key = ("h", query, category, k)
    hit = _cache.get(key)
    if hit is not None:
        return hit
    if not HYBRID:
        docs = [d for d, _ in vector_top(query, k, category)]
        docs = rc.rerank(query, docs, enabled=RETRIEVAL_RERANK)
        _cache.put(key, docs)
        return docs
    n = max(k * BM25_K_MULT, 4)
    v = vector_top(query, n, category)
    b = bm25_top(query, n, category)
    pool = {}
    v_ids: List[str] = []
    b_ids: List[str] = []
    for d, _ in v:
        did = _doc_id(d)
        pool[did] = d
        v_ids.append(did)
    for d, _ in b:
        did = _doc_id(d)
        pool.setdefault(did, d)
        b_ids.append(did)
    fused = rc.rrf([v_ids, b_ids])
    ordered = sorted(fused.items(), key=lambda kv: kv[1], reverse=True)[:k]
    docs = [pool[did] for did, _ in ordered if did in pool]
    docs = rc.rerank(query, docs, enabled=RETRIEVAL_RERANK)
    _cache.put(key, docs)
    return docs


def retrieve(query: str, k: int = 4, category: Optional[str] = None) -> List[Document]:
    """兼容旧调用：默认走混合检索。"""
    return hybrid_retrieve(query, k, category)


def grounded_top_score(query: str, category: Optional[str] = None) -> float:
    res = vectorstore.similarity_search(query, k=1, filter=({"category": category} if category else None))
    if not res:
        return 0.0
    try:
        qv = embeddings.embed_query(query)
        dv = embeddings.embed_documents([res[0].page_content])[0]
        return _cos(qv, dv)
    except Exception:
        return 0.0


def retrieve_for_test(query: str, k: int = 5):
    """管理员检索测试：返回 top-k + 余弦相关度（语义分，便于解释）。"""
    res = vectorstore.similarity_search_with_score(query, k=k)
    if not res:
        return []
    try:
        qv = embeddings.embed_query(query)
        dvs = embeddings.embed_documents([d.page_content for d, _ in res])
    except Exception:
        return [
            {
                "chunk": d.page_content,
                "source": d.metadata.get("source", ""),
                "article": d.metadata.get("article", ""),
                "origin": d.metadata.get("origin", ""),
                "score": 0.0,
            }
            for d, _ in res
        ]
    out = []
    for (d, _s), dv in zip(res, dvs):
        out.append(
            {
                "chunk": d.page_content,
                "source": d.metadata.get("source", ""),
                "article": d.metadata.get("article", ""),
                "origin": d.metadata.get("origin", ""),
                "score": round(_cos(qv, dv), 4),
            }
        )
    out.sort(key=lambda x: x["score"], reverse=True)
    return out
