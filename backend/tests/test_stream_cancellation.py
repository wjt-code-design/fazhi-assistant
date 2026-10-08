"""Isolated lifecycle tests: execute production AST, never import application/DB.

Run with --noconftest so the repository's global conftest cannot initialize BGE/Chroma.
Fakes cover lifecycle branches; installed ChatOpenAI/SDK use test-owned loopback HTTP.
Held references make assertions independent of async-generator garbage collection.
"""

import ast
import asyncio
import inspect
import json
import logging
import re
import select
import socket
import sys
import threading
import time
from contextlib import aclosing, asynccontextmanager, contextmanager
from dataclasses import dataclass, replace
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import anyio
import pytest
from langchain_core.callbacks import AsyncCallbackHandler, BaseCallbackHandler
from langchain_core.callbacks.manager import AsyncCallbackManager
from langchain_core.messages import AIMessageChunk, HumanMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnableSerializable
from pydantic.v1 import Field
from starlette.concurrency import run_in_threadpool
from starlette.responses import StreamingResponse

BACKEND = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def _loopback_only(monkeypatch):
    """Fail before DNS/connect for external destinations, including tracing/proxies."""
    for name in ("LANGCHAIN_TRACING", "LANGCHAIN_TRACING_V2", "LANGSMITH_TRACING"):
        monkeypatch.setenv(name, "false")
    connect, connect_ex, getaddrinfo = socket.socket.connect, socket.socket.connect_ex, socket.getaddrinfo

    def check(host):
        assert host in ("127.0.0.1", "::1"), f"External socket/DNS prohibited: {host}"

    def guarded_connect(sock, address):
        check(address[0])
        return connect(sock, address)

    def guarded_connect_ex(sock, address):
        check(address[0])
        return connect_ex(sock, address)

    def guarded_getaddrinfo(host, *args, **kwargs):
        check(host)
        return getaddrinfo(host, *args, **kwargs)

    monkeypatch.setattr(socket.socket, "connect", guarded_connect)
    monkeypatch.setattr(socket.socket, "connect_ex", guarded_connect_ex)
    monkeypatch.setattr(socket, "getaddrinfo", guarded_getaddrinfo)


def test_external_socket_guard_rejects_before_io():
    with socket.socket() as sock, pytest.raises(AssertionError, match="External socket"):
        sock.connect(("203.0.113.1", 443))
    with pytest.raises(AssertionError, match="External socket"):
        socket.getaddrinfo("example.invalid", 443)


@contextmanager
def _waiting_http_provider(after_content, *, streaming=True, started=None):
    """One stalled HTTP connection; observe peer EOF before SDK pool cleanup."""
    peer_closed, stop = threading.Event(), threading.Event()

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *args):
            pass

        def do_POST(self):
            assert self.path == "/v1/chat/completions"
            request = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            assert request.get("stream", False) is streaming
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream" if streaming else "application/json")
            self.send_header("Transfer-Encoding", "chunked")
            self.end_headers()
            self.wfile.flush()
            if started is not None:
                started.set()
            if after_content:
                chunk = {
                    "id": "test-stream",
                    "object": "chat.completion.chunk",
                    "created": 0,
                    "model": "test-model",
                    "choices": [{"index": 0, "delta": {"content": "first"}, "finish_reason": None}],
                }
                payload = ("data: " + json.dumps(chunk) + "\n\n").encode()
                self.wfile.write(f"{len(payload):x}\r\n".encode() + payload + b"\r\n")
                self.wfile.flush()
            try:
                while not stop.is_set():
                    if select.select([self.connection], [], [], 0.02)[0] and not self.connection.recv(
                        1, socket.MSG_PEEK
                    ):
                        peer_closed.set()
                        break
            except (ConnectionResetError, ConnectionAbortedError):
                peer_closed.set()
            finally:
                self.close_connection = True

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.02}, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/v1", peer_closed
    finally:
        stop.set()
        server.shutdown()
        server.server_close()
        thread.join(timeout=1)


def _extract(path, names, namespace):
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    nodes = [node for node in tree.body if getattr(node, "name", None) in names]
    module = ast.Module(body=nodes, type_ignores=[])
    exec(compile(module, str(path), "exec"), namespace)
    return namespace


def _chat_ownership_locals(chat):
    """Extract the product's own request-local cancellation ownership out of chat().

    `stream_state` and `compensate_unstarted` have to come from main.py: re-writing them
    in a test would let the test go green while the product still keeps the window.
    """
    nodes = []
    for node in chat.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "compensate_unstarted":
            nodes.append(node)
        elif isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "stream_state" for target in node.targets
        ):
            nodes.append(node)
    found = [getattr(node, "name", None) or node.targets[0].id for node in nodes]
    assert found == ["stream_state", "compensate_unstarted"], f"chat() ownership changed shape: {found}"
    return nodes


