"""Two historical cancellation windows, driven through real product code.

D1: cancelling a task while `_LLMGuard.__aenter__` waits for a concurrency slot
    (real `_LLMGuard`, imported directly — the module imports cleanly).
D2: disconnect after the user message is committed but before the first body
    iteration/send, and disconnect while the pre-body work is still in flight
    (real chat `stream` + real `_ChatStreamingResponse` + ASGI receive/send +
    isolated SQLite via the real `_post_placeholder`).

Run with --noconftest (checks.py BOUNDARIES mode).
"""

import ast
import asyncio
import json
import sqlite3
import sys
import threading
import time
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import anyio
import pytest
from langchain_core.messages import AIMessageChunk
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnableSerializable
from pydantic import Field
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.responses import StreamingResponse

BACKEND = Path(__file__).resolve().parents[1]
# D-23（2026-10-11）：占位文案按成因分两条，逐字硬编码在这里（不从 main import）——
# 期望值必须独立于实现，否则把"已停止"和"无响应"改回同一句时测试会跟着一起绿。
PLACEHOLDER = "服务暂时无响应，请稍后重试。"
PLACEHOLDER_STOPPED = "本次回答已停止，未生成完整内容。"

sys.path.insert(0, str(BACKEND))
from llm_guard import LLMBusyError, _LLMGuard  # noqa: E402  (stdlib-only module)

# ═══════════════════════════ D1:并发名额等待期间取消 ═══════════════════════════


def _tracking_semaphore(guard, acquire_started, late_granted):
    """Record when the async-path acquire starts blocking and when it is granted late."""
    sem = guard._sem
    original = sem.acquire

    def tracking_acquire(*args, **kwargs):
        acquire_started.set()
        got = original(*args, **kwargs)
        if got:
            late_granted.set()
        return got

    sem.acquire = tracking_acquire  # instance attribute; BoundedSemaphore is a plain Python object
    return sem


def _cancel_within(task, seconds=3.0):
    task.cancel()
    deadline = time.monotonic() + seconds
    while task.cancelled() is False and time.monotonic() < deadline:
        if task.done():
            break
        time.sleep(0.01)
    return task.done()


def test_d1_cancel_while_waiting_returns_all_capacity():
    """占满并发位 → 异步等待 → 等待期取消 → 释放原持有者 → 等待终态 → 全部容量可再获取。"""
    guard = _LLMGuard(limit=1, timeout=5.0)
    acquire_started, late_granted = threading.Event(), threading.Event()
    _tracking_semaphore(guard, acquire_started, late_granted)
    holder_entered, release_holder = threading.Event(), threading.Event()

    def holder():
        with guard:
            holder_entered.set()
            assert release_holder.wait(timeout=10)

    holder_thread = threading.Thread(target=holder)
    holder_thread.start()
    assert holder_entered.wait(5), "holder never took the only slot"

    async def scenario():
        cancelled = asyncio.Event()

        async def waiter():
            try:
                async with guard:
                    raise AssertionError("cancelled waiter must never hold the slot")
            except asyncio.CancelledError:
                cancelled.set()
                raise

        task = asyncio.create_task(waiter())
        await asyncio.to_thread(acquire_started.wait, 5)
        await asyncio.sleep(0.05)  # the acquire call is provably still blocked (slot held)
        started = time.monotonic()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert time.monotonic() - started <= 3.0, "cancel did not propagate within 3s"
        assert cancelled.is_set()
        # 释放原持有者；等待 acquire 线程到达终态（迟到授予）或证明不再有未决授予
        release_holder.set()
        await asyncio.to_thread(holder_thread.join, 5)
        await asyncio.to_thread(late_granted.wait, 1.0)  # fixed code: never fires; bug: fires with a leaked slot
        # 迟到名额必须归还：全部容量在 queue timeout + 3s 内可再次获取
        deadline = 5.0 + 3.0
        loop = asyncio.get_running_loop()
        got = await loop.run_in_executor(None, lambda: guard._sem.acquire(timeout=deadline))
        assert got, "late slot was never returned: cancelled wait leaked the concurrency slot"
        guard._sem.release()

    asyncio.run(scenario())


def test_d1_normal_wait_grants_after_release():
    guard = _LLMGuard(limit=1, timeout=5.0)
    holder_entered, release_holder = threading.Event(), threading.Event()
    acquired = asyncio.Event()

    def holder():
        with guard:
            holder_entered.set()
            assert release_holder.wait(timeout=10)

    threading.Thread(target=holder, daemon=True).start()
    assert holder_entered.wait(5)

    async def waiter():
        async with guard:
            acquired.set()

    async def scenario():
        task = asyncio.create_task(waiter())
        release_holder.set()
        await asyncio.wait_for(task, 5)
        assert acquired.is_set()
        # capacity restored after the waiter's normal release
        assert guard._sem.acquire(blocking=False)
        guard._sem.release()

    asyncio.run(scenario())


