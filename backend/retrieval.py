"""检索编排：向量 + BM25(jieba) 经 RRF 融合召回候选池 + 池内余弦精排 + 结果缓存 + 重排回落。

- HYBRID=1（默认）：向量与 BM25 双路召回 + RRF 融合；对中文法律条号/专有名词的精确匹配是语义检索的短板，BM25 补齐。
- RETRIEVAL_RERANK=1（默认关）：重排接口已就绪，模型加载与启用在此开关后填充；关闭时安全回落为原顺序。
- 检索结果按 (mode,query,category,k) 做 LRU 缓存；知识增删时调 invalidate() 失效。
- BM25 索引惰性构建并缓存；增删知识后 invalidate() 重建。
"""

import math
import re
import threading
from collections.abc import Callable
from datetime import date

from langchain_core.documents import Document

import retrieval_core as rc
from domain_rules import canon_source
from rag_chain import embeddings, vectorstore
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
    out: list[str] = []
    for i, ch in enumerate(s):
        d = int(ch)
        pos = length - i - 1
        if d == 0:
            if out and out[-1] != "零" and any(int(c) != 0 for c in s[i + 1 :]):
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


# ---- 检索措辞桥接：用户口语与条文语言的词面鸿沟 ----
# 实测 bad case：复议法第11条全文无「受案范围」（只有 12 条反面条款有），BGE/BM25 都吃字面，
# 不改写则 11 条永远进不了池；「高空抛物」被 BGE 嵌入到「高度危险责任」区域，1254 条压不出。
# 桥接只影响检索输入，不改问答原文。词面命中后 BM25 捞进池，余弦精排在池内定序。
_QUERY_BRIDGE = [
    (re.compile(r"高空抛物"), "从建筑物中抛掷物品"),
    (re.compile(r"受案范围"), "申请行政复议"),
]


def _bridge_query(query: str) -> str:
    """把口语关键词改写为条文用语（仅检索层）。"""
    for pat, rep in _QUERY_BRIDGE:
        query = pat.sub(rep, query)
    return query


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
        name = name[len(_PREFIX_CN) :]
    return name, _normalize_article(m.group(2))


def exact_article_lookup(source: str, article: str, cutoff: str | None = None) -> list[Document]:
    """精确条号查找（含时效过滤，与检索同口径）。返回匹配 Document 列表。"""
    cutoff = cutoff or date.today().isoformat()
    source = canon_source(source)  # 简称→全称（库内存全称，民诉法→民事诉讼法）
    data = vectorstore._collection.get(
        where={"$and": [{"source": source}, {"article": article}]},
        include=["documents", "metadatas"],
    )
    docs = []
    metas = data["metadatas"] or []
    documents = data["documents"] or []
    for i in range(len(data["ids"])):
        meta = metas[i]
        if not rc.is_valid_by_time(meta, cutoff):
            continue
        docs.append(Document(page_content=documents[i], metadata=meta))
    return docs


def _norm_source(name: str) -> str:
    """法名归一：去「中华人民共和国」前缀，便于答案引用与 sources 对齐。"""
    name = (name or "").strip()
    return name[len(_PREFIX_CN) :] if name.startswith(_PREFIX_CN) else name


def _source_key(name: str) -> str:
    """KB 源名归一（用于存在性比对）：去「中华人民共和国」前缀 + 去尾部（年份/版本）括注。

    必须处理「宪法（1982年）」：库存源名带括注，用户引「宪法」，不去括注会匹配不上 → 宪法引用全误报。
    """
    name = _norm_source(name)
    return re.sub(r"（[^）]*）\s*$", "", name).strip()


def article_in_kb(source: str, article: str) -> bool:
    """条号是否存在于知识库（防假引用的存在性判据，不依赖本轮检索，以用户上传的库为准）。

    按归一化 article 查库，再按 _source_key 容忍源名差异（如宪法括注）；
    source+article 双重匹配，跨法编造（如电子商务法第1260条）会被正确判 False。
    """
    art = _normalize_article(article)
    data = vectorstore._collection.get(where={"article": art}, include=["metadatas"])
    sk = _source_key(canon_source(source))  # 简称→全称（民诉法→民事诉讼法），防答案引简称被误判编造
    metas = data["metadatas"] or []
    return any(_source_key(str((m or {}).get("source", "") or "")) == sk for m in metas)


_src_set_cache: set[str] | None = None