def _production():
    namespace = {
        "asyncio": asyncio,
        "threading": threading,
        "json": json,
        "time": time,
        "re": re,
        "aclosing": aclosing,
        "asynccontextmanager": asynccontextmanager,
        "CancelScope": anyio.CancelScope,
        "anyio": anyio,
        "SimpleNamespace": SimpleNamespace,
        "StrOutputParser": StrOutputParser,
        "StreamingResponse": StreamingResponse,
        "run_in_threadpool": run_in_threadpool,
        "logger": logging.getLogger("rag_chain"),
    }
    _extract(BACKEND / "llm_guard.py", {"LLMBusyError", "_LLMGuard"}, namespace)
    guard = namespace["_LLMGuard"](1, 0.1)
    namespace["llm_guard"] = guard
    normalize = {"re": re}
    tree = ast.parse((BACKEND / "output_normalize.py").read_text(encoding="utf-8"))
    nodes = [
        node
        for node in tree.body
        if getattr(node, "name", None) == "money_normalize"
        or isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id.startswith("_MONEY_") for target in node.targets)
    ]
    exec(compile(ast.Module(body=nodes, type_ignores=[]), "output_normalize.py", "exec"), normalize)
    namespace["output_normalize"] = SimpleNamespace(money_normalize=normalize["money_normalize"])
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
    return namespace, guard


class _Response:
    def __init__(
        self, pieces=("first", "second"), *, block=False, block_after=False, error=None, close_error_after=None
    ):
        self.pieces = pieces
        self.block = block
        self.error = error
        self.block_after = block_after
        self.close_error_after = close_error_after
        self.close_attempts = 0
        self.started = asyncio.Event()
        self.closed = False
        self.reads = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        # Real httpcore.PoolByteStream.aclose shields the transport teardown.
        with anyio.CancelScope(shield=True):
            await self.close()

    async def close(self):
        self.close_attempts += 1
        await asyncio.sleep(0)
        if self.close_error_after is not None and self.close_attempts > self.close_error_after:
            raise RuntimeError("transport close failed")
        self.closed = True

    async def __aiter__(self):
        self.started.set()
        if self.block:
            await asyncio.Event().wait()
        for piece in self.pieces:
            self.reads += 1
            yield piece
            if self.block_after:
                await asyncio.Event().wait()
        if self.error:
            raise self.error


class _Client:
    def __init__(self, response):
        self.response = response
        self.calls = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        if isinstance(self.response, dict):
            return self.response[kwargs["messages"][0]]
        return self.response


class _LLM(RunnableSerializable):
    """Public model seam only; resource ownership stays in its provider iterator."""

    # Match real ChatOpenAI/BaseChatModel exclude=True fields; use the installed
    # Pydantic copy behavior instead of a fake copy that masks lost callbacks.
    async_client: Any = Field(exclude=True)
    client: Any = Field(exclude=True)
    callbacks: Any = Field(default=None, exclude=True)
    tags: Any = Field(default=None, exclude=True)
    metadata: Any = Field(default=None, exclude=True)
    streams: list = Field(default_factory=list, exclude=True)
    configs: list = Field(default_factory=list, exclude=True)

    def __init__(self, response):
        super().__init__(
            async_client=_Client(response),
            client=object(),
            callbacks=[],
            tags=["model-tag"],
            metadata={"model": "same"},
        )

    def invoke(self, input, config=None, **kwargs):
        raise AssertionError("This suite must never invoke a non-streaming model")

    def astream(self, input, config=None, **kwargs):
        assert self.callbacks == [] and self.tags == ["model-tag"] and self.metadata == {"model": "same"}
        assert self.client is not None
        self.configs.append(config)

        async def provider():
            response = await self.async_client.create(messages=input, stream=True, **kwargs)
            async with response:
                async for piece in response:
                    yield AIMessageChunk(content=piece)

        stream = provider()
        self.streams.append(stream)
        return stream


class _Chain:
    def __init__(self, response):
        self.response = response
        self.streams = []

    def astream(self, messages):
        async def generate():
            async with self.response:
                async for piece in self.response:
                    yield piece

        stream = generate()
        self.streams.append(stream)
        return stream


def _assert_slot_released(guard):
    assert guard._sem.acquire(blocking=False), "Cancelled stream retained the shared concurrency slot"
    guard._sem.release()


def test_preframe_close_closes_held_inner_before_return():
    async def scenario():
        namespace, _ = _production()
        closed = False

        async def inner():
            nonlocal closed
            try:
                yield "content"
                yield "unused"
            finally:
                await asyncio.sleep(0)
                closed = True

        owned = inner()
        outer = namespace["_stream_with_status_preframe"](owned)
        first = await anext(outer)
        if first != "content":
            assert json.loads(first[6:])["type"] == "status"
            first = await anext(outer)
        assert first == "content"
        await outer.aclose()
        assert closed, "preframe aclose returned without closing its owned inner stream"

    asyncio.run(scenario())


def test_preframe_cleanup_survives_cancelled_anyio_scope():
    async def scenario():
        namespace, _ = _production()
        closed = False

        async def inner():
            nonlocal closed
            try:
                yield "content"
            finally:
                await anyio.lowlevel.checkpoint()
                closed = True

        owned = inner()
        outer = namespace["_stream_with_status_preframe"](owned)
        first = await anext(outer)
        if first != "content":
            first = await anext(outer)
        assert first == "content"
        with anyio.CancelScope() as scope:
            scope.cancel()
            await outer.aclose()
        assert closed, "Cancelled AnyIO scope interrupted owned-stream cleanup"

    anyio.run(scenario, backend="asyncio")