def test_d1_queue_timeout_raises_busy_and_keeps_capacity():
    guard = _LLMGuard(limit=1, timeout=0.3)
    holder_entered, release_holder = threading.Event(), threading.Event()

    def holder():
        with guard:
            holder_entered.set()
            assert release_holder.wait(timeout=10)

    threading.Thread(target=holder, daemon=True).start()
    assert holder_entered.wait(5)

    async def scenario():
        started = time.monotonic()
        with pytest.raises(LLMBusyError):
            async with guard:
                raise AssertionError("must not be granted")
        assert time.monotonic() - started <= 0.3 + 3.0
        release_holder.set()
        await asyncio.sleep(0.05)
        assert guard._sem.acquire(blocking=False), "capacity lost after busy timeout"
        guard._sem.release()

    asyncio.run(scenario())


def test_d1_sync_and_async_share_one_count():
    guard = _LLMGuard(limit=2, timeout=5.0)
    sync_entered, release_sync = threading.Event(), threading.Event()

    def sync_holder():
        with guard:
            sync_entered.set()
            assert release_sync.wait(timeout=10)

    threading.Thread(target=sync_holder, daemon=True).start()
    assert sync_entered.wait(5)

    async def scenario():
        async with guard:  # async takes the second slot
            assert not guard._sem.acquire(blocking=False), "over-capacity grant"
        assert guard._sem.acquire(blocking=False), "async release did not return the slot"
        guard._sem.release()
        release_sync.set()

    asyncio.run(scenario())


def _assert_full_capacity(guard, limit):
    """Hold every configured slot at once, then prove no extra slot exists.

    The check it replaces acquired and immediately released one slot at a time, which only
    ever proved "at least one is free": a lost slot stayed invisible as long as one remained.
    """
    held = 0
    try:
        for _ in range(limit):
            assert guard._sem.acquire(blocking=False), "capacity lost after grant/cancel storm"
            held += 1
        extra = guard._sem.acquire(blocking=False)
        held += int(extra)
        assert not extra, "capacity exceeds configured limit"
    finally:
        for _ in range(held):
            guard._sem.release()


def test_capacity_assertion_rejects_one_lost_slot():
    """Negative control for the assertion itself: a lost slot must not read as healthy."""
    guard = _LLMGuard(limit=2, timeout=1.0)
    assert guard._sem.acquire(blocking=False)  # harmless stand-in for one unreturned slot
    try:
        old_check = []
        for _ in range(2):
            old_check.append(guard._sem.acquire(blocking=False))
            guard._sem.release()
        assert all(old_check), "the replaced per-slot check no longer demonstrates the blind spot"
        with pytest.raises(AssertionError, match="capacity lost"):
            _assert_full_capacity(guard, 2)
    finally:
        guard._sem.release()
    _assert_full_capacity(guard, 2)


def test_d1_grant_and_cancel_same_window_never_overruns_or_double_releases():
    limit, rounds = 2, 24
    guard = _LLMGuard(limit=limit, timeout=1.0)

    async def worker(index: int):
        try:
            async with guard:
                await asyncio.sleep(0.005 * (index % 3))
        except asyncio.CancelledError:
            raise

    async def scenario():
        tasks = []
        for index in range(rounds):
            task = asyncio.create_task(worker(index))
            tasks.append(task)
            if index % 3 == 2:
                tasks[index - 1].cancel()  # cancel a peer while grants are in flight
            await asyncio.sleep(0.002)
        results = await asyncio.gather(*tasks, return_exceptions=True)
        unexpected = [
            r for r in results if isinstance(r, Exception) and not isinstance(r, (asyncio.CancelledError, LLMBusyError))
        ]
        assert not unexpected, unexpected
        # no over-release (BoundedSemaphore raises ValueError) and full capacity back
        _assert_full_capacity(guard, limit)

    asyncio.run(scenario())


# ═══════════════════════ D2:落库后、正文开始前取消 ═══════════════════════


def _extract(path, names, namespace):
    tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
    nodes = [node for node in tree.body if getattr(node, "name", None) in names]
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), "exec"), namespace)
    return namespace


class _Response:
    """Provider response shape: async context manager + async iterator of str pieces."""

    def __init__(self, pieces=("first", "second")):
        self.pieces = list(pieces)
        self.closed = False
        self.reads = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        self.closed = True
        return False

    def __aiter__(self):
        return self._iter()

    async def _iter(self):
        for piece in self.pieces:
            self.reads += 1
            yield piece


class _Client:
    def __init__(self, response, gate=None):
        self.response = response
        self.gate = gate  # optional Event; create() blocks on it (pre-body wait)
        self.wait_entered = threading.Event()  # set when the gated wait starts blocking
        self.gate_done = threading.Event()
        self.calls = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        if self.gate is not None:

            def gated_wait():
                # set inside the worker thread: the events observe the thread's own
                # progress even if the awaiting coroutine is cancelled meanwhile
                self.wait_entered.set()
                self.gate.wait(10)
                self.gate_done.set()

            await asyncio.to_thread(gated_wait)
        return self.response


class _LLM(RunnableSerializable):
    """Public model seam only; mirrors the proven shape used by test_stream_cancellation."""

    async_client: Any = Field(exclude=True)
    client: Any = Field(exclude=True)
    callbacks: Any = Field(default=None, exclude=True)
    tags: Any = Field(default=None, exclude=True)
    metadata: Any = Field(default=None, exclude=True)
    streams: list = Field(default_factory=list, exclude=True)

    def __init__(self, response, gate=None):
        super().__init__(async_client=_Client(response, gate), client=object(), callbacks=[], tags=[], metadata={})

    def invoke(self, input, config=None, **kwargs):
        raise AssertionError("This suite must never invoke a non-streaming model")

    def astream(self, input, config=None, **kwargs):
        async def provider():
            response = await self.async_client.create(messages=input, stream=True, **kwargs)
            async with response:
                async for piece in response:
                    yield AIMessageChunk(content=piece)

        stream = provider()
        self.streams.append(stream)
        return stream


