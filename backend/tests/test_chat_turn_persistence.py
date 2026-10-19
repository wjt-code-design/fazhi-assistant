"""Real SQLite writers and route/ASGI ownership, with event-controlled interleaving."""

import ast
import asyncio
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from weakref import WeakValueDictionary

import anyio
import pytest
from sqlalchemy import func
from sqlalchemy.orm import sessionmaker

import main
from models import Conversation, Message, User
from tests.test_cancel_boundaries import _extract, _route_namespace, _RouteSeam


@pytest.fixture
def store(db):
    db.add(User(id=1, username="turn-user", password_hash="test-only"))
    db.add(Conversation(id=1, user_id=1, title="turn", message_count=0))
    db.commit()
    return sessionmaker(bind=db.get_bind(), autoflush=False, autocommit=False)


def user_write(store, conv_id, content):
    with store() as db:
        db.add(Message(conversation_id=conv_id, role="user", content=content))
        db.query(Conversation).filter(Conversation.id == conv_id).update(
            {"message_count": func.coalesce(Conversation.message_count, 0) + 1}, synchronize_session=False
        )
        db.commit()


def snapshot(store, conv_id=1):
    with store() as db:
        rows = db.query(Message).filter(Message.conversation_id == conv_id).order_by(Message.id).all()
        return db.get(Conversation, conv_id).message_count, [(row.role, row.content) for row in rows]


@pytest.mark.parametrize("writer", ["_post", "_post_placeholder"])
def test_stale_session_cannot_overwrite_another_message_increment(store, monkeypatch, writer):
    user_write(store, 1, "first")
    session = store()
    original_get = session.get

    def get_after_competing_commit(model, identifier, **kwargs):
        row = original_get(model, identifier, **kwargs)
        user_write(store, 1, "competing")  # old row cached at 1; database is now 2
        return row

    monkeypatch.setattr(session, "get", get_after_competing_commit)
    monkeypatch.setattr(main, "SessionLocal", lambda: session)
    monkeypatch.setattr(main, "needs_compress", lambda conv, recent: False)
    pre = {"conv_id": 1, "intent": "chitchat", "sources": [], "rewritten": "first", "user_text": "first"}
    if writer == "_post":
        main._post(pre, "answer", False)
    else:
        main._post_placeholder(pre)
    count, rows = snapshot(store)
    assert count == len(rows) == 3, "ORM flush overwrote an independent committed increment"


def route_namespace(store, seam=None):
    if seam is None:
        seam = _RouteSeam()
        seam.release.set()
    namespace, guard = _route_namespace(store, seam, image_validator=main.validate_image)
    namespace.update(
        SessionLocal=store,
        Message=Message,
        Conversation=Conversation,
        datetime=datetime,
        text=main.text,
        citation_grounding=lambda *args: None,
        _grounding_stats={},
        output_normalize=main.output_normalize,
        recent_messages=main.recent_messages,
        needs_compress=lambda conv, recent: False,
        source_in_kb=lambda source: False,
        time=time,
        WeakValueDictionary=WeakValueDictionary,
        _chat_turn_locks=WeakValueDictionary(),
        _CHAT_TURN_WAIT_SECONDS=180.0,
        _safe_pick=lambda *args: (None, None, False),
        _cacheable=lambda pre: True,
        _cache_key=lambda pre, cutoff: "turn-cache",
        _cache_scope=lambda pre, cutoff: None,
        create_conversation=main.create_conversation,
        validate_image=main.validate_image,
        delete_conversation=main.delete_conversation,
        Session=main.Session,
        get_db=main.get_db,
    )
    namespace["settings"].feature_router = True
    namespace["answer_cache"].get = lambda key: {"answer": "complete answer"}
    _extract(
        Path(main.__file__),
        {
            "_post",
            "_post_placeholder",
            "_acquire_chat_turn",
            "_resolve_chat_conversation",
            "_require_chat_conversation",
        },
        namespace,
    )
    tree = ast.parse(Path(main.__file__).read_text(encoding="utf-8-sig"))
    for node in tree.body:
        if getattr(node, "name", None) in {"_serialized_chat", "_serialized_delete_conversation"}:
            node.decorator_list = []
            exec(compile(ast.Module(body=[node], type_ignores=[]), main.__file__, "exec"), namespace)
    return namespace


def body(content, conv_id=1):
    return main.ChatIn(content=content, conversation_id=conv_id)


