"""路由运行态指标测试。"""

import os
import sys
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import routing_metrics as rm  # noqa: E402


def setup_function():
    rm.reset()


def test_record_and_snapshot_tier_mix():
    rm.record("light", False, "pass", "miss")  # 未升级（记 light）
    rm.record("light", False, "pass", "miss")  # 未升级（记 light）
    rm.record("flag", True, "pass", "miss")  # 升级（记 flag + escalated）
    rm.record("cache", False, "pass", "hit")
    s = rm.snapshot()
    assert s["total"] == 4
    assert s["tier_mix"]["light"] == 2 and s["tier_mix"]["flag"] == 1 and s["tier_mix"]["cache"] == 1
    assert s["upgrade_count"] == 1
    assert s["upgrade_rate"] == round(1 / 3, 3)  # 1 升级 / (2 未升级 + 1 升级)
    assert s["cache_hit_rate"] == 0.25


def test_snapshot_empty_safe():
    s = rm.snapshot()
    assert s["total"] == 0 and s["upgrade_rate"] == 0.0 and s["cache_hit_rate"] == 0.0


def test_self_check_pass_rate():
    rm.record("light", False, "pass", "miss")
    rm.record("light", False, "vague", "miss")
    s = rm.snapshot()
    assert s["self_check_pass_rate"] == 0.5


def test_upgrade_rate_denominator_includes_escalated():
    # 5 未升级(记 light) + 5 升级(记 flag, escalated) → 升级率 5/10=0.5，而非 5/5=1.0
    for _ in range(5):
        rm.record("light", False, "pass", "miss")
    for _ in range(5):
        rm.record("flag", True, "pass", "miss")
    s = rm.snapshot()
    assert s["upgrade_rate"] == 0.5


def test_checked_false_excluded_from_pass_rate():
    # 旗舰流式/缓存(checked=False) 的 pass 不稀释自检通过率
    rm.record("light", False, "vague", "miss", checked=True)  # 唯一自检，失败
    for _ in range(9):
        rm.record("flag", False, "pass", "miss", checked=False)
    s = rm.snapshot()
    assert s["self_check_pass_rate"] == 0.0  # 不被 9 个 flag pass 稀释成 0.9
    assert s["checked_count"] == 1


def test_agent_gate_metrics_are_separate_from_legacy_routing_math():
    rm.record("light", False, "pass", "miss")
    legacy_before = rm.snapshot()

    rm.record_agent_gate("agent_path", ["MULTI_ISSUE", "MISSING_FACTS"], "hashed-correlation")
    after = rm.snapshot()

    assert {key: after[key] for key in legacy_before if key != "agent_gate"} == {
        key: legacy_before[key] for key in legacy_before if key != "agent_gate"
    }
    assert after["agent_gate"] == {
        "total_predictions": 1,
        "mode_counts": {"agent_path": 1},
        "reason_code_counts": {"MULTI_ISSUE": 1, "MISSING_FACTS": 1},
        "technical_failure_count": 0,
    }


def test_agent_gate_technical_failure_is_not_misreported_as_prediction():
    rm.record_agent_gate(
        "fast_path",
        ["GATE_TECHNICAL_FAILURE"],
        "hashed-correlation",
        technical_failure=True,
    )

    assert rm.snapshot()["agent_gate"] == {
        "total_predictions": 0,
        "mode_counts": {},
        "reason_code_counts": {"GATE_TECHNICAL_FAILURE": 1},
        "technical_failure_count": 1,
    }


def test_reset_clears_legacy_and_agent_gate_state():
    rm.record("flag", True, "pass", "hit", checked=False)
    rm.record_agent_gate("agent_path", ["MULTI_STAGE"], "hashed-correlation")

    rm.reset()

    snapshot = rm.snapshot()
    assert snapshot["total"] == 0
    assert snapshot["agent_gate"] == {
        "total_predictions": 0,
        "mode_counts": {},
        "reason_code_counts": {},
        "technical_failure_count": 0,
    }


def test_concurrent_agent_gate_records_do_not_lose_counts():
    def record_one(index: int) -> None:
        rm.record_agent_gate(
            "agent_path" if index % 2 else "fast_path",
            ["MULTI_STAGE"],
            f"hashed-{index}",
        )

    with ThreadPoolExecutor(max_workers=16) as executor:
        list(executor.map(record_one, range(1000)))

    snapshot = rm.snapshot()["agent_gate"]
    assert snapshot == {
        "total_predictions": 1000,
        "mode_counts": {"fast_path": 500, "agent_path": 500},
        "reason_code_counts": {"MULTI_STAGE": 1000},
        "technical_failure_count": 0,
    }
