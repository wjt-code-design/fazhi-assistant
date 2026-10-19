"""C21-A Task 2 适配器合同测试（S13–S18）。

覆盖 `knowledge_service.search_eligible_qa` 的一次 k=9 取数、两条 metric 计分分支、资格唯一真源、
边界哨兵、失败不放行与日志格式化，以及 `request_bootstrap._default_fast_path_dependencies` 的真实绑定。

隔离：临时 SQLite（`db` 把 `database.SessionLocal` 换到 tmp 引擎）＋进程私有 `CHROMA_DIR`＋
**fake QA store**（记录请求并给出确定分数）；不碰真实 `app.db`／真实 `chroma_db`／真实嵌入模型。
"""

from __future__ import annotations

import itertools
import json
import logging
import os
import subprocess
import sys
import uuid
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import knowledge_service as ks  # noqa: E402
import main  # noqa: E402
import qa_eligibility as qe  # noqa: E402
import request_bootstrap as rb  # noqa: E402
import retrieval  # noqa: E402
from observability import _JsonFormatter  # noqa: E402

EVIDENCE = json.dumps([{"source": "中华人民共和国劳动合同法", "article": "第十九条"}], ensure_ascii=False)
ANSWER = "《劳动合同法》第十九条对试用期上限作了分层规定；同一用人单位与同一劳动者只能约定一次试用期。"
OTHER_ANSWER = "不采用方案甲：这条答案与上一条不是同一版本。"
QUESTION = "合成问题甲：试用期可以约定几次？"


class FakeQaStore:
    """替身 QA 集合：记录 `similarity_search_with_score` 的入参，返回给定 (doc, distance) 列表。"""

    def __init__(self, results=None, *, space="cosine", error=None):
        self.calls: list[tuple[str, int]] = []
        self.results = list(results or [])
        self.error = error
        self._collection = SimpleNamespace(metadata={"hnsw:space": space})

    def similarity_search_with_score(self, query, k: int = 4):
        self.calls.append((query, k))
        if self.error is not None:
            raise self.error
        return list(self.results[:k])


def qa_doc(
    doc_id, *, answer=ANSWER, question=QUESTION, evidence=EVIDENCE, basis="2026-10-01", fingerprint="", cand_id=None
):
    metadata = {
        "answer": answer,
        "evidence": evidence,
        "law_as_of_basis": basis,
        "options_fingerprint": fingerprint,
    }
    if cand_id is not None:
        metadata["qa_candidate_id"] = cand_id
    return SimpleNamespace(id=doc_id, page_content=question, metadata=metadata)


@pytest.fixture
def fake_qa(monkeypatch):
    def install(results=None, *, space="cosine", error=None):
        store = FakeQaStore(results, space=space, error=error)
        monkeypatch.setattr(ks, "_qa_store", store)
        monkeypatch.setattr(ks, "_QA_IS_COSINE", None)
        return store

    return install


@pytest.fixture
def kb_has_article(monkeypatch):
    def install(docs):
        monkeypatch.setattr(retrieval, "exact_article_lookup", lambda source, article: docs)
        monkeypatch.setattr(main, "exact_article_lookup", lambda source, article: docs, raising=False)

    return install


def _capture(logger_name):
    logger = logging.getLogger(logger_name)
    records: list[logging.LogRecord] = []

    class _Handler(logging.Handler):
        def emit(self, record):
            records.append(record)

    handler = _Handler(level=logging.WARNING)
    logger.addHandler(handler)
    return logger, handler, records


def _min_deps(**overrides):
    """快车道取数桩（接缝形状与 `FastPathDependencies` 一致，`cutoff` 关键字必收）。"""
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
    return rb.FastPathDependencies(**values)


# ==================== S13 默认依赖真实绑定 + raw 保持 k=1 ====================


