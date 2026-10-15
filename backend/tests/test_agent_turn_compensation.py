"""D-34 request ownership tests; run with --noconftest, no model/startup imports.

Execute real main functions from AST, real worker dispatch and SQLite writes.
Only the Agent service boundary is substituted to select deterministic outcomes.
"""

import ast
import asyncio
import json
import logging
import sys
import threading
from contextlib import aclosing, suppress
from datetime import date, datetime
from pathlib import Path
from types import SimpleNamespace
from weakref import WeakValueDictionary

import anyio
import pytest
from fastapi import Depends, FastAPI, HTTPException
from fastapi.concurrency import run_in_threadpool
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, text
from sqlalchemy.orm import sessionmaker
from starlette.requests import Request
from starlette.responses import StreamingResponse

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

import routing_metrics  # noqa: E402
from agent.chat_integration import AgentPublicResult, encode_sse_stream, serialize_agent_events  # noqa: E402
from agent.controller import (  # noqa: E402
    _DEFAULT_RUN_LOCKS,
    RESUME_LAW_AS_OF_DETAIL,
    RESUME_NOT_FOUND_DETAIL,
    ResumeLawAsOfConflict,
    ResumeRunConflict,
    ResumeRunNotFound,
    resume_with_user_fact,
)
from agent.repository import create_run  # noqa: E402
from agent.schemas import AgentStatus, LegalAgentState, LegalIssue, UnknownFact  # noqa: E402
from llm_guard import LLMBusyError  # noqa: E402
from models import AgentRun, Base, Conversation, Message, User  # noqa: E402
from request_bootstrap import (
    FastPathDependencies,  # noqa: E402
    RequestBootstrap,  # noqa: E402
)
from schemas import ChatIn  # noqa: E402

NO_RESPONSE = "服务暂时无响应，请稍后重试。"
STOPPED = "本次回答已停止，未生成完整内容。"


@pytest.fixture
def db(tmp_path):
    """Model-free SQLite fixture for adjacent state/finalization regression tests."""
    engine = create_engine(f"sqlite:///{tmp_path / 'agent-regression.db'}")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, autoflush=False)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture
def store(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'turn.db'}", connect_args={"check_same_thread": False})
    sessions = sessionmaker(bind=engine, autoflush=False)
    Base.metadata.create_all(engine)
    with sessions() as db:
        db.add(User(id=1, username="synthetic-owner", password_hash="synthetic-only"))
        db.add(Conversation(id=1, user_id=1, message_count=1))
        db.add(Message(conversation_id=1, role="user", content="已接受的合成提问"))
        db.commit()
    try:
        yield sessions
    finally:
        engine.dispose()


def snapshot(sessions):
    with sessions() as db:
        rows = [(row.role, row.content) for row in db.query(Message).order_by(Message.id)]
        assert db.get(Conversation, 1).message_count == len(rows)
        return rows


