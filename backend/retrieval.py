"""检索编排：向量 + BM25(jieba) 经 RRF 融合召回候选池 + 池内余弦精排 + 结果缓存 + 云 rerank。

- HYBRID=1（默认）：向量与 BM25 双路召回 + RRF 融合；对中文法律条号/专有名词的精确匹配是语义检索的短板，BM25 补齐。
- 云 rerank（ADR-011）：qwen3-rerank 系多模型按配额自动轮换，全耗尽回落池内余弦精排。
- 检索结果按 (mode,query,category,k) 做 LRU 缓存；知识增删时调 invalidate() 失效。
- BM25 索引惰性构建并缓存；增删知识后 invalidate() 重建。
- 配额扣减统一走 quota_utils（不 import llm_registry——其模块级初始化需 LLM key）。
"""

import httpx
import re
import threading
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import date

from langchain_core.documents import Document

import query_understand
import quota_utils
import retrieval_core as rc
from domain_rules import canon_source
from rag_chain import embeddings, vectorstore
from settings import settings

# ---- rerank（准度主菜，ADR-011）：qwen3-rerank 系经 OpenAI 兼容 /reranks 端点 ----
# 多模型按配额自动轮换（qwen3-rerank → gte-rerank-v2 → qwen3-vl-rerank）：每次请求选
# 当前配额最充足（剩余 >= hard 阈值）的模型；全耗尽 → None → 调用方回退池内余弦精排。
# client 与模型解耦（model 在 body），换模型无需重建 client。懒加载 + 缓存。
_rerank_client = None
_rerank_client_lock = threading.Lock()


def _get_rerank_client():
    """懒构建 rerank OpenAI client。未启用/未配 key → None。"""
    global _rerank_client
    if not settings.rerank_enabled or not settings.rerank_api_key:
        return None
    if _rerank_client is not None:
        return _rerank_client
    with _rerank_client_lock:
        if _rerank_client is None:
            from openai import OpenAI

            _rerank_client = OpenAI(
                api_key=settings.rerank_api_key,
                base_url=settings.rerank_base_url,
                timeout=30,
            )
    return _rerank_client


# 锚点语义判定：含罪名（"罪"）或法名（《》/法/条例/典/规定/办法）才算有语义；
# 纯条号（"第三百四十七条"/"第一千二百六十条"）无语义 → rerank query 回落整句（B10）。
_ANCHOR_SEMANTIC_RE = re.compile(r"罪|《|法|条例|典|规定|办法")


def _rerank_query(query: str, units: list[tuple[str, str]]) -> str:
    """rerank 用聚焦检索词：语义锚点优先，纯条号/无锚点回落整句截断。

    rerank 对聚焦 query 打分更准（省 token 是附带收益）；但**纯条号锚点无语义**
    （"第三百四十七条"）或过短锚点丢失限定信息时，硬用会损排序准度——回落整句截断。
    判定：锚点含罪名或法名（_ANCHOR_SEMANTIC_RE）→ 有语义用锚点；否则回落整句前 120
    字符（长题干截断避免稀释，实测校准阈值）。
    """
    anchors = [q for q, kind in units if kind == query_understand.KIND_ANCHOR]
    semantic = [a for a in anchors if _ANCHOR_SEMANTIC_RE.search(a)]
    if semantic:
        return " ".join(semantic)
    return query[:120]


# 原生 DashScope rerank 格式模型：OpenAI 兼容 /reranks 端点不支持，须走原生 text-rerank 端点
# （2026-08-07 实测：兼容端点报 model_not_supported；原生端点 200，返回 output.results）
_NATIVE_RERANK_MODELS = {"gte-rerank-v2", "qwen3-vl-rerank"}


