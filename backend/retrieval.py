"""检索层（阶段1：相似度 + 元数据过滤 + 检索测试 + 余弦 grounded 分）。

混合 RRF / 重排 / 父文档 放阶段2。
注意 BGE 对 query 与 document 使用不同指令，故 query 用 embed_query、文档用 embed_documents。
"""
import math
from typing import List, Optional

from langchain_core.documents import Document

from rag_chain import vectorstore, embeddings


def _cos(a: List[float], b: List[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(x * x for x in b)) or 1.0
    return dot / (na * nb)


def _filter(category: Optional[str]):
    return {"category": category} if category else None


def retrieve(query: str, k: int = 4, category: Optional[str] = None) -> List[Document]:
    return vectorstore.similarity_search(query, k=k, filter=_filter(category))


def grounded_top_score(query: str, category: Optional[str] = None) -> float:
    """query 与 top1 命中文档的余弦相似度 [0,1]，用于受控沉淀阈值；无命中返回 0。"""
    docs = vectorstore.similarity_search(query, k=1, filter=_filter(category))
    if not docs:
        return 0.0
    try:
        qv = embeddings.embed_query(query)
        dv = embeddings.embed_documents([docs[0].page_content])[0]
        return _cos(qv, dv)
    except Exception:
        return 0.0


def retrieve_for_test(query: str, k: int = 5) -> List[dict]:
    """管理员'检索测试'：返回 top-k 命中 + 余弦分（按分降序）。"""
    docs = vectorstore.similarity_search(query, k=k)
    if not docs:
        return []
    try:
        qv = embeddings.embed_query(query)
        dvs = embeddings.embed_documents([d.page_content for d in docs])
    except Exception:
        qv, dvs = None, None
    out = []
    for d, dv in zip(docs, dvs or [None] * len(docs)):
        score = round(_cos(qv, dv), 4) if (qv is not None and dv is not None) else 0.0
        out.append(
            {
                "chunk": d.page_content,
                "source": d.metadata.get("source", ""),
                "article": d.metadata.get("article", ""),
                "origin": d.metadata.get("origin", ""),
                "score": score,
            }
        )
    out.sort(key=lambda x: x["score"], reverse=True)
    return out