def namespace(sessions, service):
    scope = {
        "asyncio": asyncio,
        "Event": threading.Event,
        "suppress": suppress,
        "CancelScope": anyio.CancelScope,
        "Request": Request,
        "run_in_threadpool": run_in_threadpool,
        "execute_agent_request": service,
        "SessionLocal": sessions,
        "Conversation": Conversation,
        "Message": Message,
        "AgentRun": AgentRun,
        "func": func,
        "text": text,
        "datetime": datetime,
        "logging": logging,
        "StreamingResponse": StreamingResponse,
        "encode_sse_stream": encode_sse_stream,
        "serialize_agent_events": serialize_agent_events,
        "Depends": Depends,
        "get_current_user": lambda: None,
        "User": User,
        "ChatIn": ChatIn,
        "HTTPException": HTTPException,
        "LLMBusyError": LLMBusyError,
        "RequestBootstrap": RequestBootstrap,
        "LegalAgentState": LegalAgentState,
        "date": date,
        "_DEFAULT_RUN_LOCKS": _DEFAULT_RUN_LOCKS,
        "resume_with_user_fact": resume_with_user_fact,
        "ResumeRunNotFound": ResumeRunNotFound,
        "ResumeRunConflict": ResumeRunConflict,
        "ResumeLawAsOfConflict": ResumeLawAsOfConflict,
        "RESUME_NOT_FOUND_DETAIL": RESUME_NOT_FOUND_DETAIL,
        "RESUME_LAW_AS_OF_DETAIL": RESUME_LAW_AS_OF_DETAIL,
        "_client_law_as_of": lambda body: body.law_as_of,
        "_client_case_domain": lambda body: None,
        "answer_cache": SimpleNamespace(generation=lambda: 0),
        "_cutoff": lambda: None,
        "settings": SimpleNamespace(agent_enabled=True, feature_router=False, feature_study_retrieval=False),
        "routing_metrics": routing_metrics,
        "FastPathDependencies": FastPathDependencies,
        "query_understand": SimpleNamespace(is_meta_study=lambda *args: False),
        "ks": SimpleNamespace(search_qa=lambda *args: []),
        "_build_messages": lambda pre: [],
        "complexity": SimpleNamespace(assess=lambda *args: ("text", "flag")),
        "_stream_with_status_preframe": lambda stream: stream,
        "make_agent_correlation_id": lambda **kwargs: "synthetic-correlation",
        "decide_gate": lambda bootstrap: SimpleNamespace(mode="agent_path", reason_codes=[]),
        "_observe_agent_gate": lambda *args, **kwargs: None,
        "_stable_agent_request_seed": lambda *args: "synthetic-seed",
        "time": __import__("time"),
        "finalize_verified_agent_answer": lambda *args: None,
        "_record_actual_agent_route": lambda *args, **kwargs: None,
        "app": SimpleNamespace(post=lambda *args, **kwargs: lambda fn: fn),
        "limiter": SimpleNamespace(limit=lambda *args: lambda fn: fn),
        "_chat_turn_locks": WeakValueDictionary(),
        "_CHAT_TURN_WAIT_SECONDS": 3,
        "aclosing": aclosing,
        "logger": logging.getLogger("test-agent-turn"),
    }
    tree = ast.parse((BACKEND / "main.py").read_text(encoding="utf-8-sig"))
    functions = {
        "_execute_agent_observing_disconnect",
        "_agent_streaming_response",
        "_post_placeholder",
        "chat",
        "_serialized_chat",
        "_resume_bootstrap",
        "_resume_law_as_of",
        "_resolve_chat_conversation",
        "_require_chat_conversation",
        "_acquire_chat_turn",
        "_ChatStreamingResponse",
        "fallback_to_fast_path",
        "_prepare_fast_path_only",
        "_join_owned_task",
    }
    constants = {"_ERROR_NO_RESPONSE", "_PLACEHOLDER_NO_RESPONSE", "_PLACEHOLDER_STOPPED"}
    nodes = []
    for node in tree.body:
        if getattr(node, "name", None) in functions:
            nodes.append(node)
        elif isinstance(node, ast.Assign) and any(getattr(target, "id", None) in constants for target in node.targets):
            nodes.append(node)
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(BACKEND / "main.py"), "exec"), scope)
    closing = next(
        node
        for node in ast.parse((BACKEND / "rag_chain.py").read_text(encoding="utf-8-sig")).body
        if getattr(node, "name", None) == "ClosingStream"
    )
    exec(compile(ast.Module(body=[closing], type_ignores=[]), str(BACKEND / "rag_chain.py"), "exec"), scope)
    for name in (
        "_rewrite_for_retrieval",
        "scenario_supplement_docs",
        "retrieve_exam",
        "cheating_docs",
        "build_contract_data",
        "retrieve",
        "is_consumer_clause_scenario",
        "consumer_clause_docs",
        "is_consumer_fraud_scenario",
        "consumer_fraud_docs",
        "format_docs",
    ):
        scope[name] = lambda *args, **kwargs: None
    scope["prepare_fast_path"] = lambda bootstrap, **kwargs: {
        "conv_id": bootstrap.conv_id,
        "intent": "legal_query",
        "recent": [],
        "sources": [],
    }
    return scope


def public_result(outcome="failed", reason="PLANNER_POLICY_VIOLATION"):
    values = dict(outcome=outcome, reason_code=reason, conversation_id=1, state_version=1)
    if outcome == "clarification":
        values.update(run_id="synthetic-run", prompt="工资支付日是什么？", issue_id="issue-a")
    if outcome == "completed":
        values.update(run_id="synthetic-run", answer="合成终稿", coverage_status="full")
    return AgentPublicResult(**values)


def request(disconnected=False):
    async def receive():
        return {"type": "http.disconnect"} if disconnected else {"type": "http.request", "body": b""}

    return Request({"type": "http", "asgi": {"spec_version": "2.3"}}, receive)