def _rerank_docs(query: str, docs: list[Document]) -> list[Document] | None:
    """云 rerank 重排候选池，返回按分数降序的新排序。耗尽自动换下一个（块 2.2 扩展）。

    - 按 rerank 队列（qwen3-rerank → gte-rerank-v2 → qwen3-vl-rerank）依次尝试：
      真实 API 失败 → mark_utility_depleted 该模型 → 试下一个；全部失败/未启用 → None（降级原序）
    - query 用锚点检索词（阶段4 _rerank_query），省 token
    - rerank 整个候选池（实测 12-17 条），不裁剪——池外碰不到，池内全排最优
    - 端点分流：qwen3-rerank 走 OpenAI 兼容 /reranks（扁平 body）；gte-rerank-v2 / qwen3-vl-rerank
      走 DashScope 原生 text-rerank 端点（嵌套 body，兼容端点不支持）
    - 失败/未启用 → None：调用方保持原精排顺序（安全）
    """
    client = _get_rerank_client()
    if client is None or not docs:
        return None
    hard = settings.rerank_hard_threshold
    for model in quota_utils.rerank_model_list():
        if not quota_utils.utility_quota_ok(model, hard):
            continue  # 估算已耗尽（或上轮真实失败已标记）→ 跳过
        try:
            if model in _NATIVE_RERANK_MODELS:
                # DashScope 原生：嵌套 input/parameters + 原生 text-rerank 端点。
                # 用 httpx 直连——OpenAI client 无法解析原生响应（ValueError，2026-08-07 实测）。
                _rr = httpx.post(
                    settings.rerank_native_url,
                    json={
                        "model": model,
                        "input": {"query": query, "documents": [d.page_content for d in docs]},
                        "parameters": {"top_n": len(docs), "return_documents": False},
                    },
                    headers={"Authorization": f"Bearer {settings.rerank_api_key}"},
                    timeout=30,
                )
                _rr.raise_for_status()
                resp = _rr.json()
            else:
                # OpenAI 兼容：扁平 body + /reranks
                resp = client.post(
                    "/reranks",
                    body={
                        "model": model,
                        "query": query,
                        "documents": [d.page_content for d in docs],
                        "top_n": len(docs),
                    },
                    cast_to=dict,
                )
            # 配额扣减（ADR-011 阶段E）：rerank 按输入 token 计费（query + documents），
            # 无真实 usage 返回 → quota_utils.estimate_tokens 近似估算；key = 模型名（per-model 轮换）
            quota_utils.deduct_utility(
                model,
                quota_utils.estimate_tokens(query) + sum(quota_utils.estimate_tokens(d.page_content) for d in docs),
            )
            # 响应解析：兼容端点顶层 results；原生端点 output.results
            resp_dict = resp or {}
            results = resp_dict.get("results") or (resp_dict.get("output") or {}).get("results") or []
            if not results:
                return None
            ordered = sorted(results, key=lambda r: r.get("relevance_score", 0.0), reverse=True)
            idx = [r.get("index", 0) for r in ordered]
            return [docs[i] for i in idx if 0 <= i < len(docs)]
        except Exception:
            # 真实 API 失败（配额/模型名错）→ 标记该模型耗尽 → 下一个
            quota_utils.mark_utility_depleted(model)
            continue
    return None

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


def citation_grounding(answer, sources, stats, in_kb=None) -> tuple[list, list, list]:
    """三分法接地校验（2026-08-07 B3）：对答案中的引用分类，量化漏召回率/幻觉率。

    - ① 在上下文：引用 ∈ 本轮检索 sources → 通过
    - ② 在库未召回：不在 sources 但 article_in_kb 在库 → 漏召回（记 stats，回答不动，
      零 LLM 零延迟——recall miss 是 top-k 局限，不是编造）
    - ③ 不在库：真幻觉（记 stats；前端法条卡显示"未收录"，重生成开关默认关）

    sources: 本轮检索 sources 列表（含 source/article 字段）
    stats: {"in_context": n, "recall_miss": n, "hallucination": n} 累计（就地更新）
    in_kb: 可注入（测试用），默认 article_in_kb
    返回 (in_ctx, recall_miss, hallucination) 三元列表（各为归一化 (source, article) key）
    """
    in_kb = in_kb or article_in_kb
    context_keys = {
        (_source_key(canon_source(str(s.get("source", "")))), _normalize_article(str(s.get("article", ""))))
        for s in sources
        if s.get("article")
    }
    in_ctx, rm, hal = [], [], []
    for raw_name, raw_art, _lit in extract_citations(answer):
        key = (_source_key(canon_source(raw_name)), _normalize_article(raw_art))
        if key in context_keys:
            in_ctx.append(key)
            stats["in_context"] = stats.get("in_context", 0) + 1
        elif in_kb(raw_name, raw_art):
            rm.append(key)
            stats["recall_miss"] = stats.get("recall_miss", 0) + 1
        else:
            hal.append(key)
            stats["hallucination"] = stats.get("hallucination", 0) + 1
    return in_ctx, rm, hal


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


_COLLECTION_IS_COSINE: bool | None = None


