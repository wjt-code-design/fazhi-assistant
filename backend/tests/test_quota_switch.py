"""块 2.2：配额耗尽自动换模型测试（用户核心要求：真实 API 错误即时切换，不靠估算）。"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))


import llm_registry as R
from rag_chain import _is_quota_error, stream_with_retry


class QuotaChain:
    """首个调用抛配额错误（模拟真实 API 配额耗尽）。astream 须为 async generator（含 yield）。"""
    async def astream(self, messages):
        if False:
            yield None
        raise RuntimeError("InsufficientBalance: 余额不足")


class OkChain:
    def __init__(self, pieces=("答", "案")):
        self._pieces = pieces

    async def astream(self, messages):
        for p in self._pieces:
            yield p


def test_is_quota_error_detects():
    assert _is_quota_error(RuntimeError("InsufficientBalance")) is True
    assert _is_quota_error(RuntimeError("quota exceeded")) is True
    assert _is_quota_error(RuntimeError("429 Too Many Requests")) is True
    assert _is_quota_error(RuntimeError("Connection reset")) is False


def test_stream_switches_model_on_quota_error():
    """首个模型配额错误 → mark_depleted → 重试落到第二个模型 → 返回其答案。"""
    calls = []

    def make_chain_fn(i, disabled):
        calls.append(i)
        return QuotaChain() if i == 0 else OkChain()

    def on_quota(e):
        calls.append("depleted")

    async def run():
        out = []
        async for piece in stream_with_retry(
            make_chain_fn, [], [(False, 0.0), (False, 0.0)],
            on_quota_exhausted=on_quota,
        ):
            out.append(piece)
        return "".join(out)

    result = asyncio.run(run())
    assert result == "答案"
    assert calls[0] == 0 and calls[1] == "depleted" and calls[2] == 1  # 首模型错误 → 标记 → 换模型


def test_stream_non_quota_error_propagates():
    """非配额型错误（如连接重置）→ 原样上抛，不切换模型。"""

    class BrokenChain:
        async def astream(self, messages):
            if False:
                yield None
            raise RuntimeError("Connection reset by peer")

    def make_chain_fn(i, disabled):
        return BrokenChain()

    def on_quota(e):
        raise AssertionError("不应触发换模型")

    async def run():
        async for _ in stream_with_retry(
            make_chain_fn, [], [(False, 0.0)],
            on_quota_exhausted=on_quota,
        ):
            pass

    try:
        asyncio.run(run())
        assert False, "应上抛"
    except RuntimeError as e:
        assert "Connection reset" in str(e)


def test_mark_depleted_makes_model_unavailable():
    """mark_depleted 后该模型 remaining=0 → 立即 unavailable（下一请求自动落后备）。"""
    reg = R.LLMRegistry()  # 独立实例，不污染全局 registry
    key = "text_ds_flash"
    e = reg._entries[key]
    assert not e.unavailable
    reg.mark_depleted(key, "quota_error")
    assert e.depleted is True and e.unavailable is True
    # 配额耗尽后 pick 应跳过该模型（落到下一个）
    picked, _ = reg.pick("text", "flag")
    assert picked != key
