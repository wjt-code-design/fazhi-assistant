"""模型管理面（2026-09-15）：promote / set_disabled / pick 过滤（全 mock，非 slow）。

钉住的契约：
1. `promote(key)` 把该模型提为所在 (modality, tier) 链首（pick 立即返回它）；
2. `set_disabled(key, True)` 后 pick **跳过**该模型（自动路由禁用），恢复后重新参与；
3. 禁用**不影响** `pick_by_key`（judge 等显式指定场景）；
4. 禁用与配额 `unavailable` 语义独立（配额健康但被禁 → 仍跳过）；
5. 未知 key → KeyError；重复 promote 同一 key 无变化（确定性）；
6. `status()` 暴露 `admin_disabled` 字段。
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from llm_registry import registry


def _entry(key: str, *, priority: int, model: str = "m", quota_total: int = 1000) -> SimpleNamespace:
    """模拟 pick 所需的最小 entry 面（tests/test_tiering.py 同模式）。"""
    return SimpleNamespace(
        key=key,
        model=model,
        modality="text",
        tier="flag",
        priority=priority,
        capabilities={"text"},
        quota_total=quota_total,
        initial_used=0,
        runtime_used=0,
        llm=object(),
        quota_left=quota_total,
        depleted=False,
        below_threshold=False,
        unavailable=False,
    )


@pytest.fixture
def chain(monkeypatch):
    """3 条 text/flag 链：a(prio 0) → b(prio 1) → c(prio 2)。"""
    entries = {
        "a": _entry("a", priority=0),
        "b": _entry("b", priority=1),
        "c": _entry("c", priority=2),
    }
    monkeypatch.setattr(registry, "_entries", entries)
    monkeypatch.setattr(registry, "_admin_disabled", set())
    return entries


def test_promote_moves_key_to_chain_head(chain):
    registry.promote("c")
    assert registry.pick("text", "flag")[0] == "c"
    # 链首确定性：重复 promote 同一 key 无变化
    registry.promote("c")
    assert registry.pick("text", "flag")[0] == "c"
    # 其余按原序
    registry.promote("b")
    assert registry.pick("text", "flag")[0] == "b"


def test_promote_unknown_key_raises(chain):
    with pytest.raises(KeyError):
        registry.promote("nope")


def test_set_disabled_skips_in_pick_and_recovers(chain, monkeypatch):
    registry.set_disabled("a", True)
    assert registry.pick("text", "flag")[0] == "b", "禁用后自动路由跳过 a"
    registry.set_disabled("a", False)
    assert registry.pick("text", "flag")[0] == "a", "恢复后重新参与路由"


def test_disable_all_yields_quota_exhausted(chain):
    for k in ("a", "b", "c"):
        registry.set_disabled(k, True)
    from llm_registry import QuotaExhausted

    with pytest.raises(QuotaExhausted):
        registry.pick("text", "flag")


def test_disable_does_not_affect_pick_by_key(chain):
    """禁用只影响自动路由——judge 等显式指定场景不受限（语义决定，docstring 已注明）。"""
    registry.set_disabled("a", True)
    assert registry.pick_by_key("a") is chain["a"].llm


def test_disable_independent_of_quota_unavailable(chain):
    """配额健康但被管理禁用 → 仍跳过（两语义独立）。"""
    registry.set_disabled("a", True)
    assert not chain["a"].unavailable
    assert registry.pick("text", "flag")[0] == "b"


def test_set_disabled_unknown_key_raises(chain):
    with pytest.raises(KeyError):
        registry.set_disabled("nope", True)


def test_status_exposes_admin_disabled(chain):
    registry.set_disabled("a", True)
    status = {s["key"]: s for s in registry.status()}
    assert status["a"]["admin_disabled"] is True
    assert status["b"]["admin_disabled"] is False


def test_promote_survives_quota_exhausted_head(chain):
    """链首耗尽时 promote 第二名 → pick 仍走可用模型（与 failover 协同）。"""
    registry.set_disabled("a", True)  # 模拟链首耗尽（admin 禁用路径）
    assert registry.pick("text", "flag")[0] == "b"
    registry.promote("c")
    assert registry.pick("text", "flag")[0] == "c"


# ==================== 2026-09-15 代码审查 S1/S2：端点入参必须走 Pydantic ====================


def test_llm_disable_schema_rejects_string_bool_and_requires_disabled():
    """S1：`disabled` 必须是**真布尔**且**必填**。

    修复前端点用 `bool(body.get("disabled", True))` —— Python `bool("false") is True`，
    故字符串 `"false"`/`"0"` 会被判为**启用禁用**（误操作）；且缺省即 True（只传 key 就静默禁用）。
    现用 `StrictBool` + 必填：字符串走 422，缺字段走 422。
    """
    from pydantic import ValidationError

    from schemas import LlmDisableIn, LlmPromoteIn

    assert LlmDisableIn(key="k", disabled=True).disabled is True
    assert LlmDisableIn(key="k", disabled=False).disabled is False
    for bad in ("false", "0", "true", 1, 0):
        with pytest.raises(ValidationError):
            LlmDisableIn(key="k", disabled=bad)
    with pytest.raises(ValidationError):
        LlmDisableIn(key="k")  # 必填：不得有静默默认
    with pytest.raises(ValidationError):
        LlmPromoteIn(key="")
    with pytest.raises(ValidationError):
        LlmPromoteIn(key="x" * 65)  # 长度上限
    assert LlmPromoteIn(key="k").key == "k"


def test_admin_llm_endpoints_use_pydantic_schemas():
    """S2：两个端点的入参必须是 Pydantic schema（裸 `dict` 会绕过校验）——防回退守护。

    修复前签名是 `body: dict` + 手写 `str(body.get(...))`，与同文件 `LlmSwitchIn`/
    `LlmQuotaIn` 的既有惯例相悖（安全轴 + 气味轴双轴命中）。
    """
    import inspect

    import main
    from schemas import LlmDisableIn, LlmPromoteIn

    assert inspect.signature(main.admin_llm_promote).parameters["body"].annotation is LlmPromoteIn
    assert inspect.signature(main.admin_llm_disable).parameters["body"].annotation is LlmDisableIn


def test_admin_llm_endpoints_return_422_for_invalid_bodies():
    """S1/S2 **HTTP 级**验证（把 schema 断言升级为端点实测状态码）。

    动机（show-your-work 审计）：先前只断言了 schema 层 `ValidationError`——
    那是**推断**"框架会映射成 422"，不是实测。本测试直接打端点，锁住真实状态码。

    只打**非法体**：校验发生在进入 handler 之前，不触发 registry/审计副作用。
    合法体（未知 key）应 404（="过了校验才找不到"），**不得** 422（否则说明校验误杀）。
    """
    from fastapi.testclient import TestClient

    import main
    from auth import require_admin

    main.app.dependency_overrides[require_admin] = lambda: SimpleNamespace(id=1)
    try:
        client = TestClient(main.app)
        invalid = [
            ("/api/admin/llm-disable", {"key": "k", "disabled": "false"}),  # 字符串布尔（原误判为 True）
            ("/api/admin/llm-disable", {"key": "k", "disabled": "0"}),
            ("/api/admin/llm-disable", {"key": "k", "disabled": 1}),
            ("/api/admin/llm-disable", {"key": "k"}),  # 缺必填（原默认 True 静默禁用）
            ("/api/admin/llm-disable", {"key": "", "disabled": True}),
            ("/api/admin/llm-promote", {"key": "x" * 65}),
            ("/api/admin/llm-promote", {}),
        ]
        for url, body in invalid:
            resp = client.post(url, json=body)
            assert resp.status_code == 422, f"{url} {body} -> {resp.status_code}（期望 422）"

        unknown = "no_such_model_key_for_validation_probe"
        assert client.post("/api/admin/llm-disable", json={"key": unknown, "disabled": True}).status_code == 404
        assert client.post("/api/admin/llm-promote", json={"key": unknown}).status_code == 404
    finally:
        main.app.dependency_overrides.pop(require_admin, None)
