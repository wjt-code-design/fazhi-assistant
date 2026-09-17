"""阶段B 能力门测试：注册表缺少某模态模型时，未验证能力必须显式 501，
禁止静默回退文本模型（2026-09-05 LongCat 实测会静默忽略图片内容块）。

期望独立于实现：501 = "Not Implemented / 能力未配置"，语义上区别于
503（配额/服务过载）与 400（请求非法）——能力缺失是服务端事实而非用户错误。
"""

from __future__ import annotations

import json
import os
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

import pytest

import llm_registry as lr
import quota_store

pytest.importorskip("langchain_openai")

_TEXT_ONLY_ROLES = [
    {
        "key": "only_text",
        "model": "text-only-model",
        "modality": "text",
        "tier": "flag",
        "capabilities": ["text"],
    }
]

_IMAGE_DATA_URL = (
    "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJ"
    "AAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)


def _registry_from(monkeypatch, roles) -> lr.LLMRegistry:
    import settings as _s

    monkeypatch.setattr(_s.settings, "llm_models_json", json.dumps(roles))
    monkeypatch.setattr(quota_store, "get_used", lambda key: 0)
    monkeypatch.setattr(quota_store, "record_delta", lambda key, delta: 0)
    return lr.LLMRegistry()


def test_has_modality_reflects_registered_roles(monkeypatch):
    reg = _registry_from(monkeypatch, _TEXT_ONLY_ROLES)
    assert reg.has_modality("text") is True
    assert reg.has_modality("vision") is False
    assert reg.has_modality("voice") is False


def test_chat_with_image_returns_501_without_vision_model(monkeypatch):
    from fastapi.testclient import TestClient

    import main
    from auth import get_current_user

    monkeypatch.setattr(main.registry, "has_modality", lambda m: m == "text")
    main.app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=1)
    try:
        with TestClient(main.app) as client:
            resp = client.post(
                "/api/chat",
                json={"content": "请看这张图", "image": _IMAGE_DATA_URL},
            )
    finally:
        main.app.dependency_overrides.clear()

    assert resp.status_code == 501
    assert "视觉" in resp.json()["detail"] or "图片" in resp.json()["detail"]


def test_transcribe_returns_501_without_voice_model(monkeypatch):
    from fastapi.testclient import TestClient

    import main
    import settings as _s
    from auth import get_current_user

    monkeypatch.setattr(_s.settings, "feature_transcribe", True)
    monkeypatch.setattr(main.registry, "has_modality", lambda m: m == "text")
    main.app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=1)
    try:
        with TestClient(main.app) as client:
            resp = client.post(
                "/api/chat/transcribe",
                files={"file": ("a.wav", b"RIFF" + b"\x00" * 2048, "audio/wav")},
            )
    finally:
        main.app.dependency_overrides.clear()

    assert resp.status_code == 501


def test_health_reports_capability_flags(monkeypatch):
    from fastapi.testclient import TestClient

    import main
    import settings as _s

    monkeypatch.setattr(_s.settings, "feature_transcribe", True)
    monkeypatch.setattr(main.registry, "has_modality", lambda m: m == "text")
    with TestClient(main.app) as client:
        resp = client.get("/api/health")

    assert resp.status_code == 200
    body = resp.json()
    assert body["capabilities"]["image_chat"] is False
    assert body["capabilities"]["voice_transcribe"] is False


_DASHSCOPE_ROLES = [
    {
        "key": "vision_omni",
        "model": "qwen3.5-omni-flash",
        "modality": "vision",
        "tier": "flag",
        "capabilities": ["text", "vision"],
        "provider": "dashscope",
    },
    {
        "key": "voice_omni",
        "model": "qwen3.5-omni-flash",
        "modality": "voice",
        "tier": "flag",
        "capabilities": ["speech", "asr"],
        "provider": "dashscope",
    },
]


def test_dashscope_roles_build_with_key_and_skip_without(monkeypatch):
    import settings as _s

    monkeypatch.setattr(_s.settings, "dashscope_api_key", "test-key")
    reg = _registry_from(monkeypatch, _DASHSCOPE_ROLES)
    assert reg.has_modality("vision") is True
    assert reg.has_modality("voice") is True

    monkeypatch.setattr(_s.settings, "dashscope_api_key", "")
    reg_empty = _registry_from(monkeypatch, _DASHSCOPE_ROLES)
    # 缺 key 的 provider 角色必须被跳过而不是让启动崩溃（与 zhipu 分支同语义）
    assert reg_empty.has_modality("vision") is False
    assert reg_empty.has_modality("voice") is False


def test_describe_image_picks_vision_model(monkeypatch):
    import main

    calls = {}

    class _FakeLLM:
        pass

    def fake_pick(modality, tier):
        calls["modality"] = modality
        return "vision_omni", _FakeLLM()

    monkeypatch.setattr(main.registry, "pick", fake_pick)

    def fake_describe(llm, image, text):
        calls["llm"] = llm
        return "ok"

    monkeypatch.setattr(main, "describe_image", fake_describe)
    out = main._describe_image_for_bootstrap("data:image/png;base64,AAAA", "问题")
    assert out == "ok"
    assert calls["modality"] == "vision"
    assert isinstance(calls["llm"], _FakeLLM)


def test_describe_image_quota_exhausted_is_explicit_503(monkeypatch):
    import pytest as _pytest
    from fastapi import HTTPException

    import main
    from llm_registry import QuotaExhausted

    def exhausted(modality, tier):
        raise QuotaExhausted("no vision quota")

    monkeypatch.setattr(main.registry, "pick", exhausted)
    with _pytest.raises(HTTPException) as ei:
        main._describe_image_for_bootstrap("data:image/png;base64,AAAA", "问题")
    assert ei.value.status_code == 503
