import json
from decimal import Decimal

import httpx
import pytest

from budget_guard import BudgetGuard


def request(model="qwen3.8-flash", host="dashscope.aliyuncs.com"):
    return httpx.Request(
        "POST", f"https://{host}/v1/chat/completions", json={"model": model}
    )


def test_reservation_blocks_before_dispatch_and_restart(tmp_path):
    path = tmp_path / "ledger.jsonl"
    guard = BudgetGuard(path, "3")
    guard.reserve(request())
    with pytest.raises(RuntimeError):
        guard.reserve(request())
    with pytest.raises(FileExistsError):
        BudgetGuard(path)
    assert len(path.read_text().splitlines()) == 1


def test_usage_settlement_and_unknown_retains_reservation(tmp_path):
    guard = BudgetGuard(tmp_path / "ledger.jsonl")
    ticket = guard.reserve(request())
    response = httpx.Response(
        200, json={"usage": {"prompt_tokens": 1000, "completion_tokens": 2000}}
    )
    guard.finish(ticket, response)
    assert str(guard.charged) == "0.0062"
    ticket = guard.reserve(request())
    guard.failed(ticket, TimeoutError("secret-provider-detail"))
    assert str(guard.charged) == "2.0062"
    with pytest.raises(RuntimeError):
        guard.reserve(request())
    assert "secret-provider-detail" not in guard.path.read_text()


def test_unapproved_model_rejected_and_sse_usage_counted(tmp_path):
    guard = BudgetGuard(tmp_path / "ledger.jsonl")
    with pytest.raises(RuntimeError):
        guard.reserve(request("unpriced-model"))
    ticket = guard.reserve(request())
    usage = {"usage": {"prompt_tokens": 1000, "completion_tokens": 1000}}
    response = httpx.Response(
        200,
        content="data: " + json.dumps(usage) + "\n\ndata: [DONE]\n\n",
        headers={"content-type": "text/event-stream"},
    )
    guard.finish(ticket, response)
    assert str(guard.charged) == "0.0035"


def test_installed_guard_runs_before_http_dispatch_and_preserves_stream(
    tmp_path, monkeypatch
):
    guard = BudgetGuard(tmp_path / "ledger.jsonl", "2")
    monkeypatch.setattr(httpx.Client, "send", httpx.Client.send)
    monkeypatch.setattr(httpx.AsyncClient, "send", httpx.AsyncClient.send)
    guard.install()
    calls = []

    def upstream(req):
        assert '"event": "reserved"' in guard.path.read_text()
        calls.append(req)
        return httpx.Response(
            200,
            content='data: {"choices":[]}\n\ndata: [DONE]\n\n',
            headers={"content-type": "text/event-stream"},
        )

    with httpx.Client(transport=httpx.MockTransport(upstream)) as client:
        response = client.send(request(), stream=True)
        assert list(response.iter_lines()) == [
            'data: {"choices":[]}',
            "",
            "data: [DONE]",
            "",
        ]
        with pytest.raises(RuntimeError):
            client.send(request())
    assert (
        len(calls) == 1
    )  # Missing usage retains full reservation and blocks the next network call.


# ==================== 2026-09-15 扩展（用户授权：不设金额上限 + 配额耗尽换模型） ====================


def test_unlimited_budget_accumulates_beyond_default_without_rejection(tmp_path):
    """limit="none" → 无金额上限：累计超原 20 元仍可继续预约（账本仍完整记录）。"""
    guard = BudgetGuard(tmp_path / "ledger.jsonl", "none")
    assert guard.unlimited is True and guard.limit is None
    for _ in range(3):  # 3 × 26.16 = 78.48 > 20
        guard.reserve(request("qwen3.7-max-2026-06-08"))
    assert str(guard.charged) == "78.48"
    assert guard.calls == 3 and not guard.halted


