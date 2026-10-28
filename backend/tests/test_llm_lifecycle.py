"""SDK lifecycle contract tests: controlled llm_registry import + AST-extracted main.lifespan.

Run with --noconftest (checks.py LIFECYCLE mode). No real configuration is read:
the `settings` module is stubbed in sys.modules before the controlled import, and
quota_store writes only to a test-owned QUOTA_DB temp file. The installed
ChatOpenAI/openai SDK injection contract is asserted explicitly (version pin).
"""

import ast
import asyncio
import gc
import inspect
import json
import logging
import os
import sys
import tempfile
import types
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest

BACKEND = Path(__file__).resolve().parents[1]

ROLE = {
    "key": "vision_flag",  # must be DEFAULT_KEY so reload()/variant() target this entry
    "model": "qwen-test-model",
    "modality": "vision",
    "tier": "flag",
    "priority": 0,
    "capabilities": ["text", "vision"],
    "disable_thinking": True,
}

_TMP = Path(tempfile.mkdtemp(prefix="llm-lifecycle-quota-"))


def _controlled_import():
    """Load an isolated registry with test settings, preserving application modules."""
    fake_settings = types.ModuleType("settings")
    fake_settings.settings = SimpleNamespace(
        llm_models_json=json.dumps([ROLE]),
        llm_base_url="http://127.0.0.1:9/v1",
        api_key="test-local-placeholder",
        zhipu_base_url="http://127.0.0.1:9/v1",
        zhipuai_api_key="test-local-placeholder",
        dashscope_base_url="http://127.0.0.1:9/v1",
        dashscope_api_key="test-local-placeholder",
    )
    previous_quota, previous_path = os.environ.get("QUOTA_DB"), list(sys.path)
    os.environ["QUOTA_DB"] = str(_TMP / "quota-used.sqlite")
    saved = {
        name: sys.modules.get(name)
        for name in ("settings", "domain_rules", "quota_utils", "quota_store", "llm_registry")
    }
    for name in ("settings", "domain_rules", "quota_utils", "quota_store", "llm_registry"):
        sys.modules.pop(name, None)
    sys.modules["settings"] = fake_settings  # must precede the import chain
    try:
        sys.path.insert(0, str(BACKEND))
        import llm_registry as module
    finally:
        sys.path[:] = previous_path
        if previous_quota is None:
            os.environ.pop("QUOTA_DB", None)
        else:
            os.environ["QUOTA_DB"] = previous_quota
        for name, saved_module in saved.items():
            if saved_module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = saved_module
    # Sanity: the stub actually governed the load (otherwise real env leaked in).
    assert list(module.registry._entries) == [ROLE["key"]], (
        f"controlled import failed; got {list(module.registry._entries)}"
    )
    return module


lr = _controlled_import()


@pytest.mark.parametrize("quota_present", [False, True])
def test_controlled_import_ignores_preexisting_registry(monkeypatch, quota_present):
    """A regular pytest session may already have imported the application registry."""
    existing = types.ModuleType("llm_registry")
    monkeypatch.setitem(sys.modules, "llm_registry", existing)
    if quota_present:
        monkeypatch.setenv("QUOTA_DB", str(_TMP / "previous.sqlite"))
    else:
        monkeypatch.delenv("QUOTA_DB", raising=False)
    previous_quota, previous_path = os.environ.get("QUOTA_DB"), list(sys.path)
    isolated = _controlled_import()
    assert isolated is not existing
    assert list(isolated.registry._entries) == [ROLE["key"]]
    assert sys.modules["llm_registry"] is existing
    assert os.environ.get("QUOTA_DB") == previous_quota
    assert sys.path == previous_path
    asyncio.run(isolated.registry.aclose())


def _roots(llm):
    """(sync_root, async_root): openai SDK root clients reachable via the documented seam."""
    sync_root = getattr(getattr(llm, "client", None), "_client", None)
    async_root = getattr(getattr(llm, "async_client", None), "_client", None)
    return sync_root, async_root


def _unique_roots(llms):
    seen = {}
    for llm in llms:
        if llm is None:
            continue
        for root in _roots(llm):
            if root is not None:
                seen[id(root)] = root
    return seen