class Request:
    def __init__(self):
        self.disconnected = False
        self.checked = asyncio.Event()

    async def is_disconnected(self):
        self.checked.set()
        return self.disconnected


async def respond(response, *, cancel=False):
    sent = asyncio.Event()

    async def send(message):
        if cancel and message["type"] == "http.response.body" and message.get("body"):
            sent.set()
            await anyio.sleep_forever()

    async def receive():
        if cancel:
            await sent.wait()
            return {"type": "http.disconnect"}
        await anyio.sleep_forever()

    await response({"type": "http", "asgi": {"spec_version": "2.3"}}, receive, send)


def test_committed_answer_with_failed_summary_does_not_add_placeholder(store):
    namespace = route_namespace(store)

    def fail_after_commit(conv, recent):
        raise RuntimeError("post-commit-only failure")

    namespace["needs_compress"] = fail_after_commit

    async def scenario():
        response = await namespace["chat"](Request(), body("question"), SimpleNamespace(id=1))
        await respond(response)

    anyio.run(scenario, backend="asyncio")
    count, rows = snapshot(store)
    assert rows == [("user", "question"), ("assistant", "complete answer")]
    assert count == 2


@pytest.mark.parametrize("new_conversation", [False, True])
def test_immediate_reask_waits_for_cancelled_turn_commit(store, new_conversation):
    namespace = route_namespace(store)
    entered, release = threading.Event(), threading.Event()
    real_placeholder = namespace["_post_placeholder"]

    def blocked_placeholder(pre, reason="no_response"):
        entered.set()
        assert release.wait(3), "test must release the owned persistence work"
        real_placeholder(pre, reason)

    namespace["_post_placeholder"] = blocked_placeholder
    route = namespace.get("_serialized_chat", namespace["chat"])

    async def scenario():
        response = await route(Request(), body("cancelled", None if new_conversation else 1), SimpleNamespace(id=1))
        with store() as db:
            conv_id = db.query(Message).filter(Message.content == "cancelled").one().conversation_id
        first = asyncio.create_task(respond(response, cancel=True))
        second = None
        try:
            assert await asyncio.to_thread(entered.wait, 2)
            request = Request()
            second = asyncio.create_task(route(request, body("reasked", conv_id), SimpleNamespace(id=1)))
            await asyncio.wait_for(request.checked.wait(), 2)
            assert snapshot(store, conv_id)[1] == [("user", "cancelled")], "second user preceded prior assistant commit"
        finally:
            release.set()
            await first
            if second is not None:
                await respond(await second)
        count, rows = snapshot(store, conv_id)
        assert rows == [
            ("user", "cancelled"),
            # 这一轮是**被取消**的（cancel=True），D-23 起占位要说实话：不是服务故障
            ("assistant", "本次回答已停止，未生成完整内容。"),
            ("user", "reasked"),
            ("assistant", "complete answer"),
        ]
        assert count == 4

    anyio.run(scenario, backend="asyncio")


@pytest.mark.parametrize("reason", ["disconnect", "timeout", "task-cancel"])
def test_waiter_exits_without_persisting_or_releasing_another_turn(store, reason):
    namespace = route_namespace(store)
    if "_serialized_chat" not in namespace:
        pytest.fail("the accepted request has no persistence serialization boundary")
    namespace["_CHAT_TURN_WAIT_SECONDS"] = 0.15

    async def scenario():
        first = await namespace["_serialized_chat"](Request(), body("first"), SimpleNamespace(id=1))
        request = Request()
        waiter = asyncio.create_task(
            namespace["_serialized_chat"](request, body("must not persist"), SimpleNamespace(id=1))
        )
        await asyncio.wait_for(request.checked.wait(), 2)
        if reason == "disconnect":
            request.disconnected = True
        elif reason == "task-cancel":
            waiter.cancel()
        expected = asyncio.CancelledError if reason == "task-cancel" else main.HTTPException
        with pytest.raises(expected) as caught:
            await waiter
        if reason != "task-cancel":
            assert caught.value.status_code == (499 if reason == "disconnect" else 503)
        assert snapshot(store)[1] == [("user", "first")]
        assert namespace["_chat_turn_locks"][(1, 1)].locked()
        await respond(first)
        third = await namespace["_serialized_chat"](Request(), body("third"), SimpleNamespace(id=1))
        await respond(third)
        count, rows = snapshot(store)
        assert count == 4
        assert [row[0] for row in rows] == ["user", "assistant"] * 2

    anyio.run(scenario, backend="asyncio")


