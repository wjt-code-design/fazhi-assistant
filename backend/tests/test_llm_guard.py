"""并发门控单元测试：llm_guard 并发上限 + 排队 + 超时降级（不联网）。"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

from llm_guard import LLMBusyError, _LLMGuard  # noqa: E402


def test_async_concurrency_capped():
    """limit=2 时 5 个并发 async 请求，任意时刻最多 2 个持位（排队不崩）。"""
    guard = _LLMGuard(limit=2, timeout=30)
    peak = 0
    cur = 0

    async def holder():
        nonlocal peak, cur
        async with guard:
            cur += 1
            peak = max(peak, cur)
            await asyncio.sleep(0.03)
            cur -= 1

    async def main():
        await asyncio.gather(*[holder() for _ in range(5)])

    asyncio.run(main())
    assert peak == 2, f"并发尖峰应=limit(2)，实际 {peak}"


def test_async_timeout_raises_busy():
    """limit=1 + timeout=0.05：第二个请求持位超时 → LLMBusyError（降级信号）。"""
    guard = _LLMGuard(limit=1, timeout=0.05)
    holder_done = asyncio.Event()

    async def holder():
        async with guard:
            holder_done.set()
            await asyncio.sleep(0.2)  # 持位期间第二个请求排队超时

    async def second():
        try:
            async with guard:
                pass
            return False
        except LLMBusyError:
            return True

    async def main():
        t = asyncio.create_task(holder())
        await holder_done.wait()
        busy = await second()
        await t
        return busy

    assert asyncio.run(main()), "排队超时应抛 LLMBusyError"


def test_sync_guard_raises_busy():
    """sync 路径同样：limit=1 + timeout=0.05，持位时第二个同步 acquire 超时。"""
    guard = _LLMGuard(limit=1, timeout=0.05)
    import threading
    import time

    released = threading.Event()

    def holder():
        with guard:
            released.set()
            time.sleep(0.2)

    t = threading.Thread(target=holder)
    t.start()
    released.wait(1)
    busy = False
    try:
        with guard:
            pass
    except LLMBusyError:
        busy = True
    t.join()
    assert busy, "sync 排队超时应抛 LLMBusyError"