def _extract_lifespan():
    path = BACKEND / "main.py"
    tree = ast.parse(path.read_text(encoding="utf-8-sig"))
    node = next(n for n in tree.body if isinstance(n, ast.AsyncFunctionDef) and n.name == "lifespan")
    return node, str(path)


def _exec_lifespan(registry):
    node, path = _extract_lifespan()

    async def threadpool(fn):
        return fn()

    ns = {
        "asynccontextmanager": asynccontextmanager,
        "setup_logging": lambda level: None,
        "settings": SimpleNamespace(log_level="INFO"),
        "run_in_threadpool": threadpool,
        "prewarm": lambda: None,
        # 2026-10-25：lifespan 在 prewarm 之后还有一次尽力而为的二次预热（QA 语料集/LLM 客户端）。
        # 本文件只钉「registry 收尾与异常传播」，故把它与 logging 一起桩掉。
        "_warm_secondary": lambda: None,
        # 2026-10-28（73297d5）：lifespan 新增启动期 fail-fast；本文件只测 registry 收尾，桩掉。
        "validate_embedding_config": lambda: None,
        "logging": logging,
        "registry": registry,
    }
    exec(compile(ast.Module(body=[node], type_ignores=[]), path, "exec"), ns)
    return ns["lifespan"]


class _RecordingRegistry:
    def __init__(self):
        self.events = []
        self.aclose_calls = 0

    async def aclose(self):
        self.aclose_calls += 1
        assert asyncio.get_running_loop().is_running()
        self.events.append("close")


# ---------- 版本契约(钉住私有接缝,防依赖漂移) ----------


def test_installed_chatopenai_accepts_client_injection_and_sdk_close_api():
    import openai
    from langchain_openai import ChatOpenAI

    sync_root = openai.OpenAI(api_key="k", base_url="http://127.0.0.1:9/v1")
    async_root = openai.AsyncOpenAI(api_key="k", base_url="http://127.0.0.1:9/v1")
    llm = ChatOpenAI(
        model="m",
        api_key="k",
        base_url="http://127.0.0.1:9/v1",
        streaming=True,
        client=sync_root.chat.completions,
        async_client=async_root.chat.completions,
    )
    assert llm.client is sync_root.chat.completions
    assert llm.async_client is async_root.chat.completions
    assert llm.client._client is sync_root
    assert llm.async_client._client is async_root
    assert not inspect.iscoroutinefunction(sync_root.close)
    assert inspect.iscoroutinefunction(async_root.close)


# ---------- lifespan 收尾(真实 main.lifespan AST) ----------


def test_real_lifespan_closes_registry_in_running_loop():
    registry = _RecordingRegistry()
    lifespan = _exec_lifespan(registry)

    async def exercise():
        async with lifespan(None):
            assert registry.events == []
        assert registry.events == ["close"]

    asyncio.run(exercise())
    assert registry.aclose_calls == 1


def test_real_lifespan_closes_on_business_exception_and_reraises():
    registry = _RecordingRegistry()
    lifespan = _exec_lifespan(registry)
    boom = RuntimeError("business-boom")

    async def exercise():
        with pytest.raises(RuntimeError) as caught:
            async with lifespan(None):
                registry.events.append("ready")
                raise boom
        assert caught.value is boom

    asyncio.run(exercise())
    assert registry.events == ["ready", "close"]


# ---------- aclose:真实 SDK 根(真实关闭 + 幂等) ----------


def _fresh_registry():
    return lr.LLMRegistry()


def test_registry_aclose_closes_real_installed_sdk_roots():
    reg = _fresh_registry()
    entry = next(iter(reg._entries.values()))
    sync_root, async_root = _roots(entry.llm)
    assert sync_root is not None and async_root is not None
    # openai root exposes is_closed() as a method (httpx inner client uses a property)
    assert not sync_root.is_closed() and not async_root.is_closed()
    asyncio.run(reg.aclose())
    assert sync_root.is_closed() and async_root.is_closed()
    asyncio.run(reg.aclose())  # idempotent: must not raise or touch closed pools again