def test_retry_close_closes_chain_without_retry_and_releases_slot():
    async def scenario():
        namespace, guard = _production()
        response = _Response()
        chain = _Chain(response)
        attempts, failures = [], []

        def factory(index, disabled):
            attempts.append((index, disabled))
            return chain

        outer = namespace["stream_with_retry"](factory, [], [(False, 0), (True, 0)], failures.append)
        assert await anext(outer) == "first"
        await outer.aclose()
        assert response.closed, "retry generator aclose returned with its provider still open"
        assert attempts == [(0, False)] and failures == []
        assert response.reads == 1
        _assert_slot_released(guard)

    asyncio.run(scenario())


def test_cancel_waiting_first_token_propagates_without_model_failure():
    async def scenario():
        namespace, guard = _production()
        response = _Response(block=True)
        chain = _Chain(response)
        attempts, failures = [], []

        def factory(index, disabled):
            attempts.append(index)
            return chain

        outer = namespace["stream_with_retry"](factory, [], [(False, 0), (True, 0)], failures.append)
        cancelled = False

        async def consume():
            nonlocal cancelled
            try:
                await anext(outer)
            except asyncio.CancelledError:
                cancelled = True
                raise

        async with anyio.create_task_group() as group:
            group.start_soon(consume)
            await response.started.wait()
            group.cancel_scope.cancel()
        assert cancelled and response.closed
        assert attempts == [0] and failures == [] and response.reads == 0
        _assert_slot_released(guard)

    anyio.run(scenario, backend="asyncio")


def test_normal_completion_preserves_normalization_and_slot():
    async def scenario():
        namespace, guard = _production()
        response = _Response(("<thi", "nk>private</think>", "$150", " tail"))
        attempts = []

        def factory(index, disabled):
            attempts.append(index)
            return _Chain(response)

        actual = [piece async for piece in namespace["stream_with_retry"](factory, [], [(False, 0), (True, 0)])]
        assert actual == ["150元", " tail"]
        assert response.closed and attempts == [0]
        _assert_slot_released(guard)

    asyncio.run(scenario())


def test_exception_retry_preserves_callback_and_final_error():
    async def scenario():
        namespace, guard = _production()
        errors = [RuntimeError("one"), ValueError("two"), LookupError("last")]
        responses = [_Response((), error=error) for error in errors]
        attempts, failures = [], []

        def factory(index, disabled):
            attempts.append((index, disabled))
            return _Chain(responses[index])

        with pytest.raises(LookupError) as caught:
            async for _ in namespace["stream_with_retry"](
                factory, [], [(False, 0), (True, 0), (False, 0)], failures.append
            ):
                pass
        assert caught.value is errors[-1]
        assert failures == errors[:2] and attempts == [(0, False), (1, True), (2, False)]
        assert all(response.closed for response in responses)
        _assert_slot_released(guard)

    asyncio.run(scenario())


def test_empty_answer_retry_remains_bounded():
    async def scenario():
        namespace, guard = _production()
        responses = [_Response(()), _Response(("",)), _Response(("answer",))]
        attempts, failures = [], []

        def factory(index, disabled):
            attempts.append(index)
            return _Chain(responses[index])

        actual = [
            piece
            async for piece in namespace["stream_with_retry"](
                factory, [], [(False, 0), (True, 0), (False, 0)], failures.append
            )
        ]
        assert actual == ["answer"] and attempts == [0, 1, 2] and failures == []
        assert all(response.closed for response in responses)
        _assert_slot_released(guard)

    asyncio.run(scenario())


def test_make_chain_close_reaches_owned_provider_response():
    async def scenario():
        namespace, _ = _production()
        response = _Response()
        llm = _LLM(response)
        chain = namespace["make_chain"](llm)
        owned = chain.astream([], config={"tags": ["public-api"], "metadata": {"request": "test"}})
        assert await anext(owned) == "first"
        await owned.aclose()
        assert response.closed, "Closing the owned model stream did not close its HTTP resource"
        assert response.reads == 1
        assert llm.configs[0]["metadata"]["request"] == "test"
        assert "public-api" in llm.configs[0]["tags"]
        assert llm.async_client.calls == [{"messages": [], "stream": True}]

    asyncio.run(scenario())


@pytest.mark.parametrize("after_content", [False, True], ids=["before-content", "after-content"])
def test_make_chain_task_cancel_closes_resource_and_preserves_cancel(after_content):
    async def scenario():
        namespace, guard = _production()
        response = _Response(block=not after_content, block_after=after_content)
        llm = _LLM(response)
        failures, attempts = [], []
        delivered = asyncio.Event()
        cancelled = False

        def factory(index, disabled):
            attempts.append(index)
            return namespace["make_chain"](llm)

        outer = namespace["stream_with_retry"](factory, [], [(False, 0), (True, 0)], failures.append)

        async def consume():
            nonlocal cancelled
            try:
                async for piece in outer:
                    assert piece == "first"
                    delivered.set()
            except asyncio.CancelledError:
                cancelled = True
                raise

        with anyio.fail_after(2):
            async with anyio.create_task_group() as group:
                group.start_soon(consume)
                await (delivered if after_content else response.started).wait()
                group.cancel_scope.cancel()
        assert cancelled and response.closed
        assert attempts == [0] and failures == []
        assert response.reads == int(after_content)
        _assert_slot_released(guard)

    anyio.run(scenario, backend="asyncio")


