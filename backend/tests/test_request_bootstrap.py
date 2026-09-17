from __future__ import annotations

from pathlib import Path
from threading import Event, Thread
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from models import Base, Conversation, Message, User
from request_bootstrap import (
    BootstrapDependencies,
    FastPathDependencies,
    bootstrap_request,
    cleanup_persisted_images,
    configure_default_image_describer,
    override_default_image_describer,
    prepare_fast_path,
)

LEGACY_KEYS = {
    "conv_id",
    "summary",
    "recent",
    "context",
    "qa_hit",
    "sources",
    "image",
    "user_text",
    "image_rel",
    "thumb_rel",
    "rewritten",
    "intent",
    "is_exam",
    "has_options",
    "contract_data",
}


@pytest.fixture
def store():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    db = sessions()
    user = User(username="bootstrap", password_hash="x")
    db.add(user)
    db.flush()
    conv = Conversation(user_id=user.id, title="", summary="摘要", message_count=0, question="")
    db.add(conv)
    db.commit()
    result = SimpleNamespace(sessions=sessions, user_id=user.id, conv_id=conv.id)
    db.close()
    return result


def _bootstrap_deps(store, **overrides):
    values = dict(
        session_factory=store.sessions,
        load_context=lambda db, conv: (conv.summary or "", []),
        validate_image=lambda image: image,
        persist_image=lambda image: ("media/image.png", "media/thumb.jpg"),
        cleanup_persisted_image=lambda image_rel, thumb_rel: None,
        describe_image=lambda image, text: "图片原始描述",
        classify_intent=lambda query: "legal_query",
        is_exam_question=lambda query: False,
        has_exam_options=lambda query: False,
        is_contract_review=lambda query: False,
        feature_multi_analyze=True,
        contract_conversations=set(),
        contract_reviewed_conversations=set(),
        is_contract_exit=lambda query: False,
    )
    values.update(overrides)
    return BootstrapDependencies(**values)


def _fast_deps(**overrides):
    values = dict(
        feature_study_retrieval=True,
        is_meta_study=lambda query: False,
        rewrite_for_retrieval=lambda raw, recent_ser, recent, has_options: raw,
        scenario_supplement_docs=lambda query: [],
        retrieve_exam=lambda query: [],
        cheating_docs=lambda: [],
        build_contract_data=lambda text: {"docs": [], "blocks": [], "level": "低", "basis": "test"},
        retrieve=lambda query, k: [],
        search_qa=lambda query: None,
        is_consumer_clause_scenario=lambda query: False,
        consumer_clause_docs=lambda: [],
        is_consumer_fraud_scenario=lambda query: False,
        consumer_fraud_docs=lambda: [],
        format_docs=lambda docs: "",
    )
    values.update(overrides)
    return FastPathDependencies(**values)


def test_bootstrap_classifies_raw_and_never_calls_fast_path_capabilities(store):
    classified = []
    deps = _bootstrap_deps(store, classify_intent=lambda query: classified.append(query) or "legal_query")

    result = bootstrap_request(store.user_id, store.conv_id, "原始问题", None, False, _deps=deps)

    assert classified == ["原始问题"]
    assert result.raw_query == "原始问题"


