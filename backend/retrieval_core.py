"""检索纯逻辑：分词 / LRU / RRF 融合 / BM25 / 重排回落。

只依赖 stdlib + jieba + rank_bm25 + langchain_core 的 Document 类型，不加载嵌入模型/向量库，
因此可被单元测试快速覆盖。重排模型加载与向量检索在 retrieval.py。
"""

import json
import math
import threading
from collections import OrderedDict
from collections.abc import Callable, Mapping
from datetime import date

import jieba
from langchain_core.documents import Document
from rank_bm25 import BM25Okapi

RRF_K = 60


def cos(a, b) -> float:
    """余弦相似度（纯 math，不加载嵌入模型）。"""
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(x * x for x in b)) or 1.0
    return dot / (na * nb)


def is_cosine_space(col) -> bool:
    """collection 是否 hnsw:space=cosine（cosine 空间下 chroma 距离分 = 1 - cos 才成立）。"""
    try:
        meta = (col.metadata or {}) if col is not None else {}
        return (meta.get("hnsw:space") or "l2").lower() == "cosine"
    except Exception:
        return False


# 时效状态白名单（导入/手动添加校验用）。`未验证` = 写侧缺省，表示没人对这条做过断言
STATUS_WHITELIST = ("现行", "已修改", "已废止", "即将施行", "未生效", "未验证")


def is_valid_by_time(meta: Mapping, today: str) -> bool:
    """条文时效判定：按查询日选择当时有效的版本。

    today: 'YYYY-MM-DD'（ISO 字典序即时间序）；空串/缺失键视为无该限制。
    边界语义：effective_from == today 当日生效，effective_to == today 当日仍有效。
    此函数是向量池、BM25、grounded 打分的唯一共用谓词。

    ``status`` 表示当前管理状态，不能抹掉历史效力。已废止/未生效条文只在缺少
    相应日期边界时 fail closed；日期齐全时一律以 effective_from/effective_to 为准。
    """
    status = meta.get("status")
    ef = (meta.get("effective_from") or "").strip()
    et = (meta.get("effective_to") or "").strip()
    if ef and ef > today:
        return False  # 尚未施行
    if et and et < today:
        return False  # 已过废止日
    if status == "已废止" and not et:
        return False  # 无法证明在查询日仍有效
    if status in {"即将施行", "未生效"} and not ef:
        return False  # 无法证明已经生效
    return True


# 终止态：要说"某日之后不再有效"，必须有终止日才谈得上完备
_TERMINAL_STATUSES = {"已废止", "已修改"}


def time_validity_state(meta: Mapping) -> str:
    """时效元数据完备性：'verified' 或 'unknown'。

    与 `is_valid_by_time` 并列而语义不同 —— 谓词回答"某日是否有效"，本函数回答
    "我们手里有没有凭据这样断言"。日期缺失时谓词按 fail-open 放行，本函数把这一事实标出来，
    供答案层与门禁消费；**它不是过滤条件**，任何把它的返回值塞进检索排除分支的改动都是跑偏。

    `status='未验证'` 表示这条状态是写侧默认值、没人背过书 ⇒ 即使带日期也算 unknown。
    """
    status = meta.get("status")
    ef = (meta.get("effective_from") or "").strip()
    et = (meta.get("effective_to") or "").strip()
    if status == "未验证":
        return "unknown"
    if not ef:
        return "unknown"
    if status in _TERMINAL_STATUSES and not et:
        return "unknown"
    return "verified"


def cited_articles(evidence: str) -> list[tuple[str, str]]:
    """把 QA 语料的 `evidence` 解析成 (source, article) 对；认不出的形状返回空表。

    在库的形状（2026-09-25 对生效集合 `qa_pairs` 只读复量：279 条 = 203 JSON + 76 管道符 + 0 其它；
    那 203 里有 2 条是空数组 `'[]'`，解析不出任何一对 ⇒ 本函数实际放行 277 条）：
    种子与语料生成脚本写 `source|article`；`main._post` 的自动沉淀与管理员采纳路径写 JSON 数组；
    `feedback:<rating>` 这类形状在库实测 **0 条**（第 10 节②，且写侧已停发反馈候选），
    但它落在末尾那个 `return []` 上 ⇒ 认不出的形状一律拒，不做"看起来像就放过"。
    时效护栏与来源可校验判据共用这一份解析，不留第二份形状知识。
    """
    text = (evidence or "").strip()
    if not text:
        return []
    if text.startswith("["):
        try:
            refs = json.loads(text)
        except ValueError:
            return []
        if not isinstance(refs, list):
            return []
        pairs = []
        for ref in refs:
            if not isinstance(ref, dict):
                continue
            src = str(ref.get("source") or "").strip()
            art = str(ref.get("article") or "").strip()
            if src and art:
                pairs.append((src, art))
        return pairs
    if "|" in text:
        src, _, art = text.partition("|")
        src, art = src.strip(), art.strip()
        return [(src, art)] if src and art else []
    return []


