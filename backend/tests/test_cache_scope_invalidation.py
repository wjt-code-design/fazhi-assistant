"""Cache correctness at real module/API seams; all IO stays in isolated fixtures."""

import logging
import threading
from datetime import datetime
from logging.handlers import BufferingHandler
from types import SimpleNamespace

import pytest
from langchain_core.documents import Document

import answer_cache as ac
import knowledge_service as ks
import main
import quality
import retrieval as r
import retrieval_core as rc
from observability import _JsonFormatter
from tests import _sse_harness as harness


@pytest.fixture(autouse=True)
def isolated_cache(monkeypatch):
    # TestClient lifespan 会配置进程级日志；恢复它，避免新测试污染后续 caplog 判据。
    loggers = [logging.getLogger(name) for name in ("legal", "legal.access", "legal.chat", "uvicorn.access")]
    logger_state = [(logger, logger.handlers[:], logger.level, logger.propagate, logger.disabled) for logger in loggers]
    r.invalidate()
    monkeypatch.setattr(main.settings, "agent_enabled", False)
    monkeypatch.setattr(main.settings, "rerank_enabled", False)
    monkeypatch.setattr(main.settings, "feature_similar_cache", True)
    monkeypatch.setattr(main, "_embed_question", lambda text: [1.0, 0.0])
    monkeypatch.setattr(main, "_post", lambda *a, **kw: None)
    monkeypatch.setattr(quality, "self_check", lambda answer, context_present: quality.Verdict(True))
    yield
    r.invalidate()
    for logger, handlers, level, propagate, disabled in logger_state:
        logger.handlers[:] = handlers
        logger.setLevel(level)
        logger.propagate = propagate
        logger.disabled = disabled


def _pre(intent="legal_query", source="民法典", effective_from="2020-01-01"):
    return {
        "rewritten": "请解释这个问题的处理原则",
        "intent": intent,
        "sources": [{"source": source, "article": "第一条", "effective_from": effective_from}],
    }


def test_cache_write_guard_rejects_other_law_same_article():
    assert main._cache_write_ok(_pre(intent="study_aid"), "依据《刑法》第一条。") is False


def test_cache_write_guard_accepts_existing_name_and_article_normalization():
    assert main._cache_write_ok(_pre(intent="study_aid"), "依据《中华人民共和国民法典》第1条。") is True


def test_cache_key_includes_existing_version_metadata():
    assert main._cache_key(_pre()) != main._cache_key(_pre(effective_from="2026-10-01"))


@pytest.mark.parametrize("different", ["intent", "cutoff", "context_ids"])
def test_similar_cache_cannot_cross_scope(different):
    assert hasattr(ac, "make_scope"), "Similarity needs an explicit intent/day/evidence scope"
    scope = ac.make_scope("legal_query", "2026-10-01", ["法甲|第一条"])
    ac.put("old", "OLD", [], embedding=[1.0, 0.0], scope=scope)
    intent, cutoff, ids = "legal_query", "2026-10-01", ["法甲|第一条"]
    if different == "intent":
        intent = "study_aid"
    elif different == "cutoff":
        cutoff = "2026-10-02"
    else:
        ids = ["法乙|第一条"]
    assert ac.get_similar([1.0, 0.0], scope=ac.make_scope(intent, cutoff, ids)) is None


def test_similar_cache_same_scope_still_hits_with_order_independent_evidence():
    assert hasattr(ac, "make_scope"), "Similarity needs an explicit intent/day/evidence scope"
    scope = ac.make_scope("legal_query", "2026-10-01", ["b", "a", "a"])
    ac.put("old", "SAME_SCOPE", [], embedding=[1.0, 0.0], scope=scope)
    hit = ac.get_similar([0.99, 0.01], scope=ac.make_scope("legal_query", "2026-10-01", ["a", "b"]))
    assert hit and hit["answer"] == "SAME_SCOPE"


