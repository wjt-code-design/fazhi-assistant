from __future__ import annotations

import json
import logging
from datetime import date
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
    is_contract_exit,
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
    """快车道取数桩。检索类能力一律接受 `cutoff`（历史查询基准日），
    与 `FastPathDependencies` 声明的接缝形状保持一致。"""

    values = dict(
        feature_study_retrieval=True,
        is_meta_study=lambda query: False,
        rewrite_for_retrieval=lambda raw, recent_ser, recent, has_options: raw,
        scenario_supplement_docs=lambda query, cutoff=None: [],
        retrieve_exam=lambda query, k=6, cutoff=None: [],
        cheating_docs=lambda cutoff=None: [],
        build_contract_data=lambda text, cutoff=None: {"docs": [], "blocks": [], "level": "低", "basis": "test"},
        retrieve=lambda query, k, cutoff=None: [],
        search_qa=lambda query: None,
        is_consumer_clause_scenario=lambda query: False,
        consumer_clause_docs=lambda cutoff=None: [],
        is_consumer_fraud_scenario=lambda query: False,
        consumer_fraud_docs=lambda cutoff=None: [],
        format_docs=lambda docs: "",
    )
    values.update(overrides)
    return FastPathDependencies(**values)


def _patch_kb(monkeypatch, docs, *, calls=None):
    """把"条文能否在库中查到"钉成给定读数；`calls` 传入列表则顺带记录被问到的 (source, article)。

    判据本体自票 W1 起住在 `retrieval.qa_citations_in_kb`，它读的是 **retrieval 的模块全局**
    `exact_article_lookup` ⇒ 替身必须打在那一侧（打在 `request_bootstrap` 或 `main` 上都是自我安慰：
    那两个名字根本不会被这条路径调用）。替身**签名与真函数一致**（位置参数 `src, art`）——
    吞不下真调用形状的替身会让判据看起来"恒过"（本仓教训：替身必须像真对象）。

    为什么别的用例如 `test_fast_path_legal_branch_parity_...` 也要打这一桩：
    pytest 的默认 lane 把 `CHROMA_DIR` 隔离到进程私有**空**库（conftest.py:39），
    不桩则"条文在库"恒为 False ⇒ 用例红在仪器上而不是红在判据上。
    """

    def _lookup(src, art):
        if calls is not None:
            calls.append((src, art))
        return docs

    import retrieval

    monkeypatch.setattr(retrieval, "exact_article_lookup", _lookup)


def test_bootstrap_classifies_raw_and_never_calls_fast_path_capabilities(store):
    classified = []
    deps = _bootstrap_deps(store, classify_intent=lambda query: classified.append(query) or "legal_query")

    result = bootstrap_request(store.user_id, store.conv_id, "原始问题", None, False, _deps=deps)

    assert classified == ["原始问题"]
    assert result.raw_query == "原始问题"


def test_bootstrap_request_carries_injected_law_as_of_and_defaults_none(store):
    injected = bootstrap_request(
        store.user_id,
        store.conv_id,
        "原始问题",
        None,
        False,
        law_as_of=date(2020, 12, 31),
        _deps=_bootstrap_deps(store),
    )

    assert injected.law_as_of == date(2020, 12, 31)

    default = bootstrap_request(store.user_id, store.conv_id, "原始问题", None, False, _deps=_bootstrap_deps(store))

    assert default.law_as_of is None


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
    monkeypatch.setattr(retrieval, "retrieve", lambda query, k, cutoff=None: [])
    monkeypatch.setattr(retrieval, "scenario_supplement_docs", lambda query, cutoff=None: [])
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