@pytest.mark.parametrize("after_content", [False, True], ids=["before-content", "after-content"])
def test_real_http_cancel_disconnects_peer_before_sdk_client_cleanup(after_content):
    import httpx
    from langchain_openai import ChatOpenAI
    from openai import AsyncOpenAI, OpenAI

    async def scenario(base_url, peer_closed):
        namespace, guard = _production()
        responses, attempts, failures, model_starts = [], [], [], []
        response_ready, delivered = asyncio.Event(), asyncio.Event()

        class Recorder(BaseCallbackHandler):
            def on_chat_model_start(self, serialized, messages, **kwargs):
                model_starts.append(kwargs)

        async_http = httpx.AsyncClient(trust_env=False)
        sync_http = httpx.Client(trust_env=False)
        options = {"api_key": "test-only-placeholder", "base_url": base_url, "max_retries": 0, "timeout": 5}
        sdk = AsyncOpenAI(http_client=async_http, **options)
        sync_sdk = OpenAI(http_client=sync_http, **options)

        class ObservedCreate:
            async def create(self, **kwargs):
                response = await sdk.chat.completions.create(**kwargs)
                responses.append(response)
                response_ready.set()
                return response

        client, recorder = ObservedCreate(), Recorder()
        model = ChatOpenAI(
            client=sync_sdk.chat.completions,
            async_client=client,
            streaming=True,
            model="test-model",
            callbacks=[recorder],
            tags=["model-tag"],
            metadata={"model": "same"},
            **options,
        )
        cancelled = False

        def factory(index, disabled):
            attempts.append((index, disabled))
            return namespace["make_chain"](model)

        outer = namespace["stream_with_retry"](
            factory, [HumanMessage(content="cancel-test")], [(False, 0), (True, 0)], failures.append
        )

        async def consume():
            nonlocal cancelled
            try:
                async with namespace["ClosingStream"](outer):
                    async for piece in outer:
                        assert piece == "first"
                        delivered.set()
            except asyncio.CancelledError:
                cancelled = True
                raise

        try:
            with anyio.fail_after(5):
                async with anyio.create_task_group() as group:
                    group.start_soon(consume)
                    await (delivered if after_content else response_ready).wait()
                    # Cancel a live blocked model read, not merely the create observer.
                    await anyio.sleep(0.05)
                    group.cancel_scope.cancel()
            assert cancelled and responses and all(response.response.is_closed for response in responses)
            observed = {
                "after_content": after_content,
                "peer_disconnected": await asyncio.to_thread(peer_closed.wait, 2),
                "response_closed": responses[0].response.is_closed,
                "sdk_client_closed": sdk.is_closed(),
            }
            print(json.dumps(observed, sort_keys=True))
            assert observed["peer_disconnected"], (
                "HTTPX reports closed but provider peer is still active before SDK client cleanup"
            )
            assert not observed["sdk_client_closed"]
            assert attempts == [(0, False)] and failures == []
            assert model.async_client is client and model.callbacks == [recorder]
            assert model.tags == ["model-tag"] and model.metadata == {"model": "same"}
            assert len(model_starts) == 1 and "model-tag" in model_starts[0]["tags"]
            assert model_starts[0]["metadata"]["model"] == "same"
            _assert_slot_released(guard)
            assert outer is not None and responses, "Keep generators and SDK streams alive through EOF proof"
        finally:
            # Test-owned pool cleanup is AFTER the peer assertion and cannot earn GREEN.
            await sdk.close()
            sync_sdk.close()

    with _waiting_http_provider(after_content) as (base_url, peer_closed):
        anyio.run(scenario, base_url, peer_closed, backend="asyncio")


def test_factory_preserves_config_callbacks_and_original_client():
    class Recorder(BaseCallbackHandler):
        def __init__(self):
            self.starts = []
            self.ends = []

        def on_chain_start(self, serialized, inputs, **kwargs):
            self.starts.append((serialized, inputs, kwargs))

        def on_chain_end(self, outputs, **kwargs):
            self.ends.append((outputs, kwargs))

    async def scenario():
        namespace, _ = _production()
        response = _Response(("one", "two"))
        llm = _LLM(response)
        client = llm.async_client
        recorder = Recorder()
        config = {"callbacks": [recorder], "tags": ["callback-tag"], "metadata": {"request": "r"}}
        chain = namespace["make_chain"](llm)
        assert [piece async for piece in chain.astream([], config=config)] == ["one", "two"]
        assert llm.async_client is client, "Factory mutated the shared registered model"
        assert client.calls == [{"messages": [], "stream": True}]
        assert llm.configs[0]["metadata"] == {"request": "r"}
        assert llm.configs[0]["callbacks"] == [recorder]
        assert len(recorder.starts) == len(recorder.ends) == 2
        assert [item[0] for item in recorder.ends] == ["one", "two"]
        assert all(item[0]["id"][-1] == "StrOutputParser" for item in recorder.starts)
        assert all("callback-tag" in item[2]["tags"] for item in recorder.starts)
        assert config == {"callbacks": [recorder], "tags": ["callback-tag"], "metadata": {"request": "r"}}
        assert response.closed

    asyncio.run(scenario())