def _ensure_src_set() -> None:
    """构建源名集合（首次全量扫描约 1-3s，之后 O(1) 查；知识增删后 invalidate 重建）。"""
    global _src_set_cache
    if _src_set_cache is None:
        data = vectorstore._collection.get(include=["metadatas"])
        _src_set_cache = {
            _source_key(str((m or {}).get("source", "") or "")) for m in (data["metadatas"] or [])
        }


def source_in_kb(source: str) -> bool:
    """法名是否在知识库（源名存在性，任务2：防「问库外法」检索到相近条文误答）。

    与 article_in_kb 同思路（_source_key 归一 + 容忍括注），但不要求条号——
    用户问「工伤保险条例的认定标准」时，检索会命中相近的工伤条文（余弦分不低），
    仅靠置信度分分不出「库外」；显式检查问题指名的来源是否在库。
    源名集合全量构建一次后 O(1) 查（10266 条 metadata 首查约 1-3s，知识增删后
    invalidate() 重建）。
    """
    global _src_set_cache
    sk = _source_key(canon_source(source))  # 简称→全称（与 article_in_kb/exact_article_lookup 同口径）
    if not sk:
        return False
    _ensure_src_set()
    assert _src_set_cache is not None  # _ensure_src_set 副作用保证已构建
    return sk in _src_set_cache


def prewarm() -> None:
    """启动预热（lifespan 调用）：BM25 索引 + 源名集合，避免重启后首问 3s+ 冷启动。"""
    _ensure_bm25()
    _ensure_src_set()


def extract_citations(answer: str) -> list[tuple]:
    """抽取答案中所有《法名》第X条，按 (_source_key, _normalize_article) 去重，
    返回 [(raw_name, raw_article, literal)]（保留首次出现的原文写法）。纯函数。"""
    seen, out = set(), []
    for m in _ART_FULL_RE.finditer(answer):
        key = (_source_key(m.group(1)), _normalize_article(m.group(2)))
        if key not in seen:
            seen.add(key)
            out.append((m.group(1), m.group(2), m.group(0)))
    return out


def citation_verify(answer: str, in_kb=None) -> list[str]:
    """防假引用（优化路线 B0.1）：抽取答案中所有《法名》第X条，凡**不存在于知识库**者
    判为疑似编造，返回其原文写法（按归一化 key 去重：全称/简称、中文/阿拉伯数字合并）。

    判据是「知识库存在性」而非「本轮检索范围」——后者会误伤正确但未检索到的引用
    （study_aid 不检索、legal_query 引用未进 top-k 的真实条文）。in_kb 可注入便于测试，
    默认查真实知识库。
    """
    in_kb = in_kb or article_in_kb
    return [literal for (name, art, literal) in extract_citations(answer) if not in_kb(name, art)]


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
_bm25_docs: list[Document] = []


def invalidate() -> None:
    """知识增删后调用：清空 BM25 索引、结果缓存与回答缓存。"""
    global _bm25, _bm25_docs, _src_set_cache
    with _bm25_lock:
        _bm25 = None
        _bm25_docs = []
    _src_set_cache = None
    _cache.clear()
    import answer_cache  # 延迟 import，知识增删时同清回答缓存

    answer_cache.clear()


def _ensure_bm25() -> None:
    global _bm25, _bm25_docs
    with _bm25_lock:
        if _bm25 is not None:
            return
        data = vectorstore._collection.get(include=["documents", "metadatas"])
        documents = data["documents"] or []
        metadatas = data["metadatas"] or []
        docs = [
            Document(
                page_content=documents[i],
                metadata=metadatas[i] if i < len(metadatas) else {},
            )
            for i in range(len(data["ids"]))
        ]
        _bm25 = rc.build_bm25(docs)
        _bm25_docs = docs


def _cos(a, b) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(x * x for x in b)) or 1.0
    return dot / (na * nb)


def _append_unique(dst: list[str], seen: set[str], dids: list[str]) -> None:
    """候选池构建：逐条去重追加（向量保底 ∪ BM25 保底 ∪ RRF，防 RRF 挤出单路强匹配条）。"""
    for did in dids:
        if did not in seen:
            seen.add(did)
            dst.append(did)


def vector_top(
    query: str,
    n: int,
    category: str | None = None,
    valid: Callable | None = None,
) -> list[tuple[Document, float]]:
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
    category: str | None = None,
    valid: Callable | None = None,
) -> list[tuple[Document, float]]:
    _ensure_bm25()
    if _bm25 is None:
        return []
    return rc.bm25_top(_bm25, _bm25_docs, query, n, category, valid=valid)


