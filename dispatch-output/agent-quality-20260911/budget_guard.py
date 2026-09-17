"""Evaluation-only HTTP guard; count every SDK attempt before sending it."""

import json
import os
import threading
import time
from decimal import Decimal
from pathlib import Path

import httpx

# 模型定价表（2026-09-15 扩展；**未列入者一律拒绝**——"禁止切到未定价模型"纪律）。
#   reserve：单次预约（保守上界，不采折扣价；输入按官方最大上下文、输出按官方最大输出+思考）
#   in/out：结算价（元/百万 tokens，官方原价，不扣缓存优惠）
# qwen3.7 系列统一按 max 价预约/结算（plus 未单独取价 → 按 max 的**保守高值**，不低估）。
_QWEN37_RESERVE = Decimal("26.16")  # 1M×12 + 393216×36/1M = 12 + 14.155776
PRICING: dict[str, dict[str, Decimal]] = {
    "qwen3.8-flash": {
        "reserve": Decimal(2),
        "in": Decimal("0.8"),
        "out": Decimal("2.7"),
    },
    "qwen3.7-max-2026-06-08": {
        "reserve": _QWEN37_RESERVE,
        "in": Decimal(12),
        "out": Decimal(36),
    },
    "qwen3.7-max": {"reserve": _QWEN37_RESERVE, "in": Decimal(12), "out": Decimal(36)},
    "qwen3.7-max-2026-05-20": {
        "reserve": _QWEN37_RESERVE,
        "in": Decimal(12),
        "out": Decimal(36),
    },
    "qwen3.7-max-preview": {
        "reserve": _QWEN37_RESERVE,
        "in": Decimal(12),
        "out": Decimal(36),
    },
    "qwen3.7-max-2026-05-17": {
        "reserve": _QWEN37_RESERVE,
        "in": Decimal(12),
        "out": Decimal(36),
    },
    "qwen3.7-plus-2026-05-26": {
        "reserve": _QWEN37_RESERVE,
        "in": Decimal(12),
        "out": Decimal(36),
    },
    # 官方免费模型；付费 Pro 变体不接受
    "BAAI/bge-reranker-v2-m3": {
        "reserve": Decimal(0),
        "in": Decimal(0),
        "out": Decimal(0),
    },
}
# 配额类状态：**不 halt**（用户 2026-09-15 要求"配额耗尽自动切换其他模型"—换模型需要后续请求
# 能发出去；原实现遇任何非 2xx 即 halt，会阻断 failover）。其余非 2xx 仍 halt。
QUOTA_STATUS = {402, 429}