async def execute(scope, sessions, *, disconnected=False, run_id=None):
    with sessions() as db:
        return await scope["_execute_agent_observing_disconnect"](
            request(disconnected),
            db=db,
            user_id=1,
            settings=SimpleNamespace(),
            bootstrap=SimpleNamespace(conv_id=1),
            finalizer=lambda *args: None,
            run_id=run_id,
        )


def test_failed_agent_writes_one_failure_before_response(store):
    scope = namespace(store, lambda **kwargs: public_result())
    result = asyncio.run(execute(scope, store))
    assert result.outcome == "failed"
    assert snapshot(store) == [("user", "已接受的合成提问"), ("assistant", NO_RESPONSE)]


def test_service_exception_records_failure_and_preserves_exception(store):
    def service(**kwargs):
        raise ValueError("synthetic service exception")

    scope = namespace(store, service)
    with pytest.raises(ValueError, match="synthetic service exception"):
        asyncio.run(execute(scope, store))
    assert snapshot(store) == [("user", "已接受的合成提问"), ("assistant", NO_RESPONSE)]


def test_disconnect_records_stopped_not_server_failure(store):
    def service(**kwargs):
        assert kwargs["cancelled"]()
        return public_result(reason="CLIENT_DISCONNECTED")

    scope = namespace(store, service)
    asyncio.run(execute(scope, store, disconnected=True))
    assert snapshot(store) == [("user", "已接受的合成提问"), ("assistant", STOPPED)]


@pytest.mark.parametrize("outcome", ["clarification", "fallback"])
def test_clarification_and_fallback_keep_existing_storage_contract(store, outcome):
    scope = namespace(store, lambda **kwargs: public_result(outcome))
    result = asyncio.run(execute(scope, store))
    assert result.outcome == outcome
    assert snapshot(store) == [("user", "已接受的合成提问")]


def test_completed_answer_is_not_replaced_or_duplicated(store):
    def service(**kwargs):
        db = kwargs["db"]
        db.add(Message(conversation_id=1, role="assistant", content="合成终稿"))
        db.get(Conversation, 1).message_count += 1
        db.commit()
        return public_result("completed")

    scope = namespace(store, service)
    asyncio.run(execute(scope, store))
    assert snapshot(store) == [("user", "已接受的合成提问"), ("assistant", "合成终稿")]


def test_commit_then_service_exception_does_not_add_placeholder(store):
    def service(**kwargs):
        db = kwargs["db"]
        db.add(Message(conversation_id=1, role="assistant", content="合成终稿"))
        db.get(Conversation, 1).message_count += 1
        db.commit()
        raise ValueError("synthetic post-commit failure")

    scope = namespace(store, service)
    with pytest.raises(ValueError, match="synthetic post-commit failure"):
        asyncio.run(execute(scope, store))
    assert snapshot(store) == [("user", "已接受的合成提问"), ("assistant", "合成终稿")]


def test_guarded_placeholder_reentry_is_idempotent_even_with_fresh_context(store):
    scope = namespace(store, lambda **kwargs: public_result())
    for _ in range(2):
        scope["_post_placeholder"]({"conv_id": 1, "agent_user_id": 1, "agent_turn_after": 1})
    assert snapshot(store) == [("user", "已接受的合成提问"), ("assistant", NO_RESPONSE)]


def test_guarded_placeholder_rejects_foreign_conversation(store):
    scope = namespace(store, lambda **kwargs: public_result())
    with pytest.raises(RuntimeError):
        scope["_post_placeholder"]({"conv_id": 1, "agent_user_id": 2, "agent_turn_after": 1})
    assert snapshot(store) == [("user", "已接受的合成提问")]


def test_guarded_placeholder_refuses_to_compensate_a_later_user_turn(store):
    with store() as db:
        db.add(Message(conversation_id=1, role="user", content="不属于该请求的新输入"))
        db.get(Conversation, 1).message_count += 1
        db.commit()
    scope = namespace(store, lambda **kwargs: public_result())
    with pytest.raises(RuntimeError):
        scope["_post_placeholder"]({"conv_id": 1, "agent_user_id": 1, "agent_turn_after": 1})
    assert [role for role, _ in snapshot(store)] == ["user", "user"]


def test_cancel_waits_for_worker_before_session_close_and_records_once(store):
    entered, released = threading.Event(), threading.Event()

    def service(**kwargs):
        entered.set()
        assert released.wait(3)
        assert kwargs["cancelled"]()
        # The route must not close this worker's session during cancellation.
        kwargs["db"].query(Message).count()
        return public_result(reason="CLIENT_DISCONNECTED")

    scope = namespace(store, service)

    async def scenario():
        task = asyncio.create_task(execute(scope, store))
        assert await asyncio.to_thread(entered.wait, 3)
        task.cancel()
        await asyncio.sleep(0)
        assert not task.done(), "worker must be joined before route/session ownership ends"
        released.set()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(scenario())
    assert snapshot(store) == [("user", "已接受的合成提问"), ("assistant", STOPPED)]