def _isolated_db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    from models import Base

    Base.metadata.create_all(engine)
    sm = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    return sm, engine


def _commit_user_message(sm, content="窗口复现：劳动法第四十四条。"):
    """Commit one user message exactly the way the committed bootstrap does."""
    from models import Conversation, Message, User

    db = sm()
    try:
        user = User(id=1, username="window-user", password_hash="x", created_at=datetime.utcnow())
        db.add(user)
        conv = Conversation(id=1, user_id=1, title="t", message_count=1, created_at=datetime.utcnow())
        db.add(conv)
        db.add(Message(conversation_id=1, role="user", content=content))
        db.commit()
    finally:
        db.close()


def _sql_rows(engine):
    with sqlite3.connect("file:memdb?mode=ro", uri=True) as _:
        pass  # placeholder to keep sqlite3 import meaningful for in-memory URI doc
    return None


def _db_snapshot(engine):
    from models import Conversation, Message

    sm = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    db = sm()
    try:
        messages = [
            {"id": m.id, "role": m.role, "content": m.content}
            for m in db.query(Message).filter(Message.conversation_id == 1).order_by(Message.id)
        ]
        conv = db.get(Conversation, 1)
        return {"messages": messages, "message_count": conv.message_count}
    finally:
        db.close()


def _build_stream_namespace(sm):
    """Real stream() + real response class + REAL _post_placeholder over isolated SQLite."""
    import logging
    import re
    from contextlib import aclosing as _aclosing

    namespace = {
        "asyncio": asyncio,
        "threading": threading,
        "json": json,
        "time": time,
        "re": re,
        "aclosing": _aclosing,
        "asynccontextmanager": asynccontextmanager,
        "CancelScope": anyio.CancelScope,
        "anyio": anyio,
        "SimpleNamespace": SimpleNamespace,
        "StreamingResponse": StreamingResponse,
        "logger": logging.getLogger("rag_chain"),
        "StrOutputParser": StrOutputParser,
    }
    _extract(BACKEND / "llm_guard.py", {"LLMBusyError", "_LLMGuard"}, namespace)
    guard = namespace["_LLMGuard"](1, 0.1)
    namespace["llm_guard"] = guard
    _extract(
        BACKEND / "rag_chain.py",
        {
            "make_chain",
            "_ThinkStripper",
            "_prefix_suffix_len",
            "stream_with_retry",
            "ClosingStream",
            "_OwnedChain",
            "_OwnedStreamClient",
        },
        namespace,
    )
    _extract(BACKEND / "main.py", {"_stream_with_status_preframe", "_ChatStreamingResponse"}, namespace)
    # REAL _post_placeholder with the isolated SessionLocal
    placeholder_ns = {
        "SessionLocal": sm,
        "text": text,
        "datetime": datetime,
    }
    from models import Conversation, Message  # noqa: F401  (names inside the real function)

    placeholder_ns["Message"] = Message
    placeholder_ns["Conversation"] = Conversation
    _extract(BACKEND / "main.py", {"_post_placeholder"}, placeholder_ns)
    namespace["_post_placeholder"] = placeholder_ns["_post_placeholder"]
    error_tree = ast.parse((BACKEND / "main.py").read_text(encoding="utf-8-sig"))
    # D-23：占位文案的常量按 main.py 真值注入**两个**命名空间。测试不自带副本——否则生产改了
    # 句子而夹具仍断言旧句子，这道门就变成假绿；`_post_placeholder` 落在 placeholder_ns，
    # 正文生成器落在 namespace，两边都可能在运行时读这几条。
    for _const in ("_ERROR_NO_RESPONSE", "_PLACEHOLDER_NO_RESPONSE", "_PLACEHOLDER_STOPPED"):
        _node = next(
            (
                node
                for node in error_tree.body
                if isinstance(node, ast.Assign)
                and any(isinstance(t, ast.Name) and t.id == _const for t in node.targets)
            ),
            None,
        )
        assert _node is not None, f"main.py 不再声明 {_const}——仪器要跟改，不能静默跳过"
        for _ns in (namespace, placeholder_ns):
            exec(compile(ast.Module(body=[_node], type_ignores=[]), "error-constant", "exec"), _ns)
    return namespace, guard


def _chat_locals(chat, names):
    """Pull the *real* request-local declarations out of chat() by name.

    `stream_state` and `compensate_unstarted` are product code; a test that re-wrote them
    would prove nothing about the product's cancellation ownership.  Statements are
    returned in source order so the exec'd frame matches the product's own binding order.
    """
    nodes = []
    for node in chat.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in names:
            nodes.append(node)
        elif isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id in names for target in node.targets
        ):
            nodes.append(node)
    found = {getattr(node, "name", None) or getattr(node.targets[0], "id", None) for node in nodes}
    assert found == set(names), f"chat() no longer declares {sorted(set(names) - found)}"
    return nodes