def hybrid_retrieve(
    query: str,
    k: int = 4,
    category: str | None = None,
    cutoff: str | None = None,
) -> list[Document]:
    """混合检索（向量+BM25 RRF 召回候选池，池内余弦精排）。cutoff 为时效判定日期。

    RRF 只看排名、丢失向量分值，故只负责"召回候选池"（含 BM25 捞回的向量漏网条）；
    池内用精确余弦分重排去噪，避免 BM25 通用词噪声条（"赔偿""申请"）压过语义更对的条。
    时效过滤（阶段5）：向量池与 BM25 池在 Python 侧共用 is_valid_by_time 谓词；
    缓存 key 含 cutoff，跨日旧 key 自然淘汰。
    """
    cutoff = cutoff or date.today().isoformat()
    query = _bridge_query(query)  # 措辞桥接先于缓存 key，词表变更自动失效
    valid = lambda m: rc.is_valid_by_time(m, cutoff)  # noqa: E731
    key = ("h2cos", query, category, k, cutoff)  # h2cos: 含余弦精排，区别于旧 h 缓存
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
    v_ids: list[str] = []
    b_ids: list[str] = []
    for d, _ in v:
        did = _doc_id(d)
        pool[did] = d
        v_ids.append(did)
    for d, _ in b:
        did = _doc_id(d)
        pool.setdefault(did, d)
        b_ids.append(did)
    fused = rc.rrf([v_ids, b_ids])
    # RRF 只用排名、丢了向量分值，会让 BM25 的通用词噪声条（如"赔偿""申请"）压过语义更对的条。
    # 故 RRF 只负责"召回候选池"（BM25 捞回向量漏的条），池内再用精确余弦分精排去噪。
    # 候选池 = 向量 top-k 保底 ∪ BM25 top-k 保底（防 RRF 把任一路强匹配的条挤出池）∪ RRF top 2k。
    cand_dids: list[str] = []
    seen: set[str] = set()
    _append_unique(cand_dids, seen, [_doc_id(d) for d, _ in v[:k]])
    _append_unique(cand_dids, seen, [_doc_id(d) for d, _ in b[:k]])
    _append_unique(
        cand_dids,
        seen,
        [did for did, _ in sorted(fused.items(), key=lambda kv: kv[1], reverse=True)[: k * 2]],
    )
    cand_docs = [pool[did] for did in cand_dids]
    try:
        # 余弦精排：chroma 已是 cosine 距离（score = 1-cos），向量池内条目直接用
        # chroma 分（cos = 1 - score），只对 BM25 独有条目额外嵌入——省 ~0.5s/问
        qv = embeddings.embed_query(query)
        v_cos = {_doc_id(d): 1.0 - float(s) for d, s in v if _doc_id(d) in pool}
        bm25_only = [d for d in cand_docs if _doc_id(d) not in v_cos]
        if bm25_only:
            dvs = embeddings.embed_documents([d.page_content for d in bm25_only])
            for d, dv in zip(bm25_only, dvs, strict=True):
                v_cos[_doc_id(d)] = _cos(qv, dv)
        docs = sorted(cand_docs, key=lambda d: v_cos[_doc_id(d)], reverse=True)[:k]
    except Exception:
        # 嵌入故障：回退到 RRF 序（与旧行为一致）；不写缓存，防一次瞬断长期缓存未精排结果
        docs = [pool[did] for did, _ in sorted(fused.items(), key=lambda kv: kv[1], reverse=True)[:k]]
        docs = rc.rerank(query, docs, enabled=RETRIEVAL_RERANK)
        return docs
    docs = rc.rerank(query, docs, enabled=RETRIEVAL_RERANK)
    _cache.put(key, docs)
    return docs


def retrieve(
    query: str,
    k: int = 4,
    category: str | None = None,
    cutoff: str | None = None,
) -> list[Document]:
    """兼容旧调用。条号直查路由优先（《法名》第X条 → 精确查找，确定性命中）；
    未识别或未命中则回退混合检索。cutoff 缺省为今天。"""
    parsed = parse_article_query(query)
    if parsed:
        source, article = parsed
        exact = exact_article_lookup(source, article, cutoff)
        if exact:
            return exact
    return hybrid_retrieve(query, k, category, cutoff)


def grounded_top_score(query: str, category: str | None = None, cutoff: str | None = None) -> float:
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
    for (d, _s), dv in zip(res, dvs, strict=True):
        out.append(_hit_dict(d, _cos(qv, dv)))
    out.sort(key=lambda x: x["score"], reverse=True)
    return out
