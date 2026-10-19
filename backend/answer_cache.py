"""回答缓存（M6）：相同问题命中→零 token 直接返回；BGE 近重复命中（grilling 定稿）。

设计：
- 仅缓存「安全形态」：单轮无图 legal_query/study_aid + 检索命中 + 自检 PASS + 写闸（调用方 main.py 控制）。
- key 含 cutoff_date：跨天自然不命中，避免引用昨日已失效条文。
- 近重复命中（feature_similar_cache）：同意图/时效日/证据集合，条目存 embedding + 结构护栏，
  余弦 ≥0.95 且护栏全过 → 视为同一题改写 → 直返（比手动归一化鲁棒，零正则规则，审查 C1/C4）。
- 进程内 LRU + TTL（重启即空，配合 quota 持久化已足够；命中是性能/省配额优化非正确性依赖）。
- 失效：clear() 由 retrieval.invalidate() 在知识增删时调用（近重复命中与精确 key 同住 _cache，一处清全部）。
"""

import hashlib
from datetime import datetime, timedelta

import retrieval_core as rc

_cache = rc.LRU(maxsize=512)
TTL = timedelta(hours=6)
NEAR_DUP_THRESHOLD = 0.95  # 近重复余弦阈值（+ 结构护栏，见 get_similar）
CacheScope = tuple[str, str, tuple[str, ...]]


def make_scope(intent: str, cutoff: str, context_ids: list[str]) -> CacheScope:
    """精确与近重复缓存共享的意图、时效日和证据边界。"""
    return intent or "", cutoff or "", tuple(sorted({i for i in (context_ids or []) if i}))


def make_key(text: str, intent: str, cutoff: str, context_ids: list[str]) -> str:
    """构造缓存键：问题文本 + 意图 + 时效日 + 检索命中条文集合（排序去序）。"""
    intent, cutoff, context = make_scope(intent, cutoff, context_ids)
    ids = ",".join(context)
    raw = "|".join([text or "", intent or "", cutoff or "", ids])
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def get(key: str) -> dict | None:
    """精确命中且未过期返回条目 dict（含 answer/sources/model/护栏字段）；否则 None。"""
    v = _cache.get(key)
    if not v:
        return None
    if datetime.now() > v.get("expire_at", datetime.min):
        return None
    return v


def put(
    key: str,
    answer: str,
    sources: list,
    *,
    embedding: list[float] | None = None,
    polarity: str = "",
    option_count: int = 0,
    label_system: str = "",
    options_fingerprint: str = "",
    model: str = "",
    scope: CacheScope | None = None,
    generation: int | None = None,
    qa_dependencies=None,
) -> None:
    """写入（调用方须先确认 self_check PASS + 写闸 _cache_write_ok）。

    近重复命中所需元数据（embedding/护栏/指纹/model）由调用方 main.py 提供；
    无 embedding 或 scope 的旧条目仅可精确命中；generation 拒绝失效前启动的写入。

    票 W06-B §4.1：`qa_dependencies` 是**冻结的不可变 QA 依赖快照**（tuple[QaDependency,...]）。
    `None`（默认）＝依赖未知 ⇒ 该条目可精确保留但在读侧不服务；空 `tuple`＝已确认本次输入无 QA；
    非空 tuple＝生成实际用到的 QA 记录。模块本身**不打开 SQL**——只存冻结值，核验由 main 侧的
    异步入口（投线程池调 `qa_eligibility.validate_dependencies`）负责。旧条目没有该字段＝未知。
    """
    _cache.put(
        key,
        {
            "answer": answer,
            "sources": list(sources or []),
            "expire_at": datetime.now() + TTL,
            "embedding": embedding,
            "polarity": polarity,
            "option_count": option_count,
            "label_system": label_system,
            "options_fingerprint": options_fingerprint,
            "model": model,
            "scope": scope,
            "qa_dependencies": qa_dependencies,
        },
        generation=generation,
    )


def get_similar(
    q_embedding: list[float] | None,
    *,
    polarity: str = "",
    option_count: int = 0,
    label_system: str = "",
    options_fingerprint: str = "",
    scope: CacheScope | None = None,
) -> dict | None:
    """BGE 近重复命中（审查 C2/C4，grilling 定稿 + 指纹修复）：余弦扫描 + 结构护栏。

    命中 = 余弦 ≥ NEAR_DUP_THRESHOLD AND 极性一致（防否定词盲区）AND 选项数一致
    AND 标号体系一致 AND **选项内容指纹一致**（审查 C4 修复：同题干换选项内容必须
    miss——防旧题"选B"答案错位下发）。指纹为空时跳过该比对（非选项题/解析失败）。
    返回最佳条目或 None。本地 BGE 嵌入零成本；512 条线性扫描 trivial。
    """
    if not q_embedding or scope is None:
        return None
    now = datetime.now()
    best = None
    best_score = NEAR_DUP_THRESHOLD
    for _, v in _cache.items():
        if not isinstance(v, dict) or not v.get("embedding"):
            continue
        if v.get("scope") != scope:
            continue
        if now > v.get("expire_at", datetime.min):
            continue
        if (
            v.get("polarity") != polarity
            or v.get("option_count") != option_count
            or v.get("label_system") != label_system
        ):
            continue
        # 选项内容指纹（C4 修复）：两侧非空才比对；空指纹（非选项题）跳过
        if options_fingerprint and v.get("options_fingerprint") and options_fingerprint != v.get("options_fingerprint"):
            continue
        s = rc.cos(q_embedding, v["embedding"])
        if s > best_score:
            best_score = s
            best = v
    return best


def clear() -> None:
    _cache.clear()


def generation() -> int:
    return _cache.generation()


def __len__() -> int:  # 调试/测试
    return len(_cache)