def _collection_is_cosine() -> bool:
    """当前主库 collection 是否 cosine 空间（cos = 1 - distance 才成立）。

    本地主库 legal_provisions_cos / cloud 新库 legal_provisions_te4 均 cosine；
    qa_pairs 本地库是 L2（欧氏距离不可转 cos）。缓存判断结果。
    """
    global _COLLECTION_IS_COSINE
    if _COLLECTION_IS_COSINE is None:
        _COLLECTION_IS_COSINE = rc.is_cosine_space(vectorstore._collection)
    return _COLLECTION_IS_COSINE


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
    # 配额扣减由 rag_chain.QuotaTrackingEmbeddings 包装对象统一负责（Chroma 内部经
    # embedding_function 自动嵌入时扣减）——此处不再显式扣，防双扣（ADR-011 阶段5）。
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


def _cosine_rank(query: str, docs: list[Document]) -> list[Document]:
    """余弦精排（rerank 关闭 / 失败时的回退口径，2026-08-04 恢复旧版单段行为）。

    纯余弦（措辞桥接靠 BM25 捞进候选池 + 余弦定序——用 RRF 会改变桥接 case 排序，
    如"行政复议受案范围"的"第十一条"靠桥接在 BM25 命中但余弦不高，纯余弦更稳，
    实测回归后恢复旧口径）。
    """
    qv = embeddings.embed_query(query)
    dvs = embeddings.embed_documents([d.page_content for d in docs])
    v_cos: dict[str, float] = {_doc_id(d): rc.cos(qv, dv) for d, dv in zip(docs, dvs, strict=True)}
    return sorted(docs, key=lambda d: v_cos[_doc_id(d)], reverse=True)


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
        _cache.put(key, docs)
        return docs
    n = max(k * BM25_K_MULT, 4)
    # 查询分解（query_understand.decompose）：整句 + 法条/罪名/概念锚点 + 长文切片，
    # 每单元独立召回进候选池。强锚点（法条引用/罪名/法律概念）独立检索且 top-k 命中
    # 保底进结果——含锚点的查询无论长短，核心条文必被独立召回，不依赖整句 BGE 余弦分
    # （2026-08-04 架构改进，取代早前仅"位置切片"——短复合查询无机制保证）。
    # 切片段（弱单元）只扩大候选池，不保底（避免单元过多稀释锚点保底）。
    units = query_understand.decompose(query)
    pool: dict[str, Document] = {}
    rankings: list[list[str]] = []  # 各单元的 v 路排名
    b_rankings: list[list[str]] = []  # 各单元的 b 路排名
    anchor_rank_idx: list[int] = []  # 强锚点单元在 rankings 中的索引（保底用）
    for qi, (q, kind) in enumerate(units):
        v = vector_top(q, n, category, valid=valid)
        b = bm25_top(q, n, category, valid=valid)
        v_ids: list[str] = []
        for d, _ in v:
            did = _doc_id(d)
            pool.setdefault(did, d)
            v_ids.append(did)
        b_ids: list[str] = []
        for d, _ in b:
            did = _doc_id(d)
            pool.setdefault(did, d)
            b_ids.append(did)
        rankings.append(v_ids)
        b_rankings.append(b_ids)
        if kind == query_understand.KIND_ANCHOR:
            anchor_rank_idx.append(qi)
    # 保底：每单元向量 top-k 与 BM25 top-k 都进候选池（防 RRF 挤出任一路强匹配条）
    all_v_ids: list[str] = []
    all_b_ids: list[str] = []
    seen_v: set[str] = set()
    seen_b: set[str] = set()
    for v_ids, b_ids in zip(rankings, b_rankings, strict=True):
        for did in v_ids[:k]:
            if did not in seen_v:
                seen_v.add(did)
                all_v_ids.append(did)
        for did in b_ids[:k]:
            if did not in seen_b:
                seen_b.add(did)
                all_b_ids.append(did)
    fused = rc.rrf(rankings + b_rankings)
    # 候选池 = 各单元向量 top-k 保底 ∪ 各单元 BM25 top-k 保底 ∪ RRF top 2k
    cand_dids: list[str] = []
    seen: set[str] = set()
    _append_unique(cand_dids, seen, all_v_ids)
    _append_unique(cand_dids, seen, all_b_ids)
    _append_unique(
        cand_dids,
        seen,
        [did for did, _ in sorted(fused.items(), key=lambda kv: kv[1], reverse=True)[: k * 2]],
    )
    cand_docs = [pool[did] for did in cand_dids]
    try:
        # 结果级锚点保底：每个强锚点 v/b top-3 去重，占据结果首位（机制保证核心条文必现）。
        # 为什么保底而非精排：348 对"非法持有毒品罪"锚点排第 0 但对锚点余弦仅 0.72，
        # 低于噪声条对整句的 0.74-0.77——纯精排会把"单一精准命中"挤出 top-k。强锚点
        # 代表独立法律子问题，其 top-3 命中必须直接占位（2026-08-04 实测校准）。
        anchor_guaranteed: list[str] = []
        ag_seen: set[str] = set()
        if anchor_rank_idx:
            for qi in anchor_rank_idx:
                for did in (rankings[qi][:3] + b_rankings[qi][:3]):
                    if did not in ag_seen:
                        ag_seen.add(did)
                        anchor_guaranteed.append(did)
        rest_docs = [d for d in cand_docs if _doc_id(d) not in ag_seen]

        if settings.rerank_enabled:
            # rerank 开（ADR-011 准度主菜）：锚点保底不动，其余位次由 qwen3-rerank 定序。
            # 跳过 cosine 整池重嵌（rerank 已接管高位定序，避免既重嵌又 rerank 浪费网络往返）。
            reranked = _rerank_docs(_rerank_query(query, units), rest_docs)
            if reranked is not None:
                docs = [pool[did] for did in anchor_guaranteed] + reranked
            else:
                # rerank 失败 → 回退原余弦精排（安全）
                docs = _cosine_rank(query, rest_docs)
                docs = [pool[did] for did in anchor_guaranteed] + docs
        else:
            # rerank 关（本地 BGE 回退）：余弦精排 + 锚点保底前置（机制保证核心条文必现）
            ranked = _cosine_rank(query, cand_docs)
            docs = [pool[did] for did in anchor_guaranteed] + [d for d in ranked if _doc_id(d) not in ag_seen]
        docs = docs[:k]
    except quota_utils.UtilityQuotaExhausted:
        raise  # B3：embedding 配额耗尽必须上达 409，不能被 RRF 兜底吞掉
    except Exception:
        # 嵌入/精排故障：回退到 RRF 序（与旧行为一致）；不写缓存，防一次瞬断长期缓存未精排结果
        docs = [pool[did] for did, _ in sorted(fused.items(), key=lambda kv: kv[1], reverse=True)[:k]]
        return docs
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