def test_public_bootstrap_uses_real_forbidden_call_traps(store, monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).parents[1] / ".venv311" / "Lib" / "site-packages"))
    import answer_cache
    import database
    import domain_rules
    import intent
    import knowledge_service
    import llm_registry
    import memory
    import multimodal
    import query_understand
    import retrieval
    import settings as settings_module

    def forbidden(name):
        def fail(*args, **kwargs):
            pytest.fail(f"bootstrap called forbidden capability: {name}")

        return fail

    monkeypatch.setattr(database, "SessionLocal", store.sessions)
    monkeypatch.setattr(memory, "load_context", lambda db, conv: (conv.summary or "", []))
    monkeypatch.setattr(multimodal, "validate_image", lambda image: image)
    monkeypatch.setattr(multimodal, "persist_image", lambda image: ("unused", "unused"))
    monkeypatch.setattr(intent, "classify_intent", lambda query: "legal_query")
    monkeypatch.setattr(query_understand, "_is_exam_question", lambda query: False)
    monkeypatch.setattr(query_understand, "has_exam_options", lambda query: False)
    monkeypatch.setattr(domain_rules, "is_contract_review", lambda query: False)
    monkeypatch.setattr(settings_module.settings, "feature_multi_analyze", True)
    monkeypatch.setattr(retrieval, "retrieve", forbidden("retrieve"))
    monkeypatch.setattr(retrieval, "retrieve_exam", forbidden("retrieve_exam"))
    monkeypatch.setattr(knowledge_service, "search_qa", forbidden("search_qa"))
    monkeypatch.setattr(answer_cache, "get", forbidden("answer_cache.get"))
    monkeypatch.setattr(answer_cache, "get_similar", forbidden("answer_cache.get_similar"))
    monkeypatch.setattr(memory, "rewrite_query", forbidden("rewrite_query"))
    monkeypatch.setattr(llm_registry.registry, "get", forbidden("registry.get"))

    with override_default_image_describer(lambda image, text: "已注入的图片描述"):
        result = bootstrap_request(store.user_id, store.conv_id, "原始问题", "image-data", False)

    assert result.raw_query == "原始问题 已注入的图片描述"
    assert result.intent == "legal_query"


def test_scoped_image_capability_overrides_are_serialized_across_threads():
    import request_bootstrap as bootstrap_module

    first_entered = Event()
    release_first = Event()
    second_started = Event()
    second_entered = Event()
    observed = []

    def first_override():
        with override_default_image_describer(lambda image, text: "first"):
            first_entered.set()
            release_first.wait()
            observed.append(bootstrap_module._describe_image_with_configured_capability("image", "text"))

    def second_override():
        second_started.set()
        with override_default_image_describer(lambda image, text: "second"):
            second_entered.set()
            observed.append(bootstrap_module._describe_image_with_configured_capability("image", "text"))

    first = Thread(target=first_override, daemon=True)
    second = Thread(target=second_override, daemon=True)
    try:
        first.start()
        assert first_entered.wait(timeout=2)
        second.start()
        assert second_started.wait(timeout=2)
        assert not second_entered.wait(timeout=0.1)
    finally:
        release_first.set()
        if first.ident is not None:
            first.join(timeout=2)
        if second.ident is not None:
            second.join(timeout=2)

    assert not first.is_alive()
    assert not second.is_alive()
    assert observed == ["first", "second"]


def test_scoped_image_capability_is_visible_to_worker_thread():
    import request_bootstrap as bootstrap_module

    observed = []
    worker = Thread(
        target=lambda: observed.append(bootstrap_module._describe_image_with_configured_capability("image", "text")),
        daemon=True,
    )
    try:
        with override_default_image_describer(lambda image, text: "worker-visible"):
            worker.start()
            worker.join(timeout=1)
            assert not worker.is_alive()
    finally:
        worker.join(timeout=2)

    assert observed == ["worker-visible"]


def test_production_configuration_waits_for_temporary_override(monkeypatch):
    import request_bootstrap as bootstrap_module

    def production(image, text):
        return "production"

    monkeypatch.setattr(bootstrap_module, "_configured_image_describer", production)
    configure_started = Event()
    configure_finished = Event()

    def configure_production():
        configure_started.set()
        configure_default_image_describer(production)
        configure_finished.set()

    worker = Thread(target=configure_production, daemon=True)
    try:
        with override_default_image_describer(lambda image, text: "temporary"):
            worker.start()
            assert configure_started.wait(timeout=2)
            assert not configure_finished.wait(timeout=0.1)
        worker.join(timeout=2)
    finally:
        if worker.ident is not None:
            worker.join(timeout=2)

    assert not worker.is_alive()
    assert configure_finished.is_set()
    assert bootstrap_module._configured_image_describer is production


def test_runtime_image_capability_replacement_is_rejected():
    def first(image, text):
        return "first"

    def second(image, text):
        return "second"

    with override_default_image_describer(first):
        configure_default_image_describer(first)
        with pytest.raises(RuntimeError, match="already configured"):
            configure_default_image_describer(second)