def test_cancelled_fallback_does_not_leave_an_unanswered_turn(store):
    entered, released = threading.Event(), threading.Event()

    def service(**kwargs):
        entered.set()
        assert released.wait(3)
        return public_result("fallback", "TOOL_UNAVAILABLE")

    scope = namespace(store, service)

    async def scenario():
        task = asyncio.create_task(execute(scope, store))
        assert await asyncio.to_thread(entered.wait, 3)
        task.cancel()
        await asyncio.sleep(0)
        released.set()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(scenario())
    assert snapshot(store) == [("user", "已接受的合成提问"), ("assistant", STOPPED)]


def test_resumed_failure_keeps_fact_only_input_contract_and_records_result(store):
    scope = namespace(store, lambda **kwargs: public_result())
    asyncio.run(execute(scope, store, run_id="same-run"))
    assert snapshot(store) == [("user", "已接受的合成提问"), ("assistant", NO_RESPONSE)]


def test_public_clarification_still_has_no_failure_event(store):
    scope = namespace(store, lambda **kwargs: public_result("clarification"))

    async def scenario():
        result = await execute(scope, store)
        response = scope["_agent_streaming_response"](result)
        return [frame async for frame in response.body_iterator]

    frames = asyncio.run(scenario())
    events = [json.loads(frame[6:]) for frame in frames if frame.startswith("data: {")]
    assert [event["type"] for event in events] == ["agent_status", "clarification"]
    assert snapshot(store) == [("user", "已接受的合成提问")]


def test_cancel_on_fallback_return_before_handoff_still_records_stop(store):
    scope = namespace(store, lambda **kwargs: public_result("fallback", "TOOL_UNAVAILABLE"))

    async def scenario():
        parent = asyncio.current_task()
        original = scope["run_in_threadpool"]

        async def at_boundary(fn, *args, **kwargs):
            if fn is scope["execute_agent_request"]:
                result = fn(*args, **kwargs)
                asyncio.get_running_loop().call_soon(parent.cancel)
                return result
            return await original(fn, *args, **kwargs)

        scope["run_in_threadpool"] = at_boundary
        with pytest.raises(asyncio.CancelledError):
            await execute(scope, store)

    asyncio.run(scenario())
    assert snapshot(store) == [("user", "已接受的合成提问"), ("assistant", STOPPED)]


def waiting_run(sessions):
    state = LegalAgentState(
        status=AgentStatus.WAITING_USER,
        steps=1,
        clarifications=1,
        issues=[
            LegalIssue(
                issue_id="issue-a",
                question="工资请求",
                unknown_facts=[
                    UnknownFact(statement="工资支付日是什么？", why_outcome_changes="确定到期日"),
                ],
            ),
        ],
    )
    with sessions() as db:
        run = create_run(db, user_id=1, conversation_id=1, state=state)
        run.pending_question = "工资支付日是什么？"
        db.commit()
        return run.id


def api(scope):
    app = FastAPI()

    @app.post("/api/chat")
    async def endpoint(request: Request, body: ChatIn):
        return await scope["_serialized_chat"](request, body, SimpleNamespace(id=1))

    return TestClient(app)


def test_public_resume_failure_records_once_and_stale_replay_adds_nothing(store):
    run_id = waiting_run(store)
    calls = []

    def service(**kwargs):
        calls.append(kwargs["run_id"])
        return public_result()

    scope = namespace(store, service)
    payload = {"content": "每月5日", "conversation_id": 1, "agent_run_id": run_id, "agent_state_version": 0}
    with api(scope) as client:
        response = client.post("/api/chat", json=payload)
        stale = client.post("/api/chat", json=payload)
    assert response.status_code == 200
    assert '"type": "error"' in response.text
    assert stale.status_code == 409
    assert calls == [run_id]
    assert snapshot(store) == [("user", "已接受的合成提问"), ("assistant", NO_RESPONSE)]
    with store() as db:
        state = LegalAgentState.model_validate_json(db.get(AgentRun, run_id).state_json)
    assert state.issues[0].facts[0].statement == "每月5日"