class BudgetGuard:
    def __init__(self, path, limit="20"):
        self.path = Path(path)
        self.path.touch(exist_ok=False)  # Never silently restart a spent budget.
        # 显式无金额上限（2026-09-15 用户授权）：只认字面 "none"（大小写不敏感）。
        # 不采 0/负数/None 的隐式语义（0 应为"零预算"，负数非法，None 语义不明）。
        raw_limit = str(limit).strip().lower()
        self.unlimited = raw_limit == "none"
        self.limit = None if self.unlimited else Decimal(raw_limit)
        self.charged = Decimal(0)
        self.calls = 0
        self.halted = False
        # 2026-09-15（用户指令"配额耗尽/调用失败自动切换下一个模型"）：
        # 传输类失败**不 halt**（halt 会使换模型后的新请求也发不出去 → 阻断 failover），
        # 改为**按模型**记录失败：同一模型不得补发（保留原纪律"未知服务端状态不重跑同一模型"），
        # 换到**其他模型**放行（用户要求）。完整预约仍保留（不退还）。
        self.failed_models: set[str] = set()
        self.lock = threading.Lock()

    def log(self, **event):
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(
                json.dumps({"time": time.time(), **event}, ensure_ascii=False) + "\n"
            )
            fh.flush()
            os.fsync(fh.fileno())

    def reserve(self, request):
        body = json.loads(request.content)
        model = body.get("model")
        if request.url.scheme != "https":
            raise RuntimeError("Evaluation requires HTTPS")
        if request.url.host == "dashscope.aliyuncs.com":
            entry = PRICING.get(model)
            amount = None if entry is None else entry["reserve"]
        elif (
            request.url.host == "api.siliconflow.cn"
            and model == "BAAI/bge-reranker-v2-m3"
        ):
            amount = Decimal(
                0
            )  # Published free model; paid Pro variant is NOT accepted.
        else:
            raise RuntimeError("Unapproved evaluation endpoint or model")
        if amount is None:
            # 未定价模型一律拒绝（"禁止切到未定价模型"）；须先补 PRICING 条目。
            raise RuntimeError("Unapproved evaluation endpoint or model")
        with self.lock:
            over_budget = (not self.unlimited) and (self.charged + amount > self.limit)
            if self.halted or self.calls >= 60 or over_budget:
                raise RuntimeError("Evaluation budget or attempt limit reached")
            if model in self.failed_models:
                # 同一模型失败后不得补发（原纪律）；换其他模型放行（用户 2026-09-15 指令）。
                raise RuntimeError(
                    f"Model previously failed; not re-dispatching: {model}"
                )
            self.calls += 1
            self.charged += amount
            ticket = (self.calls, model, amount)
            self.log(
                event="reserved",
                call=self.calls,
                model=model,
                reserve_cny=str(amount),
                accounted_upper_cny=str(self.charged),
                unlimited=self.unlimited,
            )
            return ticket

    def finish(self, ticket, response):
        call, model, reserved = ticket
        usage = None
        payloads = []
        if "text/event-stream" in response.headers.get("content-type", ""):
            for line in response.text.splitlines():
                if line.startswith("data: ") and line[6:] != "[DONE]":
                    try:
                        payloads.append(json.loads(line[6:]))
                    except ValueError:
                        pass
        else:
            try:
                payloads.append(response.json())
            except ValueError:
                pass
        for item in payloads:
            if isinstance(item, dict) and isinstance(item.get("usage"), dict):
                usage = item["usage"]
        charged = reserved
        entry = PRICING.get(model) or {}
        if response.is_success and usage and entry:
            inp, out = usage.get("prompt_tokens"), usage.get("completion_tokens")
            if type(inp) is int and type(out) is int and inp >= 0 and out >= 0:
                # completion_tokens includes reasoning tokens; do not subtract cached input.
                charged = (
                    Decimal(inp) * entry["in"] + Decimal(out) * entry["out"]
                ) / 1_000_000
        with self.lock:
            if charged > reserved:
                self.halted = True
            self.charged += charged - reserved
            quota_exhausted = (
                not response.is_success
            ) and response.status_code in QUOTA_STATUS
            if not response.is_success and not quota_exhausted:
                self.halted = True
            self.log(
                event="finished",
                call=call,
                status=response.status_code,
                usage=usage,
                accounted_cny=str(charged),
                accounted_upper_cny=str(self.charged),
                quota_exhausted=quota_exhausted,
                halt=self.halted,
            )

    def failed(self, ticket, exc):
        with self.lock:
            # 保留完整预约（不退还）；**不 halt**——换模型必须能发出新请求（用户 2026-09-15 指令）。
            # 纪律保留方式：把该模型加入 failed_models，同一模型后续 reserve 被拒（不补发）。
            self.failed_models.add(ticket[1])
            self.log(
                event="unknown_server_state",
                call=ticket[0],
                model=ticket[1],
                error_class=type(exc).__name__,
                accounted_upper_cny=str(self.charged),
                halt=False,
            )

    def install(self):
        sync_send, async_send = httpx.Client.send, httpx.AsyncClient.send

        def guarded_send(client, request, **kwargs):
            request.read()
            ticket = self.reserve(request)
            try:
                response = sync_send(client, request, **kwargs)
                response.read()
                self.finish(ticket, response)
                return response
            except Exception as exc:
                self.failed(ticket, exc)
                raise

        async def guarded_asend(client, request, **kwargs):
            await request.aread()
            ticket = self.reserve(request)
            try:
                response = await async_send(client, request, **kwargs)
                await response.aread()
                self.finish(ticket, response)
                return response
            except Exception as exc:
                self.failed(ticket, exc)
                raise

        httpx.Client.send, httpx.AsyncClient.send = guarded_send, guarded_asend