def test_public_api_supports_task6_bootstrap_then_fast_path_consumption(store, monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).parents[1] / ".venv311" / "Lib" / "site-packages"))
    import database
    import domain_rules
    import intent
    import knowledge_service
    import memory
    import multimodal
    import query_understand
    import rag_chain
    import retrieval
    import settings as settings_module

    monkeypatch.setattr(database, "SessionLocal", store.sessions)
    monkeypatch.setattr(memory, "load_context", lambda db, conv: (conv.summary or "", []))
    monkeypatch.setattr(multimodal, "validate_image", lambda image: image)
    monkeypatch.setattr(multimodal, "persist_image", lambda image: ("unused", "unused"))
    monkeypatch.setattr(intent, "classify_intent", lambda query: "legal_query")
    monkeypatch.setattr(query_understand, "_is_exam_question", lambda query: False)
    monkeypatch.setattr(query_understand, "has_exam_options", lambda query: False)
    monkeypatch.setattr(domain_rules, "is_contract_review", lambda query: False)
    monkeypatch.setattr(settings_module.settings, "feature_multi_analyze", True)
    monkeypatch.setattr(settings_module.settings, "feature_study_retrieval", True)
    monkeypatch.setattr(retrieval, "retrieve", lambda query, k: [])
    monkeypatch.setattr(retrieval, "scenario_supplement_docs", lambda query: [])
    monkeypatch.setattr(knowledge_service, "search_qa", lambda query: None)
    monkeypatch.setattr(rag_chain, "format_docs", lambda docs: "")

    bootstrap = bootstrap_request(store.user_id, store.conv_id, "借款纠纷", None, False)
    gate_input = (bootstrap.conv_id, bootstrap.raw_query, bootstrap.intent)
    result = prepare_fast_path(bootstrap)

    assert gate_input == (store.conv_id, "借款纠纷", "legal_query")
    assert set(result) == LEGACY_KEYS


def test_bootstrap_persists_message_and_increments_count_exactly_once(store):
    result = bootstrap_request(store.user_id, store.conv_id, "借款纠纷", None, False, _deps=_bootstrap_deps(store))

    db = store.sessions()
    assert result.conv_id == store.conv_id
    assert db.query(Message).filter_by(conversation_id=store.conv_id, role="user").count() == 1
    assert db.get(Conversation, store.conv_id).message_count == 1
    db.close()


def test_bootstrap_uses_new_conversation_for_foreign_conversation(store):
    db = store.sessions()
    other = User(username="other", password_hash="x")
    db.add(other)
    db.commit()
    other_id = other.id
    db.close()

    result = bootstrap_request(other_id, store.conv_id, "不能接管", None, False, _deps=_bootstrap_deps(store))

    assert result.conv_id != store.conv_id
    db = store.sessions()
    assert db.get(Conversation, result.conv_id).user_id == other_id
    db.close()


@pytest.mark.parametrize("failure_at", ["validate", "persist", "describe"])
def test_bootstrap_rolls_back_and_closes_on_image_failure(store, failure_at):
    closed = []

    class TrackingSession:
        def __init__(self):
            self._session = store.sessions()

        def __getattr__(self, name):
            return getattr(self._session, name)

        def rollback(self):
            return self._session.rollback()

        def close(self):
            closed.append(True)
            return self._session.close()

    def fail(message):
        def inner(*args):
            raise ValueError(message)

        return inner

    deps = _bootstrap_deps(
        store,
        session_factory=TrackingSession,
        validate_image=fail("validate failed") if failure_at == "validate" else lambda image: image,
        persist_image=fail("persist failed") if failure_at == "persist" else lambda image: ("a", "b"),
        describe_image=fail("describe failed") if failure_at == "describe" else lambda image, text: "desc",
    )

    with pytest.raises(ValueError, match=failure_at):
        bootstrap_request(store.user_id, store.conv_id, "看图", "data:image/png;base64,x", False, _deps=deps)

    db = store.sessions()
    assert db.query(Message).filter_by(conversation_id=store.conv_id).count() == 0
    assert db.get(Conversation, store.conv_id).message_count == 0
    db.close()
    assert closed == [True]


