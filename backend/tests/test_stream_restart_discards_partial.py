"""R15：模型失败后的"零重答"必须**立刻作废半截**，而不是等下一段非空正文才作废。

改前形状（对 `ee5bfef` 静态核对，两分支同形）：
失败回调只置 `_restart_pending` / `_rstart` 标志，真正的 `chunks = []` 写在
`async for piece in pieces:` 的**循环体**里 —— 若后续尝试全部「空内容、无异常」，
这个循环体一次都不执行，`join(chunks)` 仍得首模型的半截 ⇒ 被当成正常答案
（合同分支还会 `_contract_reviewed_convs.add` 并可能写缓存）。

端点级而非单元级：`chunks` 的消费点在 `stream()` 的调用点，直调 `stream_with_retry`
看不到"半截是否被当成本次答案"。

诚实边界：半截正文在失败前**已经作为 content 帧发出去了**，帧不可收回 ⇒ 判据只能落在
"服务端把它当没答上来"（error 帧 + 不进 reviewed），不能断言帧里没有那半截。
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

import main  # noqa: E402
from tests._sse_harness import CONTRACT_PARTS, chat_frames, login, sse_client  # noqa: E402

CONTRACT_QUESTION = "帮我审一下这份租赁合同"
HALF = "半截错答"


class _HalfThenEmpty:
    """首轮吐半截后抛错（触发换模型/零重答），之后每次尝试都空内容、无异常。"""

    def __init__(self) -> None:
        self.n = 0

    async def astream(self, messages):  # noqa: ARG002
        self.n += 1
        if self.n == 1:
            yield HALF
            raise RuntimeError("模拟模型侧失败：触发零重答")
        if False:
            yield None  # 让它保持异步生成器，且后续尝试一个块都不产


def _objs(frames: list[str]) -> list[dict]:
    out = []
    for f in frames:
        if f.startswith("data: ") and f.strip() != "data: [DONE]":
            obj = json.loads(f[len("data: ") :])
            if isinstance(obj, dict):
                out.append(obj)
    return out


def test_flagship_stream_discards_half_answer_when_retries_are_empty(monkeypatch):
    """旗舰流式分支：后续尝试全空 ⇒ 半截不得被当答案（必须出现 error 帧）。"""
    shared = _HalfThenEmpty()
    with sse_client(monkeypatch, route="flagship_stream", flagship_parts=()) as c:
        monkeypatch.setattr(main, "make_chain", lambda _llm: shared)
        frames = chat_frames(c, login(c), "租赁合同押金不退怎么办")

    assert shared.n >= 2, f"链只被调用 {shared.n} 次 ⇒ 根本没触发重答，本条是空枪"
    assert any("error" in o for o in _objs(frames)), f"后续尝试全空、半截却仍被当成答案（没有 error 帧）：{frames}"


def test_contract_stream_discards_half_answer_when_retries_are_empty(monkeypatch):
    """合同报告分支：同形判据——半截不得进 reviewed、不得被当完整报告。"""
    shared = _HalfThenEmpty()
    with sse_client(monkeypatch, route="contract_review", flagship_parts=CONTRACT_PARTS) as c:
        monkeypatch.setattr(main, "make_chain", lambda _llm: shared)
        frames = chat_frames(c, login(c), CONTRACT_QUESTION)

    assert shared.n >= 2, f"链只被调用 {shared.n} 次 ⇒ 根本没触发重答，本条是空枪"
    assert any("error" in o for o in _objs(frames)), f"后续尝试全空、半截却仍被当成完整报告（没有 error 帧）：{frames}"
    assert main._contract_reviewed_convs == set(), "半截被当成完整报告：会被加进 reviewed，之后的追问会被误判成续聊"
