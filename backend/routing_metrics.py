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
_checked = 0  # 真正执行过 self_check 的请求数（仅 light 路径）
_pass_checked = 0  # 其中自检通过数


def record(tier: str, escalated: bool, verdict: str, cache: str, checked: bool = True) -> None:
    """checked=True 表示本请求真正跑过 self_check（light 路径）；旗舰流式/缓存命中传 False。"""
    global _escalated, _cache_hit, _total, _checked, _pass_checked
    with _lock:
        _tier[tier or "legacy"] += 1
        _verdict[verdict or "pass"] += 1
        if escalated:
            _escalated += 1
        if cache == "hit":
            _cache_hit += 1
        if checked:
            _checked += 1
            if (verdict or "pass") == "pass":
                _pass_checked += 1
        _total += 1


def snapshot() -> dict:
    with _lock:
        total = _total
        light = _tier.get("light", 0)
        flag = _tier.get("flag", 0)
        cache = _tier.get("cache", 0)
        legacy = _tier.get("legacy", 0)
        # 走过轻量路由的请求 = 未升级(记 light) + 已升级(记 flag 但 escalated)
        light_routed = light + _escalated
        return {
            "total": total,
            "tier_mix": {"light": light, "flag": flag, "cache": cache, "legacy": legacy},
            "upgrade_count": _escalated,
            "upgrade_rate": round(_escalated / light_routed, 3) if light_routed else 0.0,
            # 自检通过率只统计真正跑过自检的请求，避免被未自检路径稀释
            "self_check_pass_rate": round(_pass_checked / _checked, 3) if _checked else 0.0,
            "checked_count": _checked,
            "cache_hit_rate": round(_cache_hit / total, 3) if total else 0.0,
            "verdict_top": dict(_verdict.most_common(5)),
        }


def reset() -> None:
    """测试用。"""
    global _escalated, _cache_hit, _total, _checked, _pass_checked
    with _lock:
        _tier.clear()
        _verdict.clear()
        _escalated = 0
        _cache_hit = 0
        _total = 0
        _checked = 0
        _pass_checked = 0
