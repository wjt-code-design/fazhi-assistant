"""llm_registry 多模型路由 + 配额测试（隔离 quota_store，不碰真实文件）。"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

import pytest

import llm_registry as lr
import quota_store


def _make_registry(monkeypatch, roles, used=None):
    """构造隔离 registry：注入角色表 + 假 quota_store（monkeypatch 自动恢复）。"""
    used = used or {}
    pytest.importorskip("langchain_openai")
    monkey_store: dict[str, int] = dict(used)

    def fake_get(key):
        return monkey_store.get(key, 0)

    def fake_record(key, delta):
        monkey_store[key] = monkey_store.get(key, 0) + int(delta)
        return monkey_store[key]

    import settings as _s

    monkeypatch.setattr(_s.settings, "llm_models_json", json.dumps(roles))
    monkeypatch.setattr(quota_store, "get_used", fake_get)
    monkeypatch.setattr(quota_store, "record_delta", fake_record)
    reg = lr.LLMRegistry()
    return reg, monkey_store


ROLES = [
    {
        "key": "t_light",
        "model": "m-light",
        "modality": "text",
        "tier": "light",
        "capabilities": ["text"],
        "quota_total": 1000,
        "initial_used": 0,
    },
    {
        "key": "t_flag",
        "model": "m-flag",
        "modality": "text",
        "tier": "flag",
        "capabilities": ["text"],
        "quota_total": 1000,
        "initial_used": 0,
    },
    {
        "key": "v_light",
        "model": "v-light",
        "modality": "vision",
        "tier": "light",
        "capabilities": ["text", "vision"],
        "quota_total": 1000,
        "initial_used": 0,
    },
    {
        "key": "v_flag",
        "model": "v-flag",
        "modality": "vision",
        "tier": "flag",
        "capabilities": ["text", "vision"],
        "quota_total": 1000,
        "initial_used": 0,
    },
]


def test_pick_returns_requested_tier(monkeypatch):
    reg, _ = _make_registry(monkeypatch, ROLES)
    key, llm = reg.pick("text", "light")
    assert key == "t_light" and llm is not None


def test_pick_same_tier_by_priority_then_quota(monkeypatch):
    # priority 主导：b 配额少但 priority 低（能力强）→ 先选 b
    roles = [
        {
            "key": "a",
            "model": "x",
            "modality": "text",
            "tier": "light",
            "priority": 1,
            "capabilities": ["text"],
            "quota_total": 1000,
            "initial_used": 0,
        },
        {
            "key": "b",
            "model": "x",
            "modality": "text",
            "tier": "light",
            "priority": 0,
            "capabilities": ["text"],
            "quota_total": 1000,
            "initial_used": 800,
        },
    ]
    reg, _ = _make_registry(monkeypatch, roles)
    key, _ = reg.pick("text", "light")
    assert key == "b"
    # priority 相同 → 比剩余配额（tie-break）
    roles2 = [
        {
            "key": "a",
            "model": "x",
            "modality": "text",
            "tier": "light",
            "priority": 0,
            "capabilities": ["text"],
            "quota_total": 1000,
            "initial_used": 800,
        },
        {
            "key": "b",
            "model": "x",
            "modality": "text",
            "tier": "light",
            "priority": 0,
            "capabilities": ["text"],
            "quota_total": 1000,
            "initial_used": 100,
        },
    ]
    reg2, _ = _make_registry(monkeypatch, roles2)
    key2, _ = reg2.pick("text", "light")
    assert key2 == "b"  # 剩余 900 > 200


def test_pick_skips_below_threshold_and_falls_back(monkeypatch):
    roles = [dict(r) for r in ROLES]
    roles[0]["initial_used"] = 970  # left=30 → 3% < 5%
    reg, _ = _make_registry(monkeypatch, roles)
    key, _ = reg.pick("text", "light")
    assert key == "t_flag"


def test_pick_skips_depleted(monkeypatch):
    roles = [dict(r) for r in ROLES]
    roles[0]["initial_used"] = 1000  # depleted
    reg, _ = _make_registry(monkeypatch, roles)
    key, _ = reg.pick("text", "light")
    assert key == "t_flag"


def test_pick_exhausted_raises(monkeypatch):
    roles = [
        {
            "key": "a",
            "model": "x",
            "modality": "text",
            "tier": "light",
            "capabilities": ["text"],
            "quota_total": 100,
            "initial_used": 100,
        },
        {
            "key": "b",
            "model": "x",
            "modality": "text",
            "tier": "flag",
            "capabilities": ["text"],
            "quota_total": 100,
            "initial_used": 100,
        },
    ]
    reg, _ = _make_registry(monkeypatch, roles)
    with pytest.raises(lr.QuotaExhausted):
        reg.pick("text", "light")


def test_deduct_accumulates_and_persists(monkeypatch):
    reg, store = _make_registry(monkeypatch, ROLES)
    reg.deduct("t_light", 100)
    reg.deduct("t_light", 50)
    assert reg._entries["t_light"].runtime_used == 150
    assert store["t_light"] == 150
    assert reg._entries["t_light"].quota_left == 850


def test_deduct_zero_ignored(monkeypatch):
    reg, store = _make_registry(monkeypatch, ROLES)
    reg.deduct("t_light", 0)
    assert "t_light" not in store


def test_status_fields(monkeypatch):
    reg, _ = _make_registry(monkeypatch, ROLES)
    s = reg.status()
    keys = {e["key"] for e in s}
    assert keys == {"t_light", "t_flag", "v_light", "v_flag"}
    one = next(e for e in s if e["key"] == "t_light")
    assert set(one) >= {"key", "model", "modality", "tier", "quota_total", "quota_left", "depleted", "below_threshold"}


def test_get_backward_compat(monkeypatch):
    reg, _ = _make_registry(monkeypatch, ROLES)
    assert reg.get() is not None
    assert reg.config()["model"]


def test_calibrate_writes_a_complete_baseline_on_a_depleted_model(monkeypatch):
    """R19（改前失败）：校准必须真的把剩余拉回 R，且内存与持久一致。

    改前只改 `initial_used = max(0, total - R - runtime_used)` 而**保留 runtime_used**：
    runtime 已被 `mark_depleted` 记满（= total）时，无论 R 取何值都算出 initial_used=0
    ⇒ quota_left 仍 0（校准对"已耗尽"的模型完全无效）；而 initial 已落库 ⇒ 内存与持久分叉。
    """
    reg, store = _make_registry(monkeypatch, ROLES)
    persisted_init: dict[str, int] = {}
    monkeypatch.setattr(quota_store, "set_used", lambda k, v: store.__setitem__(k, int(v)))
    monkeypatch.setattr(quota_store, "set_initial", lambda k, v: persisted_init.__setitem__(k, int(v)))

    e = reg._entries["t_light"]
    e.runtime_used = e.quota_total  # 模拟 mark_depleted 把 runtime 记满
    assert e.quota_left == 0, "前提：调用前该模型已耗尽"

    res = reg.calibrate("t_light", 500)

    assert e.quota_left == 500, "校准后剩余没回到 500 ⇒ 对已耗尽模型无效"
    assert res["quota_left"] == 500 and res["initial_used"] == e.quota_total - 500
    # 内存与持久一致（runtime 归零也落库）
    assert e.runtime_used == 0
    assert store["t_light"] == 0
    assert persisted_init["t_light"] == e.quota_total - 500


def test_calibrate_after_mark_depleted_restores_the_model_to_routing(monkeypatch):
    """端到端语义：`mark_depleted` → 校准回 900 ⇒ 该模型必须重新可被自动路由选中。"""
    reg, store = _make_registry(monkeypatch, ROLES)
    monkeypatch.setattr(quota_store, "set_used", lambda k, v: store.__setitem__(k, int(v)))
    monkeypatch.setattr(quota_store, "set_initial", lambda k, v: None)

    reg.mark_depleted("t_light", "quota_error")
    assert reg._entries["t_light"].unavailable is True

    reg.calibrate("t_light", 900)

    assert reg._entries["t_light"].unavailable is False, "校准后仍不可用 ⇒ 校准没生效"


def test_estimate_tokens():
    assert lr.estimate_tokens("") == 1
    assert lr.estimate_tokens("abc") >= 1
    assert lr.estimate_tokens("a" * 150) == 100