def test_legacy_entries_without_scope_do_not_participate_in_similarity():
    ac.put("old", "LEGACY", [], embedding=[1.0, 0.0])
    assert ac.get_similar([1.0, 0.0]) is None
    scope = ac.make_scope("legal_query", "2026-10-01", ["民法典|第一条"])
    assert ac.get_similar([1.0, 0.0], scope=scope) is None
    assert ac.get("old")["answer"] == "LEGACY"


def test_lru_rejects_old_generation_and_accepts_current_generation():
    cache = rc.LRU()
    assert hasattr(cache, "generation"), "Invalidation needs an atomic stale-writer guard"
    old = cache.generation()
    cache.clear()
    cache.put("old", "STALE", generation=old)
    assert cache.get("old") is None
    cache.put("new", "FRESH", generation=cache.generation())
    assert cache.get("new") == "FRESH"


@pytest.mark.parametrize("hybrid", [False, True])
def test_old_retrieval_cannot_repopulate_after_invalidation(monkeypatch, hybrid):
    old = Document(page_content="OLD", metadata={"source": "测试法", "article": "第一条"})
    new = Document(page_content="NEW", metadata={"source": "测试法", "article": "第一条"})
    active = [old]
    entered, release = threading.Event(), threading.Event()
    outputs, errors = [], []

    def vector(*args, **kwargs):
        snapshot = active[0]
        if snapshot is old:
            entered.set()
            assert release.wait(10)
        return [(snapshot, 0.0)]

    def query():
        try:
            outputs.extend(r.hybrid_retrieve("缓存代次回归", cutoff="2026-10-01"))
        except BaseException as exc:
            errors.append(exc)

    monkeypatch.setattr(r, "HYBRID", hybrid)
    monkeypatch.setattr(r.settings, "query_rewrite_enabled", False)
    monkeypatch.setattr(r, "vector_top", vector)
    monkeypatch.setattr(r, "bm25_top", lambda *a, **kw: [])
    monkeypatch.setattr(r, "_cosine_rank", lambda query, docs: docs)
    worker = threading.Thread(target=query, daemon=True)
    worker.start()
    try:
        assert entered.wait(10)
        active[0] = new
        r.invalidate()
    finally:
        release.set()
        worker.join(10)
    assert not worker.is_alive() and not errors
    assert outputs == [old]  # An already-started request may finish.
    assert r.hybrid_retrieve("缓存代次回归", cutoff="2026-10-01") == [new]


def test_bm25_uses_consistent_snapshot_when_invalidation_intervenes(monkeypatch):
    old = Document(page_content="OLD", metadata={})
    monkeypatch.setattr(r, "_bm25", SimpleNamespace(get_scores=lambda query: [1.0]))
    monkeypatch.setattr(r, "_bm25_docs", [old])
    original = r._ensure_bm25

    def capture_then_invalidate():
        snapshot = original()
        r.invalidate()
        return snapshot

    monkeypatch.setattr(r, "_ensure_bm25", capture_then_invalidate)
    assert r.bm25_top("一致快照", 1) == [(old, 1.0)]


def test_source_set_uses_consistent_snapshot_when_invalidation_intervenes(monkeypatch):
    monkeypatch.setattr(
        r,
        "vectorstore",
        SimpleNamespace(_collection=SimpleNamespace(get=lambda **kw: {"metadatas": [{"source": "测试法"}]})),
    )
    original = r._ensure_src_set

    def capture_then_invalidate():
        snapshot = original()
        r.invalidate()
        return snapshot

    monkeypatch.setattr(r, "_ensure_src_set", capture_then_invalidate)
    assert r.source_in_kb("测试法") is True


