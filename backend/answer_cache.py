"""回答缓存（M6）：相同问题命中→零 token 直接返回；BGE 近重复命中（grilling 定稿）。

设计：
- 仅缓存「安全形态」：单轮无图 legal_query/study_aid + 检索命中 + 自检 PASS + 写闸（调用方 main.py 控制）。
- key 含 cutoff_date：跨天自然不命中，避免引用昨日已失效条文。
- 近重复命中（feature_similar_cache）：条目存问题 embedding + 结构护栏（极性/选项数/标号体系），
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


def make_key(text: str, intent: str, cutoff: str, context_ids: list[str]) -> str:
    """构造缓存键：问题文本 + 意图 + 时效日 + 检索命中条文集合（排序去序）。"""
    ids = ",".join(sorted({i for i in (context_ids or []) if i}))
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
    model: str = "",
) -> None:
    """写入（调用方须先确认 self_check PASS + 写闸 _cache_write_ok）。

    近重复命中所需元数据（embedding/护栏/model）由调用方 main.py 提供；
    get_similar 对无 embedding 的旧条目跳过（不参与近重复命中，仅精确 key 可命中）。
    """
    _cache.put(key, {
        "answer": answer,
        "sources": list(sources or []),
        "expire_at": datetime.now() + TTL,
        "embedding": embedding,
        "polarity": polarity,
        "option_count": option_count,
        "label_system": label_system,
        "model": model,
    })


def get_similar(
    q_embedding: list[float] | None,
    *,
    polarity: str = "",
    option_count: int = 0,
    label_system: str = "",
) -> dict | None:
    """BGE 近重复命中（审查 C2/C4，grilling 定稿）：余弦扫描 + 结构护栏。

    命中 = 余弦 ≥ NEAR_DUP_THRESHOLD AND 极性一致（防否定词盲区）AND 选项数一致
    AND 标号体系一致（防答案"选B"错位展示给 ①-④ 题）。返回最佳条目或 None。
    本地 BGE 嵌入零成本；512 条线性扫描 trivial。
    """
    if not q_embedding:
        return None
    now = datetime.now()
    best = None
    best_score = NEAR_DUP_THRESHOLD
    for _, v in _cache.items():
        if not isinstance(v, dict) or not v.get("embedding"):
            continue
        if now > v.get("expire_at", datetime.min):
            continue
        if (
            v.get("polarity") != polarity
            or v.get("option_count") != option_count
            or v.get("label_system") != label_system
        ):
            continue
        s = rc.cos(q_embedding, v["embedding"])
        if s > best_score:
            best_score = s
            best = v
    return best


def clear() -> None:
    _cache.clear()


def __len__() -> int:  # 调试/测试
    return len(_cache)