@pytest.mark.parametrize("requested_id", [None, 999, 2])
def test_actual_conversation_is_owned_before_postcommit_retrieval(store, requested_id):
    with store() as db:
        db.add(User(id=2, username="other-user", password_hash="test-only"))
        db.add(Conversation(id=2, user_id=2, title="not owned", message_count=0))
        db.commit()
    seam = _RouteSeam()
    namespace = route_namespace(store, seam)
    route = namespace["_serialized_chat"]

    async def scenario():
        first = asyncio.create_task(route(Request(), body("first", requested_id), SimpleNamespace(id=1)))
        second = None
        try:
            assert await asyncio.to_thread(seam.entered.wait, 2)
            # Real list endpoint can expose the new ID before the first response exists.
            with store() as db:
                listed = main.my_conversations(SimpleNamespace(id=1), db)
                conv_id = next(item.id for item in listed if item.title == "first")
                assert db.get(Conversation, conv_id).user_id == 1
            owner = namespace["_chat_turn_locks"].get((1, conv_id))
            assert owner is not None and owner.locked(), "published ID has no persistence owner"
            request = Request()
            second = asyncio.create_task(route(request, body("second", conv_id), SimpleNamespace(id=1)))
            await asyncio.wait_for(request.checked.wait(), 2)
            assert snapshot(store, conv_id)[1] == [("user", "first")], "published ID bypassed the prior turn owner"
        finally:
            seam.release.set()
            await respond(await first)
            if second is not None:
                await respond(await second)
        assert snapshot(store, conv_id)[0] == 4
        assert [row[0] for row in snapshot(store, conv_id)[1]] == ["user", "assistant"] * 2
        assert snapshot(store, 2) == (0, [])

    anyio.run(scenario, backend="asyncio")


def test_grant_and_task_cancel_same_beat_does_not_accept_or_leak_lock(store):
    namespace = route_namespace(store)

    class HandoffRequest(Request):
        checks = 0

        async def is_disconnected(self):
            self.checks += 1
            if self.checks > 1:
                await asyncio.sleep(0)  # cancellation must be observable before ownership is returned
            return await super().is_disconnected()

    async def scenario():
        lock = asyncio.Lock()
        await lock.acquire()
        namespace["_chat_turn_locks"][(1, 1)] = lock
        request = HandoffRequest()
        task = asyncio.create_task(namespace["_acquire_chat_turn"](request, 1, 1))
        await request.checked.wait()
        # The direct waiter (fixed) or wait_for child (old) must be blocked on the real lock.
        while not lock._waiters:
            await asyncio.sleep(0)
        lock.release()
        asyncio.get_running_loop().call_soon(task.cancel)
        try:
            with pytest.raises(asyncio.CancelledError):
                await task
            assert not lock.locked(), "cancelled acquire retained conversation ownership"
            assert snapshot(store) == (0, [])
        finally:
            if lock.locked():
                lock.release()

    anyio.run(scenario, backend="asyncio")


@pytest.mark.parametrize("requested_id", [None, 999])
@pytest.mark.parametrize("reason", ["empty", "unsupported-vision", "historical-disabled", "malformed-image"])
def test_rejected_input_does_not_create_conversation(store, requested_id, reason):
    namespace = route_namespace(store)
    payload = body("question", requested_id)
    expected = 400
    if reason == "empty":
        payload.content = ""
    elif reason == "unsupported-vision":
        payload.image = "data:image/png;base64,aW52YWxpZA=="
        namespace["registry"].has_modality = lambda modality: False
        expected = 501
    elif reason == "historical-disabled":
        payload.law_as_of = main.date(2020, 1, 1)
        expected = 503
    else:
        payload.image = "data:image/png;base64,aW52YWxpZA=="

    async def scenario():
        with pytest.raises(main.HTTPException) as caught:
            await namespace["_serialized_chat"](Request(), payload, SimpleNamespace(id=1))
        assert caught.value.status_code == expected

    anyio.run(scenario, backend="asyncio")
    with store() as db:
        assert db.query(Conversation).count() == 1, "rejected input left a committed empty conversation"
    assert snapshot(store) == (0, [])