def test_numeric_limit_still_enforced_and_zero_is_zero_not_unlimited(tmp_path):
    """数字口径向后兼容；且 0 不等于"无上限"（不猜隐式语义）。"""
    guard = BudgetGuard(tmp_path / "ledger.jsonl", "20")
    with pytest.raises(RuntimeError):
        guard.reserve(request("qwen3.7-max-2026-06-08"))  # 26.16 > 20
    zero = BudgetGuard(tmp_path / "zero.jsonl", "0")
    assert zero.unlimited is False and zero.limit == 0
    with pytest.raises(RuntimeError):
        zero.reserve(request())


def test_qwen37_series_approved_with_conservative_reserve_and_settlement(tmp_path):
    """qwen3.7 系列在白名单内；预约按保守上界 26.16，结算按官方原价 12/36（不采折扣）。"""
    guard = BudgetGuard(tmp_path / "ledger.jsonl", "none")
    ticket = guard.reserve(request("qwen3.7-max-2026-06-08"))
    assert ticket[2] == Decimal("26.16")
    response = httpx.Response(
        200, json={"usage": {"prompt_tokens": 1000, "completion_tokens": 2000}}
    )
    guard.finish(ticket, response)
    # 1000×12/1M + 2000×36/1M = 0.012 + 0.072
    assert str(guard.charged) == "0.084"
    # 其余快照/plus 同样在册（配额耗尽可切换到链内任一模型）
    for m in (
        "qwen3.7-max",
        "qwen3.7-max-2026-05-20",
        "qwen3.7-max-preview",
        "qwen3.7-max-2026-05-17",
        "qwen3.7-plus-2026-05-26",
    ):
        assert guard.reserve(request(m))[2] == Decimal("26.16")


def test_quota_exhausted_does_not_halt_but_other_errors_do(tmp_path):
    """429/402（配额类）不 halt → 允许换下一个模型继续；500 仍 halt（保守纪律）。"""
    guard = BudgetGuard(tmp_path / "ledger.jsonl", "none")
    t = guard.reserve(request("qwen3.7-max-2026-06-08"))
    guard.finish(t, httpx.Response(429, json={"error": "quota exhausted"}))
    assert guard.halted is False, "配额耗尽不得 halt（否则阻断换模型）"
    t = guard.reserve(request("qwen3.7-max"))  # 换下一个模型仍可发
    guard.finish(t, httpx.Response(500, json={"error": "boom"}))
    assert guard.halted is True, "非配额类非 2xx 仍 halt"
    with pytest.raises(RuntimeError):
        guard.reserve(request("qwen3.7-max-2026-05-20"))
    text = guard.path.read_text(encoding="utf-8")
    assert "quota_exhausted" in text


def test_transport_failure_blocks_same_model_but_allows_switch(tmp_path):
    """传输失败后：同模型不补发（原纪律）；**换模型放行**（用户 2026-09-15 指令）。

    背景：原实现 failed() → halt=True → 换模型的新请求也被拒，阻断 failover
    （实测 C01：APIConnectionError 后 6 次 failover_switch 全被 guard 拦死）。
    """
    guard = BudgetGuard(tmp_path / "ledger.jsonl", "none")
    t = guard.reserve(request("qwen3.7-max-2026-06-08"))
    guard.failed(t, httpx.ConnectError("connection refused"))
    assert guard.halted is False, "传输失败不得 halt（否则阻断换模型）"
    assert str(guard.charged) == "26.16", "完整预约保留（不退还）"
    # 同模型不补发
    with pytest.raises(RuntimeError):
        guard.reserve(request("qwen3.7-max-2026-06-08"))
    # 换模型放行（failover 路径）
    t2 = guard.reserve(request("qwen3.7-max"))
    assert t2[1] == "qwen3.7-max"
    assert guard.failed_models == {"qwen3.7-max-2026-06-08"}
    text = guard.path.read_text(encoding="utf-8")
    assert "unknown_server_state" in text and '"halt": false' in text
