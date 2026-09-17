"""路由选择与运行态指标（进程内计数器，重启清零，持久审计看日志）。

记录每次回答的 tier / 是否升级 / 自检结果 / 缓存命中，供 admin 面板算
tier_mix / upgrade_rate / self_check_pass_rate / cache_hit_rate。
诚实标注：本指标为运行态，重启清零；如需跨重启审计，查 legal.chat 日志。
"""

import hashlib
import threading
from collections import Counter
from typing import Any

TECHNICAL_FALLBACK_REASON_CODES = frozenset(
    {
        "PLANNER_PARSE_ERROR",
        "TOOL_TIMEOUT",
        "TOOL_UNAVAILABLE",
        "AGENT_BUDGET_EXCEEDED",
        "VERIFIER_TECHNICAL_FAILURE",
    }
)
_AGENT_ROUTES = frozenset({"agent_path", "fast_path"})
_ROLLOUT_NAMESPACE = b"legal-agent-rollout-v1\x00"

_lock = threading.Lock()
_tier: Counter[str] = Counter()
_verdict: Counter[str] = Counter()
_escalated = 0
_cache_hit = 0
_total = 0
_checked = 0  # 真正执行过 self_check 的请求数（仅 light 路径）
_pass_checked = 0  # 其中自检通过数
_agent_mode: Counter[str] = Counter()
_agent_reason: Counter[str] = Counter()
_agent_total_predictions = 0
_agent_technical_failures = 0
_agent_route: Counter[str] = Counter()
_agent_fallback_reason: Counter[str] = Counter()
_agent_total_routes = 0
_agent_fallback_count = 0


def should_route_agent(gate: Any, settings: Any, stable_request_seed: object) -> bool:
    """Select live Agent traffic deterministically after the pure Gate accepts it."""
    if not isinstance(stable_request_seed, str) or not stable_request_seed:
        return False
    if getattr(gate, "mode", None) != "agent_path":
        return False
    if not bool(getattr(settings, "agent_enabled", False)):
        return False
    percent = getattr(settings, "agent_traffic_percent", 0)
    if not isinstance(percent, int) or isinstance(percent, bool) or not 0 <= percent <= 100:
        return False
    if percent == 0:
        return False
    if percent == 100:
        return True
    digest = hashlib.sha256(_ROLLOUT_NAMESPACE + stable_request_seed.encode("utf-8")).digest()
    bucket = int.from_bytes(digest[:8], "big") % 100
    return bucket < percent


def is_technical_fallback_reason(reason_code: object) -> bool:
    return isinstance(reason_code, str) and reason_code in TECHNICAL_FALLBACK_REASON_CODES


def record_agent_route(route: str, *, fallback_reason: str | None = None) -> None:
    """Record the executed route; Gate predictions remain a separate metric family."""
    if route not in _AGENT_ROUTES:
        raise ValueError("route must be agent_path or fast_path")
    if fallback_reason is not None:
        if route != "fast_path":
            raise ValueError("fallback requires the fast_path actual route")
        if not is_technical_fallback_reason(fallback_reason):
            raise ValueError("fallback reason is not in the technical allowlist")
    global _agent_total_routes, _agent_fallback_count
    with _lock:
        _agent_route[route] += 1
        _agent_total_routes += 1
        if fallback_reason is not None:
            _agent_fallback_reason[fallback_reason] += 1
            _agent_fallback_count += 1


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


def record_agent_gate(
    mode: str,
    reason_codes: list[str],
    agent_correlation_id: str,
    *,
    technical_failure: bool = False,
) -> None:
    """Record a Shadow Gate event without changing legacy answer-routing math.

    ``agent_correlation_id`` is intentionally accepted at this observation seam so
    the caller uses the same hashed value for metrics and logs. Aggregates do not
    retain per-request identifiers.
    """
    del agent_correlation_id
    global _agent_total_predictions, _agent_technical_failures
    with _lock:
        _agent_reason.update(reason_codes)
        if technical_failure:
            _agent_technical_failures += 1
            return
        _agent_mode[mode] += 1
        _agent_total_predictions += 1


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
            "agent_gate": {
                "total_predictions": _agent_total_predictions,
                "mode_counts": dict(_agent_mode),
                "reason_code_counts": dict(_agent_reason),
                "technical_failure_count": _agent_technical_failures,
            },
            "agent_route": {
                "total_routes": _agent_total_routes,
                "route_counts": dict(_agent_route),
                "fallback_count": _agent_fallback_count,
                "fallback_reason_code_counts": dict(_agent_fallback_reason),
            },
        }


def reset() -> None:
    """测试用。"""
    global _escalated, _cache_hit, _total, _checked, _pass_checked
    global _agent_total_predictions, _agent_technical_failures
    global _agent_total_routes, _agent_fallback_count
    with _lock:
        _tier.clear()
        _verdict.clear()
        _escalated = 0
        _cache_hit = 0
        _total = 0
        _checked = 0
        _pass_checked = 0
        _agent_mode.clear()
        _agent_reason.clear()
        _agent_total_predictions = 0
        _agent_technical_failures = 0
        _agent_route.clear()
        _agent_fallback_reason.clear()
        _agent_total_routes = 0
        _agent_fallback_count = 0
