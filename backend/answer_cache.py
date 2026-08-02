"""回答缓存（M6）：相同问题命中→零 token 直接返回。

设计：
- 仅缓存「安全形态」：单轮无图 legal_query + 检索命中 + 自检 PASS（写闸在调用方 main.py 控制）。
- key 含 cutoff_date：跨天自然不命中，避免引用昨日已失效条文。
- 进程内 LRU + TTL（重启即空，配合 quota 持久化已足够；命中是性能/省配额优化非正确性依赖）。
- 失效：clear() 由 retrieval.invalidate() 在知识增删时调用。
"""
import hashlib
from datetime import datetime, timedelta

import retrieval_core as rc

_cache = rc.LRU(maxsize=512)
TTL = timedelta(hours=6)


def make_key(text: str, intent: str, cutoff: str, context_ids: list[str]) -> str:
    """构造缓存键：问题文本 + 意图 + 时效日 + 检索命中条文集合（排序去序）。"""
    ids = ",".join(sorted({i for i in (context_ids or []) if i}))
    raw = "|".join([text or "", intent or "", cutoff or "", ids])
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def get(key: str) -> dict | None:
    """命中且未过期返回 {answer, sources}；否则 None。"""
    v = _cache.get(key)
    if not v:
        return None
    answer, sources, expire_at = v
    if datetime.now() > expire_at:
        return None
    return {"answer": answer, "sources": sources}


def put(key: str, answer: str, sources: list) -> None:
    """写入（调用方须先确认 self_check PASS）。"""
    _cache.put(key, (answer, list(sources or []), datetime.now() + TTL))


def clear() -> None:
    _cache.clear()


def __len__() -> int:  # 调试/测试
    return len(_cache)
