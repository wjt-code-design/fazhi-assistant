"""检索编排：向量 + BM25(jieba) 经 RRF 融合 + 结果缓存 + 重排回落。

- HYBRID=1（默认）：向量与 BM25 双路召回 + RRF 融合；对中文法律条号/专有名词的精确匹配是语义检索的短板，BM25 补齐。
- RETRIEVAL_RERANK=1（默认关）：重排接口已就绪，模型加载与启用在此开关后填充；关闭时安全回落为原顺序。
- 检索结果按 (mode,query,category,k) 做 LRU 缓存；知识增删时调 invalidate() 失效。
- BM25 索引惰性构建并缓存；增删知识后 invalidate() 重建。
"""
import math
import os
import re
import threading
from datetime import date
from typing import List, Optional, Tuple

from langchain_core.documents import Document

from rag_chain import vectorstore, embeddings
import retrieval_core as rc

from settings import settings

# ---- 条号直查路由（阶段7.2）：《法名》第X条 / 法名第X条 → 精确查找，零嵌入零检索 ----
_ART_FULL_RE = re.compile(
    r"《([^》]{1,24}?)》\s*(第[零〇○一二三四五六七八九十百千万0-9０-９]+条(?:之[一二三四五六七八九十百千万0-9０-９]+)?)"
)
_ART_NO_BRACKET_RE = re.compile(
    r"(?<!《)([一-龥]{1,13}?(?:法|典|条例|规定|办法))"
    r"\s*(第[零〇○一二三四五六七八九十百千万0-9０-９]+条(?:之[一二三四五六七八九十百千万0-9０-９]+)?)"
)
_PREFIX_CN = "中华人民共和国"

_CN_DIGITS = "零一二三四五六七八九"  # 下标即数字值（d=1 → 一）


def _num_to_cn(n: int) -> str:
    """阿拉伯数字条号 → 中文条号（1→一, 10→十, 19→十九, 108→一百零八, 1260→一千二百六十）。"""
    if n == 0:
        return "零"
    s = str(n)
    length = len(s)
    out = []
    for i, ch in enumerate(s):
        d = int(ch)
        pos = length - i - 1
        if d == 0:
            if out and out[-1] != "零" and any(int(c) != 0 for c in s[i + 1:]):
                out.append("零")
            continue
        if pos == 1 and d == 1 and i == 0 and length > 1:
            pass  # 十位为 1 且为首位：不写前导「一」（13=十三，不是一十三）
        else:
            out.append(_CN_DIGITS[d])
        if pos % 4 == 1:
            out.append("十")
        elif pos % 4 == 2:
            out.append("百")
        elif pos % 4 == 3:
            out.append("千")
        elif pos == 4:
            out.append("万")
    return "".join(out)


def _normalize_article(art: str) -> str:
    """条号归一：〇→零（«第一百〇一条» 与 «第一百零一条» 视为同一）；阿拉伯数字转中文。"""
    m = re.match(r"^第([零〇○一二三四五六七八九十百千万0-9０-９]+)条(之[一二三四五六七八九十百千万0-9０-９]+)?$", art)
    if not m:
        return art
    num = m.group(1).replace("〇", "零").replace("○", "零")
    if num.isdigit():
        num = _num_to_cn(int(num))
    tail = m.group(2) or ""
    if tail:
        tail = tail.replace("〇", "零").replace("○", "零")
        if tail[1:].isdigit():
            tail = "之" + _num_to_cn(int(tail[1:]))
    return "第" + num + "条" + tail


def parse_article_query(query: str):
    """识别「《劳动法》第三条」「中华人民共和国劳动合同法第十九条」「刑法第13条」→ (source, article) 或 None。"""
    m = _ART_FULL_RE.search(query) or _ART_NO_BRACKET_RE.search(query)
    if not m:
        return None
    name = m.group(1).strip()
    if name.startswith(_PREFIX_CN):
        name = name[len(_PREFIX_CN):]
    return name, _normalize_article(m.group(2))


def exact_article_lookup(source: str, article: str, cutoff: Optional[str] = None) -> List[Document]:
    """精确条号查找（含时效过滤，与检索同口径）。返回匹配 Document 列表。"""
    cutoff = cutoff or date.today().isoformat()
    data = vectorstore._collection.get(
        where={"$and": [{"source": source}, {"article": article}]},
        include=["documents", "metadatas"],
    )
    docs = []
    for i in range(len(data["ids"])):
        meta = data["metadatas"][i]
        if not rc.is_valid_by_time(meta, cutoff):
            continue
        docs.append(Document(page_content=data["documents"][i], metadata=meta))
    return docs


def _norm_source(name: str) -> str:
    """法名归一：去「中华人民共和国」前缀，便于答案引用与 sources 对齐。"""
    name = (name or "").strip()
    return name[len(_PREFIX_CN):] if name.startswith(_PREFIX_CN) else name


def citation_verify(answer: str, sources: List[dict]) -> List[str]:
    """防假引用（优化路线 B0.1）：抽取答案中所有《法名》第X条，与检索返回的 sources 比对。

    返回**异常引用**列表（引用了未出现在检索结果中的法条 = 疑似模型凭记忆编造）。
    sources 每项含 {source, article}。法名/条号均归一化后比对（全称=简称、〇=零）。
    """
    ok_set = {(_norm_source(s.get("source", "")), _normalize_article(s.get("article", ""))) for s in sources}
    bad = []
    for m in _ART_FULL_RE.finditer(answer):
        key = (_norm_source(m.group(1)), _normalize_article(m.group(2)))
        if key not in ok_set:
            bad.append(m.group(0))
    # 去重保序
    seen, uniq = set(), []
    for b in bad:
        if b not in seen:
            seen.add(b)
            uniq.append(b)
    return uniq

RETRIEVAL_RERANK = settings.feature_rerank
HYBRID = settings.feature_hybrid
# 池放大倍数：千级语料下小池会丢掉相关条文（RRF 需要条文同时进双池才有融合分）。
# 实测：k=4 时池=8，相关条文排第 6/10 位会掉出 top-4；池=16 后恢复。
BM25_K_MULT = 4
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
    """兼容旧调用。条号直查路由优先（《法名》第X条 → 精确查找，确定性命中）；
    未识别或未命中则回退混合检索。cutoff 缺省为今天。"""
    parsed = parse_article_query(query)
    if parsed:
        source, article = parsed
        exact = exact_article_lookup(source, article, cutoff)
        if exact:
            return exact
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