def test_fast_path_legal_branch_parity_for_context_sources_and_qa(store, monkeypatch):
    # 票 W1 之后，一条 QA 记录要在产生处活下来，除了形状判据还得**条文查得到**（时效判据）。
    # 不钉这个桩，本用例的 qa_hit 会红在进程私有空库上而不是红在判据上（假阴性取证）。
    _patch_kb(monkeypatch, ["doc"])
    doc = SimpleNamespace(
        metadata={
            "source": "民法典",
            "article": "第六百七十九条",
            "effective_from": "2021-01-01",
            "effective_to": "",
            "status": "effective",
        }
    )
    verifiable_qa = {
        "question": "改写问题",
        "answer": "缓存答案",
        "evidence": "劳动合同法|第十九条",
        "law_as_of_basis": "2026-01-01",
    }
    bootstrap = bootstrap_request(store.user_id, store.conv_id, "借款纠纷", None, False, _deps=_bootstrap_deps(store))
    deps = _fast_deps(
        rewrite_for_retrieval=lambda raw, *_: "改写问题",
        retrieve=lambda query, k, cutoff=None: [doc],
        search_qa=lambda query: dict(verifiable_qa),
        format_docs=lambda docs: "格式化法条",
    )

    result = prepare_fast_path(bootstrap, _deps=deps)

    assert result["rewritten"] == "改写问题"
    assert result["context"] == "格式化法条"
    assert result["qa_hit"] == verifiable_qa
    assert result["sources"] == [
        {
            "source": "民法典",
            "article": "第六百七十九条",
            "effective_from": "2021-01-01",
            "effective_to": "",
            "status": "effective",
        }
    ]


def test_fast_path_drops_qa_hit_whose_provenance_is_not_verifiable(store):
    """产生处接缝：来源校验不了的 QA 记录不给它 `qa_hit`，直返与 prompt 注入两个出口一起关。

    旧行为：`search_qa` 返回什么就原样进 `qa_hit` ⇒ `evidence='[]'`（生效 `qa_pairs` 实测 2 条，
    另一 lane `qa_pairs_te4` 另 2 条）和缺 `law_as_of_basis` 的记录都能被直返、并被注入 prompt。
    判据刻意放在这一缝而不是 `search_qa` 内部：`qa_seeds.py` 与 `scripts/gen_qa_corpus.py`
    拿 `search_qa(threshold=0.99)` 做**幂等去重**，把策略塞进去会外溢到写侧语义。
    """
    bootstrap = bootstrap_request(store.user_id, store.conv_id, "借款纠纷", None, False, _deps=_bootstrap_deps(store))

    for label, qa in {
        "无条文引用": {"question": "q", "answer": "a", "evidence": "[]", "law_as_of_basis": "2026-01-01"},
        "缺版本基准日": {"question": "q", "answer": "a", "evidence": "劳动合同法|第十九条", "law_as_of_basis": ""},
        "反馈来源": {"question": "q", "answer": "a", "evidence": "feedback:down", "law_as_of_basis": ""},
    }.items():
        deps = _fast_deps(search_qa=lambda query, _qa=qa: dict(_qa))
        result = prepare_fast_path(bootstrap, _deps=deps)
        assert result["qa_hit"] is None, label


