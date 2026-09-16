"""1c「失败即换模型」的正式单测（2026-09-14，grilling 确认 F1–F8，指导书 §9.2）。

覆盖的生产行为：
- F1 `registry.pick(exclude=...)`：排除**已尝试** key（瞬时故障不标记，无法靠 `unavailable` 推进）；
- F2 终止条件 =「每个 key 最多试一次」→ 用「已尝试集合」而非「是否成功」判定，
     外部持续失败也**必然终止**（本文件用独立信号验证：pick 调用次数 + 每个假模型 invoke 次数）；
- F3 schema 能力拒绝 → **原样上抛、不换模型、不标记**，交给既有降级路径（保护 V2-T4 的窄判定）；
- F5 瞬时/永久判定统一走 `llm_errors.is_transient_error`（与 rerank 的 1k 修复同一口径）；
- F6 观测复用既有白名单字段（`llm_adapter_stage` = `failover_switch` / `failover_exhausted`）。

设计纪律：**不联网、不构造真实模型**——全链路经假 transport + 脚本化 registry；
且**不拿真实模型试失败路径**（F8）。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from types import SimpleNamespace

import httpx
import pytest

import llm_errors
import llm_registry
from agent.runtime import RegistryFailoverTransport, is_schema_capability_rejection
from llm_registry import QuotaExhausted

# ---------------------------------------------------------------------------
# 假对象与异常工厂
# ---------------------------------------------------------------------------


def _http_status(status: int) -> httpx.HTTPStatusError:
    """httpx 形态：状态码在 `.response.status_code` 上。"""
    req = httpx.Request("POST", "https://example.invalid/v1/chat/completions")
    return httpx.HTTPStatusError(str(status), request=req, response=httpx.Response(status, request=req))


class _PlatformStatusError(Exception):
    """openai SDK 形态：状态码直接在 `.status_code`，可选 `body` 文本。

    （镜像 tests/test_agent_runtime.py 的同类假异常；生产 Agent 的 transport 是 ChatOpenAI，
    抛的正是这种形态，故两类形态都必须被判定覆盖。）
    """

    def __init__(self, status_code: int, message: str, body: str = "") -> None:
        super().__init__(message)
        self.status_code = status_code
        self.body = body


class _RaisingTransport:
    """调用即抛预置异常的假模型。"""

    def __init__(self, exc: BaseException) -> None:
        self.exc = exc
        self.calls = 0

    def invoke(self, messages: object) -> object:
        self.calls += 1
        raise self.exc


class _OkTransport:
    """调用即返回标记的假模型。"""

    def __init__(self, tag: str) -> None:
        self.tag = tag
        self.calls = 0

    def invoke(self, messages: object) -> object:
        self.calls += 1
        return self.tag


class _BindRecordingTransport:
    """带 `bind` 的假模型：记录收到的 bind 参数，绑定后调用返回 `"<tag>#bound"`。"""

    def __init__(self, tag: str) -> None:
        self.tag = tag
        self.bind_calls: list[dict[str, object]] = []
        self.invoke_calls = 0

    def bind(self, **kwargs: object) -> _BindRecordingTransport:
        self.bind_calls.append(dict(kwargs))
        return self

    def invoke(self, messages: object) -> object:
        self.invoke_calls += 1
        return f"{self.tag}#bound"


@dataclass
class ScriptedRegistry:
    """脚本化 registry：按预置序列返回 `(key, llm)`，并**复刻真实 pick 的 exclude 语义**。

    真实 `pick` 在「无未尝试模型」时抛 `QuotaExhausted`——这里同样抛，使终止条件可被验证。
    """

    seq: list[tuple[str, object]]
    picks: list[frozenset[str]] = field(default_factory=list)
    marked: list[tuple[str, str]] = field(default_factory=list)

    def pick(self, modality: str, tier: str, *, exclude: set[str] | None = None) -> tuple[str, object]:
        skipped = set(exclude or set())
        self.picks.append(frozenset(skipped))
        for key, llm in self.seq:
            if key not in skipped:
                return key, llm
        raise QuotaExhausted("无未尝试模型")

    def mark_depleted(self, key: str, reason: str) -> None:
        self.marked.append((key, reason))


@pytest.fixture
def install_registry(monkeypatch):
    """把全局 registry 的 pick / mark_depleted 替换为脚本化实现（monkeypatch 自动还原）。"""

    def _install(seq: list[tuple[str, object]]) -> ScriptedRegistry:
        reg = ScriptedRegistry(seq=seq)
        monkeypatch.setattr(llm_registry.registry, "pick", reg.pick)
        monkeypatch.setattr(llm_registry.registry, "mark_depleted", reg.mark_depleted)
        return reg

    return _install


@pytest.fixture
def adapter_records():
    """直接挂在 `legal.agent` logger 上抓观测记录——不依赖 propagate 设置，比 caplog 稳。"""
    logger = logging.getLogger("legal.agent")
    records: list[logging.LogRecord] = []

    class _Handler(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            records.append(record)

    handler = _Handler(level=logging.WARNING)
    logger.addHandler(handler)
    previous_level = logger.level
    logger.setLevel(logging.WARNING)
    try:
        yield records
    finally:
        logger.removeHandler(handler)
        logger.setLevel(previous_level)


def _invoke() -> object:
    return RegistryFailoverTransport().invoke([{"role": "user", "content": "hi"}])


# ---------------------------------------------------------------------------
# llm_errors：瞬时/永久判定矩阵（F5）
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("status", [408, 429, 500, 502, 503, 504])
def test_transient_status_is_transient_in_both_sdk_shapes(status):
    """两种 SDK 形态都必须判为瞬时——httpx 的状态码在 .response，OpenAI 的在顶层。"""
    assert llm_errors.is_transient_error(_http_status(status)) is True
    assert llm_errors.is_transient_error(_PlatformStatusError(status, "boom")) is True


@pytest.mark.parametrize("status", [400, 401, 403, 404, 422])
def test_permanent_status_is_not_transient_in_both_sdk_shapes(status):
    assert llm_errors.is_transient_error(_http_status(status)) is False
    assert llm_errors.is_transient_error(_PlatformStatusError(status, "boom")) is False


def test_network_transport_errors_are_transient():
    req = httpx.Request("POST", "https://example.invalid/")
    assert llm_errors.is_transient_error(httpx.ConnectError("boom", request=req)) is True
    # TimeoutException 是 TransportError 子类 → 与本模块口径一致地判为瞬时
    assert llm_errors.is_transient_error(httpx.ReadTimeout("slow", request=req)) is True


def test_unknown_local_exception_is_not_transient():
    """无状态码的本地异常保守判为永久失败（按真实失败处理）。"""
    assert llm_errors.is_transient_error(ValueError("local bug")) is False


def test_status_of_handles_both_shapes_and_missing():
    assert llm_errors.status_of(_http_status(429)) == 429
    assert llm_errors.status_of(_PlatformStatusError(500, "x")) == 500
    assert llm_errors.status_of(ValueError("x")) is None


def test_retrieval_shares_one_transient_decision():
    """rerank（1k 修复）与 Agent 失败换模型必须共用同一判定，不得两处分叉。"""
    import retrieval

    assert retrieval._is_transient_rerank_error is llm_errors.is_transient_error


# ---------------------------------------------------------------------------
# llm_registry.pick(exclude=...)（F1）
# ---------------------------------------------------------------------------


def _entry(key: str, *, priority: int = 1, quota_left: int = 100, unavailable: bool = False) -> SimpleNamespace:
    return SimpleNamespace(
        key=key,
        modality="text",
        tier="flag",
        priority=priority,
        quota_left=quota_left,
        unavailable=unavailable,
        llm=object(),
    )


@pytest.fixture
def install_entries(monkeypatch):
    def _install(entries: list[SimpleNamespace]) -> None:
        monkeypatch.setattr(llm_registry.registry, "_entries", {e.key: e for e in entries})

    return _install


def test_pick_without_exclude_is_unchanged(install_entries):
    """缺省 exclude=None → 行为与历史一致（同档按 priority 升序取首个可用）。"""
    install_entries([_entry("k1", priority=1), _entry("k2", priority=2)])
    assert llm_registry.registry.pick("text", "flag")[0] == "k1"


def test_pick_exclude_none_and_empty_set_are_noops(install_entries):
    install_entries([_entry("k1")])
    assert llm_registry.registry.pick("text", "flag", exclude=None)[0] == "k1"
    assert llm_registry.registry.pick("text", "flag", exclude=set())[0] == "k1"


def test_pick_exclude_advances_to_next_candidate(install_entries):
    install_entries([_entry("k1", priority=1), _entry("k2", priority=2)])
    assert llm_registry.registry.pick("text", "flag", exclude={"k1"})[0] == "k2"


def test_pick_exclude_all_raises_quota_exhausted(install_entries):
    """全部被排除 → 与「无可用模型」同语义：抛 QuotaExhausted（循环据此终止）。"""
    install_entries([_entry("k1"), _entry("k2")])
    with pytest.raises(QuotaExhausted):
        llm_registry.registry.pick("text", "flag", exclude={"k1", "k2"})


def test_pick_exclude_does_not_rescue_unavailable_model(install_entries):
    """exclude 只排除指定 key，不改变「耗尽即不可用」判定。"""
    install_entries([_entry("k1", priority=1, unavailable=True), _entry("k2", priority=2)])
    assert llm_registry.registry.pick("text", "flag")[0] == "k2"


# ---------------------------------------------------------------------------
# RegistryFailoverTransport：A 瞬时换模型
# ---------------------------------------------------------------------------


def test_transient_429_switches_model_without_marking(install_registry):
    t1, t2 = _RaisingTransport(_http_status(429)), _OkTransport("k2-ok")
    reg = install_registry([("k1", t1), ("k2", t2)])

    assert _invoke() == "k2-ok"
    assert reg.marked == [], "瞬时故障不应把模型标记为耗尽"
    assert reg.picks == [frozenset(), frozenset({"k1"})], "exclude 必须推进到下一个 key"
    assert (t1.calls, t2.calls) == (1, 1)


def test_connection_error_switches_model_without_marking(install_registry):
    err = httpx.ConnectError("boom", request=httpx.Request("POST", "https://example.invalid/"))
    t1, t2 = _RaisingTransport(err), _OkTransport("k2-ok")
    reg = install_registry([("k1", t1), ("k2", t2)])

    assert _invoke() == "k2-ok"
    assert reg.marked == []
    assert (t1.calls, t2.calls) == (1, 1)


@pytest.mark.parametrize("status", [429, 500, 503])
def test_all_transient_statuses_are_switchable_without_marking(install_registry, status):
    t1, t2 = _RaisingTransport(_http_status(status)), _OkTransport("k2-ok")
    reg = install_registry([("k1", t1), ("k2", t2)])

    assert _invoke() == "k2-ok"
    assert reg.marked == []


# ---------------------------------------------------------------------------
# RegistryFailoverTransport：B 永久失败换模型 + 标记
# ---------------------------------------------------------------------------


def test_permanent_400_switches_and_marks_depleted(install_registry):
    t1, t2 = _RaisingTransport(_http_status(400)), _OkTransport("k2-ok")
    reg = install_registry([("k1", t1), ("k2", t2)])

    assert _invoke() == "k2-ok"
    assert reg.marked == [("k1", "model_failure")]
    assert (t1.calls, t2.calls) == (1, 1)


@pytest.mark.parametrize("status", [400, 401, 403, 404])
def test_permanent_statuses_all_mark_before_switching(install_registry, status):
    t1, t2 = _RaisingTransport(_http_status(status)), _OkTransport("k2-ok")
    reg = install_registry([("k1", t1), ("k2", t2)])

    assert _invoke() == "k2-ok"
    assert reg.marked == [("k1", "model_failure")]


def test_plain_400_without_schema_marker_is_permanent(install_registry):
    """「未知 400」不得被当成 schema 能力拒绝（F3 的反向守卫）。"""
    exc = _PlatformStatusError(400, "invalid model name")
    assert is_schema_capability_rejection(exc) is False
    assert llm_errors.is_transient_error(exc) is False

    reg = install_registry([("k1", _RaisingTransport(exc)), ("k2", _OkTransport("k2-ok"))])
    assert _invoke() == "k2-ok"
    assert reg.marked == [("k1", "model_failure")]


# ---------------------------------------------------------------------------
# RegistryFailoverTransport：C 全失败 → 上抛最后一个，且有界（F2）
# ---------------------------------------------------------------------------


def test_all_models_failed_raises_last_exception_and_is_bounded(install_registry, adapter_records):
    e1, e2 = _http_status(429), _http_status(500)
    t1, t2 = _RaisingTransport(e1), _RaisingTransport(e2)
    reg = install_registry([("k1", t1), ("k2", t2)])

    with pytest.raises(httpx.HTTPStatusError) as ei:
        _invoke()

    assert ei.value is e2, "应上抛**最后一个**异常（保留原始失败原因，而非配平用的 QuotaExhausted）"
    assert (t1.calls, t2.calls) == (1, 1), "每个 key 最多尝试一次"
    assert len(reg.picks) == 3, "k1/k2 各 pick 一次，第 3 次无未尝试模型即终止 → 循环有界"
    assert reg.picks[-1] == frozenset({"k1", "k2"})
    assert reg.marked == [], "429/500 均为瞬时 → 都不标记"

    stages = [(r.llm_adapter_stage, r.llm_invoke_mode) for r in adapter_records]
    assert ("failover_switch", "transient") in stages
    assert ("failover_exhausted", "all_models_failed") in stages


def test_no_available_model_raises_quota_exhausted_without_marking(install_registry, adapter_records):
    """一个模型都没试过就无可用 → 原样上抛 QuotaExhausted（调用方转 RuntimeUnavailable）。"""
    reg = install_registry([])

    with pytest.raises(QuotaExhausted):
        _invoke()

    assert reg.marked == []
    assert reg.picks == [frozenset()]
    assert [r.llm_adapter_stage for r in adapter_records] == [], "未尝试任何模型 → 不写 exhausted 观测"


# ---------------------------------------------------------------------------
# RegistryFailoverTransport：E schema 能力拒绝原样上抛（F3）
# ---------------------------------------------------------------------------


def test_schema_rejection_passes_through_without_switch_or_mark(install_registry):
    exc = _PlatformStatusError(
        400,
        "response_format is not supported",
        body='{"error":"structured output unsupported"}',
    )
    assert is_schema_capability_rejection(exc) is True, "前提：本用例的异常确实被判为 schema 拒绝"

    t1, t2 = _RaisingTransport(exc), _OkTransport("k2-ok")
    reg = install_registry([("k1", t1), ("k2", t2)])

    with pytest.raises(_PlatformStatusError) as ei:
        _invoke()

    assert ei.value is exc
    assert reg.marked == []
    assert reg.picks == [frozenset()], "pick 仅 1 次 → 未换模型"
    assert (t1.calls, t2.calls) == (1, 0), "不得因 schema 拒绝而切到下一个模型"


# ---------------------------------------------------------------------------
# RegistryFailoverTransport：绑定必须按当前选中模型重建
# ---------------------------------------------------------------------------


def test_unbound_transport_invokes_model_directly(install_registry):
    install_registry([("k1", _OkTransport("k1-ok"))])
    assert _invoke() == "k1-ok"


def test_bind_kwargs_reach_the_selected_model(install_registry):
    llm = _BindRecordingTransport("k1")
    install_registry([("k1", llm)])

    transport = RegistryFailoverTransport().bind(response_format={"type": "json_object"})
    assert transport.invoke([{"role": "user", "content": "hi"}]) == "k1#bound"
    assert llm.bind_calls == [{"response_format": {"type": "json_object"}}]
    assert llm.invoke_calls == 1


def test_bind_is_rebuilt_on_the_model_selected_after_switch(install_registry):
    """换模型后旧绑定失效 → 新模型必须重新收到同一组 bind 参数。"""
    bad, good = _RaisingTransport(_http_status(429)), _BindRecordingTransport("k2")
    install_registry([("k1", bad), ("k2", good)])

    transport = RegistryFailoverTransport().bind(temperature=0)
    assert transport.invoke([{"role": "user", "content": "hi"}]) == "k2#bound"
    assert good.bind_calls == [{"temperature": 0}]
    assert bad.calls == 1


# ---------------------------------------------------------------------------
# 组合根装配：wrapper 必须真的被装进生产链路，而不只是"存在"
# ---------------------------------------------------------------------------


class _SettingsSnapshot:
    """`build_agent_runtime` 只读这几个预算字段（镜像 tests/test_agent_runtime.py 的同名快照）。"""

    agent_max_steps = 8
    agent_max_tool_calls = 10
    agent_max_replans = 3
    agent_max_clarifications = 2
    agent_max_verifier_research_returns = 1


def test_build_agent_runtime_installs_failover_transport(monkeypatch, install_registry):
    """`llm=None` → 组合根必须装配 RegistryFailoverTransport，且**该实例**真的能换模型。

    这一条针对「测试 seam 绕过守卫」这一污染源：只在单测里手搓一个包装实例，证明不了生产装配
    路径真的用了它；这里验证的是 `build_agent_runtime` 交到 planner 手上的那个对象。
    """
    from agent.runtime import build_agent_runtime
    from llm_registry import registry

    monkeypatch.setattr(registry, "get", lambda: object())  # 启动期探测（原语义）通过
    reg = install_registry([("k1", _RaisingTransport(_http_status(429))), ("k2", _OkTransport("k2-ok"))])

    runtime = build_agent_runtime(db=object(), user_id=1, settings=_SettingsSnapshot())

    transport = runtime.controller._planner._transport
    assert isinstance(transport, RegistryFailoverTransport)
    assert transport.invoke([{"role": "user", "content": "hi"}]) == "k2-ok"
    assert reg.marked == [], "瞬时故障不得标记耗尽"


def test_build_agent_runtime_keeps_injected_transport_unwrapped():
    """`llm=...` 注入点必须保持不包装——既有测试依赖它注入 fake 以绕过真实模型。"""
    from agent.runtime import build_agent_runtime

    injected = _OkTransport("injected")
    runtime = build_agent_runtime(db=object(), user_id=1, settings=_SettingsSnapshot(), llm=injected)

    assert runtime.controller._planner._transport is injected
