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
    {"key": "t_light", "model": "m-light", "modality": "text", "tier": "light", "capabilities": ["text"], "quota_total": 1000, "initial_used": 0},
    {"key": "t_flag", "model": "m-flag", "modality": "text", "tier": "flag", "capabilities": ["text"], "quota_total": 1000, "initial_used": 0},
    {"key": "v_light", "model": "v-light", "modality": "vision", "tier": "light", "capabilities": ["text", "vision"], "quota_total": 1000, "initial_used": 0},
    {"key": "v_flag", "model": "v-flag", "modality": "vision", "tier": "flag", "capabilities": ["text", "vision"], "quota_total": 1000, "initial_used": 0},
]


def test_pick_returns_requested_tier(monkeypatch):
    reg, _ = _make_registry(monkeypatch, ROLES)
    key, llm = reg.pick("text", "light")
    assert key == "t_light" and llm is not None


def test_pick_same_tier_by_priority_then_quota(monkeypatch):
    # priority 主导：b 配额少但 priority 低（能力强）→ 先选 b
    roles = [
        {"key": "a", "model": "x", "modality": "text", "tier": "light", "priority": 1, "capabilities": ["text"], "quota_total": 1000, "initial_used": 0},
        {"key": "b", "model": "x", "modality": "text", "tier": "light", "priority": 0, "capabilities": ["text"], "quota_total": 1000, "initial_used": 800},
    ]
    reg, _ = _make_registry(monkeypatch, roles)
    key, _ = reg.pick("text", "light")
    assert key == "b"
    # priority 相同 → 比剩余配额（tie-break）
    roles2 = [
        {"key": "a", "model": "x", "modality": "text", "tier": "light", "priority": 0, "capabilities": ["text"], "quota_total": 1000, "initial_used": 800},
        {"key": "b", "model": "x", "modality": "text", "tier": "light", "priority": 0, "capabilities": ["text"], "quota_total": 1000, "initial_used": 100},
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
        {"key": "a", "model": "x", "modality": "text", "tier": "light", "capabilities": ["text"], "quota_total": 100, "initial_used": 100},
        {"key": "b", "model": "x", "modality": "text", "tier": "flag", "capabilities": ["text"], "quota_total": 100, "initial_used": 100},
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


def test_estimate_tokens():
    assert lr.estimate_tokens("") == 1
    assert lr.estimate_tokens("abc") >= 1
    assert lr.estimate_tokens("a" * 150) == 100
