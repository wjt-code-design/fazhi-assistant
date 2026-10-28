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


# ==================== R15（2026-10-21）：siliconflow provider + 转写通道 ====================

_SILICONFLOW_VOICE_ROLES = [
    {
        "key": "voice_sf",
        "model": "XingChenAGI/XingChenASR-V3.2-Ultra",
        "modality": "voice",
        "tier": "flag",
        "capabilities": ["speech", "asr"],
        "provider": "siliconflow",
        "transport": "audio_transcriptions",
    }
]


def _pin_siliconflow_settings(monkeypatch, sf_key: str) -> None:
    import settings as _s

    monkeypatch.setattr(_s.settings, "llm_base_url", "https://api.longcat.chat/openai")
    monkeypatch.setattr(_s.settings, "llm_api_key", "longcat-key")
    monkeypatch.setattr(_s.settings, "siliconflow_base_url", "https://api.siliconflow.cn/v1")
    monkeypatch.setattr(_s.settings, "siliconflow_api_key", sf_key)


def test_siliconflow_provider_routes_to_siliconflow_endpoint(monkeypatch):
    """provider=siliconflow 必须走硅基流动端点；修前会落到通用分支拿 LongCat 端点。"""
    _pin_siliconflow_settings(monkeypatch, "sf-key")
    reg = _registry_from(monkeypatch, _SILICONFLOW_VOICE_ROLES)

    key, entry = reg.pick_entry("voice", "flag")

    assert key == "voice_sf"
    assert entry.cfg["base_url"] == "https://api.siliconflow.cn/v1"
    assert entry.cfg["api_key"] == "sf-key"
    assert entry.transport == "audio_transcriptions"


def test_siliconflow_voice_skipped_without_key(monkeypatch):
    """缺 siliconflow key 时该角色必须被跳过，不得回落到 LongCat 凭据。"""
    _pin_siliconflow_settings(monkeypatch, "")
    reg = _registry_from(monkeypatch, _SILICONFLOW_VOICE_ROLES)

    assert reg.has_modality("voice") is False


def test_transcribe_dispatches_to_audio_transcriptions_transport(monkeypatch):
    from fastapi.testclient import TestClient

    import main
    import settings as _s
    from auth import get_current_user

    monkeypatch.setattr(_s.settings, "feature_transcribe", True)
    monkeypatch.setattr(main.registry, "has_modality", lambda m: True)
    entry = SimpleNamespace(
        transport="audio_transcriptions",
        model="XingChenAGI/XingChenASR-V3.2-Ultra",
        cfg={"base_url": "https://api.siliconflow.cn/v1", "api_key": "sf-key"},
        llm=None,
    )
    monkeypatch.setattr(main.registry, "pick_entry", lambda modality, tier: ("voice_sf", entry))
    monkeypatch.setattr(main.registry, "deduct", lambda key, tokens: None)

    calls = {}

    def fake_transcriptions(base_url, api_key, model, raw, fmt):
        calls.update(base_url=base_url, api_key=api_key, model=model, raw=raw, fmt=fmt)
        return "你好"

    def fake_chat(llm, b64, fmt):  # 不应被调用
        raise AssertionError("transport=audio_transcriptions 时不得走 chat 通道")

    monkeypatch.setattr(main, "transcribe_audio_transcriptions", fake_transcriptions)
    monkeypatch.setattr(main, "transcribe_audio", fake_chat)

    main.app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=1)
    try:
        with TestClient(main.app) as client:
            resp = client.post(
                "/api/chat/transcribe",
                files={"file": ("a.wav", b"RIFF" + b"\x00" * 2048, "audio/wav")},
            )
    finally:
        main.app.dependency_overrides.clear()

    assert resp.status_code == 200
    assert resp.json()["text"] == "你好"
    assert calls["base_url"] == "https://api.siliconflow.cn/v1"
    assert calls["api_key"] == "sf-key"
    assert calls["model"] == "XingChenAGI/XingChenASR-V3.2-Ultra"
    assert calls["fmt"] == "wav"


def test_transcribe_defaults_to_chat_transport_when_transport_absent(monkeypatch):
    from fastapi.testclient import TestClient

    import main
    import settings as _s
    from auth import get_current_user

    monkeypatch.setattr(_s.settings, "feature_transcribe", True)
    monkeypatch.setattr(main.registry, "has_modality", lambda m: True)
    entry = SimpleNamespace(transport=None, model="qwen-omni", cfg={}, llm=object())
    monkeypatch.setattr(main.registry, "pick_entry", lambda modality, tier: ("voice_omni", entry))
    monkeypatch.setattr(main.registry, "deduct", lambda key, tokens: None)

    calls = {}
    monkeypatch.setattr(
        main, "transcribe_audio", lambda llm, b64, fmt: calls.setdefault("chat", (llm, fmt)) and "旧通道"
    )
    monkeypatch.setattr(
        main,
        "transcribe_audio_transcriptions",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("transport=None 时不得走 transcriptions")),
    )

    main.app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=1)
    try:
        with TestClient(main.app) as client:
            resp = client.post(
                "/api/chat/transcribe",
                files={"file": ("a.wav", b"RIFF" + b"\x00" * 2048, "audio/wav")},
            )
    finally:
        main.app.dependency_overrides.clear()

    assert resp.status_code == 200
    assert calls["chat"][1] == "wav"


def test_transcribe_audio_transcriptions_posts_multipart(monkeypatch):
    """断言请求形状：URL、Bearer、multipart 字段与 MIME——不触网。"""
    import httpx

    import multimodal

    captured = {}

    class _Resp:
        def raise_for_status(self):
            return None

        def json(self):
            return {"text": "  你好  "}

    class _Client:
        def __init__(self, timeout=None):
            self.timeout = timeout

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def post(self, url, headers=None, files=None, data=None):
            captured.update(url=url, headers=headers, files=files, data=data)
            return _Resp()

    monkeypatch.setattr(httpx, "Client", _Client)

    out = multimodal.transcribe_audio_transcriptions(
        "https://api.siliconflow.cn/v1", "sf-key", "XingChenAGI/XingChenASR-V3.2-Ultra", b"RIFFDATA", "wav"
    )

    assert out == "你好"
    assert captured["url"] == "https://api.siliconflow.cn/v1/audio/transcriptions"
    assert captured["headers"]["Authorization"] == "Bearer sf-key"
    assert captured["data"]["model"] == "XingChenAGI/XingChenASR-V3.2-Ultra"
    filename, payload, mime = captured["files"]["file"]
    assert payload == b"RIFFDATA"
    assert mime == "audio/wav"
    assert filename.endswith(".wav")
