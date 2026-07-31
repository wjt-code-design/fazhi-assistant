"""检索编排：向量 + BM25(jieba) 经 RRF 融合 + 结果缓存 + 重排回落。

- HYBRID=1（默认）：向量与 BM25 双路召回 + RRF 融合；对中文法律条号/专有名词的精确匹配是语义检索的短板，BM25 补齐。
- RETRIEVAL_RERANK=1（默认关）：重排接口已就绪，模型加载与启用在此开关后填充；关闭时安全回落为原顺序。
- 检索结果按 (mode,query,category,k) 做 LRU 缓存；知识增删时调 invalidate() 失效。
- BM25 索引惰性构建并缓存；增删知识后 invalidate() 重建。
"""
import math
import os
import threading
from datetime import date
from typing import List, Optional, Tuple

from langchain_core.documents import Document

from rag_chain import vectorstore, embeddings
import retrieval_core as rc

from settings import settings

RETRIEVAL_RERANK = settings.feature_rerank
HYBRID = settings.feature_hybrid
BM25_K_MULT = 2
# 向量池放大倍数：先取大池，Python 侧按时效谓词过滤后再取 top-n（阶段5）。
# 原因：chromadb 0.4.24 的 where 不支持字符串日期比较，过滤必须留在 Python 侧。
VECTOR_POOL_MULT = 4
VECTOR_POOL_MIN = 32

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


def vector_top(
    query: str,
    n: int,
    category: Optional[str] = None,
    valid: Optional[callable] = None,
) -> List[Tuple[Document, float]]:
    """向量召回。category 走 Chroma where（字符串 $eq 可靠）；时效谓词在 Python 侧过滤（D6）。"""
    filt = {"category": category} if category else None
    fetch_n = max(n * VECTOR_POOL_MULT, VECTOR_POOL_MIN)
    res = vectorstore.similarity_search_with_score(query, k=fetch_n, filter=filt)
    out = []
    for d, s in res:
        if valid and not valid(d.metadata):
            continue
        out.append((d, float(s)))
        if len(out) >= n:
            break
    return out


def _doc_id(d: Document) -> str:
    # 无稳定外部 id 时以内容作融合 key（chunk 内容唯一）
    return d.page_content


def bm25_top(
    query: str,
    n: int,
    category: Optional[str] = None,
    valid: Optional[callable] = None,
) -> List[Tuple[Document, float]]:
    _ensure_bm25()
    if _bm25 is None:
        return []
    return rc.bm25_top(_bm25, _bm25_docs, query, n, category, valid=valid)


def hybrid_retrieve(
    query: str,
    k: int = 4,
    category: Optional[str] = None,
    cutoff: Optional[str] = None,
) -> List[Document]:
    """混合检索（向量+BM25 RRF）。cutoff 为时效判定日期（'YYYY-MM-DD'，默认今天）。

    时效过滤（阶段5）：向量池与 BM25 池在 Python 侧共用 is_valid_by_time 谓词；
    缓存 key 含 cutoff，跨日旧 key 自然淘汰。
    """
    cutoff = cutoff or date.today().isoformat()
    valid = lambda m: rc.is_valid_by_time(m, cutoff)  # noqa: E731
    key = ("h", query, category, k, cutoff)
    hit = _cache.get(key)
    if hit is not None:
        return hit
    if not HYBRID:
        docs = [d for d, _ in vector_top(query, k, category, valid=valid)]
        docs = rc.rerank(query, docs, enabled=RETRIEVAL_RERANK)
        _cache.put(key, docs)
        return docs
    n = max(k * BM25_K_MULT, 4)
    v = vector_top(query, n, category, valid=valid)
    b = bm25_top(query, n, category, valid=valid)
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


def retrieve(
    query: str,
    k: int = 4,
    category: Optional[str] = None,
    cutoff: Optional[str] = None,
) -> List[Document]:
    """兼容旧调用：默认走混合检索。cutoff 缺省为今天。"""
    return hybrid_retrieve(query, k, category, cutoff)


def grounded_top_score(query: str, category: Optional[str] = None, cutoff: Optional[str] = None) -> float:
    """受控沉淀打分：只对"当前仍有效"的条文计分（阶段5），避免沉淀失效条文。"""
    cutoff = cutoff or date.today().isoformat()
    valid = lambda m: rc.is_valid_by_time(m, cutoff)  # noqa: E731
    res = vectorstore.similarity_search(
        query, k=max(VECTOR_POOL_MIN, 8), filter=({"category": category} if category else None)
    )
    res = [d for d in res if valid(d.metadata)]
    if not res:
        return 0.0
    try:
        qv = embeddings.embed_query(query)
        dv = embeddings.embed_documents([res[0].page_content])[0]
        return _cos(qv, dv)
    except Exception:
        return 0.0


def _hit_dict(d: Document, score: float) -> dict:
    """管理端检索测试条目：不过滤时效（全量展示），追加三键供管理员核对（D5）。"""
    return {
        "chunk": d.page_content,
        "source": d.metadata.get("source", ""),
        "article": d.metadata.get("article", ""),
        "origin": d.metadata.get("origin", ""),
        "status": d.metadata.get("status", "现行"),
        "effective_from": d.metadata.get("effective_from", ""),
        "effective_to": d.metadata.get("effective_to", ""),
        "score": round(float(score), 4),
    }


def retrieve_for_test(query: str, k: int = 5):
    """管理员检索测试：返回 top-k + 余弦相关度（语义分，便于解释）；不过滤已废止条文。"""
    res = vectorstore.similarity_search_with_score(query, k=k)
    if not res:
        return []
    try:
        qv = embeddings.embed_query(query)
        dvs = embeddings.embed_documents([d.page_content for d, _ in res])
    except Exception:
        return [_hit_dict(d, 0.0) for d, _ in res]
    out = []
    for (d, _s), dv in zip(res, dvs):
        out.append(_hit_dict(d, _cos(qv, dv)))
    out.sort(key=lambda x: x["score"], reverse=True)
    return out