def qa_provenance_verifiable(qa: Mapping | None) -> bool:
    """这条 QA 语料记录能否被独立校验 ⇒ 才允许参与答复生成。

    两个条件缺一不可：① `evidence` 里存在可校验的条文引用，否则时效护栏没有输入，答案
    对不对只能信产出它的那一方；② `law_as_of_basis` 是有效的 YYYY-MM-DD 日期，否则版本分水岭守卫没有输入，
    旧版答案可以原样答给现行查询。

    判据按**证据形状**整类判定而不是点名 `feedback:` 前缀：未来任何新来源默认落在判据外，
    同时补掉 `knowledge_service.search_qa` 用 `.get("evidence", "")` 造成的缺键放行。
    """
    if not qa:
        return False
    if not cited_articles(str(qa.get("evidence") or "")):
        return False
    basis = qa.get("law_as_of_basis")
    if not isinstance(basis, str):
        return False
    try:
        return date.fromisoformat(basis).isoformat() == basis
    except ValueError:
        return False


def tokenize(text: str) -> list[str]:
    """中文分词（jieba），过滤空白与纯空白片段。"""
    return [t for t in jieba.cut(text or "") if t and t.strip()]


class LRU:
    """线程安全的简单 LRU 缓存（用于检索结果缓存）。"""

    def __init__(self, maxsize: int = 256):
        self._d: OrderedDict[tuple, object] = OrderedDict()
        self._max = maxsize
        self._lock = threading.Lock()
        self._generation = 0

    def get(self, key):
        with self._lock:
            if key in self._d:
                self._d.move_to_end(key)
                return self._d[key]
        return None

    def generation(self) -> int:
        with self._lock:
            return self._generation

    def put(self, key, value, *, generation: int | None = None) -> None:
        with self._lock:
            if generation is not None and generation != self._generation:
                return
            self._d[key] = value
            self._d.move_to_end(key)
            while len(self._d) > self._max:
                self._d.popitem(last=False)

    def clear(self) -> None:
        with self._lock:
            self._generation += 1
            self._d.clear()

    def __len__(self) -> int:
        with self._lock:
            return len(self._d)

    def items(self):
        """快照迭代（线程安全，拷贝）：供近重复命中余弦扫描（answer_cache.get_similar）。"""
        with self._lock:
            return list(self._d.items())


def rrf(rankings: list[list[str]], k: int = RRF_K) -> dict[str, float]:
    """Reciprocal Rank Fusion。rankings=多个按相关性排序的 doc-id 列表；返回 id->融合分。纯函数。"""
    scores: dict[str, float] = {}
    for ranking in rankings:
        for rank, doc_id in enumerate(ranking):
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank + 1)
    return scores


def build_bm25(docs: list[Document]) -> BM25Okapi | None:
    """由分片构建 jieba 分词 BM25 索引（混合检索的一路召回源）；空库返回 None。"""
    if not docs:
        return None
    return BM25Okapi([tokenize(d.page_content) for d in docs])


def bm25_top(
    bm25: BM25Okapi,
    docs: list[Document],
    query: str,
    n: int,
    category: str | None = None,
    valid: Callable | None = None,
) -> list[tuple[Document, float]]:
    scores = bm25.get_scores(tokenize(query))
    order = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
    out: list[tuple[Document, float]] = []
    for i in order:
        d = docs[i]
        if category and d.metadata.get("category") != category:
            continue
        if valid and not valid(d.metadata):
            continue
        out.append((d, float(scores[i])))
        if len(out) >= n:
            break
    return out