def test_bootstrap_rolls_back_and_closes_on_database_commit_failure(store):
    rolled_back = []
    closed = []

    class FailingCommitSession:
        def __init__(self):
            self._session = store.sessions()

        def __getattr__(self, name):
            return getattr(self._session, name)

        def commit(self):
            raise RuntimeError("commit failed")

        def rollback(self):
            rolled_back.append(True)
            return self._session.rollback()

        def close(self):
            closed.append(True)
            return self._session.close()

    with pytest.raises(RuntimeError, match="commit failed"):
        bootstrap_request(
            store.user_id,
            store.conv_id,
            "借款纠纷",
            None,
            False,
            _deps=_bootstrap_deps(store, session_factory=FailingCommitSession),
        )

    assert rolled_back == [True]
    assert closed == [True]


@pytest.mark.parametrize("failure_at", ["describe", "classify"])
def test_close_failure_does_not_replace_original_bootstrap_failure(store, failure_at):
    rolled_back = []
    cleaned = []

    class FailingCloseSession:
        def __init__(self):
            self._session = store.sessions()

        def __getattr__(self, name):
            return getattr(self._session, name)

        def rollback(self):
            rolled_back.append(True)
            return self._session.rollback()

        def close(self):
            self._session.close()
            raise RuntimeError("close failed")

    def maybe_fail(name, value):
        def call(*args):
            if failure_at == name:
                raise ValueError(f"{name} failed")
            return value

        return call

    deps = _bootstrap_deps(
        store,
        session_factory=FailingCloseSession,
        cleanup_persisted_image=lambda image_rel, thumb_rel: cleaned.append((image_rel, thumb_rel)),
        describe_image=maybe_fail("describe", "desc"),
        classify_intent=maybe_fail("classify", "legal_query"),
    )

    with pytest.raises(ValueError, match=rf"^{failure_at} failed$"):
        bootstrap_request(store.user_id, store.conv_id, "看图", "image-data", False, _deps=deps)

    assert rolled_back == [True]
    assert cleaned == [("media/image.png", "media/thumb.jpg")]


def test_close_failure_after_successful_commit_still_returns_accepted_bootstrap(store):
    close_attempts = []

    class FailingCloseSession:
        def __init__(self):
            self._session = store.sessions()

        def __getattr__(self, name):
            return getattr(self._session, name)

        def close(self):
            close_attempts.append(True)
            self._session.close()
            raise RuntimeError("close failed")

    result = bootstrap_request(
        store.user_id,
        store.conv_id,
        "借款纠纷",
        None,
        False,
        _deps=_bootstrap_deps(store, session_factory=FailingCloseSession),
    )

    assert result.conv_id == store.conv_id
    assert close_attempts == [True]
    db = store.sessions()
    assert db.query(Message).filter_by(conversation_id=store.conv_id, role="user").count() == 1
    assert db.get(Conversation, store.conv_id).message_count == 1
    db.close()


@pytest.mark.parametrize("failure_at", ["describe", "classify", "commit"])
def test_persisted_image_files_are_cleaned_after_later_failure(store, tmp_path, failure_at):
    backend_dir = tmp_path / "backend"
    media_dir = backend_dir / "media"
    media_dir.mkdir(parents=True)
    image_path = media_dir / "request.png"
    thumb_path = media_dir / "request_thumb.jpg"

    class OptionalFailingCommitSession:
        def __init__(self):
            self._session = store.sessions()

        def __getattr__(self, name):
            return getattr(self._session, name)

        def commit(self):
            if failure_at == "commit":
                raise RuntimeError("commit failed")
            return self._session.commit()

    def persist(_image):
        image_path.write_bytes(b"image")
        thumb_path.write_bytes(b"thumb")
        return "media/request.png", "media/request_thumb.jpg"

    def maybe_fail(name, value):
        def call(*args):
            if failure_at == name:
                raise RuntimeError(f"{name} failed")
            return value

        return call

    deps = _bootstrap_deps(
        store,
        session_factory=OptionalFailingCommitSession,
        persist_image=persist,
        cleanup_persisted_image=lambda image_rel, thumb_rel: cleanup_persisted_images(
            image_rel, thumb_rel, media_dir=media_dir, backend_dir=backend_dir
        ),
        describe_image=maybe_fail("describe", "desc"),
        classify_intent=maybe_fail("classify", "legal_query"),
    )

    with pytest.raises(RuntimeError, match=failure_at):
        bootstrap_request(store.user_id, store.conv_id, "看图", "image-data", False, _deps=deps)

    assert not image_path.exists()
    assert not thumb_path.exists()