@pytest.mark.parametrize("content,version,status", [("每月5日", 99, 409), ("", 0, 400)])
def test_public_resume_rejection_does_not_compensate(store, content, version, status):
    run_id = waiting_run(store)
    scope = namespace(store, lambda **kwargs: pytest.fail("rejected input must not execute Agent"))
    with api(scope) as client:
        response = client.post(
            "/api/chat",
            json={"content": content, "conversation_id": 1, "agent_run_id": run_id, "agent_state_version": version},
        )
    assert response.status_code == status
    assert snapshot(store) == [("user", "已接受的合成提问")]
    with store() as db:
        assert db.get(AgentRun, run_id).state_version == 0


def test_compensation_storage_failure_is_observable_not_a_success(store, capsys):
    scope = namespace(store, lambda **kwargs: public_result())

    def failed_write(*args):
        raise RuntimeError("synthetic sensitive value must not be logged")

    scope["_post_placeholder"] = failed_write
    with pytest.raises(RuntimeError):
        asyncio.run(execute(scope, store))
    output = capsys.readouterr().out
    assert "[agent-turn-compensate] failed: RuntimeError" in output
    assert "sensitive value" not in output
    assert snapshot(store) == [("user", "已接受的合成提问")]


def test_repeated_task_cancel_does_not_abandon_worker_or_double_write(store):
    entered, released = threading.Event(), threading.Event()

    def service(**kwargs):
        entered.set()
        assert released.wait(3)
        return public_result(reason="CLIENT_DISCONNECTED")

    scope = namespace(store, service)

    async def scenario():
        task = asyncio.create_task(execute(scope, store))
        assert await asyncio.to_thread(entered.wait, 3)
        for _ in range(4):
            task.cancel()
            await asyncio.sleep(0)
        assert not task.done()
        released.set()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(scenario())
    assert snapshot(store) == [("user", "已接受的合成提问"), ("assistant", STOPPED)]


def test_anyio_level_cancellation_joins_worker_and_preserves_stop(store):
    entered, released = threading.Event(), threading.Event()

    def service(**kwargs):
        entered.set()
        assert released.wait(3)
        assert kwargs["cancelled"]()
        return public_result(reason="CLIENT_DISCONNECTED")

    scope = namespace(store, service)

    async def scenario():
        with anyio.fail_after(4):
            async with anyio.create_task_group() as group:

                async def owner():
                    await execute(scope, store)

                group.start_soon(owner)
                assert await asyncio.to_thread(entered.wait, 3)
                group.cancel_scope.cancel()
                released.set()

    anyio.run(scenario, backend="asyncio")
    assert snapshot(store) == [("user", "已接受的合成提问"), ("assistant", STOPPED)]


@pytest.mark.parametrize("outcome", ["completed", "clarification", "failed"])
def test_disconnect_during_response_start_does_not_rewrite_stored_result(store, outcome):
    def service(**kwargs):
        if outcome == "completed":
            db = kwargs["db"]
            db.add(Message(conversation_id=1, role="assistant", content="合成终稿"))
            db.get(Conversation, 1).message_count += 1
            db.commit()
        return public_result(outcome)

    scope = namespace(store, service)

    async def scenario():
        result = await execute(scope, store)
        before = snapshot(store)
        response = scope["_agent_streaming_response"](result)
        headers = anyio.Event()

        async def send(message):
            if message["type"] == "http.response.start":
                headers.set()
                await anyio.sleep_forever()

        async def receive():
            await headers.wait()
            return {"type": "http.disconnect"}

        with anyio.fail_after(3):
            await response({"type": "http", "asgi": {"spec_version": "2.3"}}, receive, send)
        assert snapshot(store) == before

    anyio.run(scenario, backend="asyncio")


def test_same_run_can_record_a_stop_then_a_separately_accepted_resume_failure(store):
    run_id = waiting_run(store)
    scope = namespace(store, lambda **kwargs: public_result(reason="CLIENT_DISCONNECTED"))
    asyncio.run(execute(scope, store, disconnected=True, run_id=run_id))
    scope["execute_agent_request"] = lambda **kwargs: public_result()
    with api(scope) as client:
        response = client.post(
            "/api/chat",
            json={
                "content": "每月5日",
                "conversation_id": 1,
                "agent_run_id": run_id,
                "agent_state_version": 0,
            },
        )
    assert response.status_code == 200
    assert snapshot(store) == [
        ("user", "已接受的合成提问"),
        ("assistant", STOPPED),
        ("assistant", NO_RESPONSE),
    ]