def _real_chat_response(namespace):
    path = BACKEND / "main.py"
    tree = ast.parse(path.read_text(encoding="utf-8-sig"))
    chat = next(node for node in tree.body if getattr(node, "name", None) == "chat")
    stream = next(node for node in chat.body if isinstance(node, ast.AsyncFunctionDef) and node.name == "stream")
    locals_nodes = _chat_locals(chat, {"stream_state", "compensate_unstarted"})
    exec(compile(ast.Module(body=[stream], type_ignores=[]), str(path), "exec"), namespace)
    exec(compile(ast.Module(body=locals_nodes, type_ignores=[]), str(path), "exec"), namespace)
    final_return = chat.body[-1]
    assert isinstance(final_return, ast.Return)
    return eval(compile(ast.Expression(body=final_return.value), str(path), "eval"), namespace)


def _stream_namespace_base(namespace, llm):
    async def run_in_threadpool(fn, *args):
        return fn(*args)

    namespace.update(
        pre={"conv_id": 1, "sources": []},
        body=SimpleNamespace(no_cache=True),
        cache_hit=None,
        cache_key=None,
        use_router=False,
        use_light=False,
        strategy="answer",
        flag_key=None,
        flag_llm=None,
        messages=[],
        settings=SimpleNamespace(fast_path_law_version_check=False),
        registry=SimpleNamespace(get=lambda: llm, variant=lambda disabled: llm),
        _contract_messages=lambda pre, cd: [],
        run_in_threadpool=run_in_threadpool,
        _post=lambda *args: namespace.setdefault("_post_calls", []).append(args),
    )


def _await_placeholder(sm, engine, expected_rows, timeout=5.0):
    """Wait until the executor-scheduled placeholder thread work lands in the DB."""
    deadline = time.monotonic() + timeout
    snapshot = None
    while time.monotonic() < deadline:
        snapshot = _db_snapshot(engine)
        if len(snapshot["messages"]) >= expected_rows:
            return snapshot
        time.sleep(0.05)
    return snapshot


@pytest.mark.parametrize(
    "gate_first_chunk",
    [False, True],
    ids=["disconnect-before-first-iteration", "disconnect-while-prebody-work-in-flight"],
)
def test_d2_disconnect_before_body_persists_exactly_one_placeholder(gate_first_chunk):
    gate = threading.Event() if gate_first_chunk else None
    sm, engine = _isolated_db()
    _commit_user_message(sm)
    namespace, guard = _build_stream_namespace(sm)
    provider = _Response(pieces=("first", "second"))
    llm = _LLM(provider, gate=gate)
    _stream_namespace_base(namespace, llm)
    response = _real_chat_response(namespace)

    sent_frames = []

    async def send(message):
        if message["type"] == "http.response.body" and message.get("body"):
            sent_frames.append(message["body"].decode("utf-8"))

    async def receive():
        # disconnect is queued before the first body send; for the gated provider it
        # arrives only once the pre-body wait is provably blocking (no cancel-vs-start race)
        if gate is not None:
            await asyncio.to_thread(llm.async_client.wait_entered.wait, 5)
        return {"type": "http.disconnect"}

    async def scenario():
        with anyio.fail_after(10):
            await response({"type": "http", "asgi": {"spec_version": "2.3"}}, receive, send)

    anyio.run(scenario, backend="asyncio")
    # the pre-body provider wait completes after the disconnect (no abandoned thread)
    if gate is not None:
        gate.set()
        assert llm.async_client.gate_done.wait(5), "pre-body wait thread never finished its work after the disconnect"
    snapshot = _await_placeholder(sm, engine, expected_rows=2)
    assert snapshot is not None and len(snapshot["messages"]) == 2, snapshot
    roles = [row["role"] for row in snapshot["messages"]]
    contents = [row["content"] for row in snapshot["messages"]]
    assert roles == ["user", "assistant"], roles
    assert contents[1] == PLACEHOLDER_STOPPED, contents
    assert snapshot["message_count"] == 2, snapshot
    # no half-body persisted: the placeholder is the only assistant row
    assert not any("first" in c or "second" in c for c in contents), contents
    # no content frame was ever sent to the disconnected client
    assert not any('"content"' in frame for frame in sent_frames), sent_frames
    # provider torn down if it was ever opened; guard slot released
    assert provider.closed or provider.reads == 0, "opened provider response left open after disconnect"
    assert guard._sem.acquire(blocking=False), "concurrency slot lost"
    guard._sem.release()
    # normal _post never ran (no answer was produced)
    assert namespace.setdefault("_post_calls", []) == []