def test_closing_one_registry_keeps_another_registrys_clients_open():
    first, second = _fresh_registry(), _fresh_registry()
    second_roots = _roots(next(iter(second._entries.values())).llm)
    try:
        asyncio.run(first.aclose())
        assert all(not root.is_closed() for root in second_roots)
    finally:
        asyncio.run(first.aclose())
        asyncio.run(second.aclose())


@pytest.mark.parametrize(
    ("openai_proxy", "system_proxy"),
    [("", True), ("http://127.0.0.1:19003", False), ("http://127.0.0.1:19003", True)],
)
def test_proxy_routing_timeout_and_registry_ownership(monkeypatch, openai_proxy, system_proxy):
    """Inspect transport selection only: never send a request to a model or proxy."""
    import httpx
    from openai._models import FinalRequestOptions

    for name in ("OPENAI_PROXY", "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY"):
        monkeypatch.delenv(name, raising=False)
        monkeypatch.delenv(name.lower(), raising=False)
    monkeypatch.setenv("OPENAI_PROXY", openai_proxy)
    if system_proxy:
        monkeypatch.setenv("HTTP_PROXY", "http://127.0.0.1:19001")
        monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:19002")
        monkeypatch.setenv("NO_PROXY", "bypass.example")
    monkeypatch.setattr(lr, "_load_roles", lambda: [dict(ROLE, timeout=37)])
    # The previous implementation delegated proxy precedence to this native path.
    reference = lr.ChatOpenAI(model=ROLE["model"], api_key="k", timeout=37)
    first, second = _fresh_registry(), None
    try:
        second = _fresh_registry()
        llm = next(iter(second._entries.values())).llm
        roots = _roots(llm)
        for root, reference_root in zip(roots, _roots(reference), strict=True):
            assert root.timeout == 37
            request = root._build_request(FinalRequestOptions.construct(method="get", url="/models"))
            assert request.extensions["timeout"] == dict(connect=37, read=37, write=37, pool=37)
            for scheme, port in (("http", 19001), ("https", 19002)):
                transport = root._client._transport_for_url(httpx.URL(f"{scheme}://llm.example/v1"))
                if not openai_proxy or not system_proxy:
                    assert transport._pool._proxy_url.port == (19003 if openai_proxy else port)
                bypass = root._client._transport_for_url(httpx.URL(f"{scheme}://bypass.example/v1"))
                if not openai_proxy:
                    assert bypass is root._client._transport
                for host in ("llm.example", "bypass.example"):
                    url = httpx.URL(f"{scheme}://{host}/v1")
                    actual = root._client._transport_for_url(url)._pool
                    expected = reference_root._client._transport_for_url(url)._pool
                    assert getattr(actual, "_proxy_url", None) == getattr(expected, "_proxy_url", None)
        variant = second.variant(False)
        assert _roots(variant) == roots
        second.reload(model="qwen-proxy-reload")
        assert _roots(next(iter(second._entries.values())).llm) == roots
        asyncio.run(first.aclose())
        assert all(not root.is_closed() for root in roots)
    finally:
        asyncio.run(first.aclose())
        if second is not None:
            asyncio.run(second.aclose())
        reference_sync, reference_async = _roots(reference)
        reference_sync.close()
        asyncio.run(reference_async.close())


# ---------- aclose:去重、失败隔离、显式失败(合成根,不依赖 SDK 内部) ----------


class _FakeRoot:
    def __init__(self, fail=False):
        self.calls = 0
        self.closed = False
        self._fail = fail

    def close(self):
        self.calls += 1
        if self._fail:
            raise RuntimeError("injected close failure")
        self.closed = True


def _install_fake_roots(reg, fail_async=False):
    from langchain_openai import ChatOpenAI

    entry = next(iter(reg._entries.values()))
    sync_root = _FakeRoot()
    async_root = _FakeRoot(fail=fail_async)
    entry.llm = ChatOpenAI(
        model=entry.model,
        api_key="k",
        base_url="http://127.0.0.1:9/v1",
        streaming=True,
        client=SimpleNamespace(_client=sync_root),
        async_client=SimpleNamespace(_client=async_root),
    )
    return entry, sync_root, async_root