def test_cancel_during_result_write_waits_for_commit_and_keeps_failure_cause(store):
    entered, released = threading.Event(), threading.Event()
    scope = namespace(store, lambda **kwargs: public_result())
    original = scope["_post_placeholder"]

    def gated_write(pre, reason="no_response"):
        entered.set()
        assert released.wait(3)
        original(pre, reason)

    scope["_post_placeholder"] = gated_write

    async def scenario():
        task = asyncio.create_task(execute(scope, store))
        assert await asyncio.to_thread(entered.wait, 3)
        task.cancel()
        await asyncio.sleep(0)
        task.cancel()
        await asyncio.sleep(0)
        assert not task.done()
        released.set()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(scenario())
    # Failure preceded cancellation; the later transport stop must not relabel it.
    assert snapshot(store) == [("user", "已接受的合成提问"), ("assistant", NO_RESPONSE)]


def resume_body(store):
    return ChatIn(content="每月5日", conversation_id=1, agent_run_id=waiting_run(store), agent_state_version=0)


def test_public_disconnected_fallback_does_not_enter_fast_path(store):
    scope = namespace(store, lambda **kwargs: public_result("fallback", "TOOL_UNAVAILABLE"))
    scope["fallback_to_fast_path"] = lambda *args, **kwargs: pytest.fail("stopped turn must not hand off")
    body = resume_body(store)
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(scope["chat"](request(True), body, SimpleNamespace(id=1)))
    assert snapshot(store) == [("user", "已接受的合成提问"), ("assistant", STOPPED)]


def test_public_cancel_during_fallback_preparation_waits_and_records_once(store):
    entered, released = threading.Event(), threading.Event()
    scope = namespace(store, lambda **kwargs: public_result("fallback", "TOOL_UNAVAILABLE"))
    body = resume_body(store)

    def prepare(*args, **kwargs):
        entered.set()
        assert released.wait(3)
        return {"conv_id": 1}

    scope["fallback_to_fast_path"] = prepare

    async def scenario():
        task = asyncio.create_task(scope["chat"](request(), body, SimpleNamespace(id=1)))
        assert await asyncio.to_thread(entered.wait, 3)
        task.cancel()
        await asyncio.sleep(0)
        assert not task.done(), "preparation worker must retain conversation ownership"
        released.set()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(scenario())
    assert snapshot(store) == [("user", "已接受的合成提问"), ("assistant", STOPPED)]


def test_public_cancel_after_resume_commit_waits_before_session_close(store):
    entered, released = threading.Event(), threading.Event()
    scope = namespace(store, lambda **kwargs: public_result(reason="CLIENT_DISCONNECTED"))
    body = resume_body(store)
    closed = threading.Event()
    original_resume = scope["resume_with_user_fact"]

    def tracked_session():
        db = store()
        original_close = db.close

        def close():
            closed.set()
            original_close()

        db.close = close
        return db

    def resume(**kwargs):
        result = original_resume(**kwargs)
        entered.set()
        assert released.wait(3)
        assert not closed.is_set(), "CAS worker must finish before its session closes"
        return result

    scope["SessionLocal"] = tracked_session
    scope["resume_with_user_fact"] = resume

    async def scenario():
        task = asyncio.create_task(scope["chat"](request(), body, SimpleNamespace(id=1)))
        assert await asyncio.to_thread(entered.wait, 3)
        task.cancel()
        await asyncio.sleep(0)
        assert not closed.is_set()
        released.set()
        with pytest.raises(asyncio.CancelledError):
            await task

    try:
        asyncio.run(scenario())
    finally:
        released.set()
    with store() as db:
        assert db.get(AgentRun, str(body.agent_run_id)).state_version == 1
    assert snapshot(store) == [("user", "已接受的合成提问"), ("assistant", STOPPED)]


def test_normal_fallback_shares_guard_with_real_response_close(store):
    scope = namespace(store, lambda **kwargs: public_result("fallback", "TOOL_UNAVAILABLE"))
    body = resume_body(store)

    async def scenario():
        response = await scope["chat"](request(), body, SimpleNamespace(id=1))
        assert isinstance(response, scope["_ChatStreamingResponse"])
        assert snapshot(store) == [("user", "已接受的合成提问")]
        await response._on_response_close()
        await response._on_response_close()

    asyncio.run(scenario())
    assert snapshot(store) == [("user", "已接受的合成提问"), ("assistant", STOPPED)]