def test_refused_qa_hit_leaves_a_log_trace(store, monkeypatch):
    """拦截要留痕：这道门关掉的是零 token 直返，不留日志则"语料在衰减"在线上没有一点痕迹。

    三腿：① 拒一次 ⇒ 归因键 `qa_provenance_refused` 恰好出现一次；
    ② 放行 ⇒ 不留痕（否则计数虚高，这条日志当不了指标）；
    ③ 留痕里不许有问句原文（AUTH-3：日志不落原文；语料题干可能就是用户问句）。
    """
    raw_query = "借款合同纠纷怎么起诉"
    bootstrap = bootstrap_request(store.user_id, store.conv_id, raw_query, None, False, _deps=_bootstrap_deps(store))
    refused = {"question": raw_query, "answer": "答案", "evidence": "[]", "law_as_of_basis": ""}
    accepted = {
        "question": raw_query,
        "answer": "答案",
        "evidence": "劳动合同法|第十九条",
        "law_as_of_basis": "2026-01-01",
    }

    chat_logger = logging.getLogger("legal.chat")
    records: list[logging.LogRecord] = []

    class _Handler(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            records.append(record)

    handler = _Handler(level=logging.WARNING)
    previous_level = chat_logger.level
    chat_logger.addHandler(handler)
    chat_logger.setLevel(logging.WARNING)
    try:
        dropped = prepare_fast_path(bootstrap, _deps=_fast_deps(search_qa=lambda query: dict(refused)))
        fired = [r for r in records if getattr(r, "qa_provenance_refused", False)]
        assert dropped["qa_hit"] is None
        assert len(fired) == 1, "拦截未留痕 ⇒ 直返率下降在线上不可归因"
        from observability import _JsonFormatter  # 留痕要真的能出机器（白名单外的键会被 JSON formatter 静默丢弃）

        assert json.loads(_JsonFormatter().format(fired[0]))["qa_provenance_refused"] is True
        assert raw_query not in " ".join([r.getMessage() for r in fired] + [repr(fired[0].__dict__)])

        records.clear()
        _patch_kb(monkeypatch, ["doc"])  # 票 W1：放行腿还要过时效判据，不桩就红在空库上（见 _patch_kb docstring）
        kept = prepare_fast_path(bootstrap, _deps=_fast_deps(search_qa=lambda query: dict(accepted)))
        assert kept["qa_hit"] is not None
        assert not [r for r in records if getattr(r, "qa_provenance_refused", False)], "放行也留痕 ⇒ 计数不可用"
    finally:
        chat_logger.removeHandler(handler)
        chat_logger.setLevel(previous_level)


# ==================== 票 W1：时效判据上提到产生处（两出口对称收口） ====================
# 上面那组用例闭的是**形状**判据（引用给不给得出）。第 8 节② 的漏口还有另一半：
# "引用的那条文今天还在不在库"这步只写在 `main._qa_direct_return` 里（时效护栏），
# 产生处从来不做 ⇒ 一条引用已失效条文的记录照样进 `pre["qa_hit"]`，被
# `main._build_messages` 以"此前已确认的问答（可优先参考）"递给模型。Owner 裁决（2026-09-25）：
# 对称收口、判据上提到产生处，且两个出口调**同一个**函数（见
# `tests/test_qa_citation_gate_symmetry.py` 的那条同一性断言）。

_CITABLE_QA = {
    "question": "试用期最长多久",
    "answer": "最长六个月",
    "score": 0.95,
    "fingerprint": "",
    "evidence": "劳动合同法|第十九条",
    "law_as_of_basis": "2026-01-01",
}


@pytest.mark.parametrize("basis", ["not-a-date", "2026-02-30"])
def test_invalid_qa_basis_never_reaches_prompt_or_kb(store, monkeypatch, basis):
    from main import _build_messages

    calls = []
    _patch_kb(monkeypatch, ["doc"], calls=calls)
    qa = dict(_CITABLE_QA, law_as_of_basis=basis)
    result = prepare_fast_path(_citation_bootstrap(store), _deps=_fast_deps(search_qa=lambda query: qa))
    text = "\n".join(m.content or "" for m in _build_messages(result))

    assert result["qa_hit"] is None
    assert "此前已确认的问答" not in text
    assert qa["answer"] not in text
    assert calls == []


@pytest.mark.parametrize("score,expected_lookups", [(0.8, 1), (0.95, 2)])
def test_w1_lookup_count_characterization(store, monkeypatch, score, expected_lookups):
    """现状基线而非性能目标：完整准备→直返接缝的查条次数，不把次数冒充延迟。"""
    from main import _build_messages, _qa_direct_return

    calls = []
    _patch_kb(monkeypatch, ["doc"], calls=calls)
    qa = dict(_CITABLE_QA, score=score)
    result = prepare_fast_path(_citation_bootstrap(store), _deps=_fast_deps(search_qa=lambda query: qa))
    direct = _qa_direct_return(result, date(2026, 9, 25))

    if score == 0.95:
        assert direct == qa["answer"]
    else:
        assert direct is None
        assert qa["answer"] in "\n".join(m.content or "" for m in _build_messages(result))
    assert calls == [("劳动合同法", "第十九条")] * expected_lookups


def _citation_bootstrap(store):
    return bootstrap_request(store.user_id, store.conv_id, "借款纠纷", None, False, _deps=_bootstrap_deps(store))


def test_fast_path_drops_qa_hit_whose_citation_is_not_in_kb(store, monkeypatch):
    """先红腿：引用给得出、条文查不在库 ⇒ 产生处就不该把它交给任何一个出口。

    旧行为下本用例红在**判据点**（`qa_hit` 仍是那条记录），不是红在插桩：库替身返回 `[]`
    在旧代码里根本不会被调用，而形状判据 `qa_provenance_verifiable` 对此记录是**放行**的
    （它只问"引用给不给得出"，不问"引用可不可核验"）。
    """
    _patch_kb(monkeypatch, [])

    result = prepare_fast_path(_citation_bootstrap(store), _deps=_fast_deps(search_qa=lambda query: dict(_CITABLE_QA)))

    assert result["qa_hit"] is None, "失效引用仍进 qa_hit ⇒ 直返之外的注入通道带着旧答案进 prompt"


def test_fast_path_keeps_qa_hit_whose_citation_is_in_kb(store, monkeypatch):
    """控制腿（必须两侧都绿）：条文在库 ⇒ 照常保留 qa_hit，否则这次收口等于整体关掉语料加速。"""
    _patch_kb(monkeypatch, ["doc"])
    from main import _build_messages

    result = prepare_fast_path(_citation_bootstrap(store), _deps=_fast_deps(search_qa=lambda query: dict(_CITABLE_QA)))

    assert result["qa_hit"] == _CITABLE_QA
    assert "此前已确认的问答" in "\n".join(getattr(m, "content", "") or "" for m in _build_messages(result))


def test_prompt_omits_stale_citation_qa_from_the_producer_result(store, monkeypatch):
    """链条后半：喂进 `main._build_messages` 的是产生处**实际返回**的那个 `pre`，不自造。

    与 `test_qa_provenance_guard.py::test_prompt_omits_note_when_the_producer_dropped_the_hit`
    同款纪律——那条的 docstring 就写明"只测后半等于没测"。旧行为下本用例同样红：
    `qa_hit` 非 None ⇒ 注入照旧发生。
    """
    _patch_kb(monkeypatch, [])

    result = prepare_fast_path(_citation_bootstrap(store), _deps=_fast_deps(search_qa=lambda query: dict(_CITABLE_QA)))
    from main import _build_messages

    text = "\n".join(getattr(m, "content", "") or "" for m in _build_messages(result))
    assert "此前已确认的问答" not in text
    assert "最长六个月" not in text, "失效问答的答案仍进 prompt"


def test_fast_path_drops_qa_hit_when_article_lookup_raises(store, monkeypatch):
    """fail-closed 腿：库读不动 ⇒ 不能校验就当不校验（与直返出口既有的 `except Exception` 同口径）。

    这一半是**新增面**：旧产生处压根不碰库，所以"查不动"与"查得到"在它眼里没有区别。
    """

    def _boom(src, art):
        raise RuntimeError("chroma 读失败")

    import retrieval

    monkeypatch.setattr(retrieval, "exact_article_lookup", _boom)

    result = prepare_fast_path(_citation_bootstrap(store), _deps=_fast_deps(search_qa=lambda query: dict(_CITABLE_QA)))

    assert result["qa_hit"] is None


def test_shape_gate_runs_before_the_kb_and_skips_the_lookup(store, monkeypatch):
    """判据顺序腿：形状判据先拒 ⇒ **不碰库**（无效形状不该白付一次读库成本）。

    见证记录刻意选"**引用给得出、缺 `law_as_of_basis`**"而不是"`evidence='[]'`"：
    后者在 `qa_citations_in_kb` 内部因解析不出成对引用而**根本不会查库** ⇒ 拿它当见证，
    两道门换序也照样绿（仪器看不见被检的性质）。用缺 basis 的形状，"先查库"就会留下 calls ⇒ 红。
    旧行为下本用例也绿（产生处从不碰库），它钉的是新实现的分支可达性。
    """
    calls: list[tuple[str, str]] = []
    _patch_kb(monkeypatch, ["doc"], calls=calls)
    no_basis = {"question": "q", "answer": "a", "evidence": "劳动合同法|第十九条", "law_as_of_basis": ""}

    result = prepare_fast_path(_citation_bootstrap(store), _deps=_fast_deps(search_qa=lambda query: dict(no_basis)))

    assert result["qa_hit"] is None
    assert calls == [], f"形状判据已拒仍去查库 ⇒ 每条无效记录都白付一次读库成本：{calls}"


def test_citation_refused_qa_hit_leaves_a_log_trace(store, monkeypatch):
    """拦截要留痕，且与形状判据**分键**：两个门是两个数，合成一个就没法归因是哪道在衰减。

    腿：① 失效引用 ⇒ `qa_citation_refused` 恰好一次，且不落 `qa_provenance_refused`（形状门没参与）；
    ② 在库 ⇒ 两个键都不落；③ 不落问句原文（AUTH-3）；④ JSON formatter 真能把这个键带出来
    （白名单外的键会被静默丢弃 ⇒ 只在 Python 对象上断言等于没断言）。
    """
    _patch_kb(monkeypatch, [])
    raw_query = "借款合同纠纷怎么起诉"
    bootstrap = bootstrap_request(store.user_id, store.conv_id, raw_query, None, False, _deps=_bootstrap_deps(store))
    stale = dict(_CITABLE_QA, question=raw_query)

    chat_logger = logging.getLogger("legal.chat")
    records: list[logging.LogRecord] = []

    class _Handler(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            records.append(record)

    handler = _Handler(level=logging.WARNING)
    previous_level = chat_logger.level
    chat_logger.addHandler(handler)
    chat_logger.setLevel(logging.WARNING)
    try:
        dropped = prepare_fast_path(bootstrap, _deps=_fast_deps(search_qa=lambda query: dict(stale)))
        fired = [r for r in records if getattr(r, "qa_citation_refused", False)]
        assert dropped["qa_hit"] is None
        assert len(fired) == 1, "失效引用被拦但无线上痕迹 ⇒ 直返率下降不可归因"
        assert not [r for r in records if getattr(r, "qa_provenance_refused", False)], "两键串了 ⇒ 归因失真"

        from observability import _JsonFormatter

        assert json.loads(_JsonFormatter().format(fired[0]))["qa_citation_refused"] is True
        assert raw_query not in " ".join([r.getMessage() for r in fired] + [repr(fired[0].__dict__)])

        records.clear()
        _patch_kb(monkeypatch, ["doc"])
        kept = prepare_fast_path(bootstrap, _deps=_fast_deps(search_qa=lambda query: dict(stale)))
        assert kept["qa_hit"] is not None
        assert not [r for r in records if getattr(r, "qa_citation_refused", False)], "放行也留痕 ⇒ 计数不可用"
    finally:
        chat_logger.removeHandler(handler)
        chat_logger.setLevel(previous_level)


def test_historical_fast_path_uses_date_for_all_evidence_and_skips_current_qa(store):
    old = SimpleNamespace(
        metadata={
            "source": "旧法",
            "article": "第一条",
            "effective_from": "2010-01-01",
            "effective_to": "2020-12-31",
            "status": "已废止",
        }
    )
    new = SimpleNamespace(
        metadata={
            "source": "新法",
            "article": "第一条",
            "effective_from": "2021-01-01",
            "effective_to": "",
            "status": "现行",
        }
    )
    seen_cutoffs = []
    bootstrap = bootstrap_request(
        store.user_id,
        store.conv_id,
        "借款纠纷",
        None,
        False,
        law_as_of=date(2019, 1, 1),
        _deps=_bootstrap_deps(store),
    )
    deps = _fast_deps(
        retrieve=lambda query, k, cutoff: seen_cutoffs.append(cutoff) or [old, new],
        scenario_supplement_docs=lambda query, cutoff: seen_cutoffs.append(cutoff) or [new],
        search_qa=lambda query: {"question": query, "answer": "现行法答案"},
        format_docs=lambda docs: ",".join(doc.metadata["source"] for doc in docs),
    )

    result = prepare_fast_path(bootstrap, _deps=deps)

    assert len(seen_cutoffs) == 2, seen_cutoffs  # 语义检索 + 场景补充两条取数口都须带上基准日
    assert set(seen_cutoffs) == {"2019-01-01"}, seen_cutoffs
    assert result["context"] == "旧法"
    assert [source["source"] for source in result["sources"]] == ["旧法"]
    assert result["qa_hit"] is None
    assert result["law_as_of"] == date(2019, 1, 1)

    from main import _build_messages

    assert "2019-01-01" in _build_messages(result)[-1].content


# ==================== 历史查询：每条取数口都按基准日捞（AUTH-2 续） ====================
# 只在末尾过滤是不够的：末尾过滤保证的是「不把现行法下发给历史查询」（精度），
# 而「历史有效版本有没有被召回」（召回）取决于取数时带的 cutoff。
# 下面逐个分支钉第二件事——缺一个分支，该分支的历史查询就会静默变薄或拿错版。

HISTORICAL = date(2019, 1, 1)


def _historical_bootstrap(store, **bootstrap_dep_overrides):
    return bootstrap_request(
        store.user_id,
        store.conv_id,
        "借款合同纠纷",
        None,
        False,
        law_as_of=HISTORICAL,
        _deps=_bootstrap_deps(store, **bootstrap_dep_overrides),
    )


def _pre_cutoff_doc():
    """2021-01-01 起生效：在 2019 基准日下**不该**出现。"""
    return SimpleNamespace(
        metadata={
            "source": "民法典",
            "article": "第五百八十五条",
            "effective_from": "2021-01-01",
            "effective_to": "",
            "status": "现行",
        }
    )


def _historical_doc():
    return SimpleNamespace(
        metadata={
            "source": "合同法",
            "article": "第一百一十四条",
            "effective_from": "1999-10-01",
            "effective_to": "2021-01-01",
            "status": "已废止",
        }
    )


def _docs_by_cutoff(seen, label=None):
    """按 cutoff 分流的取数桩：带基准日 → 旧法，不带 → 现行法。

    旧实现把 cutoff 丢在调用点 ⇒ 桩只会拿到现行法 ⇒ 末尾过滤再把这唯一一条剔掉
    ⇒ `sources` 为空。故本桩同时验「带了日期」与「带对日期（真去改了取数口径）」。
    """

    def _factory(*args, **kwargs):
        cutoff = kwargs.get("cutoff")
        seen.append((label, cutoff) if label is not None else cutoff)
        return [_historical_doc() if cutoff else _pre_cutoff_doc()]

    return _factory


def test_historical_exam_branch_fetches_exam_units_at_cutoff(store):
    seen = []
    bootstrap = _historical_bootstrap(store, is_exam_question=lambda query: True)
    deps = _fast_deps(
        scenario_supplement_docs=_docs_by_cutoff(seen, "supplement"),
        retrieve_exam=_docs_by_cutoff(seen, "exam"),
    )

    result = prepare_fast_path(bootstrap, _deps=deps)

    assert [name for name, _ in seen] == ["supplement", "exam"], seen
    assert {cutoff for _, cutoff in seen} == {HISTORICAL.isoformat()}, seen
    assert {s["source"] for s in result["sources"]} == {"合同法"}, result["sources"]


def test_historical_study_aid_branch_fetches_exam_units_at_cutoff(store):
    seen = []
    bootstrap = _historical_bootstrap(store, classify_intent=lambda query: "study_aid")
    deps = _fast_deps(
        scenario_supplement_docs=lambda query, cutoff=None: seen.append(("supplement", cutoff)) or [],
        retrieve_exam=lambda query, k=6, cutoff=None: seen.append(("exam", cutoff)) or [_historical_doc()],
    )

    prepare_fast_path(bootstrap, _deps=deps)

    assert [cutoff for _, cutoff in seen] == [HISTORICAL.isoformat()] * 2, seen


def test_historical_cheating_branch_fetches_spec_docs_at_cutoff(store):
    seen = []
    bootstrap = _historical_bootstrap(store, classify_intent=lambda query: "cheating_request")
    deps = _fast_deps(cheating_docs=lambda cutoff=None: seen.append(cutoff) or [_historical_doc()])

    result = prepare_fast_path(bootstrap, _deps=deps)

    assert seen == [HISTORICAL.isoformat()], seen
    assert [s["source"] for s in result["sources"]] == ["合同法"], result["sources"]


def test_historical_consumer_scenarios_fetch_spec_docs_at_cutoff(store):
    seen = []
    bootstrap = _historical_bootstrap(store)
    deps = _fast_deps(
        scenario_supplement_docs=_docs_by_cutoff(seen, "supplement"),
        is_consumer_clause_scenario=lambda query: True,
        consumer_clause_docs=_docs_by_cutoff(seen, "clause"),
        is_consumer_fraud_scenario=lambda query: True,
        consumer_fraud_docs=_docs_by_cutoff(seen, "fraud"),
    )

    result = prepare_fast_path(bootstrap, _deps=deps)

    assert [name for name, _ in seen] == ["supplement", "clause", "fraud"], seen
    assert {cutoff for _, cutoff in seen} == {HISTORICAL.isoformat()}, seen
    assert {s["source"] for s in result["sources"]} == {"合同法"}, result["sources"]


def test_historical_contract_branch_builds_evidence_at_cutoff(store):
    """合同证据必须**按基准日构建**：`blocks` 与 `docs` 同源，事后重过滤改不到 blocks。"""
    seen = []
    bootstrap = _historical_bootstrap(store, is_contract_review=lambda query: True)

    def build_contract_data(text, cutoff=None):
        seen.append(cutoff)
        doc = _historical_doc() if cutoff else _pre_cutoff_doc()
        return {
            "docs": [doc],
            "blocks": [
                {"n": 1, "label": "违约责任", "text": "违约金条款", "articles": [doc.metadata["article"]], "tags": []}
            ],
            "level": "中",
            "basis": "test",
        }

    deps = _fast_deps(
        build_contract_data=build_contract_data, format_docs=lambda docs: "、".join(d.metadata["source"] for d in docs)
    )

    result = prepare_fast_path(bootstrap, _deps=deps)

    assert seen == [HISTORICAL.isoformat()], seen
    assert result["contract_data"]["blocks"][0]["articles"] == ["第一百一十四条"], result["contract_data"]
    assert [s["source"] for s in result["sources"]] == ["合同法"], result["sources"]


def test_current_date_contract_branch_is_unchanged(store):
    """对照组：不带基准日 ⇒ 传 None ⇒ 合同证据取现行法（生产默认路径零变化）。"""
    seen = []
    bootstrap = bootstrap_request(
        store.user_id,
        store.conv_id,
        "借款合同纠纷",
        None,
        False,
        _deps=_bootstrap_deps(store, is_contract_review=lambda query: True),
    )

    def build_contract_data(text, cutoff=None):
        seen.append(cutoff)
        doc = _historical_doc() if cutoff else _pre_cutoff_doc()
        return {"docs": [doc], "blocks": [], "level": "低", "basis": "test"}

    result = prepare_fast_path(bootstrap, _deps=_fast_deps(build_contract_data=build_contract_data))

    assert seen == [None], seen
    assert [s["source"] for s in result["sources"]] == ["民法典"], result["sources"]


def test_contract_messages_mark_historical_baseline_date(store):
    """合同链的模型可见上下文必须标出基准日，与 `_build_messages` 同口径。

    不标 ⇒ 模型拿到的是一版旧法，却按现行法措辞作答（民法典时代语境）。
    对照组（无基准日不出现该标注）防止把标注写成无条件字面量。
    """
    from main import _contract_messages

    contract_data = {
        "docs": [_historical_doc()],
        "blocks": [
            {
                "n": 1,
                "label": "违约责任",
                "text": "违约金条款",
                "articles": ["第一百一十四条"],
                "tags": ["违约"],
            }
        ],
        "level": "中",
        "basis": "test",
    }
    deps = _fast_deps(build_contract_data=lambda text, cutoff=None: contract_data)
    historical = prepare_fast_path(_historical_bootstrap(store, is_contract_review=lambda query: True), _deps=deps)
    current = prepare_fast_path(
        bootstrap_request(
            store.user_id,
            store.conv_id,
            "借款合同纠纷",
            None,
            False,
            _deps=_bootstrap_deps(store, is_contract_review=lambda query: True),
        ),
        _deps=deps,
    )

    assert "2019-01-01" in _contract_messages(historical, contract_data)[-1].content
    assert "法律版本基准日" not in _contract_messages(current, contract_data)[-1].content


# ---------------- 口径②（2026-10-13 裁定）：退出只认本轮明示短命令，贴入的合同正文不作退出指令 ----------------
def test_contract_body_words_do_not_exit_contract_mode():
    """合同正文里写着"合同结束""暂停履行"，那是文档内容，不是用户的退出指令。"""
    pasted = chr(10).join(
        [
            "第五条 本合同结束后的三十日内，押金不予退还。",
            "第六条 双方可协商暂停履行，暂停期间不计违约金。",
            "第七条 一方提出终止的，应提前三十日通知；合同结束时未结算款项按下列方式处理。",
        ]
    )
    assert is_contract_exit(pasted) is False


def test_long_prose_with_exit_phrase_does_not_exit():
    prose = "我们之前那份合同我还在考虑，不过你说如果双方协商一致的话，结束合同之后押金到底怎么退？"
    assert len(prose) > 20
    assert is_contract_exit(prose) is False


def test_explicit_short_exit_commands_still_exit():
    for t in ("结束合同", "换个话题", "退出合同。", "不审合同了"):
        assert is_contract_exit(t) is True, t


def test_bare_pause_and_stop_words_no_longer_exit():
    """裸词不再算退出：含糊时交确认（裁定），不静默退出——这也是"合同正文自触发退出"的根因。"""
    for t in ("暂停", "结束", "先暂停一下"):
        assert is_contract_exit(t) is False, t


def _keep_touched():
    """把模块级时间戳表存/还原，避免用例互相污染。"""
    import request_bootstrap as rb

    before = dict(rb._contract_touched)
    return rb, before


def test_contract_state_expires_after_idle_ttl():
    """口径②：状态不落盘但必须有过期边界——闲置超过 TTL 即**摘除**（不只是判 False）。"""
    rb, before = _keep_touched()
    active = {7}
    rb._contract_touched[7] = 1000.0
    try:
        assert rb.contract_session_active(7, active, now=1000.0 + rb.CONTRACT_IDLE_TTL_S - 1) is True
        rb._contract_touched[7] = 1000.0  # 重置时间戳：这是闲置 TTL，上一次调用已续期
        assert rb.contract_session_active(7, active, now=1000.0 + rb.CONTRACT_IDLE_TTL_S + 1) is False
        assert 7 not in active
        assert 7 not in rb._contract_touched
    finally:
        rb._contract_touched.clear()
        rb._contract_touched.update(before)


def test_contract_turn_refreshes_idle_clock():
    """本轮活跃即续期：这是闲置 TTL，不是绝对 TTL。"""
    rb, before = _keep_touched()
    active = {8}
    rb._contract_touched[8] = 1000.0
    try:
        mid = 1000.0 + rb.CONTRACT_IDLE_TTL_S - 1
        assert rb.contract_session_active(8, active, now=mid) is True
        assert rb._contract_touched[8] == mid
        assert rb.contract_session_active(8, active, now=mid + rb.CONTRACT_IDLE_TTL_S - 1) is True
    finally:
        rb._contract_touched.clear()
        rb._contract_touched.update(before)


def test_legacy_entry_without_timestamp_is_not_killed():
    """旧路径（无时间戳）的会话当活跃并补记，避免升级瞬间把在途会话全判死。"""
    rb, before = _keep_touched()
    active = {9}
    rb._contract_touched.pop(9, None)
    try:
        assert rb.contract_session_active(9, active) is True
        assert 9 in rb._contract_touched
    finally:
        rb._contract_touched.clear()
        rb._contract_touched.update(before)