@pytest.mark.parametrize("use_manager", [False, True], ids=["async-handler-list", "async-manager"])
def test_per_chunk_parser_awaits_async_callbacks_inside_running_loop(use_manager, recwarn, caplog):
    class Recorder(AsyncCallbackHandler):
        def __init__(self):
            self.starts, self.ends, self.callback_loops = [], [], []

        async def on_chain_start(self, serialized, inputs, **kwargs):
            await asyncio.sleep(0)
            self.callback_loops.append(asyncio.get_running_loop())
            self.starts.append((serialized, inputs, kwargs))

        async def on_chain_end(self, outputs, **kwargs):
            await asyncio.sleep(0)
            self.callback_loops.append(asyncio.get_running_loop())
            self.ends.append((outputs, kwargs))

    async def scenario():
        namespace, _ = _production()
        response = _Response(("one", "two"))
        llm, recorder = _LLM(response), Recorder()
        callbacks = AsyncCallbackManager([recorder], inheritable_handlers=[recorder]) if use_manager else [recorder]
        config = {"callbacks": callbacks, "tags": ["async-tag"], "metadata": {"request": "async"}}
        actual = [piece async for piece in namespace["make_chain"](llm).astream([], config=config)]
        assert actual == ["one", "two"] and all(isinstance(piece, str) for piece in actual)
        assert llm.configs[0] is config and llm.configs[0]["callbacks"] is callbacks
        assert [item[0] for item in recorder.ends] == ["one", "two"]
        assert len(recorder.starts) == len(recorder.ends) == 2
        assert all(item[0]["id"][-1] == "StrOutputParser" for item in recorder.starts)
        assert all(
            "async-tag" in item[2]["tags"] and item[2]["metadata"] == {"request": "async"} for item in recorder.starts
        )
        assert len(recorder.callback_loops) == 4 and response.closed
        assert config["tags"] == ["async-tag"] and config["metadata"] == {"request": "async"}

    asyncio.run(scenario())
    assert not [warning for warning in recwarn if "never awaited" in str(warning.message)]
    assert "Error in" not in caplog.text


def test_concurrent_streams_keep_responses_request_local():
    async def scenario():
        namespace, _ = _production()
        responses = {name: _Response((name, "unused")) for name in ("a", "b")}
        llm = _LLM(responses)
        client = llm.async_client
        chain = namespace["make_chain"](llm)
        first, second = chain.astream(["a"]), chain.astream(["b"])
        assert await anext(first) == "a"
        assert await anext(second) == "b"
        await first.aclose()
        assert responses["a"].closed and not responses["b"].closed
        await second.aclose()
        assert responses["b"].closed and llm.async_client is client

    asyncio.run(scenario())


def test_cleanup_error_does_not_mask_generator_close_or_hold_guard(caplog):
    async def scenario():
        namespace, guard = _production()
        response = _Response(close_error_after=0)
        llm = _LLM(response)
        failures = []
        outer = namespace["stream_with_retry"](
            lambda *args: namespace["make_chain"](llm), [], [(False, 0), (True, 0)], failures.append
        )
        assert await anext(outer) == "first"
        await outer.aclose()
        assert response.close_attempts >= 1, "Cleanup was never attempted"
        assert failures == []
        _assert_slot_released(guard)

    asyncio.run(scenario())
    assert "close failed" in caplog.text


def test_cleanup_error_preserves_original_provider_exception(caplog):
    async def scenario():
        namespace, guard = _production()
        original = LookupError("original provider failure")
        response = _Response(("first",), error=original, close_error_after=1)
        llm = _LLM(response)
        outer = namespace["stream_with_retry"](lambda *args: namespace["make_chain"](llm), [], [(False, 0)])
        with pytest.raises(LookupError) as caught:
            async for _ in outer:
                pass
        assert caught.value is original
        _assert_slot_released(guard)

    asyncio.run(scenario())
    assert "close failed" in caplog.text


@pytest.mark.parametrize("contract", [False, True], ids=["ordinary", "contract"])
@pytest.mark.parametrize("status_only", [False, True], ids=["partial-output", "status-only"])
def test_real_main_stream_close_closes_retry_and_keeps_failure_placeholder(contract, status_only):
    async def scenario():
        namespace, guard = _production()
        response = _Response()
        llm = _LLM(response)
        placeholder = threading.Event()
        placeholders = []
        posted = []
        pre = {"conv_id": 1, "sources": []}
        if contract:
            pre["contract_data"] = {"blocks": ["one"], "level": "low", "docs": []}
        namespace.update(
            pre=pre,
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
            _post_placeholder=lambda pre: (placeholders.append(pre), placeholder.set()),
            _post=lambda *args: posted.append(args),
        )
        tree = ast.parse((BACKEND / "main.py").read_text(encoding="utf-8"))
        chat = next(node for node in tree.body if getattr(node, "name", None) == "chat")
        stream_node = next(
            node for node in chat.body if isinstance(node, ast.AsyncFunctionDef) and node.name == "stream"
        )
        exec(
            compile(
                ast.Module(body=_chat_ownership_locals(chat) + [stream_node], type_ignores=[]),
                str(BACKEND / "main.py"),
                "exec",
            ),
            namespace,
        )
        inner = namespace["stream"]()
        outer = namespace["_stream_with_status_preframe"](inner)
        assert json.loads((await anext(outer))[6:]) == {"type": "status", "msg": "正在思考…"}
        if contract and not status_only:
            assert json.loads((await anext(outer))[6:])["type"] == "step"
        if not status_only:
            assert json.loads((await anext(outer))[6:]) == {"content": "first"}
        await outer.aclose()
        if not status_only:
            assert response.closed, "Actual main stream left the provider response open after client close"
        assert response.reads == int(not status_only) and posted == []
        assert len(llm.async_client.calls) == int(not status_only)
        _assert_slot_released(guard)
        assert await asyncio.to_thread(placeholder.wait, 0.5), "Cancellation lost the existing failure placeholder"
        assert placeholders == [pre], "Cancellation scheduled duplicate failure placeholders"

    asyncio.run(scenario())