def test_upload_replacement_invalidates_after_old_documents_are_deleted(monkeypatch):
    old = Document(page_content="第一条 旧版正文", metadata={"source": "测试法", "article": "第一条"})
    active = [old]
    entered, release = threading.Event(), threading.Event()
    errors = []

    def delete(ids):
        entered.set()
        assert release.wait(10)
        active.remove(old)

    collection = SimpleNamespace(get=lambda **kw: {"ids": ["old-id"]}, delete=delete)
    monkeypatch.setattr(
        ks, "vectorstore", SimpleNamespace(_collection=collection, add_documents=lambda docs: active.extend(docs))
    )
    monkeypatch.setattr(r, "vector_top", lambda *a, **kw: [(active[0], 0.0)])
    monkeypatch.setattr(r, "bm25_top", lambda *a, **kw: [])
    monkeypatch.setattr(r, "_cosine_rank", lambda query, docs: docs)
    monkeypatch.setattr(r, "HYBRID", True)
    monkeypatch.setattr(r.settings, "query_rewrite_enabled", False)

    def update():
        try:
            ks.add_text("第一条 新版正文", "测试法", origin="upload", file_hash_value="fake-hash")
        except BaseException as exc:
            errors.append(exc)

    worker = threading.Thread(target=update, daemon=True)
    worker.start()
    try:
        assert entered.wait(10)
        assert r.hybrid_retrieve("重传窗口回归", cutoff="2026-10-01")[0] == old
    finally:
        release.set()
        worker.join(10)
    assert not worker.is_alive() and not errors
    assert r.hybrid_retrieve("重传窗口回归", cutoff="2026-10-01")[0] != old


def test_partial_add_failure_still_invalidates_existing_answers(monkeypatch):
    ac.put("old", "OLD", [])

    def partial_write(docs):
        raise RuntimeError("fake partial write failure")

    monkeypatch.setattr(ks, "vectorstore", SimpleNamespace(add_documents=partial_write))
    with pytest.raises(RuntimeError, match="fake partial write failure"):
        ks.add_chunks([("第一条 新版正文", {"article": "第一条"})], "测试法", "manual")
    assert ac.get("old") is None


@pytest.mark.parametrize("write_error", [RuntimeError("FAKE_SENSITIVE_WRITE"), KeyboardInterrupt()])
def test_add_failure_remains_primary_when_invalidation_also_fails(monkeypatch, write_error):
    def failed_write(docs):
        raise write_error

    def failed_invalidation():
        raise ValueError("FAKE_SENSITIVE_INVALIDATION")

    capture = BufferingHandler(10)
    monkeypatch.setattr(ks.logger, "handlers", [capture])
    monkeypatch.setattr(ks.logger, "level", logging.WARNING)
    monkeypatch.setattr(ks.logger, "propagate", False)
    monkeypatch.setattr(ks, "vectorstore", SimpleNamespace(add_documents=failed_write))
    with monkeypatch.context() as fault:
        fault.setattr(r, "invalidate", failed_invalidation)
        with pytest.raises(type(write_error)) as raised:
            ks.add_chunks([("第一条 测试正文", {"article": "第一条"})], "测试法", "manual")
    assert raised.value is write_error
    assert len(capture.buffer) == 1
    record = capture.buffer[0]
    payload = _JsonFormatter().format(record)
    assert "ValueError" in payload
    assert "FAKE_SENSITIVE" not in payload
    assert record.exc_info is None


def test_successful_add_does_not_hide_invalidation_failure(monkeypatch):
    written = []
    cleanup_error = ValueError("fake invalidation failure")

    def failed_invalidation():
        raise cleanup_error

    monkeypatch.setattr(ks, "vectorstore", SimpleNamespace(add_documents=lambda docs: written.extend(docs)))
    with monkeypatch.context() as fault:
        fault.setattr(r, "invalidate", failed_invalidation)
        with pytest.raises(ValueError) as raised:
            ks.add_chunks([("第一条 测试正文", {"article": "第一条"})], "测试法", "manual")
    assert raised.value is cleanup_error
    assert [doc.page_content for doc in written] == ["第一条 测试正文"]


