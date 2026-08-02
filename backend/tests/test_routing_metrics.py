"""路由运行态指标测试。"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import routing_metrics as rm  # noqa: E402


def setup_function():
    rm.reset()


def test_record_and_snapshot_tier_mix():
    rm.record("light", False, "pass", "miss")
    rm.record("light", True, "pass", "miss")  # 升级
    rm.record("flag", False, "pass", "miss")
    rm.record("cache", False, "pass", "hit")
    s = rm.snapshot()
    assert s["total"] == 4
    assert s["tier_mix"]["light"] == 2 and s["tier_mix"]["flag"] == 1 and s["tier_mix"]["cache"] == 1
    assert s["upgrade_count"] == 1
    assert s["upgrade_rate"] == 0.5  # 1 升级 / 2 light
    assert s["cache_hit_rate"] == 0.25


def test_snapshot_empty_safe():
    s = rm.snapshot()
    assert s["total"] == 0 and s["upgrade_rate"] == 0.0 and s["cache_hit_rate"] == 0.0


def test_self_check_pass_rate():
    rm.record("light", False, "pass", "miss")
    rm.record("light", False, "vague", "miss")
    s = rm.snapshot()
    assert s["self_check_pass_rate"] == 0.5