def test_other_conversation_is_not_blocked_and_route_exception_releases_lock(store):
    namespace = route_namespace(store)
    with store() as db:
        db.add(Conversation(id=2, user_id=1, title="other", message_count=0))
        db.commit()

    async def scenario():
        route = namespace["_serialized_chat"]
        first = await route(Request(), body("first"), SimpleNamespace(id=1))
        try:
            other = await asyncio.wait_for(route(Request(), body("other", 2), SimpleNamespace(id=1)), 0.5)
            await respond(other)
            assert snapshot(store, 2)[0] == 2
            assert snapshot(store)[1] == [("user", "first")]
        finally:
            await respond(first)
        real_chat = namespace["chat"]

        async def fail(*args, accepted_agent_turn):
            assert accepted_agent_turn == {}
            raise RuntimeError("before bootstrap")

        namespace["chat"] = fail
        with pytest.raises(RuntimeError, match="before bootstrap"):
            await route(Request(), body("must not persist"), SimpleNamespace(id=1))
        namespace["chat"] = real_chat
        following = await asyncio.wait_for(route(Request(), body("following"), SimpleNamespace(id=1)), 0.5)
        await respond(following)
        assert snapshot(store)[0] == 4

    anyio.run(scenario, backend="asyncio")


def test_closed_response_leaves_no_strong_global_turn_registry(store):
    namespace = route_namespace(store)

    async def scenario():
        response = await namespace["_serialized_chat"](Request(), body("question"), SimpleNamespace(id=1))
        await respond(response)
        del response
        assert not namespace["_chat_turn_locks"]

    anyio.run(scenario, backend="asyncio")


def test_delete_waits_until_current_assistant_is_committed(store):
    namespace = route_namespace(store)
    committed = []
    real_post = namespace["_post"]

    def observe_commit(*args, **kwargs):
        real_post(*args, **kwargs)
        committed.append(snapshot(store))

    namespace["_post"] = observe_commit

    async def scenario():
        response = await namespace["_serialized_chat"](Request(), body("first"), SimpleNamespace(id=1))
        request = Request()

        async def remove():
            with store() as db:
                if "_serialized_delete_conversation" in namespace:
                    return await namespace["_serialized_delete_conversation"](request, 1, SimpleNamespace(id=1), db)
                # Baseline sync endpoint has no await/gate; exercise its real DB deletion.
                await request.is_disconnected()
                return main.delete_conversation(1, SimpleNamespace(id=1), db)

        deletion = asyncio.create_task(remove())
        try:
            await asyncio.wait_for(request.checked.wait(), 2)
            with store() as db:
                assert db.get(Conversation, 1) is not None, "delete ran before current turn persistence"
            assert not deletion.done()
        finally:
            await respond(response)
            await deletion
        del response
        assert committed == [(2, [("user", "first"), ("assistant", "complete answer")])]
        with store() as db:
            assert db.get(Conversation, 1) is None
            assert db.query(Message).count() == 0
        assert not namespace["_chat_turn_locks"]

    anyio.run(scenario, backend="asyncio")


@pytest.mark.parametrize("reuse_deleted_id", [False, True])
def test_queued_chat_rejects_deleted_conversation_instead_of_recreating_it(store, reuse_deleted_id):
    namespace = route_namespace(store)
    with store() as db:
        original_created_at = db.get(Conversation, 1).created_at
        db.add(Conversation(id=2, user_id=1, title="other", message_count=0))
        db.commit()

    async def scenario():
        # The deleting operation owns this same gate before the chat is queued.
        lock = asyncio.Lock()
        await lock.acquire()
        namespace["_chat_turn_locks"][(1, 1)] = lock
        request = Request()
        queued = asyncio.create_task(
            namespace["_serialized_chat"](request, body("must not persist"), SimpleNamespace(id=1))
        )
        await asyncio.wait_for(request.checked.wait(), 2)
        with store() as db:
            main.delete_conversation(1, SimpleNamespace(id=1), db)
            if reuse_deleted_id:
                db.add(
                    Conversation(
                        id=1, user_id=1, created_at=original_created_at + timedelta(seconds=1), message_count=0
                    )
                )
                db.commit()
        lock.release()
        try:
            response = await queued
        except main.HTTPException as exc:
            assert exc.status_code == 404
        else:
            await respond(response, cancel=True)
            pytest.fail("queued chat silently recreated or reused the deleted conversation")
        with store() as db:
            assert db.query(Message).count() == 0
            assert db.query(Conversation).count() == (2 if reuse_deleted_id else 1)
        assert not lock.locked()

    anyio.run(scenario, backend="asyncio")