def test_fallback_preparation_failure_uses_same_guard_not_a_second_marker(store):
    scope = namespace(store, lambda **kwargs: public_result("fallback", "TOOL_UNAVAILABLE"))
    body = resume_body(store)

    def fail_prepare(*args, **kwargs):
        raise RuntimeError("synthetic retrieval failure")

    scope["prepare_fast_path"] = fail_prepare
    with pytest.raises(RuntimeError, match="synthetic retrieval failure"):
        asyncio.run(scope["chat"](request(), body, SimpleNamespace(id=1)))
    assert snapshot(store) == [("user", "已接受的合成提问"), ("assistant", NO_RESPONSE)]


@pytest.mark.parametrize("force_agent", [True, False])
def test_cancel_after_initial_bootstrap_commit_keeps_turn_owned(store, force_agent):
    entered, released = threading.Event(), threading.Event()
    scope = namespace(store, lambda **kwargs: public_result(reason="CLIENT_DISCONNECTED"))
    scope["decide_gate"] = lambda bootstrap: SimpleNamespace(mode="fast_path", reason_codes=[])
    scope["settings"].agent_rollout_percent = 0

    def bootstrap(*args):
        with store() as db:
            db.add(Message(conversation_id=1, role="user", content="本次新提问"))
            db.get(Conversation, 1).message_count += 1
            db.commit()
        entered.set()
        assert released.wait(3)
        return SimpleNamespace(conv_id=1)

    scope["_bootstrap_only"] = bootstrap
    body = ChatIn(content="本次新提问", conversation_id=1, force_agent=force_agent)

    async def scenario():
        task = asyncio.create_task(scope["chat"](request(), body, SimpleNamespace(id=1)))
        assert await asyncio.to_thread(entered.wait, 3)
        task.cancel()
        await asyncio.sleep(0)
        assert not task.done(), "bootstrap must finish before the accepted turn is released"
        released.set()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(scenario())
    assert snapshot(store) == [
        ("user", "已接受的合成提问"),
        ("user", "本次新提问"),
        ("assistant", STOPPED),
    ]


@pytest.mark.parametrize("boundary", ["messages", "complexity", "model"])
def test_response_construction_exception_after_fallback_must_record_result(store, boundary):
    """Preparation has returned, but no response owns result storage yet."""
    scope = namespace(store, lambda **kwargs: public_result("fallback", "TOOL_UNAVAILABLE"))
    body = resume_body(store)

    def fail_build(*args):
        raise RuntimeError("synthetic response-construction failure")

    if boundary == "messages":
        scope["_build_messages"] = fail_build
    elif boundary == "complexity":
        scope["complexity"].assess = fail_build
    else:
        scope["settings"].feature_router = True
        scope["clarify"] = SimpleNamespace(decide=lambda *args: "direct")
        scope["_clarified"] = {}
        scope["_safe_pick"] = fail_build
        body = body.model_copy(update={"no_cache": True})
    with pytest.raises(RuntimeError, match="synthetic response-construction failure"):
        asyncio.run(scope["_serialized_chat"](request(), body, SimpleNamespace(id=1)))
    assert snapshot(store) == [("user", "已接受的合成提问"), ("assistant", NO_RESPONSE)]


def test_pre_response_cancellation_cleanup_waits_for_commit_under_repeated_cancel(store):
    entered, released = threading.Event(), threading.Event()
    scope = namespace(store, lambda **kwargs: public_result("fallback", "TOOL_UNAVAILABLE"))
    body = resume_body(store)
    original_write = scope["_post_placeholder"]

    def cancel_before_response(pre):
        raise asyncio.CancelledError

    def gated_write(pre, reason="no_response"):
        entered.set()
        assert released.wait(3)
        original_write(pre, reason)

    scope["_build_messages"] = cancel_before_response
    scope["_post_placeholder"] = gated_write

    async def scenario():
        task = asyncio.create_task(scope["_serialized_chat"](request(), body, SimpleNamespace(id=1)))
        assert await asyncio.to_thread(entered.wait, 1), "response-preparation cancel needs result cleanup"
        lock = scope["_chat_turn_locks"][(1, 1)]
        for _ in range(3):
            task.cancel()
            await asyncio.sleep(0)
        assert lock.locked(), "cleanup must keep conversation ownership until commit"
        assert not task.done()
        released.set()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert not lock.locked()

    try:
        asyncio.run(scenario())
    finally:
        released.set()
    assert snapshot(store) == [("user", "已接受的合成提问"), ("assistant", STOPPED)]


