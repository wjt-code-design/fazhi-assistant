"""Deterministic Legal Agent rollout and actual-route metric contracts."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import pytest

import routing_metrics as rm
from agent.gate import AgentGateDecision
from settings import Settings

_AGENT_ENV_NAMES = (
    "AGENT_ENABLED",
    "AGENT_SHADOW_ENABLED",
    "AGENT_TRAFFIC_PERCENT",
)


@pytest.fixture(autouse=True)
def _isolated_rollout_state(monkeypatch):
    rm.reset()
    for name in _AGENT_ENV_NAMES:
        monkeypatch.delenv(name, raising=False)
    yield
    rm.reset()


def _settings(*, enabled: bool, percent: int) -> Settings:
    return Settings(
        _env_file=None,
        agent_enabled=enabled,
        agent_shadow_enabled=False,
        agent_traffic_percent=percent,
    )


def _gate(mode: str) -> AgentGateDecision:
    if mode == "agent_path":
        return AgentGateDecision(
            mode="agent_path",
            complexity="complex",
            reason_codes=("MULTI_STAGE",),
        )
    return AgentGateDecision(
        mode="fast_path",
        complexity="simple",
        reason_codes=("SINGLE_ISSUE_QUERY",),
    )


@pytest.mark.parametrize(
    ("gate_mode", "enabled", "percent", "expected"),
    [
        ("fast_path", True, 100, False),
        ("agent_path", False, 100, False),
        ("agent_path", True, 0, False),
        ("agent_path", True, 100, True),
    ],
)
def test_rollout_hard_boundaries(gate_mode, enabled, percent, expected):
    assert (
        rm.should_route_agent(
            _gate(gate_mode),
            _settings(enabled=enabled, percent=percent),
            "seed-a",
        )
        is expected
    )


def test_rollout_uses_frozen_sha256_v1_buckets_and_is_repeatable():
    settings = _settings(enabled=True, percent=20)

    # Frozen independent vectors for SHA-256("legal-agent-rollout-v1\\0" + seed),
    # using the first 8 digest bytes as a big-endian integer modulo 100:
    # seed-a -> 15, seed-b -> 29.
    assert rm.should_route_agent(_gate("agent_path"), settings, "seed-a") is True
    assert rm.should_route_agent(_gate("agent_path"), settings, "seed-b") is False
    assert [rm.should_route_agent(_gate("agent_path"), settings, "seed-a") for _ in range(20)] == [True] * 20


@pytest.mark.parametrize("seed", ["", None, b"seed-a"])
def test_invalid_stable_seed_fails_closed(seed):
    assert (
        rm.should_route_agent(
            _gate("agent_path"),
            _settings(enabled=True, percent=100),
            seed,
        )
        is False
    )


def test_settings_rollout_defaults_are_safe_off_even_if_other_test_env_exists():
    actual = Settings(_env_file=None)

    assert actual.agent_enabled is False
    assert actual.agent_shadow_enabled is False
    assert actual.agent_traffic_percent == 0


def test_settings_rollout_reads_explicit_environment_in_isolation(monkeypatch):
    monkeypatch.setenv("AGENT_ENABLED", "true")
    monkeypatch.setenv("AGENT_SHADOW_ENABLED", "true")
    monkeypatch.setenv("AGENT_TRAFFIC_PERCENT", "37")

    actual = Settings(_env_file=None)

    assert actual.agent_enabled is True
    assert actual.agent_shadow_enabled is True
    assert actual.agent_traffic_percent == 37


def test_technical_fallback_allowlist_is_immutable_and_complete():
    assert isinstance(rm.TECHNICAL_FALLBACK_REASON_CODES, frozenset)
    assert rm.TECHNICAL_FALLBACK_REASON_CODES == frozenset(
        {
            "PLANNER_PARSE_ERROR",
            "TOOL_TIMEOUT",
            "TOOL_UNAVAILABLE",
            "AGENT_BUDGET_EXCEEDED",
            "VERIFIER_TECHNICAL_FAILURE",
        }
    )
    assert all(rm.is_technical_fallback_reason(code) for code in rm.TECHNICAL_FALLBACK_REASON_CODES)


@pytest.mark.parametrize(
    "forbidden_reason",
    [
        "AUTHORIZATION_FAILURE",
        "OWNERSHIP_FAILURE",
        "POLICY_CHEATING_REQUEST",
        "PROMPT_INJECTION_DETECTED",
        "INPUT_VALIDATION_ERROR",
        "LAW_DATE_MISMATCH",
        "FAIL_SAFE",
        "FINAL_GATE_TECHNICAL_FAILURE",
        "",
        None,
    ],
)
def test_non_allowlisted_reason_is_not_a_technical_fallback(forbidden_reason):
    assert rm.is_technical_fallback_reason(forbidden_reason) is False


def test_actual_route_and_fallback_metrics_are_separate_from_gate_prediction():
    rm.record_agent_gate(
        "agent_path",
        ["MULTI_STAGE"],
        "hashed-correlation",
    )
    rm.record_agent_route("agent_path")
    rm.record_agent_route("fast_path", fallback_reason="TOOL_UNAVAILABLE")

    snapshot = rm.snapshot()

    assert snapshot["agent_gate"] == {
        "total_predictions": 1,
        "mode_counts": {"agent_path": 1},
        "reason_code_counts": {"MULTI_STAGE": 1},
        "technical_failure_count": 0,
    }
    assert snapshot["agent_route"] == {
        "total_routes": 2,
        "route_counts": {"agent_path": 1, "fast_path": 1},
        "fallback_count": 1,
        "fallback_reason_code_counts": {"TOOL_UNAVAILABLE": 1},
    }


@pytest.mark.parametrize("route", ["", "shadow", "unknown", None])
def test_actual_route_metric_rejects_invalid_route(route):
    with pytest.raises(ValueError, match="route"):
        rm.record_agent_route(route)


@pytest.mark.parametrize(
    "forbidden_reason",
    ["FAIL_SAFE", "AUTHORIZATION_FAILURE", "FINAL_GATE_TECHNICAL_FAILURE"],
)
def test_actual_route_metric_rejects_forbidden_fallback_reason(forbidden_reason):
    with pytest.raises(ValueError, match="fallback"):
        rm.record_agent_route("fast_path", fallback_reason=forbidden_reason)

    assert rm.snapshot()["agent_route"] == {
        "total_routes": 0,
        "route_counts": {},
        "fallback_count": 0,
        "fallback_reason_code_counts": {},
    }


def test_fallback_metric_requires_fast_path_actual_route():
    with pytest.raises(ValueError, match="fast_path"):
        rm.record_agent_route("agent_path", fallback_reason="TOOL_TIMEOUT")


def test_reset_clears_actual_route_metrics():
    rm.record_agent_route("fast_path", fallback_reason="AGENT_BUDGET_EXCEEDED")

    rm.reset()

    assert rm.snapshot()["agent_route"] == {
        "total_routes": 0,
        "route_counts": {},
        "fallback_count": 0,
        "fallback_reason_code_counts": {},
    }


def test_concurrent_actual_route_records_do_not_lose_counts():
    def record_one(index: int) -> None:
        if index % 2:
            rm.record_agent_route("agent_path")
        else:
            rm.record_agent_route("fast_path", fallback_reason="TOOL_TIMEOUT")

    with ThreadPoolExecutor(max_workers=16) as executor:
        list(executor.map(record_one, range(1000)))

    assert rm.snapshot()["agent_route"] == {
        "total_routes": 1000,
        "route_counts": {"fast_path": 500, "agent_path": 500},
        "fallback_count": 500,
        "fallback_reason_code_counts": {"TOOL_TIMEOUT": 500},
    }
