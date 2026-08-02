"""路由运行态指标（进程内计数器，管理员可观测；重启清零，持久审计看日志）。

记录每次回答的 tier / 是否升级 / 自检结果 / 缓存命中，供 admin 面板算
tier_mix / upgrade_rate / self_check_pass_rate / cache_hit_rate。
诚实标注：本指标为运行态，重启清零；如需跨重启审计，查 legal.chat 日志。
"""
import threading
from collections import Counter

_lock = threading.Lock()
_tier: Counter[str] = Counter()
_verdict: Counter[str] = Counter()
_escalated = 0
_cache_hit = 0
_total = 0


def record(tier: str, escalated: bool, verdict: str, cache: str) -> None:
    global _escalated, _cache_hit, _total
    with _lock:
        _tier[tier or "legacy"] += 1
        _verdict[verdict or "pass"] += 1
        if escalated:
            _escalated += 1
        if cache == "hit":
            _cache_hit += 1
        _total += 1


def snapshot() -> dict:
    with _lock:
        total = _total
        light = _tier.get("light", 0)
        flag = _tier.get("flag", 0)
        cache = _tier.get("cache", 0)
        legacy = _tier.get("legacy", 0)
        pass_n = _verdict.get("pass", 0)
        return {
            "total": total,
            "tier_mix": {"light": light, "flag": flag, "cache": cache, "legacy": legacy},
            "upgrade_count": _escalated,
            # 升级率 = 升级次数 / 走过轻量路由的次数（light tier 含升级与不升级）
            "upgrade_rate": round(_escalated / light, 3) if light else 0.0,
            "self_check_pass_rate": round(pass_n / total, 3) if total else 0.0,
            "cache_hit_rate": round(_cache_hit / total, 3) if total else 0.0,
            "verdict_top": dict(_verdict.most_common(5)),
        }


def reset() -> None:
    """测试用。"""
    global _escalated, _cache_hit, _total
    with _lock:
        _tier.clear()
        _verdict.clear()
        _escalated = 0
        _cache_hit = 0
        _total = 0