def retrieve_exam(question: str, k: int = 6) -> list[Document]:
    """分步分析型检索（ADR-012）：拆题干+每选项 → 逐项并发检索 → 合并去重。

    解决"单次整题检索漏项"（死刑复核 252 漏召回）：每个选项独立召回其考点条文，
    题干结果作**主锚（优先）**，选项结果作**扩展补漏**（评审点4 合并权重）。

    实现要点：
    - `query_understand._split_by_choice` 拆解（多格式）；无法识别选项 → 整题 fallback
    - **ThreadPoolExecutor 并发**（grilling 自审修正：_pre 在 run_in_threadpool 线程里
      无 event loop，asyncio.gather 不可用）
    - 每单元走 `hybrid_retrieve`（内部已含锚点保底 + rerank），合并后按"题干→选项"
      顺序收集（题干主锚在前），去重截 k
    - 任一单元异常 → 跳过该单元不崩（fallback 链：逐项 → 题干 → 整题）
    - **回退说明（2026-08-05 逆向）**：动态 k（h10/o4/c12）曾把 recall@6 提到 0.9625，
      但深池拉长每次检索持有 BGE/Chroma 的时间，显著加大 Windows onnxruntime 偶发原生
      segfault 的窗口（恢复 rerank/降并发/串行/嵌入锁均压不住）——**生产稳定优先回退
      k=6**。recall 维持 0.9083。多条文题 recall 上限为已知局限（ADR-014 诚实标注）。
    """
    units = query_understand._split_by_choice(question)
    if len(units) <= 1:
        return hybrid_retrieve(question, k=k)  # 无选项 → 整题检索（fallback）
    # 题干主锚 = **完整问题文本**（含选项信号——实测剥离选项的题干丢关键条：
    # 高空抛物题裸题干 top-3 全无关，整题检索 1254 排第 1）。选项单元独立补漏
    # （防"单次整题检索漏项"如死刑复核 252）。题干给足候选，选项瘦身池控总量。
    head_q = question  # 主锚：含 A-D 选项的完整问题
    opt_queries = units[1:]  # 每选项独立召回其考点条文
    head_k = k
    opt_k = max(2, k // 3)
    n = 1 + len(opt_queries)
    collected: list[list[Document]] = [None] * n  # type: ignore[list-item]
    with ThreadPoolExecutor(max_workers=min(6, n)) as ex:
        futs = [(0, ex.submit(hybrid_retrieve, head_q, head_k))]
        futs += [(i + 1, ex.submit(hybrid_retrieve, q, opt_k)) for i, q in enumerate(opt_queries)]
        for i, f in futs:
            try:
                collected[i] = f.result()
            except Exception:
                collected[i] = []  # 该单元失败 → 跳过，不崩
    out: list[Document] = []
    seen: set[str] = set()
    for docs in collected:  # 按题干→选项顺序（题干主锚优先）
        if not docs:
            continue
        for d in docs:
            did = _doc_id(d)
            if did not in seen:
                seen.add(did)
                out.append(d)
    if not out:
        return hybrid_retrieve(question, k=k)  # 全失败 → 整题兜底
    return out[:k]


_supplements_cache: list[dict] | None = None


def _load_supplements() -> list[dict]:
    """加载 scenario_supplements.json（数据驱动，ADR-012 阶段2B）：新增场景零代码改动。"""
    global _supplements_cache
    if _supplements_cache is None:
        import json as _json
        import os as _os

        path = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "scenario_supplements.json")
        try:
            with open(path, encoding="utf-8") as f:
                _supplements_cache = _json.load(f)
        except Exception:
            _supplements_cache = []
    return _supplements_cache