def test_d2_normal_completion_after_disconnect_case_contract():
    """Contract guard: a normal (non-disconnected) completion posts the real answer instead."""
    sm, engine = _isolated_db()
    _commit_user_message(sm)
    namespace, guard = _build_stream_namespace(sm)
    provider = _Response(pieces=("first",))
    llm = _LLM(provider)
    _stream_namespace_base(namespace, llm)

    async def run_in_threadpool(fn, *args):
        return fn(*args)

    namespace.update(
        cache_hit={"answer": "cached"},
        user=SimpleNamespace(id=1),
        t0=time.perf_counter(),
        text="question",
        routing_metrics=SimpleNamespace(record=lambda *args, **kwargs: None),
        log_account=lambda **kwargs: None,
        run_in_threadpool=run_in_threadpool,
    )
    sent_frames = []

    async def send(message):
        if message["type"] == "http.response.body" and message.get("body"):
            sent_frames.append(message["body"].decode("utf-8"))

    async def receive():
        await anyio.sleep_forever()

    async def scenario():
        response = _real_chat_response(namespace)
        with anyio.fail_after(10):
            await response({"type": "http", "asgi": {"spec_version": "2.3"}}, receive, send)

    anyio.run(scenario, backend="asyncio")
    assert any('"content"' in frame for frame in sent_frames), sent_frames
    assert namespace.setdefault("_post_calls", []), "normal completion must post the answer"
    # the real DB must NOT contain a failure placeholder on the normal path
    snapshot = _db_snapshot(engine)
    assert [row["role"] for row in snapshot["messages"]] == ["user"], snapshot
    assert snapshot["message_count"] == 1, snapshot


# ── R1: the disconnect lands while `http.response.start` is still blocking, so the
# body iterator never enters and closing an un-started async generator runs no finally.


def test_d2_disconnect_during_response_start_before_iterator_enters():
    sm, engine = _isolated_db()
    try:
        _commit_user_message(sm)
        namespace, guard = _build_stream_namespace(sm)
        llm = _LLM(_Response())
        _stream_namespace_base(namespace, llm)
        response = _real_chat_response(namespace)
        headers_started = asyncio.Event()
        bodies = []

        async def send(message):
            if message["type"] == "http.response.start":
                headers_started.set()
                await anyio.sleep_forever()
            elif message["type"] == "http.response.body":
                bodies.append(message)

        async def receive():
            await headers_started.wait()
            return {"type": "http.disconnect"}

        async def scenario():
            with anyio.fail_after(3):
                await response({"type": "http", "asgi": {"spec_version": "2.3"}}, receive, send)

        anyio.run(scenario, backend="asyncio")
        snapshot = _await_placeholder(sm, engine, expected_rows=2, timeout=0.5)
        assert [row["role"] for row in snapshot["messages"]] == ["user", "assistant"], snapshot
        assert snapshot["messages"][1]["content"] == PLACEHOLDER_STOPPED
        assert snapshot["message_count"] == 2
        assert bodies == []
        assert llm.async_client.calls == []
        assert namespace.get("_post_calls", []) == []
        assert guard._sem.acquire(blocking=False)
        guard._sem.release()
    finally:
        engine.dispose()


# ── R1 second layer: the same window reached through the real chat() route, with the
# real _pre commit chain.  Proves the ordering (user committed -> pre returns -> response
# handed over -> response.start -> body never entered) instead of asserting it.


class _RouteSeam:
    """Blocks the post-commit retrieval seam so the pre window stays open on demand.

    `prepare_fast_path` reaches `retrieve` only after `bootstrap_request` has already
    committed the user message, so blocking here proves "the user row landed while the
    `_pre` thread is still working" without touching any product code.
    """

    def __init__(self):
        self.entered = threading.Event()
        self.release = threading.Event()
        self.finished = threading.Event()

    def retrieve(self, query, k=10, cutoff=None):
        self.entered.set()
        assert self.release.wait(15), "retrieval seam was never released"
        self.finished.set()
        return []