def test_normal_chat_has_single_first_status_and_no_failure_placeholder():
    async def scenario():
        namespace, _ = _production()
        posted, placeholders = [], []
        pre = {"conv_id": 1, "sources": []}

        async def run_in_threadpool(fn, *args):
            return fn(*args)

        namespace.update(
            pre=pre,
            cache_hit={"answer": "cached"},
            user=SimpleNamespace(id=1),
            t0=time.perf_counter(),
            text="question",
            routing_metrics=SimpleNamespace(record=lambda *args, **kwargs: None),
            log_account=lambda **kwargs: None,
            run_in_threadpool=run_in_threadpool,
            _post=lambda *args: posted.append(args),
            _post_placeholder=lambda pre: placeholders.append(pre),
        )
        tree = ast.parse((BACKEND / "main.py").read_text(encoding="utf-8"))
        chat = next(node for node in tree.body if getattr(node, "name", None) == "chat")
        stream = next(node for node in chat.body if isinstance(node, ast.AsyncFunctionDef) and node.name == "stream")
        exec(
            compile(
                ast.Module(body=_chat_ownership_locals(chat) + [stream], type_ignores=[]),
                str(BACKEND / "main.py"),
                "exec",
            ),
            namespace,
        )
        actual = [frame async for frame in namespace["_stream_with_status_preframe"](namespace["stream"]())]
        assert len(actual) == 4
        assert json.loads(actual[0][6:]) == {"type": "status", "msg": "正在思考…"}
        assert json.loads(actual[1][6:]) == {"content": "cached"}
        assert json.loads(actual[2][6:]) == {"conversation_id": 1, "sources": []}
        assert actual[3] == "data: [DONE]\n\n"
        assert posted == [(pre, "cached", False)] and placeholders == []

    asyncio.run(scenario())


def _real_chat_response(namespace):
    """Build the actual chat return expression, including its selected response class."""
    path = BACKEND / "main.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    chat = next(node for node in tree.body if getattr(node, "name", None) == "chat")
    stream = next(node for node in chat.body if isinstance(node, ast.AsyncFunctionDef) and node.name == "stream")
    exec(
        compile(ast.Module(body=_chat_ownership_locals(chat) + [stream], type_ignores=[]), str(path), "exec"), namespace
    )
    final_return = chat.body[-1]
    assert isinstance(final_return, ast.Return)
    return eval(compile(ast.Expression(body=final_return.value), str(path), "eval"), namespace)


@pytest.mark.parametrize("contract", [False, True], ids=["ordinary", "contract"])
def test_asgi_disconnect_during_blocked_content_send_owns_body_cleanup(contract):
    async def scenario():
        namespace, guard = _production()
        provider = _Response()
        llm = _LLM(provider)
        placeholder_ready = threading.Event()
        placeholders, posted = [], []
        pre = {"conv_id": 1, "sources": []}
        if contract:
            pre["contract_data"] = {"blocks": ["one"], "level": "low", "docs": []}
        namespace.update(
            pre=pre,
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
            _post_placeholder=lambda pre: (placeholders.append(pre), placeholder_ready.set()),
            _post=lambda *args: posted.append(args),
        )
        response = _real_chat_response(namespace)
        content_send_entered = anyio.Event()
        sent_types = []

        async def send(message):
            if message["type"] != "http.response.body" or not message["body"]:
                return
            frame = json.loads(message["body"].decode("utf-8")[6:])
            sent_types.append(frame.get("type", "content"))
            if frame.get("content") == "first":
                content_send_entered.set()
                await anyio.sleep_forever()

        async def receive():
            await content_send_entered.wait()
            return {"type": "http.disconnect"}

        with anyio.fail_after(2):
            await response({"type": "http", "asgi": {"spec_version": "2.3"}}, receive, send)
        slot_available = guard._sem.acquire(blocking=False)
        if slot_available:
            guard._sem.release()
        if provider.closed:
            assert await asyncio.to_thread(placeholder_ready.wait, 0.5)
        observed = {
            "provider_closed": provider.closed,
            "provider_reads": provider.reads,
            "active_slot_available": slot_available,
            "placeholder_count": len(placeholders),
            "normal_post_count": len(posted),
        }
        print(json.dumps(observed, sort_keys=True))
        assert observed == {
            "provider_closed": True,
            "provider_reads": 1,
            "active_slot_available": True,
            "placeholder_count": 1,
            "normal_post_count": 0,
        }, "ASGI request returned before closing its suspended body iterator"
        assert sent_types == (["status", "step", "content"] if contract else ["status", "content"])
        assert response.body_iterator is not None and llm.streams, "Keep body/provider references alive; no GC proof"

    anyio.run(scenario, backend="asyncio")