def test_s13_default_deps_bind_eligible_entry_and_raw_keeps_k1(fake_qa, kb_has_article):
    kb_has_article([{"page_content": "第十九条 试用期……"}])
    deps = rb._default_fast_path_dependencies()
    assert deps.search_qa is ks.search_eligible_qa, "默认取语料口没绑到有界资格选择入口"

    store = fake_qa([(qa_doc("a"), 0.03)])  # cosine：score = 1 - 0.03 = 0.97
    hit = deps.search_qa("默认入口问句")
    assert hit is not None and hit["score"] == pytest.approx(0.97)
    assert store.calls == [("默认入口问句", 9)], f"服务入口不是一次 k=9：{store.calls}"

    # raw `search_qa` 仍是写侧幂等去重入口：k=1、阈值独立（0.97 < 0.99 ⇒ miss）。
    store.calls.clear()
    assert ks.search_qa("写侧去重问句", threshold=0.99) is None
    assert store.calls == [("写侧去重问句", 1)], f"raw 查询不是一次 k=1：{store.calls}"

    store.calls.clear()
    assert ks.search_qa("写侧默认阈值") is not None
    assert store.calls == [("写侧默认阈值", 1)]


# ==================== S14 两条 metric 计分口径 + 嵌入异常不放行 ====================


def test_s14_cosine_branch_scores_by_unrounded_distance(fake_qa, kb_has_article):
    kb_has_article([{"page_content": "第十九条"}])
    store = fake_qa([(qa_doc("a", answer=ANSWER), 0.04), (qa_doc("b", answer=OTHER_ANSWER), 0.06)])
    hit = ks.search_eligible_qa("问句")
    assert hit is not None and hit["score"] == pytest.approx(0.96), "cosine 分支未按未舍入 1-distance 计分"
    assert hit["answer"] == ANSWER
    assert store.calls == [("问句", 9)]


def test_s14_non_cosine_branch_embeds_once_and_batches_candidates(fake_qa, kb_has_article, monkeypatch):
    kb_has_article([{"page_content": "第十九条"}])
    fake_qa([(qa_doc("a", answer=ANSWER), 4.0), (qa_doc("b", answer=OTHER_ANSWER), 8.0)], space="l2")
    calls = {"query": 0, "docs": 0, "batch": None}

    def embed_query(text):
        calls["query"] += 1
        return [1.0, 0.0]

    def embed_documents(texts):
        calls["docs"] += 1
        calls["batch"] = list(texts)
        return [[1.0, 0.0], [0.6, 0.8]]  # cos(q,A)=1.0，cos(q,B)=0.6

    monkeypatch.setattr(ks.embeddings, "embed_query", embed_query)
    monkeypatch.setattr(ks.embeddings, "embed_documents", embed_documents)

    hit = ks.search_eligible_qa("问句")
    assert hit is not None and hit["answer"] == ANSWER
    assert calls["query"] == 1, "非 cosine 分支 query 嵌入不是恰好 1 次"
    assert calls["docs"] == 1, "非 cosine 分支候选不是一次批量嵌入"
    assert calls["batch"] == [QUESTION, QUESTION], calls["batch"]


def test_s14_embedding_failure_does_not_borrow_distance_score(fake_qa, kb_has_article, monkeypatch):
    kb_has_article([{"page_content": "第十九条"}])
    # 距离 0.04 在 cosine 支本会得 0.96；嵌入炸掉后不许偷用这个分放行。
    fake_qa([(qa_doc("a"), 0.04)], space="l2")

    def _boom(text):
        raise RuntimeError("模拟嵌入调用失败")

    monkeypatch.setattr(ks.embeddings, "embed_query", _boom)
    assert ks.search_eligible_qa("问句") is None


# ==================== S15 doc id 回查 SQL 的资格权威 ====================