def _route_namespace(sm, seam, *, image_validator=None):
    """Real chat() + real stream() + real _post_placeholder over isolated SQLite.

    Only the injected dependency seams are replaced -- that is what
    `BootstrapDependencies`/`FastPathDependencies` exist for: the session factory points
    at the isolated engine, the post-commit retrieval seam blocks, inert helpers return
    empty values.  Nothing about the compensation is re-implemented here; the placeholder
    writer is the product's own `_post_placeholder` extracted from main.py.
    """
    import dataclasses
    from datetime import date

    from fastapi import HTTPException
    from fastapi.concurrency import run_in_threadpool
    from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

    import prompts
    import query_understand
    import request_bootstrap

    namespace, guard = _build_stream_namespace(sm)
    main_path = BACKEND / "main.py"

    bootstrap_deps = request_bootstrap.BootstrapDependencies(
        **{
            field.name: {
                "session_factory": sm,
                "load_context": lambda db, conv: ("", []),
                "validate_image": image_validator or (lambda image: None),
                "persist_image": lambda image: (None, None),
                "cleanup_persisted_image": lambda rel, thumb: None,
                "describe_image": lambda image, text: "",
                "classify_intent": lambda query: "legal_query",
                "is_exam_question": lambda query: False,
                "has_exam_options": lambda query: False,
                "is_contract_review": lambda query: False,
                "contract_trigger_reason": lambda query: None,
                "feature_multi_analyze": False,
                "contract_conversations": set(),
                "contract_reviewed_conversations": set(),
                "is_contract_exit": lambda query: False,
            }[field.name]
            for field in dataclasses.fields(request_bootstrap.BootstrapDependencies)
        }
    )
    fast_values = {
        "feature_study_retrieval": False,
        "is_meta_study": lambda query: False,
        "rewrite_for_retrieval": lambda raw, recent, recent_msgs, has_options: raw,
        "scenario_supplement_docs": lambda text, cutoff=None: [],
        "retrieve_exam": lambda query, k=10, cutoff=None: [],
        "cheating_docs": lambda cutoff=None: [],
        "build_contract_data": lambda text, cutoff=None: {"docs": []},
        "retrieve": seam.retrieve,
        "search_qa": lambda query: None,
        "is_consumer_clause_scenario": lambda query: False,
        "consumer_clause_docs": lambda cutoff=None: [],
        "is_consumer_fraud_scenario": lambda query: False,
        "consumer_fraud_docs": lambda cutoff=None: [],
        "format_docs": lambda docs: "",
    }
    fast_deps = request_bootstrap.FastPathDependencies(
        **{field.name: fast_values[field.name] for field in dataclasses.fields(request_bootstrap.FastPathDependencies)}
    )

    def _pre(user_id, conversation_id, text, image, client_truncated=False, law_as_of=None):
        """Product dependency wiring with this harness's seams substituted."""
        bootstrap = request_bootstrap.bootstrap_request(
            user_id,
            conversation_id,
            text,
            image,
            client_truncated,
            law_as_of=law_as_of,
            _deps=bootstrap_deps,
        )
        return request_bootstrap.prepare_fast_path(bootstrap, _deps=fast_deps)

    # Annotations on the extracted product functions are evaluated at definition time,
    # so every name they mention must already live in the namespace.
    namespace.update(
        _pre=_pre,
        date=date,
        datetime=datetime,
        settings=SimpleNamespace(
            agent_enabled=False,
            agent_shadow_enabled=False,
            feature_router=False,
            feature_multi_analyze=False,
            feature_study_retrieval=False,
            feature_study_cache=False,
            feature_similar_cache=False,
            fast_path_law_version_check=False,
            allow_client_law_as_of=False,
            allow_client_case_domain=False,
        ),
        answer_cache=SimpleNamespace(generation=lambda: 0, get=lambda key: None),
        complexity=SimpleNamespace(assess=lambda *args: ("text", "flag"), admit_light=lambda *args, **kwargs: False),
        registry=SimpleNamespace(
            has_modality=lambda modality: True,
            has_role=lambda *args: False,
            get=lambda: None,
            variant=lambda disabled: None,
        ),
        clarify=SimpleNamespace(decide=lambda *args: "direct", CLARIFY_PROMPT="", REFUSE_PROMPT=""),
        routing_metrics=SimpleNamespace(
            record=lambda *args, **kwargs: None,
            record_agent_route=lambda *args, **kwargs: None,
            should_route_agent=lambda *args, **kwargs: False,
        ),
        log_account=lambda **kwargs: None,
        HTTPException=HTTPException,
        run_in_threadpool=run_in_threadpool,
        Request=object,
        ChatIn=object,
        User=object,
        Depends=lambda dependency: None,
        get_current_user=lambda: None,
        HumanMessage=HumanMessage,
        SystemMessage=SystemMessage,
        AIMessage=AIMessage,
        query_understand=query_understand,
        _clarified={},
        _post=lambda *args: namespace.setdefault("_post_calls", []).append(args),
    )
    # `_cache_key`/`_cache_scope`/`_cacheable` are deliberately not extracted: their
    # annotations mention `answer_cache.CacheScope`, and with `body.no_cache` true the
    # cache branch is never reached on this route path.
    _extract(
        main_path,
        {
            "_build_messages",
            "_law_version_scope_note",
            "_cutoff",
            "_client_law_as_of",
            "_client_case_domain",
            "_record_actual_agent_route",
        },
        namespace,
    )
    # `_extract` matches statements by `name`, which a module-level constant does not
    # have, so the citation-rule text is compiled out of domain_rules.py explicitly.
    rules_tree = ast.parse((BACKEND / "domain_rules.py").read_text(encoding="utf-8-sig"))
    rule_node = next(
        node
        for node in rules_tree.body
        if isinstance(node, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "CITATION_SELECTION_RULE" for t in node.targets)
    )
    exec(compile(ast.Module(body=[rule_node], type_ignores=[]), "domain_rules.py", "exec"), namespace)
    for name in (
        "SYSTEM_BASE",
        "SYSTEM_STUDY",
        "SYSTEM_CHEATING",
        "OUTPUT_FORMAT_RULE",
        "IMAGE_GUIDANCE",
        "_EXAM_TYPE_SUFFIX",
        "_EXAM_VERDICT_RULE",
    ):
        namespace[name] = getattr(prompts, name)
    tree = ast.parse(main_path.read_text(encoding="utf-8-sig"))
    chat = next(node for node in tree.body if isinstance(node, ast.AsyncFunctionDef) and node.name == "chat")
    chat.decorator_list = []  # @app.post needs a live app; @limiter.limit needs a limiter backend
    exec(compile(ast.Module(body=[chat], type_ignores=[]), str(main_path), "exec"), namespace)
    return namespace, guard


