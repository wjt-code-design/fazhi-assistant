"""DB-17（2026-10-09，审查报告 B-48）：请求被拒 ≠ 积分用完——两条通道必须分得开。

改前的形状（状态码网格实测见报告 §12.4，openai 1.109.1 打 127.0.0.1 stub）：
`llm_errors.is_transient_error` 判 permanent 之后，调用方**只有一条**处理通道
`registry.mark_depleted(key, "model_failure")`，而它的实现是 `runtime_used += quota_left`
（把配额记满）且**把 `reason` 参数整个丢弃**（连日志都不落）。
⇒ 一次 400（超长上下文 / 内容审核 / 模型名写错 / key 失效）在管理台、`quota_store`、
看门狗眼里的读数全都是"这个模型积分用完了"；运维据此去加积分或调 `calibrate`，
真病因（payload/配置）永远不出现在任何一张表里。**恢复只有两条路：重启，或人工校准。**

本轮**不动**分类口径：`tests/test_llm_failover.py:167-170` 把 400/401/403/404/422 钉成
permanent 是有意的（模型名错、key 失效该退出轮换）。改的是"以什么名义、退多久"。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import httpx
import pytest

import agent.runtime as agent_runtime
import llm_errors
import llm_registry
from agent.runtime import RegistryFailoverTransport
from llm_registry import ModelEntry, QuotaExhausted


def _http_status(status: int) -> httpx.HTTPStatusError:
    req = httpx.Request("POST", "https://example.invalid/v1/chat/completions")
    return httpx.HTTPStatusError(str(status), request=req, response=httpx.Response(status, request=req))


class _PlatformStatusError(Exception):
    """openai SDK 形态：状态码直接在 `.status_code`。"""

    def __init__(self, status_code: int, message: str = "boom") -> None:
        super().__init__(message)
        self.status_code = status_code


class _RaisingTransport:
    def __init__(self, exc: BaseException) -> None:
        self.exc = exc
        self.calls = 0

    def invoke(self, messages: object) -> object:
        self.calls += 1
        raise self.exc


class _OkTransport:
    def __init__(self, value: str) -> None:
        self.value = value
        self.calls = 0

    def invoke(self, messages: object) -> object:
        self.calls += 1
        return self.value


def _entry(key: str, *, priority: int = 1, quota_total: int = 1000, initial_used: int = 0) -> ModelEntry:
    return ModelEntry(
        key=key,
        model=f"model-{key}",
        modality="text",
        tier="flag",
        priority=priority,
        capabilities=set(),
        cfg={},
        quota_total=quota_total,
        initial_used=initial_used,
        llm=object(),  # pick 只断言非 None
    )


@pytest.fixture
def entries(monkeypatch):
    def _install(*objs: ModelEntry) -> dict[str, ModelEntry]:
        monkeypatch.setattr(llm_registry.registry, "_entries", {e.key: e for e in objs})
        return {e.key: e for e in objs}

    return _install


@pytest.fixture
def records():
    """直挂 `legal.llm` 抓记录，不依赖 propagate（与 test_llm_failover 的 adapter_records 同法）。"""
    logger = logging.getLogger("legal.llm")
    bag: list[logging.LogRecord] = []

    class _H(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            bag.append(record)

    h = _H(level=logging.DEBUG)
    logger.addHandler(h)
    prev = logger.level
    logger.setLevel(logging.DEBUG)
    try:
        yield bag
    finally:
        logger.removeHandler(h)
        logger.setLevel(prev)


# ---------------------------------------------------------------------------
# 判据：哪些 4xx 算"请求被拒"
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("status", [400, 401, 403, 404, 422])
def test_request_shape_rejections_are_recognized_in_both_sdk_shapes(status: int):
    assert llm_errors.is_request_shape_rejection(_http_status(status)) is True
    assert llm_errors.is_request_shape_rejection(_PlatformStatusError(status)) is True


@pytest.mark.parametrize("status", [408, 429, 500, 502, 503, 504])
def test_transient_statuses_are_not_request_rejections(status: int):
    assert llm_errors.is_request_shape_rejection(_http_status(status)) is False


def test_no_status_local_error_is_not_a_rejection():
    """无状态码（真耗尽文案、解析错等）必须仍走老通道 mark_depleted——否则我把耗尽也豁免了。"""
    assert llm_errors.is_request_shape_rejection(RuntimeError("Insufficient Balance")) is False


def test_classifying_a_rejection_does_not_change_transient_verdict():
    """在册口径不许被顺手动：4xx 仍判 permanent（test_llm_failover.py:167-170 钉着）。"""
    for status in (400, 401, 403, 404, 422):
        exc = _PlatformStatusError(status)
        assert llm_errors.is_transient_error(exc) is False
        assert llm_errors.is_request_shape_rejection(exc) is True


# ---------------------------------------------------------------------------
# 通道本体：拒绝不动配额账，耗尽才动
# ---------------------------------------------------------------------------


def test_mark_rejected_leaves_quota_untouched_and_cools_the_model(entries, records):
    reg = llm_registry.registry
    table = entries(_entry("k1"), _entry("k2", priority=2))
    before = table["k1"].quota_left
    assert before == 1000

    reg.mark_rejected("k1", "model_failure", status=400)

    assert table["k1"].quota_left == before, "被拒不该把配额记满（这正是 B-48 的病根）"
    assert table["k1"].depleted is False
    assert reg.pick("text", "flag")[0] == "k2", "冷却期内应退出自动路由"
    hit = [r for r in records if r.getMessage() == "llm_request_rejected"]
    assert len(hit) == 1
    assert hit[0].model_failure_channel == "rejected"  # type: ignore[attr-defined]
    assert hit[0].llm_error_status_code == 400  # type: ignore[attr-defined]


def test_rejection_expires_by_itself(entries, monkeypatch):
    """冷却会自愈（改前的"永久"只能靠重启或人工校准解除）。"""
    reg = llm_registry.registry
    entries(_entry("k1"), _entry("k2", priority=2))
    clock = {"t": 1000.0}
    monkeypatch.setattr(llm_registry.time, "monotonic", lambda: clock["t"])

    reg.mark_rejected("k1", "model_failure", status=400)
    assert reg.pick("text", "flag")[0] == "k2"
    clock["t"] += llm_registry.REJECT_COOLDOWN_S + 1
    assert reg.pick("text", "flag")[0] == "k1", "冷却到期必须重新参与路由"


def test_mark_depleted_still_burns_the_quota_and_now_logs_a_reason(entries, records):
    """对照腿（负向自证）：老通道确实把配额记满，且 `reason` 不再被丢弃。"""
    reg = llm_registry.registry
    table = entries(_entry("k1"), _entry("k2", priority=2))
    reg.mark_depleted("k1", "quota_exhausted")
    assert table["k1"].quota_left == 0
    hit = [r for r in records if r.getMessage() == "llm_model_depleted"]
    assert len(hit) == 1
    assert hit[0].model_failure_channel == "exhausted"  # type: ignore[attr-defined]
    assert hit[0].model_failure_reason == "quota_exhausted"  # type: ignore[attr-defined]


def test_all_models_rejected_raises_quota_exhausted(entries):
    """全链被拒时的终态仍是可诊断的异常（不是静默成功）。"""
    reg = llm_registry.registry
    entries(_entry("k1"), _entry("k2", priority=2))
    reg.mark_rejected("k1", "model_failure", status=400)
    reg.mark_rejected("k2", "model_failure", status=400)
    with pytest.raises(QuotaExhausted):
        reg.pick("text", "flag")


# ---------------------------------------------------------------------------
# 调用点接线：transport 的 permanent 分支按成因分流
# ---------------------------------------------------------------------------


@dataclass
class _SpyRegistry:
    seq: list[tuple[str, object]]
    tried_exhausted: list[tuple[str, str]] = field(default_factory=list)
    tried_rejected: list[tuple[str, str, object]] = field(default_factory=list)
    picks: list[frozenset[str]] = field(default_factory=list)

    def pick(self, modality: str, tier: str, *, exclude: set[str] | None = None):
        skipped = set(exclude or set())
        self.picks.append(frozenset(skipped))
        for key, llm in self.seq:
            if key not in skipped:
                return key, llm
        raise QuotaExhausted("无未尝试模型")

    def mark_depleted(self, key: str, reason: str) -> None:
        self.tried_exhausted.append((key, reason))

    def mark_rejected(self, key: str, reason: str, *, status: int | None = None) -> None:
        self.tried_rejected.append((key, reason, status))


@pytest.fixture
def spy(monkeypatch):
    def _install(seq: list[tuple[str, object]]) -> _SpyRegistry:
        reg = _SpyRegistry(seq=seq)
        monkeypatch.setattr(llm_registry.registry, "pick", reg.pick)
        monkeypatch.setattr(llm_registry.registry, "mark_depleted", reg.mark_depleted)
        monkeypatch.setattr(llm_registry.registry, "mark_rejected", reg.mark_rejected)
        return reg

    return _install


def _invoke() -> object:
    return RegistryFailoverTransport().invoke([{"role": "user", "content": "hi"}])


def test_failover_routes_400_to_the_rejection_channel(spy):
    t1, t2 = _RaisingTransport(_PlatformStatusError(400, "context_length_exceeded-ish")), _OkTransport("ok2")
    reg = spy([("k1", t1), ("k2", t2)])
    assert _invoke() == "ok2"
    assert reg.tried_rejected == [("k1", "model_failure", 400)], "400 必须走冷却通道"
    assert reg.tried_exhausted == [], "400 不该再被记成配额耗尽"


def test_failover_routes_statusless_quota_error_to_depletion(spy):
    """对照腿：没有状态码的失败（真耗尽/本地异常）仍走老通道，别把耗尽一起豁免掉。"""
    t1, t2 = _RaisingTransport(RuntimeError("Insufficient Balance")), _OkTransport("ok2")
    reg = spy([("k1", t1), ("k2", t2)])
    assert _invoke() == "ok2"
    assert reg.tried_rejected == []
    assert reg.tried_exhausted == [("k1", "model_failure")]


def test_failover_does_not_mark_transient_at_all(spy):
    """F7 那半边在册语义一字未动：瞬时只换模型不标记。"""
    t1, t2 = _RaisingTransport(_http_status(429)), _OkTransport("ok2")
    reg = spy([("k1", t1), ("k2", t2)])
    assert _invoke() == "ok2"
    assert (reg.tried_rejected, reg.tried_exhausted) == ([], [])


# ---------------------------------------------------------------------------
# 变异腿：证明"分通道"这件事是被生产判据驱动的，不是用例自己挑了一支
# ---------------------------------------------------------------------------


def test_routing_predicate_is_load_bearing_both_ways(spy, monkeypatch):
    """把 `is_request_shape_rejection` 打死成常量，两条通道必须各自翻面。

    缺这条时，"400 → 冷却"与"无状态码 → 配额"两腿可能只是**同一条 if 的两个分支各测一次**；
    若有人把路由写成无条件 `mark_rejected`（或无条件 `mark_depleted`），单看那两腿都会红得没有信息量。
    这里分别钉：判据恒假 ⇒ 400 落回配额通道；判据恒真 ⇒ 无状态码落进冷却通道。
    """
    monkeypatch.setattr(agent_runtime, "is_request_shape_rejection", lambda exc: False)
    reg = spy([("k1", _RaisingTransport(_PlatformStatusError(400))), ("k2", _OkTransport("ok2"))])
    assert _invoke() == "ok2"
    assert reg.tried_exhausted == [("k1", "model_failure")], "判据恒假 → 400 退回老通道（证明路由真由它决定）"
    assert reg.tried_rejected == []

    monkeypatch.setattr(agent_runtime, "is_request_shape_rejection", lambda exc: True)
    reg2 = spy([("k1", _RaisingTransport(RuntimeError("Insufficient Balance"))), ("k2", _OkTransport("ok2"))])
    assert _invoke() == "ok2"
    assert reg2.tried_rejected == [("k1", "model_failure", None)], "判据恒真 → 耗尽也被冷却（这正是控制腿要防的错法）"
    assert reg2.tried_exhausted == []


def test_pick_actually_consumes_the_cooldown_flag(monkeypatch):
    """冷却位必须被 `pick` 真读：同一只条目，只动 `rejected_until` 一根轴，结论就该翻转。

    刻意用**配额充足**的条目（`quota_total=100`）——否则 QuotaExhausted 可能只是"没配额"，
    那条腿就成了假对照。反向腿再把 `rejected_now` 打死成 False，验证跳过确实来自这个属性。
    """
    entry = ModelEntry(
        key="k1",
        model="m1",
        modality="text",
        tier="flag",
        priority=1,
        capabilities=set(),
        cfg={},
        quota_total=100,
        initial_used=0,
        llm=object(),  # type: ignore[arg-type]
    )
    monkeypatch.setattr(llm_registry.registry, "_entries", {"k1": entry})

    assert llm_registry.registry.pick("text", "flag")[0] == "k1", "未冷却 → 正常选中（正对照）"

    entry.rejected_until = llm_registry.time.monotonic() + 3600
    with pytest.raises(QuotaExhausted):
        llm_registry.registry.pick("text", "flag")
    assert entry.quota_left == 100, "冷却不得动配额账（B-48 的记账面）"

    monkeypatch.setattr(ModelEntry, "rejected_now", property(lambda self: False))
    assert llm_registry.registry.pick("text", "flag")[0] == "k1", "把冷却位摘掉即可选中 → 上一步的红确实来自它"


# ---------------------------------------------------------------------------
# 复核轮 B 路（2026-10-09）补的洞：`_safe_pick` 的回落支绕过 `pick` 的冷却过滤
# ---------------------------------------------------------------------------


def test_safe_pick_marks_a_cooling_default_as_degraded(monkeypatch):
    """整池冷却时，回落到默认模型也必须标 degraded——否则冷却只剩"少选它"没有"别打它"。

    形状：`_entries` 里只有一只 text/flag、**配额健康**的模型；
    用 `_safe_pick("vision", ...)` 逼出 `QuotaExhausted` 走回落支（不 patch 任何方法，
    这样 `is_unavailable`／`is_rejected` 都是真判定，测试不自证）。
    """
    import main as main_module

    entry = ModelEntry(
        key="k1",
        model="m1",
        modality="text",
        tier="flag",
        priority=1,
        capabilities=set(),
        cfg={},
        quota_total=100,
        initial_used=0,
        llm=object(),  # type: ignore[arg-type]
    )
    monkeypatch.setattr(llm_registry.registry, "_entries", {"k1": entry})
    monkeypatch.setattr(llm_registry.registry, "_admin_disabled", set())

    key, _llm, degraded = main_module._safe_pick("vision", "flag")
    assert (key, degraded) == ("k1", False), "回落到配额健康且未冷却的模型 ⇒ 不标降级（改前后同读数）"

    llm_registry.registry.mark_rejected("k1", "model_failure", status=400)
    assert entry.quota_left == 100, "冷却不写配额账（B-48 的记账面，本腿再钉一次）"
    assert llm_registry.registry.is_unavailable("k1") is False, "配额轴仍说它健康——问题在拒绝轴"

    key2, _llm2, degraded2 = main_module._safe_pick("vision", "flag")
    assert (key2, degraded2) == ("k1", True), "同一只模型进入 4xx 冷却后，回落支必须标降级"


def test_reject_predicate_is_the_only_thing_that_moves_the_flag(monkeypatch):
    """反向对照：把冷却位摘掉，回落支的 degraded 必须回到 False（证明上一步的红来自那一维）。"""
    import main as main_module

    entry = ModelEntry(
        key="k1",
        model="m1",
        modality="text",
        tier="flag",
        priority=1,
        capabilities=set(),
        cfg={},
        quota_total=100,
        initial_used=0,
        llm=object(),  # type: ignore[arg-type]
    )
    entry.rejected_until = llm_registry.time.monotonic() + 600
    monkeypatch.setattr(llm_registry.registry, "_entries", {"k1": entry})
    monkeypatch.setattr(llm_registry.registry, "_admin_disabled", set())
    assert main_module._safe_pick("vision", "flag")[2] is True, "前提：冷却中 ⇒ 标降级"

    monkeypatch.setattr(ModelEntry, "rejected_now", property(lambda self: False))
    assert main_module._safe_pick("vision", "flag")[2] is False, "摘掉冷却位即回到 False ⇒ 判据真由它决定"