def scenario_supplement_docs(text: str) -> list[Document]:
    """场景定向补充（数据驱动）：命中关键词 → 前置该场景核心条文（防整题检索漏项）。

    复用 exact_article_lookup 精确取条（条号直查零嵌入零检索），返回的 Document 由
    调用方前置到检索结果。仅用于非选项题（选项题已走 retrieve_exam 逐项检索）。
    """
    t = text or ""
    out: list[Document] = []
    seen: set[str] = set()
    for spec in _load_supplements():
        if not any(k in t for k in spec.get("keywords", [])):
            continue
        for a in spec.get("articles", []):
            try:
                docs = exact_article_lookup(a.get("source", ""), a.get("article", ""))
            except Exception:
                docs = []
            for d in docs:
                did = _doc_id(d)
                if did not in seen:
                    seen.add(did)
                    out.append(d)
    return out


def grounded_top_score(query: str, category: str | None = None, cutoff: str | None = None) -> float:
    """受控沉淀打分：只对"当前仍有效"的条文计分（阶段5），避免沉淀失效条文。

    性能优化（ADR-011 阶段D）：cosine 空间下 chroma 距离分 = 1 - cos，直接复用免重嵌。
    """
    cutoff = cutoff or date.today().isoformat()
    valid = lambda m: rc.is_valid_by_time(m, cutoff)  # noqa: E731
    res = vectorstore.similarity_search_with_score(
        query, k=max(VECTOR_POOL_MIN, 8), filter=({"category": category} if category else None)
    )
    res = [(d, s) for d, s in res if valid(d.metadata)]
    if not res:
        return 0.0
    if _collection_is_cosine():
        # cosine 空间：score = 1 - cos → cos = 1 - score（免重嵌）
        return max(0.0, min(1.0, 1.0 - float(res[0][1])))
    try:
        qv = embeddings.embed_query(query)
        dv = embeddings.embed_documents([res[0][0].page_content])[0]
        return rc.cos(qv, dv)
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
    """管理员检索测试：返回 top-k + 余弦相关度（语义分，便于解释）；不过滤已废止条文。

    性能优化（ADR-011 阶段D）：cosine 空间复用 chroma 距离分，免整池重嵌。
    """
    res = vectorstore.similarity_search_with_score(query, k=k)
    if not res:
        return []
    if _collection_is_cosine():
        out = [_hit_dict(d, max(0.0, min(1.0, 1.0 - float(s)))) for d, s in res]
        out.sort(key=lambda x: x["score"], reverse=True)
        return out
    try:
        qv = embeddings.embed_query(query)
        dvs = embeddings.embed_documents([d.page_content for d, _ in res])
    except Exception:
        return [_hit_dict(d, 0.0) for d, _ in res]
    out = []
    for (d, _s), dv in zip(res, dvs, strict=True):
        out.append(_hit_dict(d, rc.cos(qv, dv)))
    out.sort(key=lambda x: x["score"], reverse=True)
    return out