@pytest.mark.parametrize("outcome", ["completed", "clarification", "failed"])
def test_terminal_agent_response_error_does_not_activate_outer_compensation(store, outcome):
    """Characterize unchanged terminal ownership: only Fast Path activates the outer guard."""

    def service(**kwargs):
        if outcome == "completed":
            db = kwargs["db"]
            db.add(Message(conversation_id=1, role="assistant", content="合成终稿"))
            db.get(Conversation, 1).message_count += 1
            db.commit()
        return public_result(outcome)

    scope = namespace(store, service)
    body = resume_body(store)

    def fail_response(result):
        raise RuntimeError("synthetic Agent response error")

    scope["_agent_streaming_response"] = fail_response
    with pytest.raises(RuntimeError, match="synthetic Agent response error"):
        asyncio.run(scope["_serialized_chat"](request(), body, SimpleNamespace(id=1)))
    expected = [("user", "已接受的合成提问")]
    if outcome != "clarification":
        expected.append(("assistant", "合成终稿" if outcome == "completed" else NO_RESPONSE))
    assert snapshot(store) == expected


def test_pre_response_compensation_failure_logs_context_and_retains_original_error(store, caplog):
    scope = namespace(store, lambda **kwargs: public_result("fallback", "TOOL_UNAVAILABLE"))
    body = resume_body(store)

    def fail_build(pre):
        raise ValueError("synthetic primary error")

    def fail_write(*args):
        raise RuntimeError("synthetic secret must not be logged")

    scope["_build_messages"] = fail_build
    scope["_post_placeholder"] = fail_write
    with (
        caplog.at_level(logging.ERROR, logger="legal.agent"),
        pytest.raises(ValueError, match="synthetic primary error"),
    ):
        asyncio.run(scope["_serialized_chat"](request(), body, SimpleNamespace(id=1)))
    record = next(record for record in caplog.records if "agent_response_compensation_failed" in record.message)
    assert (record.conv_id, record.user_id) == (1, 1)
    assert record.message.endswith("RuntimeError")
    assert "synthetic secret" not in caplog.text
    assert snapshot(store) == [("user", "已接受的合成提问")]


def test_initial_agent_fallback_response_error_records_only_current_turn(store):
    scope = namespace(store, lambda **kwargs: public_result("fallback", "TOOL_UNAVAILABLE"))

    def bootstrap(*args):
        with store() as db:
            db.add(Message(conversation_id=1, role="user", content="新提问"))
            db.get(Conversation, 1).message_count += 1
            db.commit()
        return SimpleNamespace(conv_id=1)

    def fail_build(pre):
        raise RuntimeError("synthetic response error")

    scope["_bootstrap_only"] = bootstrap
    scope["_build_messages"] = fail_build
    body = ChatIn(content="新提问", conversation_id=1, force_agent=True)
    with pytest.raises(RuntimeError, match="synthetic response error"):
        asyncio.run(scope["_serialized_chat"](request(), body, SimpleNamespace(id=1)))
    assert snapshot(store) == [
        ("user", "已接受的合成提问"),
        ("user", "新提问"),
        ("assistant", NO_RESPONSE),
    ]


def test_anyio_cancel_during_pre_response_cleanup_preserves_commit_and_lock(store):
    entered, released = threading.Event(), threading.Event()
    scope = namespace(store, lambda **kwargs: public_result("fallback", "TOOL_UNAVAILABLE"))
    body = resume_body(store)
    original_write = scope["_post_placeholder"]

    def cancel_before_response(pre):
        raise asyncio.CancelledError

    def gated_write(pre, reason="no_response"):
        entered.set()
        assert released.wait(3)
        original_write(pre, reason)

    scope["_build_messages"] = cancel_before_response
    scope["_post_placeholder"] = gated_write

    async def scenario():
        lock = None
        with anyio.fail_after(4):
            async with anyio.create_task_group() as group:

                async def owner():
                    await scope["_serialized_chat"](request(), body, SimpleNamespace(id=1))

                group.start_soon(owner)
                assert await asyncio.to_thread(entered.wait, 1)
                lock = scope["_chat_turn_locks"][(1, 1)]
                assert lock.locked()
                group.cancel_scope.cancel()
                released.set()
            assert lock is not None, "cancelled request must enter owned response cleanup"
            assert not lock.locked()

    try:
        anyio.run(scenario, backend="asyncio")
    finally:
        released.set()
    assert snapshot(store) == [("user", "已接受的合成提问"), ("assistant", STOPPED)]