def test_asgi_normal_completion_preserves_single_status_and_post():
    async def scenario():
        namespace, _ = _production()
        posted, placeholders = [], []
        pre = {"conv_id": 1, "sources": []}

        async def run_in_threadpool(fn, *args):
            return fn(*args)

        namespace.update(
            pre=pre,
            cache_hit={"answer": "cached"},
            user=SimpleNamespace(id=1),
            t0=time.perf_counter(),
            text="question",
            routing_metrics=SimpleNamespace(record=lambda *args, **kwargs: None),
            log_account=lambda **kwargs: None,
            run_in_threadpool=run_in_threadpool,
            _post=lambda *args: posted.append(args),
            _post_placeholder=lambda pre: placeholders.append(pre),
        )
        response = _real_chat_response(namespace)
        sent = []

        async def send(message):
            sent.append(message)

        async def receive():
            await anyio.sleep_forever()

        with anyio.fail_after(2):
            await response({"type": "http", "asgi": {"spec_version": "2.3"}}, receive, send)
        frames = [
            message["body"].decode("utf-8")
            for message in sent
            if message["type"] == "http.response.body" and message["body"]
        ]
        assert len(frames) == 4
        assert json.loads(frames[0][6:]) == {"type": "status", "msg": "正在思考…"}
        assert json.loads(frames[1][6:]) == {"content": "cached"}
        assert json.loads(frames[2][6:]) == {"conversation_id": 1, "sources": []}
        assert frames[3] == "data: [DONE]\n\n"
        assert sent[-1] == {"type": "http.response.body", "body": b"", "more_body": False}
        assert posted == [(pre, "cached", False)] and placeholders == []

    anyio.run(scenario, backend="asyncio")


def test_application_import_boundary_stays_isolated():
    # The normal suite has already imported main through conftest.  This helper
    # must neither import nor replace application modules in either entry mode.
    names = {"main", "rag_chain", "database", "models", "llm_registry"}
    before = {name: sys.modules.get(name) for name in names}
    _production()
    assert all(sys.modules.get(name) is module for name, module in before.items())


def _buffered_namespace(llm):
    namespace, guard = _production()
    namespace.update(
        dataclass=dataclass,
        replace=replace,
        date=date,
        EXIT_LIGHT="light-output",
        settings=SimpleNamespace(fast_path_law_version_check=False),
        _safe_pick=lambda *args: ("light", llm, False),
        registry=SimpleNamespace(get=lambda: llm),
        clean_answer=lambda text: text,
        _token_charge=lambda *args: 1,
        quality=SimpleNamespace(self_check=lambda *args: SimpleNamespace(ok=True)),
        _law_version_gate=lambda answer, *args, **kwargs: (answer, False),
    )
    _extract(
        BACKEND / "main.py",
        {"_LightResult", "_ainvoke_cancel_safe", "_light_buffered", "_light_buffered_locked", "_invoke_llm"},
        namespace,
    )
    return namespace, guard


@pytest.mark.parametrize("name", ["_light_buffered", "_invoke_llm"])
def test_buffered_cancel_propagates_and_releases_capacity(name):
    started = threading.Event()
    release = threading.Event()
    state = {"async_cancelled": False}

    class WaitingLLM:
        def invoke(self, messages):
            started.set()
            assert release.wait(3), "test-owned watchdog did not release the sync provider"
            return SimpleNamespace(content="answer")

        async def ainvoke(self, messages):
            started.set()
            try:
                await asyncio.Event().wait()
            finally:
                state["async_cancelled"] = True

    namespace, guard = _buffered_namespace(WaitingLLM())
    call = namespace[name]
    args = ({"sources": []}, []) if name == "_light_buffered" else ([],)
    watchdog = threading.Timer(1.0, release.set)

    async def request():
        # Execute the actual legacy/current helper using its real calling convention.
        if inspect.iscoroutinefunction(call):
            await call(*args)
        else:
            await run_in_threadpool(call, *args)

    async def scenario():
        async with anyio.create_task_group() as tasks:
            tasks.start_soon(request)
            deadline = time.monotonic() + 3
            while not started.is_set() and time.monotonic() < deadline:
                await anyio.sleep(0.005)
            assert started.is_set(), "provider was never entered"
            watchdog.start()
            cancelled_at = time.monotonic()
            tasks.cancel_scope.cancel()
        assert time.monotonic() - cancelled_at < 0.3, "buffered provider ignored request cancellation"
        assert state["async_cancelled"], "cancellation did not reach the asynchronous provider"
        _assert_slot_released(guard)

    try:
        anyio.run(scenario)
    finally:
        release.set()
        watchdog.cancel()
        if watchdog.ident is not None:
            watchdog.join(2)


@pytest.mark.parametrize("name", ["_light_buffered", "_invoke_llm"])
def test_buffered_normal_completion_keeps_answer_and_releases_capacity(name):
    class AnsweringLLM:
        def invoke(self, messages):
            return SimpleNamespace(content="answer")

        async def ainvoke(self, messages):
            return self.invoke(messages)

    namespace, guard = _buffered_namespace(AnsweringLLM())
    call = namespace[name]
    args = ({"sources": []}, []) if name == "_light_buffered" else ([],)

    async def scenario():
        result = await call(*args) if inspect.iscoroutinefunction(call) else await run_in_threadpool(call, *args)
        if name == "_light_buffered":
            assert result.answer == "answer" and result.verdict == "pass" and result.usage == 1
        else:
            assert result == "answer"
        _assert_slot_released(guard)

    anyio.run(scenario)


