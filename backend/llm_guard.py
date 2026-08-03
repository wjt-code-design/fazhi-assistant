"""全局 LLM 并发门控：限制同一时刻的 LLM 调用数，突增时可预测降级而非无界打向供应商。

背景（突增应对，ADR-007 补充）：每请求开一条 SSE 流直连供应商 LLM，原先无全局上限——
突增时并发调用无界 → 撞供应商 QPS/配额上限 → 全体变慢或报错。本模块给 LLM 调用加
全局信号量（默认 4，env `LLM_MAX_CONCURRENCY` 可调），超限排队最多
`LLM_QUEUE_TIMEOUT` 秒，仍无位则抛 `LLMBusyError`（调用方降级为"服务繁忙"提示）。

async 流式（stream_with_retry）与同步兜底（线程池内 invoke）**共用同一计数**：
threading.BoundedSemaphore 为唯一计数源，async 侧经 asyncio.to_thread 桥接，
避免"两套池子两套数"导致并发上限形同虚设。

注意：缓存命中 / clarify / refuse 分支零 LLM，不经过本门控（本来就是瞬时返回）。
评测脚本（scripts/*）直调 registry，不经门控——评测是离线脚本，不受生产并发约束。
"""

import asyncio
import os
import threading

_LIMIT = int(os.getenv("LLM_MAX_CONCURRENCY", "4"))
_QUEUE_TIMEOUT = float(os.getenv("LLM_QUEUE_TIMEOUT", "30"))


class LLMBusyError(Exception):
    """LLM 并发位满且排队超时——调用方降级为「服务繁忙，请稍后重试」。"""


class _LLMGuard:
    def __init__(self, limit: int, timeout: float) -> None:
        self._sem = threading.BoundedSemaphore(limit)
        self._timeout = timeout

    # ---- async 流式路径（stream_with_retry）----
    async def __aenter__(self):
        got = await asyncio.to_thread(self._sem.acquire, True, self._timeout)
        if not got:
            raise LLMBusyError("LLM 并发位满且排队超时")
        return self

    async def __aexit__(self, *exc):
        self._sem.release()

    # ---- 同步兜底路径（_invoke_llm / _light_buffered / _pre 内 LLM 调用）----
    def __enter__(self):
        if not self._sem.acquire(timeout=self._timeout):
            raise LLMBusyError("LLM 并发位满且排队超时")
        return self

    def __exit__(self, *exc):
        self._sem.release()


llm_guard = _LLMGuard(_LIMIT, _QUEUE_TIMEOUT)