def test_d2_disconnect_during_pre_window_hands_over_at_the_response_boundary():
    from unittest import mock

    seam = _RouteSeam()
    disconnect_queued = asyncio.Event()
    order = []
    sm, engine = _isolated_db()
    try:
        _commit_user_message(sm)
        namespace, guard = _route_namespace(sm, seam)
        body = SimpleNamespace(
            content="前置窗口复现：劳动法第四十四条加班工资如何计算？（本机接线测试）",
            question=None,
            image=None,
            truncated=False,
            no_cache=True,
            conversation_id=1,
            agent_run_id=None,
            agent_state_version=None,
            law_as_of=None,
            case_domain=None,
        )

        async def send(message):
            if message["type"] == "http.response.start":
                order.append("response_start")
                await anyio.sleep_forever()  # the client is already gone
            elif message["type"] == "http.response.body":
                order.append("body_entered")

        async def receive():
            await disconnect_queued.wait()
            return {"type": "http.disconnect"}

        async def scenario():
            with anyio.fail_after(20):
                task = asyncio.create_task(namespace["chat"](SimpleNamespace(), body, SimpleNamespace(id=1)))
                assert await asyncio.to_thread(seam.entered.wait, 15), (
                    "the post-commit retrieval seam never executed -- the route never reached prepare_fast_path"
                )
                during_pre = _db_snapshot(engine)
                order.append("user_committed")
                assert [row["role"] for row in during_pre["messages"]] == ["user", "user"], during_pre
                assert during_pre["message_count"] == 2, during_pre
                disconnect_queued.set()
                seam.release.set()
                response = await task
                order.append("pre_returned")
                assert isinstance(response, namespace["_ChatStreamingResponse"]), type(response)
                await response({"type": "http", "asgi": {"spec_version": "2.3"}}, receive, send)
                order.append("response_returned")

        # prepare_fast_path imports two retrieval helpers unconditionally even though
        # neither is called when search_qa yields None; the real modules build a Chroma
        # client and load BGE weights, which a unit gate must never do.
        dummies = {
            "retrieval": SimpleNamespace(
                qa_citations_in_kb=lambda hit: True,
                # W04/C02 之后 `prepare_fast_path` 还从 retrieval 取这两个符号做条号对账。
                # 假模块面必须跟着补齐，否则这条用例红的是"接线没补"而不是"取消行为变了"。
                article_lookup_report=lambda query, docs, **kw: {
                    "asked": [],
                    "found": [],
                    "missing": [],
                    "missing_absent": [],
                    "missing_version_uncertain": [],
                    "state": "no_explicit_reference",
                },
                exact_article_lookup=lambda source, article, cutoff=None: [],
            ),
            "retrieval_core": SimpleNamespace(
                qa_provenance_verifiable=lambda hit: True, is_valid_by_time=lambda meta, cutoff: True
            ),
        }
        with mock.patch.dict(sys.modules, dummies):
            anyio.run(scenario, backend="asyncio")

        assert seam.finished.is_set(), "the pre thread was abandoned instead of reaching a terminal state"
        assert order == ["user_committed", "pre_returned", "response_start", "response_returned"], order
        snapshot = _await_placeholder(sm, engine, expected_rows=3, timeout=0.5)
        assert [row["role"] for row in snapshot["messages"]] == ["user", "user", "assistant"], snapshot
        assert snapshot["messages"][2]["content"] == PLACEHOLDER_STOPPED, snapshot
        assert snapshot["message_count"] == 3, snapshot
        assert namespace.get("_post_calls", []) == []
        assert guard._sem.acquire(blocking=False)
        guard._sem.release()
    finally:
        engine.dispose()


def test_d2_normal_completion_persists_the_full_answer_through_real_post():
    """Persistence gate, not call gate: the answer row must land through the product's `_post`.

    `_post`'s compress decision and its "is this citation in the KB" lookup are the two
    external seams (the first is a read/decision outside this window, the second lives in
    `retrieval`, which builds a Chroma client on import).  The write path itself -- output
    normalisation, assistant row insert, `message_count` bump, conversation title/answer --
    is main.py's own `_post`, executed against isolated SQLite.
    """
    import memory
    import output_normalize
    from models import Conversation, Message

    sm, engine = _isolated_db()
    try:
        _commit_user_message(sm)
        namespace, guard = _build_stream_namespace(sm)
        provider = _Response(pieces=("first",))
        llm = _LLM(provider)
        _stream_namespace_base(namespace, llm)

        post_namespace = {
            "SessionLocal": sm,
            "text": text,
            "datetime": datetime,
            "json": json,
            "Message": Message,
            "Conversation": Conversation,
            "output_normalize": output_normalize,
            "recent_messages": memory.recent_messages,
            "needs_compress": lambda conv, recent: False,
            "compress": lambda *args, **kwargs: None,
            "llm_guard": guard,
            "registry": namespace["registry"],
            "source_in_kb": lambda *args, **kwargs: False,
        }
        _extract(BACKEND / "main.py", {"_post"}, post_namespace)
        namespace["_post"] = post_namespace["_post"]
        namespace.update(
            cache_hit={"answer": "cached"},
            user=SimpleNamespace(id=1),
            t0=time.perf_counter(),
            text="question",
            routing_metrics=SimpleNamespace(record=lambda *args, **kwargs: None),
            log_account=lambda **kwargs: None,
        )

        frames = []

        async def send(message):
            if message["type"] == "http.response.body" and message.get("body"):
                frames.append(message["body"].decode("utf-8"))

        async def receive():
            await anyio.sleep_forever()

        async def scenario():
            response = _real_chat_response(namespace)
            with anyio.fail_after(10):
                await response({"type": "http", "asgi": {"spec_version": "2.3"}}, receive, send)

        anyio.run(scenario, backend="asyncio")

        snapshot = _db_snapshot(engine)
        roles = [row["role"] for row in snapshot["messages"]]
        assert roles == ["user", "assistant"], snapshot
        # 正常完成既不该拿到"无响应"也不该拿到"已停止"——两个标签对它都是假话
        assert snapshot["messages"][1]["content"] not in (PLACEHOLDER, PLACEHOLDER_STOPPED), snapshot
        assert "cached" in snapshot["messages"][1]["content"], snapshot
        assert snapshot["message_count"] == 2, snapshot
        assert any('"conversation_id"' in frame for frame in frames), frames
        assert guard._sem.acquire(blocking=False)
        guard._sem.release()
    finally:
        engine.dispose()