def test_registry_aclose_attempts_remaining_and_fails_loudly_with_resource_label():
    reg = _fresh_registry()
    entry, sync_root, async_root = _install_fake_roots(reg, fail_async=True)

    with pytest.raises(RuntimeError) as caught:
        asyncio.run(reg.aclose())

    assert sync_root.closed and sync_root.calls == 1  # one failure must not stop the rest
    assert async_root.calls == 1
    assert "async" in str(caught.value) and entry.key in str(caught.value)
    assert "http://127.0.0.1:9" not in str(caught.value)  # never leak endpoint/cfg


# ---------- variant / reload:复用根 + 参数语义 ----------


def test_variant_and_model_reload_reuse_roots_and_keep_request_params():
    reg = _fresh_registry()
    entry = next(iter(reg._entries.values()))
    base = entry.llm
    v_off = reg.variant(True)
    v_on = reg.variant(False)
    reg.reload(model="qwen-test-model-2")  # returns config dict; the new llm lives on the entry
    r = entry.llm

    for instance in (v_off, v_on, r):
        assert instance.client._client is base.client._client
        assert instance.async_client._client is base.async_client._client

    assert v_off._default_params.get("extra_body") == {"thinking": {"type": "disabled"}}
    assert not v_on._default_params.get("extra_body")
    assert r._default_params.get("extra_body") == {"thinking": {"type": "disabled"}}
    assert r.model_name == "qwen-test-model-2"
    assert entry.model == "qwen-test-model-2"
    assert v_off.streaming is True and v_off.temperature == base.temperature
    assert v_off.request_timeout == base.request_timeout


def test_repeated_variant_and_reload_do_not_grow_sdk_owner_count():
    reg = _fresh_registry()
    entry = next(iter(reg._entries.values()))
    pool = [entry.llm]
    for _ in range(3):
        pool.append(reg.variant(True))
        pool.append(reg.variant(False))
    pool.append(reg.reload(model="qwen-test-model-3"))
    pool.append(reg.variant_of(entry.key, False))
    roots = _unique_roots(pool)
    assert len(roots) == 2  # exactly one sync + one async transport owner
    asyncio.run(reg.aclose())
    assert all(root.is_closed() for root in roots.values())


def test_variant_of_reuses_roots_and_keeps_params():
    reg = _fresh_registry()
    entry = next(iter(reg._entries.values()))
    base = entry.llm
    v = reg.variant_of(entry.key, False)
    assert v.client._client is base.client._client
    assert v.async_client._client is base.async_client._client
    assert not v._default_params.get("extra_body")


# ---------- 单请求取消不关共享客户端 ----------


def test_discarded_request_variant_leaves_shared_roots_open():
    reg = _fresh_registry()
    entry = next(iter(reg._entries.values()))
    sync_root, async_root = _roots(entry.llm)
    first = reg.variant(True)  # request 1's per-request instance
    assert first.async_client._client is async_root
    del first
    gc.collect()  # request 1 cancelled/abandoned: no per-request close path exists
    assert not sync_root.is_closed() and not async_root.is_closed()
    second = reg.variant(False)  # request 2 keeps using the shared transports
    assert second.client._client is sync_root
    assert not sync_root.is_closed()


def test_non_qwen_thinking_param_is_loaded(monkeypatch):
    """非 qwen 模型也能通过 thinking_param 关闭思考（deepseek-v4.1-flash 实测依赖此开关）。"""
    role = dict(ROLE, model="deepseek-test-model", capabilities=["text"], thinking_param="thinking")
    monkeypatch.setattr(lr.settings, "llm_models_json", json.dumps([role]))
    reg = _fresh_registry()
    try:
        entry = reg._entries[ROLE["key"]]
        assert entry.cfg["thinking_param"] == "thinking"
        assert entry.llm._default_params.get("extra_body") == {"thinking": {"type": "disabled"}}
    finally:
        asyncio.run(reg.aclose())
