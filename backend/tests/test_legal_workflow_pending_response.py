"""Exercise the real pending response without importing the live application."""

import ast
import asyncio
import json
import logging
import queue
from contextlib import aclosing
from pathlib import Path
from threading import Event
from types import SimpleNamespace

from anyio import CancelScope
from starlette.concurrency import run_in_threadpool
from starlette.responses import StreamingResponse


def load():
    tree = ast.parse((Path(__file__).parents[1] / "main.py").read_text(encoding="utf-8"))
    names = {"_pending_agent_response", "_ChatStreamingResponse"}
    ns = dict(
        asyncio=asyncio,
        Event=Event,
        CancelScope=CancelScope,
        logging=logging,
        ClosingStream=aclosing,
        run_in_threadpool=run_in_threadpool,
        StreamingResponse=StreamingResponse,
        _record_actual_agent_route=lambda *a, **kw: None,
        encode_sse_stream=lambda events: iter(events),
        serialize_agent_events=lambda result: ["verified answer", "DONE"],
    )
    exec(
        compile(
            ast.Module(body=[n for n in tree.body if getattr(n, "name", None) in names], type_ignores=[]),
            "main.py",
            "exec",
        ),
        ns,
    )
    return ns


def test_status_precedes_work_and_text_waits_for_verified_result():
    async def scenario():
        ns = load()
        started = Event()
        release = Event()

        def execute(cancelled):
            started.set()
            assert release.wait(2)
            return SimpleNamespace(outcome="completed")

        response = ns["_pending_agent_response"](execute=execute, fallback=None)
        body = response.body_iterator
        assert "processing" in await anext(body)
        assert not started.is_set()
        following = asyncio.create_task(anext(body))
        await asyncio.to_thread(started.wait, 1)
        assert not following.done()
        release.set()
        assert await following == "verified answer"
        await body.aclose()
        await response._on_response_close()

    asyncio.run(scenario())


def test_close_before_iteration_does_not_start_work():
    async def scenario():
        ns = load()
        calls = []
        response = ns["_pending_agent_response"](execute=lambda stop: calls.append(1), fallback=None)
        await response._on_response_close()
        assert calls == []

    asyncio.run(scenario())


def test_worker_failure_emits_error_and_cleanup_does_not_raise_again():
    async def scenario():
        ns = load()

        def execute(stop):
            raise RuntimeError("synthetic provider failure")

        response = ns["_pending_agent_response"](execute=execute, fallback=None)
        frames = [frame async for frame in response.body_iterator]
        assert '"type":"error"' in frames[-2]
        assert "[DONE]" in frames[-1]
        await response._on_response_close()

    asyncio.run(scenario())


def test_fallback_stream_and_cleanup_are_preserved():
    async def scenario():
        ns = load()
        closed = []

        async def frames():
            yield "fallback text"

        async def cleanup():
            closed.append(True)

        async def fallback(reason):
            assert reason == "TOOL_UNAVAILABLE"
            return SimpleNamespace(body_iterator=frames(), _on_response_close=cleanup)

        response = ns["_pending_agent_response"](
            execute=lambda stop: SimpleNamespace(outcome="fallback", reason_code="TOOL_UNAVAILABLE"), fallback=fallback
        )
        frames_seen = [frame async for frame in response.body_iterator]
        assert "processing" in frames_seen[0]
        assert frames_seen[1:] == ["fallback text"]
        await response._on_response_close()
        assert closed == [True]

    asyncio.run(scenario())


def test_disconnect_signals_and_joins_running_worker():
    async def scenario():
        ns = load()
        started, ended = Event(), Event()

        def execute(stop):
            import time

            started.set()
            while not stop():
                time.sleep(0.001)
            ended.set()
            return SimpleNamespace(outcome="failed")

        response = ns["_pending_agent_response"](execute=execute, fallback=None)
        body = response.body_iterator
        await anext(body)
        waiting = asyncio.create_task(anext(body))
        assert await asyncio.to_thread(started.wait, 1)
        waiting.cancel()
        try:
            await waiting
        except asyncio.CancelledError:
            pass
        await response._on_response_close()
        assert ended.is_set()

    asyncio.run(scenario())


def test_step_queue_emits_real_steps_before_final():
    async def scenario():
        ns = load()
        ns["json"] = json
        step_queue = queue.Queue()

        def execute(stop, on_step):
            on_step({"label": "拆解争点", "detail": "识别 2 个争点"})
            on_step({"label": "检索法条", "detail": "绑定 3 条依据"})
            on_step({"label": "校验", "detail": "通过"})
            return SimpleNamespace(outcome="completed")

        response = ns["_pending_agent_response"](execute=execute, fallback=None, step_queue=step_queue)
        frames = [frame async for frame in response.body_iterator]
        assert "processing" in frames[0]
        step_frames = [json.loads(frame[6:]) for frame in frames if frame.startswith("data: ")]
        assert [item["type"] for item in step_frames[:4]] == ["agent_status", "step", "step", "step"]
        assert [item["steps"][0]["label"] for item in step_frames[1:4]] == ["拆解争点", "检索法条", "校验"]
        assert frames[-2:] == ["verified answer", "DONE"]
        await response._on_response_close()

    asyncio.run(scenario())


def test_heartbeat_keeps_pending_worker_alive_without_revealing_text():
    async def scenario():
        ns = load()
        started, release = Event(), Event()
        timeouts = []

        async def wait(tasks, *, timeout):
            timeouts.append(timeout)
            if len(timeouts) == 1:
                return set(), tasks
            return await asyncio.wait(tasks, timeout=2)

        ns["asyncio"] = SimpleNamespace(create_task=asyncio.create_task, wait=wait, shield=asyncio.shield)

        def execute(stop):
            started.set()
            assert release.wait(2)
            assert not stop()
            return SimpleNamespace(outcome="completed")

        response = ns["_pending_agent_response"](execute=execute, fallback=None)
        body = response.body_iterator
        assert "processing" in await anext(body)
        assert await anext(body) == ": heartbeat\n\n"
        assert await asyncio.to_thread(started.wait, 1)
        release.set()
        assert [frame async for frame in body] == ["verified answer", "DONE"]
        await response._on_response_close()
        assert timeouts == [15, 15]

    asyncio.run(scenario())
