"""可观测：request_id（contextvar + 响应头）+ 结构化 JSON 日志 + 问答调用记账。

注意：中间件用纯 ASGI 实现（只包装 send，不缓冲 body），以免破坏 SSE 流式响应
（BaseHTTPMiddleware 会缓冲 StreamingResponse，导致流式失效/内存暴涨）。
"""

import contextvars
import json
import logging
import time
import uuid

request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")

# token_est/tier/cache/escalated/verdict：log_account 实际传入的记账字段——此前遗漏被
# JSON formatter 静默丢弃（每问成本算不出、eval_latency_log 的 rule 剔除恒为 0），
# 2026-08-03 交付级验收修复。追加尾部，不动既有字段顺序。
_ACCOUNT_FIELDS = (
    "method", "path", "status", "ms", "first_ms", "model", "ok", "conv_id", "user_id", "q_len",
    "token_est", "tier", "cache", "escalated", "verdict", "kind", "detail",
)


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        rec = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(record.created)),
            "level": record.levelname,
            "logger": record.name,
            "req": getattr(record, "request_id", "-"),
            "msg": record.getMessage(),
        }
        for k in _ACCOUNT_FIELDS:
            v = getattr(record, k, None)
            if v is not None:
                rec[k] = v
        if record.exc_info and record.exc_info[1] is not None:
            rec["exc"] = self.formatException(record.exc_info)
        return json.dumps(rec, ensure_ascii=False)


def setup_logging(level: str) -> None:
    """配置应用结构化日志；用我们的结构化访问日志替代 uvicorn 的明文 access 日志。"""
    handler = logging.StreamHandler()
    handler.setFormatter(_JsonFormatter())
    for name in ("legal", "legal.access", "legal.chat"):
        lg = logging.getLogger(name)
        lg.handlers = [handler]
        lg.propagate = False
        lg.setLevel(level or "INFO")
    # 关闭 uvicorn 自带的明文 access 日志，避免与结构化访问日志重复
    logging.getLogger("uvicorn.access").disabled = True


class RequestIdMiddleware:
    """纯 ASGI 中间件：注入 request_id、记录结构化访问日志、回写响应头。不缓冲流式 body。"""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        rid = None
        for k, v in scope.get("headers", []):
            if k.lower() == b"x-request-id":
                rid = v.decode("latin-1")
                break
        if not rid:
            rid = uuid.uuid4().hex[:12]

        token = request_id_var.set(rid)
        t0 = time.perf_counter()
        status = {"code": 0}

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                status["code"] = message.get("status", 0)
                headers = list(message.get("headers", []))
                headers.append((b"x-request-id", rid.encode("latin-1")))
                message = {**message, "headers": headers}
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            ms = round((time.perf_counter() - t0) * 1000, 1)
            logging.getLogger("legal.access").info(
                "req",
                extra={
                    "request_id": rid,
                    "method": scope.get("method", ""),
                    "path": scope.get("path", ""),
                    "status": status["code"],
                    "ms": ms,
                },
            )
            request_id_var.reset(token)


def log_account(**kw) -> None:
    """记录一次问答的调用记账（模型/耗时/成功/会话/用户/问句长度）。"""
    extra = {"request_id": request_id_var.get()}
    extra.update(kw)
    logging.getLogger("legal.chat").info("chat", extra=extra)