@pytest.mark.parametrize("route", ["flagship_stream", "light_buffered", "contract_review"])
@pytest.mark.parametrize("invalidate_at", ["retrieval", "model"])
def test_api_all_answer_writers_reject_invalidated_request(monkeypatch, route, invalidate_at):
    with harness.sse_client(monkeypatch, route=route, flagship_parts=harness.CONTRACT_PARTS) as client:
        if invalidate_at == "retrieval":
            name = "build_contract_data" if route == "contract_review" else "retrieve"
            original = getattr(main, name)

            def retrieve_then_invalidate(*args, **kwargs):
                result = original(*args, **kwargs)
                r.invalidate()
                return result

            monkeypatch.setattr(main, name, retrieve_then_invalidate)
        elif route == "light_buffered":
            original = harness._FakeInvokableLLM.invoke

            def invoke_then_invalidate(self, messages):
                result = original(self, messages)
                r.invalidate()
                return result

            monkeypatch.setattr(harness._FakeInvokableLLM, "invoke", invoke_then_invalidate)
        else:
            original_stream = harness._FakeChain.astream

            async def stream_then_invalidate(self, messages):
                r.invalidate()
                async for piece in original_stream(self, messages):
                    yield piece

            monkeypatch.setattr(harness._FakeChain, "astream", stream_then_invalidate)
        token = harness.login(client)
        frames = harness.chat_frames(client, token, "请说明这件劳动争议的处理原则")
        assert harness.content_of(frames)
        assert ac.__len__() == 0


@pytest.mark.parametrize("route", ["flagship_stream", "light_buffered", "contract_review"])
def test_api_current_request_still_populates_answer_cache(monkeypatch, route):
    with harness.sse_client(monkeypatch, route=route, flagship_parts=harness.CONTRACT_PARTS) as client:
        token = harness.login(client)
        frames = harness.chat_frames(client, token, "请说明这件劳动争议的处理原则")
        assert harness.content_of(frames)
        assert ac.__len__() == 1


def test_api_similarity_cannot_reuse_answer_from_different_retrieved_source(monkeypatch):
    parts = [harness.FLAGSHIP_PARTS]
    with harness.sse_client(monkeypatch) as client:
        monkeypatch.setattr(main, "make_chain", lambda llm: harness._FakeChain(parts[0]))
        token = harness.login(client)
        first = harness.chat_frames(client, token, "请说明这件劳动争议的处理原则")
        assert "六个月" in "".join(harness.content_of(first))
        parts[0] = ("依据《民法典》第一条，", "这是另一组证据下的新答案。")
        monkeypatch.setattr(
            main,
            "retrieve",
            lambda *a, **kw: [
                Document(page_content="第一条 测试正文", metadata={"source": "民法典", "article": "第一条"})
            ],
        )
        second = harness.chat_frames(client, token, "请解释另一件争议的处理原则")
        assert "新答案" in "".join(harness.content_of(second))


def test_api_same_scope_similarity_still_reuses_answer(monkeypatch):
    with harness.sse_client(monkeypatch) as client:
        token = harness.login(client)
        first = harness.chat_frames(client, token, "请说明这件劳动争议的处理原则")
        monkeypatch.setattr(
            main, "make_chain", lambda llm: pytest.fail("Same-scope cache should avoid model invocation")
        )
        second = harness.chat_frames(client, token, "请解释这件劳动争议的处理原则")
        assert "".join(harness.content_of(second)) == "".join(harness.content_of(first))


def test_api_cached_day_is_not_recomputed_after_midnight(monkeypatch):
    clock = [datetime(2026, 10, 1, 23, 50)]
    monkeypatch.setattr(main, "_cutoff", lambda: clock[0].date().isoformat())
    with harness.sse_client(monkeypatch) as client:
        original = harness._FakeChain.astream

        async def cross_midnight(self, messages):
            clock[0] = datetime(2026, 10, 2, 0, 10)
            async for piece in original(self, messages):
                yield piece

        monkeypatch.setattr(harness._FakeChain, "astream", cross_midnight)
        token = harness.login(client)
        harness.chat_frames(client, token, "请说明这件劳动争议的处理原则")
        values = ac._cache.items()
        assert len(values) == 1
        assert "scope" in values[0][1], "Answer entries must retain the request's captured scope"
        assert values[0][1]["scope"][1] == "2026-10-01"