def _synthetic_row(db, *, doc_id, question):
    row = ks.QaCandidate(
        question=question,
        answer=ANSWER,
        grounded_score=0.95,
        evidence=EVIDENCE,
        status="approved",
        approval_source="human",
        eligibility="ok",
        vector_doc_id=doc_id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def test_s15_revoked_and_sql_error_are_not_served(db, fake_qa, kb_has_article, monkeypatch):
    kb_has_article([{"page_content": "第十九条 试用期……"}])
    doc_id = uuid.uuid4().hex
    row = _synthetic_row(db, doc_id=doc_id, question=QUESTION)
    store = fake_qa([(qa_doc(doc_id), 0.03)])  # metadata 无链 ⇒ 只能靠 doc id 回查 SQL

    assert ks.search_eligible_qa("问句") is not None, "可服务的带链记录没被选中，样本无效"

    ks.decide_candidate(db, row.id, "rejected")
    assert ks.search_eligible_qa("问句") is None, "SQL 撤回后仍被服务"

    # SQL 回查异常 ⇒ fail-closed（「查不动」不等于「没有链所以放行」）
    def _boom(_doc_id):
        raise RuntimeError("模拟 SQL 查询炸")

    monkeypatch.setattr(qe, "_select_candidate_id_by_doc_id", _boom)
    store.results = [(qa_doc("absent"), 0.03)]
    assert ks.search_eligible_qa("问句") is None


def test_s15_truly_unlinked_record_still_defers_to_provenance(fake_qa, kb_has_article):
    kb_has_article([{"page_content": "第十九条 试用期……"}])
    fake_qa([(qa_doc("seed-without-row"), 0.03)])  # 库里没有这条 doc id 的候选行
    hit = ks.search_eligible_qa("问句")
    assert hit is not None, "无链但来源可校验的存量记录被误拒（放行面被收窄）"
    assert hit["qa_candidate_id"] is None


# ==================== S16 高分不合格不挡较低合格项 ====================


def test_s16_high_score_ineligible_yields_to_lower_eligible(fake_qa, kb_has_article):
    kb_has_article([{"page_content": "第十九条"}])
    high_bad = qa_doc("high", answer=OTHER_ANSWER, evidence="[]")  # 来源不可校验 ⇒ 不合格
    low_good = qa_doc("low", answer=ANSWER)
    fake_qa([(high_bad, 0.01), (low_good, 0.06)])  # 0.99 不合格 / 0.94 合格
    hit = ks.search_eligible_qa("问句")
    assert hit is not None and hit["answer"] == ANSWER, "高分不合格项挡住了窗内下一条合格项"
    assert hit["score"] == pytest.approx(0.94)


def test_s16_direct_return_guards_still_hold(fake_qa, kb_has_article):
    kb_has_article([{"page_content": "第十九条"}])
    fake_qa([(qa_doc("a"), 0.03)])  # 0.97
    hit = ks.search_eligible_qa("问句")
    assert hit is not None
    assert main._qa_direct_return({"rewritten": "问句", "qa_hit": hit})  # ≥0.92 且指纹/来源/引用全过
    blocked = dict(hit, score=0.90)
    assert main._qa_direct_return({"rewritten": "问句", "qa_hit": blocked}) is None, "0.92 直返门被放宽"


def test_s16_historical_date_never_queries_qa():
    called = []
    deps = _min_deps(search_qa=lambda query: called.append(query))
    bootstrap = SimpleNamespace(
        conv_id=1,
        raw_query="历史问句",
        user_text="历史问句",
        contract_text="",
        supplement_text="",
        summary="",
        recent=[],
        recent_messages=[],
        has_options=False,
        is_exam=False,
        intent="legal_query",
        contract_mode=False,
        client_truncated=False,
        intent_confirm=False,
        law_as_of=date(2020, 1, 1),
        image=None,
        image_rel=None,
        thumb_rel=None,
    )
    pre = rb.prepare_fast_path(bootstrap, _deps=deps)
    assert pre["qa_hit"] is None
    assert called == [], "显式历史日期仍查了 QA"


# ==================== S17 失败不放行 + 日志不落原文 ====================


def test_s17_store_failure_is_fail_closed_and_log_has_no_content(fake_qa, kb_has_article):
    kb_has_article([{"page_content": "第十九条"}])
    fake_qa([(qa_doc("a"), 0.03)], error=RuntimeError("模拟向量库故障"))
    logger, handler, records = _capture("legal.knowledge")
    try:
        assert ks.search_eligible_qa("敏感问句原文-不应落日志") is None
    finally:
        logger.removeHandler(handler)

    payloads = [json.loads(_JsonFormatter().format(r)) for r in records]
    assert payloads, "查询失败没有任何留痕"
    # 票 C21-A review（J2）：召回层失败改落专用键 ⇒ 不再冒充 `qa_eligibility_reason="state"`。
    assert all(p.get("qa_candidate_query_failed") is True for p in payloads), payloads
    assert all(p.get("qa_eligibility_reason") is None for p in payloads), payloads
    blob = json.dumps(payloads, ensure_ascii=False)
    assert "敏感问句" not in blob and ANSWER not in blob, "日志落了问句/答案原文"


def test_s17_rejected_candidate_log_has_no_content(fake_qa, kb_has_article):
    kb_has_article([{"page_content": "第十九条"}])
    fake_qa([(qa_doc("a", evidence="[]"), 0.03)])  # 来源不可校验 ⇒ 拒绝
    logger, handler, records = _capture("legal.chat")
    try:
        assert ks.search_eligible_qa("敏感问句原文-不应落日志") is None
    finally:
        logger.removeHandler(handler)
    denied = [r for r in records if getattr(r, "qa_eligibility_reason", None)]
    assert len(denied) == 1, [r.getMessage() for r in records]
    payload = json.loads(_JsonFormatter().format(denied[0]))
    assert payload["qa_eligibility_reason"] == "provenance"
    # 票 C21-A review（J6）：适配器作为「产生处」必须带门布尔 ⇒ 在册 qa_provenance_refused 有生产者。
    assert payload.get("qa_provenance_refused") is True, payload
    blob = json.dumps(payload, ensure_ascii=False)
    assert "敏感问句" not in blob and ANSWER not in blob


def test_s17b_multiple_rejections_log_at_most_once_per_request(fake_qa, kb_has_article):
    """票 C21-A review（J7）：窗内多条被拒 ⇒ 每请求最多一条拒绝留痕（不放大成 ≤8 条）。

    原先逐候选各记一次 ⇒ 一次候选集合里的多条来源不可校验会被计成多次拒绝，
    与验收 S17「不重复计成多次请求」相悖。
    """
    kb_has_article([{"page_content": "第十九条"}])
    # 5 条来源都不可校验 ⇒ 全部被拒（provenance），doc id 各不相同。
    fake_qa([(qa_doc(f"d{i}", evidence="[]"), 0.03) for i in range(5)])
    logger, handler, records = _capture("legal.chat")
    try:
        assert ks.search_eligible_qa("敏感问句原文-不应落日志") is None
    finally:
        logger.removeHandler(handler)
    denied = [r for r in records if getattr(r, "qa_eligibility_reason", None)]
    assert len(denied) == 1, [r.getMessage() for r in records]
    payload = json.loads(_JsonFormatter().format(denied[0]))
    assert payload["qa_eligibility_reason"] == "provenance"


def test_s17_single_vector_query_per_request(fake_qa, kb_has_article):
    kb_has_article([{"page_content": "第十九条"}])
    store = fake_qa([(qa_doc(f"d{i}"), 0.03) for i in range(5)])
    ks.search_eligible_qa("问句")
    assert len(store.calls) == 1 and store.calls[0][1] == 9


def test_call_counts_for_a_full_window(fake_qa, kb_has_article, monkeypatch):
    """记录真实调用计数：1 次 k=9 向量查询；9 条候选；窗内 8 条各一次 doc id 回查 SQL，哨兵 0 次。"""
    import database

    kb_has_article([{"page_content": "第十九条"}])
    # 窗内 8 条同分同内容（可去重）+ 第 9 条低分哨兵（不构成边界风险）。
    results = [(qa_doc(f"d{i}"), 0.03) for i in range(8)] + [(qa_doc("sentinel"), 0.5)]
    store = fake_qa(results)
    opens = {"n": 0}
    real = database.SessionLocal

    def counting():
        opens["n"] += 1
        return real()

    monkeypatch.setattr(database, "SessionLocal", counting)
    hit = ks.search_eligible_qa("问句")
    assert hit is not None
    assert store.calls == [("问句", 9)], f"向量查询计数/参数：{store.calls}"
    assert len(store.results) == 9
    assert opens["n"] == 8, f"窗内 8 条的 SQL 回查计数：{opens['n']}（哨兵不该查）"


# ==================== S18 顺序与进程无关 + 窗口耗尽保守回退 ====================


_SUBPROCESS_SCRIPT = """
import json, sys
sys.path.insert(0, {backend!r})
from qa_selection import Candidate, select_candidate

def mk(doc, score=0.95):
    return Candidate(
        {{"question": "q", "answer": "a", "evidence": "e|1", "law_as_of_basis": "2026-10-01",
          "fingerprint": "", "qa_candidate_id": 1, "marker": doc}},
        doc, score, True,
    )

a, b = mk("a"), mk("b")
out = []
for items in ([a, b], [b, a]):
    r = select_candidate(items)
    out.append([r.reason, r.hit["marker"] if r.hit else None])
print(json.dumps(out))
"""


def test_s18_selection_is_order_and_process_independent():
    backend = str(Path(__file__).resolve().parents[1])
    script = _SUBPROCESS_SCRIPT.format(backend=backend)
    outs = []
    for _ in range(2):
        proc = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, check=False)
        assert proc.returncode == 0, proc.stderr
        outs.append(proc.stdout.strip())
    assert outs[0] == outs[1], f"跨进程结果不一致：{outs}"
    assert json.loads(outs[0]) == [["hit", "a"], ["hit", "a"]], outs[0]