def test_cleanup_rejects_paths_outside_media_directory(tmp_path):
    backend_dir = tmp_path / "backend"
    media_dir = backend_dir / "media"
    media_dir.mkdir(parents=True)
    outside = backend_dir / "keep.txt"
    outside.write_text("keep", encoding="utf-8")

    cleanup_persisted_images("keep.txt", "../keep.txt", media_dir=media_dir, backend_dir=backend_dir)

    assert outside.read_text(encoding="utf-8") == "keep"


def test_image_only_empty_description_preserves_legacy_title(store):
    result = bootstrap_request(
        store.user_id,
        store.conv_id,
        "",
        "image-data",
        False,
        _deps=_bootstrap_deps(store, describe_image=lambda image, text: ""),
    )

    db = store.sessions()
    assert db.get(Conversation, result.conv_id).title == "[图片] "
    db.close()


def test_contract_entry_and_exit_mutate_only_injected_state(store):
    active = set()
    reviewed = {store.conv_id}
    enter = _bootstrap_deps(
        store,
        contract_conversations=active,
        contract_reviewed_conversations=reviewed,
        is_contract_review=lambda query: query == "审合同",
    )

    entered = bootstrap_request(store.user_id, store.conv_id, "审合同", None, False, _deps=enter)
    assert entered.contract_mode is True
    assert active == {store.conv_id}

    exit_deps = _bootstrap_deps(
        store,
        contract_conversations=active,
        contract_reviewed_conversations=reviewed,
        is_contract_exit=lambda query: query == "退出合同",
    )
    exited = bootstrap_request(store.user_id, store.conv_id, "退出合同", None, False, _deps=exit_deps)
    assert exited.contract_mode is False
    assert active == set()
    assert reviewed == set()


def test_prepare_fast_path_returns_exact_legacy_keys(store):
    bootstrap = bootstrap_request(store.user_id, store.conv_id, "借款纠纷", None, False, _deps=_bootstrap_deps(store))

    result = prepare_fast_path(bootstrap, _deps=_fast_deps())

    assert set(result) == LEGACY_KEYS
    assert result["conv_id"] == store.conv_id
    assert result["rewritten"] == "借款纠纷"


def test_fast_path_receives_detached_history_snapshot_after_bootstrap_commit(store):
    db = store.sessions()
    db.add(Message(conversation_id=store.conv_id, role="user", content="上轮问题", image_desc=None))
    db.commit()
    db.close()
    bootstrap = bootstrap_request(
        store.user_id,
        store.conv_id,
        "继续问",
        None,
        False,
        _deps=_bootstrap_deps(
            store,
            load_context=lambda db, conv: (
                conv.summary or "",
                db.query(Message).filter_by(conversation_id=conv.id).all(),
            ),
        ),
    )
    deps = _fast_deps(rewrite_for_retrieval=lambda raw, recent_ser, recent, has_options: recent[0].content)

    result = prepare_fast_path(bootstrap, _deps=deps)

    assert result["rewritten"] == "上轮问题"


def test_fast_path_legal_branch_parity_for_context_sources_and_qa(store):
    doc = SimpleNamespace(
        metadata={
            "source": "民法典",
            "article": "第六百七十九条",
            "effective_from": "2021-01-01",
            "effective_to": "",
            "status": "effective",
        }
    )
    bootstrap = bootstrap_request(store.user_id, store.conv_id, "借款纠纷", None, False, _deps=_bootstrap_deps(store))
    deps = _fast_deps(
        rewrite_for_retrieval=lambda raw, *_: "改写问题",
        retrieve=lambda query, k: [doc],
        search_qa=lambda query: {"question": query, "answer": "缓存答案"},
        format_docs=lambda docs: "格式化法条",
    )

    result = prepare_fast_path(bootstrap, _deps=deps)

    assert result["rewritten"] == "改写问题"
    assert result["context"] == "格式化法条"
    assert result["qa_hit"] == {"question": "改写问题", "answer": "缓存答案"}
    assert result["sources"] == [
        {
            "source": "民法典",
            "article": "第六百七十九条",
            "effective_from": "2021-01-01",
            "effective_to": "",
            "status": "effective",
        }
    ]