def test_d2_compensation_failure_is_observable_and_does_not_swallow_the_disconnect(capsys):
    """A failing placeholder write must leave a greppable marker, not a silent `except: pass`."""
    sm, engine = _isolated_db()
    try:
        _commit_user_message(sm)
        namespace, guard = _build_stream_namespace(sm)
        llm = _LLM(_Response())
        _stream_namespace_base(namespace, llm)
        headers_started = asyncio.Event()

        def boom(pre, reason="no_response"):
            # 签名跟生产一致（D-23 起第二个位置参数是成因档），否则这里红的是 TypeError 而不是被模拟的写库失败
            raise RuntimeError("isolated sqlite unavailable")

        namespace["_post_placeholder"] = boom
        response = _real_chat_response(namespace)

        async def send(message):
            if message["type"] == "http.response.start":
                headers_started.set()
                await anyio.sleep_forever()

        async def receive():
            await headers_started.wait()
            return {"type": "http.disconnect"}

        async def scenario():
            with anyio.fail_after(3):
                await response({"type": "http", "asgi": {"spec_version": "2.3"}}, receive, send)

        anyio.run(scenario, backend="asyncio")
        captured = capsys.readouterr()
        assert "[chat-cancel-compensate] failed: RuntimeError" in captured.out, captured.out
        snapshot = _db_snapshot(engine)
        assert [row["role"] for row in snapshot["messages"]] == ["user"], snapshot
        assert guard._sem.acquire(blocking=False)
        guard._sem.release()
    finally:
        engine.dispose()


def test_stopped_label_can_only_be_set_by_a_disconnect_signal():
    """D-23 的不变量：历史里那句"已停止"只能由**断开信号**置起，不能由控制流走到哪推断。

    反例形状（独立复核 B 2026-10-11 打中过我第一版实现）：用"有没有走到 try 结尾"反推取消，
    而 `stream()` 的 try 体里有若干**主动 return**（正常分支走完就退），于是轻量分支的空答
    被写成"已停止"，同样的空答在旗舰分支写"不响应"——同一症状两句话。
    这条测试钉的就是：`_client_gone = True` 只许出现在捕获 GeneratorExit/CancelledError 的
    except 块里，且 finally 的档位判定读的是它。
    """
    import ast

    src = (Path(__file__).resolve().parents[1] / "main.py").read_text(encoding="utf-8-sig")
    tree = ast.parse(src)
    chat = next(n for n in tree.body if getattr(n, "name", None) == "chat")
    stream = next(n for n in chat.body if isinstance(n, ast.AsyncFunctionDef) and n.name == "stream")

    def assign_targets(node):
        return {t.id for t in ast.walk(node) if isinstance(t, ast.Name) and isinstance(t.ctx, ast.Store)}

    def caught_names(handler):
        """`except (GeneratorExit, asyncio.CancelledError)` 里后者是 Attribute，不是 Name。"""
        out = set()
        for part in handler.type.elts if isinstance(handler.type, ast.Tuple) else [handler.type]:
            if isinstance(part, ast.Name):
                out.add(part.id)
            elif isinstance(part, ast.Attribute):
                out.add(part.attr)
        return out

    # ① 谁把 _client_gone 置真：必须只在"抓到断开异常"的 except 块里
    setters = []
    for handler in (n for n in ast.walk(stream) if isinstance(n, ast.ExceptHandler)):
        if "_client_gone" in assign_targets(handler):
            names = caught_names(handler)
            assert {"GeneratorExit", "CancelledError"} <= names, f"置真它的 except 抓的是 {sorted(names)}"
            setters.append(handler.lineno)
    assert setters, "没有任何 except 块置 _client_gone——那「已停止」档是靠什么判的？"

    # ② try 体里不许出现对该标记的赋值（return 路径不能冒充取消）
    for stmt in (n for n in ast.walk(stream) if isinstance(n, ast.Try)):
        body_targets = set()
        for sub in stmt.body:
            body_targets |= {t.id for t in ast.walk(sub) if isinstance(t, ast.Name) and isinstance(t.ctx, ast.Store)}
        assert "_client_gone" not in body_targets, "try 体内在给断开标记赋值 ⇒ 又回到用控制流推断取消"

    # ③ finally 的档位判定必须读这个标记
    fin = next(n for n in ast.walk(stream) if isinstance(n, ast.Try) and n.finalbody)
    readers = {n.id for n in ast.walk(fin) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)}
    assert "_client_gone" in readers, "finally 没在读断开标记 ⇒ 档位判定又和断开脱钩了"