def test_s18_synthetic_index_order_does_not_change_selected_identity(fake_qa, kb_has_article):
    kb_has_article([{"page_content": "第十九条"}])
    results = [(qa_doc("a", answer=ANSWER), 0.04), (qa_doc("aa", answer=ANSWER), 0.04)]
    seen = set()
    for order in itertools.permutations(results):
        store = fake_qa(list(order))
        hit = ks.search_eligible_qa("问句")
        seen.add(hit.doc_id if hit is not None else None)
        assert store.calls == [("问句", 9)]
    assert seen == {"a"}, f"同一候选集合随注入顺序改变选择：{seen}"


def test_s18_window_exhaustion_falls_back_conservatively(fake_qa, kb_has_article):
    kb_has_article([{"page_content": "第十九条"}])
    # 8 条全不合格 + 第 9 条合格：不许拿哨兵兜底，也不扩池（仍只有一次 k=9）。
    results = [(qa_doc(f"w{i}", evidence="[]"), 0.03) for i in range(8)] + [(qa_doc("sentinel"), 0.01)]
    store = fake_qa(results)
    assert ks.search_eligible_qa("问句") is None
    assert store.calls == [("问句", 9)], store.calls


def test_s18_non_finite_sentinel_is_treated_as_risky(fake_qa, kb_has_article, monkeypatch):
    kb_has_article([{"page_content": "第十九条"}])
    results = [(qa_doc(f"d{i}"), 0.04) for i in range(8)] + [(qa_doc("s"), 0.5)]
    fake_qa(results)
    # 低分哨兵 ⇒ 窗内项可选（阳性对照）。
    monkeypatch.setattr(ks, "_score_qa_candidates", lambda q, r: [0.95] * 8 + [0.5])
    assert ks.search_eligible_qa("问句") is not None
    # 计分异常哨兵 ⇒ 保守判边界风险，不选窗内项。
    monkeypatch.setattr(ks, "_score_qa_candidates", lambda q, r: [0.95] * 8 + [float("nan")])
    assert ks.search_eligible_qa("问句") is None


def test_reason_is_not_stuffed_into_the_public_hit(fake_qa, kb_has_article):
    kb_has_article([{"page_content": "第十九条"}])
    fake_qa([(qa_doc("a"), 0.03)])
    hit = ks.search_eligible_qa("问句")
    assert set(hit) == {
        "question",
        "answer",
        "score",
        "evidence",
        "law_as_of_basis",
        "fingerprint",
        "qa_candidate_id",
    }, f"公开 hit 键集被塞进测试/SQL 字段：{sorted(hit)}"
    assert hit.doc_id == "a", "选中的原对象丢了 doc_id"
    assert hasattr(hit, "state_slot"), "选中的原对象丢了请求内状态槽"


def test_non_finite_score_is_not_admitted(fake_qa, kb_has_article, monkeypatch):
    kb_has_article([{"page_content": "第十九条"}])
    fake_qa([(qa_doc("a"), 0.04)])
    monkeypatch.setattr(ks, "_score_qa_candidates", lambda q, results: [float("inf")])
    assert ks.search_eligible_qa("问句") is None