def test_queued_delete_cannot_delete_a_new_conversation_reusing_the_id(store):
    namespace = route_namespace(store)

    async def scenario():
        lock = asyncio.Lock()
        await lock.acquire()
        namespace["_chat_turn_locks"][(1, 1)] = lock
        request = Request()

        async def remove():
            with store() as db:
                return await namespace["_serialized_delete_conversation"](request, 1, SimpleNamespace(id=1), db)

        queued = asyncio.create_task(remove())
        await asyncio.wait_for(request.checked.wait(), 2)
        with store() as db:
            main.delete_conversation(1, SimpleNamespace(id=1), db)
            recreated = main.create_conversation(SimpleNamespace(id=1), db)
            assert recreated["id"] == 1, "negative control requires SQLite ID reuse"
        lock.release()
        with pytest.raises(main.HTTPException) as caught:
            await queued
        assert caught.value.status_code == 404
        with store() as db:
            assert db.get(Conversation, 1) is not None, "stale DELETE deleted a different conversation"
        assert not lock.locked()

    anyio.run(scenario, backend="asyncio")


@pytest.mark.parametrize("reason", ["disconnect", "timeout", "task-cancel"])
def test_queued_delete_exits_without_deleting_or_releasing_another_owner(store, reason):
    namespace = route_namespace(store)
    namespace["_CHAT_TURN_WAIT_SECONDS"] = 0.15

    async def scenario():
        response = await namespace["_serialized_chat"](Request(), body("first"), SimpleNamespace(id=1))
        request = Request()

        async def remove():
            with store() as db:
                return await namespace["_serialized_delete_conversation"](request, 1, SimpleNamespace(id=1), db)

        task = asyncio.create_task(remove())
        await asyncio.wait_for(request.checked.wait(), 2)
        if reason == "disconnect":
            request.disconnected = True
        elif reason == "task-cancel":
            task.cancel()
        expected = asyncio.CancelledError if reason == "task-cancel" else main.HTTPException
        try:
            with pytest.raises(expected) as caught:
                await task
            if reason != "task-cancel":
                assert caught.value.status_code == (499 if reason == "disconnect" else 503)
            assert snapshot(store)[1] == [("user", "first")]
            assert namespace["_chat_turn_locks"][(1, 1)].locked()
        finally:
            await respond(response)
        assert snapshot(store)[0] == 2

    anyio.run(scenario, backend="asyncio")


def test_delete_keeps_ownership_checks_and_other_conversations_independent(store):
    namespace = route_namespace(store)
    with store() as db:
        db.add(Conversation(id=2, user_id=1, title="other", message_count=0))
        db.commit()

    async def scenario():
        response = await namespace["_serialized_chat"](Request(), body("first"), SimpleNamespace(id=1))
        try:
            with store() as db:
                with pytest.raises(main.HTTPException) as caught:
                    await namespace["_serialized_delete_conversation"](Request(), 1, SimpleNamespace(id=2), db)
                assert caught.value.status_code == 404
                result = await asyncio.wait_for(
                    namespace["_serialized_delete_conversation"](Request(), 2, SimpleNamespace(id=1), db), 0.5
                )
                assert result == {"deleted": 2}
            assert snapshot(store)[1] == [("user", "first")]
        finally:
            await respond(response)
        assert snapshot(store)[0] == 2

    anyio.run(scenario, backend="asyncio")


@pytest.mark.parametrize("failure_type", [RuntimeError, ValueError, main.LLMBusyError])
def test_failed_postcommit_retrieval_persists_one_placeholder_before_returning(store, monkeypatch, failure_type):
    user_write(store, 1, "accepted question")
    monkeypatch.setattr(main, "SessionLocal", store)

    def fail_retrieval(bootstrap, *, _deps):
        assert snapshot(store)[1] == [("user", "accepted question")]
        raise failure_type("retrieval failed after the user commit")

    monkeypatch.setattr(main, "prepare_fast_path", fail_retrieval)
    with pytest.raises(failure_type, match="retrieval failed after the user commit"):
        main._prepare_fast_path_only(SimpleNamespace(conv_id=1))
    assert snapshot(store) == (
        2,
        [("user", "accepted question"), ("assistant", "服务暂时无响应，请稍后重试。")],
    ), "retrieval exception returned before the accepted turn was paired"