@pytest.mark.parametrize("name", ["_light_buffered", "_invoke_llm"])
def test_chat_directly_awaits_cancelable_buffered_helpers(name):
    tree = ast.parse((BACKEND / "main.py").read_text(encoding="utf-8-sig"))
    chat = next(node for node in tree.body if getattr(node, "name", None) == "chat")
    calls = [node.value for node in ast.walk(chat) if isinstance(node, ast.Await) and isinstance(node.value, ast.Call)]
    assert any(isinstance(call.func, ast.Name) and call.func.id == name for call in calls)


@pytest.mark.parametrize("route", ["light", "light-escalation", "empty-stream-fallback"])
@pytest.mark.parametrize("streaming", [False, True], ids=["json-sdk", "streaming-sdk"])
def test_buffered_asgi_disconnect_closes_real_sdk_request_before_pool_cleanup(route, streaming):
    import httpx
    from langchain_openai import ChatOpenAI
    from openai import AsyncOpenAI, OpenAI

    started = threading.Event()

    async def scenario(base_url, peer_closed):
        options = {"api_key": "test-only-placeholder", "base_url": base_url, "max_retries": 0, "timeout": 5}
        sdk = AsyncOpenAI(http_client=httpx.AsyncClient(trust_env=False), **options)
        sync_sdk = OpenAI(http_client=httpx.Client(trust_env=False), **options)
        model = ChatOpenAI(
            client=sync_sdk.chat.completions,
            async_client=sdk.chat.completions,
            streaming=streaming,
            model="test-model",
            **options,
        )
        namespace, guard = _buffered_namespace(model)
        placeholder_ready = threading.Event()
        placeholders, posted, sent = [], [], []
        pre = {"conv_id": 1, "sources": []}

        if route == "light-escalation":

            class FirstAnswer:
                async def ainvoke(self, messages):
                    return SimpleNamespace(content="first answer")

            namespace["_safe_pick"] = lambda *args: ("light", FirstAnswer(), False)
            namespace["quality"] = SimpleNamespace(self_check=lambda *args: SimpleNamespace(ok=False))

        async def empty_stream(*args, **kwargs):
            # Select the actual fallback branch without another provider connection.
            if False:
                yield ""

        namespace.update(
            pre=pre,
            body=SimpleNamespace(no_cache=True),
            cache_hit=None,
            cache_key=None,
            use_router=False,
            use_light=route != "empty-stream-fallback",
            strategy="answer",
            flag_key=None,
            flag_llm=model,
            messages=[HumanMessage(content="cancel-test")],
            registry=SimpleNamespace(
                get=lambda: model, variant=lambda disabled: model, pick=lambda *args: ("flag", model)
            ),
            stream_with_retry=empty_stream,
            _exit_law_as_of=lambda *args: None,
            _post_placeholder=lambda value: (placeholders.append(value), placeholder_ready.set()),
            _post=lambda *args: posted.append(args),
        )
        response = _real_chat_response(namespace)

        async def send(message):
            sent.append(message)

        async def receive():
            deadline = time.monotonic() + 3
            while not started.is_set() and time.monotonic() < deadline:
                await anyio.sleep(0.005)
            assert started.is_set(), "buffered SDK request was never entered"
            return {"type": "http.disconnect"}

        try:
            with anyio.fail_after(4):
                await response({"type": "http", "asgi": {"spec_version": "2.3"}}, receive, send)
            assert await asyncio.to_thread(peer_closed.wait, 1), "cancelled request retained its upstream connection"
            assert not sdk.is_closed(), "client cleanup must not earn the disconnect proof"
            _assert_slot_released(guard)
            assert await asyncio.to_thread(placeholder_ready.wait, 0.5)
            assert placeholders == [pre] and posted == []
            frames = [
                message["body"].decode()
                for message in sent
                if message["type"] == "http.response.body" and message.get("body")
            ]
            assert len(frames) == 1 and json.loads(frames[0][6:])["type"] == "status"
        finally:
            await sdk.close()
            sync_sdk.close()

    with _waiting_http_provider(False, streaming=streaming, started=started) as (base_url, peer_closed):
        anyio.run(scenario, base_url, peer_closed)


def test_buffered_provider_exception_preserves_original_and_releases_slot():
    original = ValueError("test-only provider failure")

    class FailingLLM:
        async def ainvoke(self, messages):
            raise original

    namespace, guard = _buffered_namespace(FailingLLM())

    async def scenario():
        with pytest.raises(ValueError) as caught:
            await namespace["_invoke_llm"]([])
        assert caught.value is original
        _assert_slot_released(guard)

    anyio.run(scenario)


def test_buffered_cleanup_exception_does_not_replace_parent_cancellation(capsys):
    started = asyncio.Event()

    class FailingCleanupLLM:
        async def ainvoke(self, messages):
            started.set()
            try:
                await asyncio.Event().wait()
            finally:
                raise RuntimeError("test-only cleanup details must not be logged")

    namespace, guard = _buffered_namespace(FailingCleanupLLM())

    async def scenario():
        task = asyncio.create_task(namespace["_invoke_llm"]([]))
        await started.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        _assert_slot_released(guard)

    anyio.run(scenario)
    log = capsys.readouterr().out
    assert "[llm-cancel-cleanup] failed: RuntimeError" in log
    assert "test-only cleanup details" not in log
