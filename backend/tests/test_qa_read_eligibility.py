"""W06 行为测试：QA 读取资格单一真源 + 撤回闭合（票 W06-IMPL §4 项 1–5）。

先红后绿（实现前本文件因缺 `qa_eligibility` 与缺列而红）。判据唯一真源住在
`qa_eligibility.qa_read_eligible`，三条读出口只「把数据送进去、把裁决读出来」，不各抄一份。

C03=形状 P 口径落地在这里：存量隔离不删（撤回只置资格、不删向量记录）；未知来源不可服务；
读不到 SQL 状态 fail-closed。唯一保留的放行面是「无候选链、但来源可校验且引用在库」的语料记录
（那两条对照腿 `test_qa_provenance_guard.py`／`test_qa_citation_gate_symmetry.py` 钉死不许打掉）。

隔离：临时 SQLite（`db`，它把 `database.SessionLocal` 换到 tmp 引擎，出口内 `load_read_state` 走同一引擎）
+ conftest 临时 `CHROMA_DIR` + `double_embeddings`；不碰真实 `app.db`／真实 `chroma_db`。
"""

import ast
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

import answer_cache  # noqa: E402
import knowledge_service as ks  # noqa: E402
import main  # noqa: E402
import qa_eligibility as qe  # noqa: E402
import retrieval  # noqa: E402

EVIDENCE = json.dumps([{"source": "中华人民共和国劳动合同法", "article": "第十九条"}], ensure_ascii=False)
ANSWER = (
    "《劳动合同法》第十九条对试用期上限作了分层规定：合同期限三个月以上不满一年的，试用期不得超过一个月；"
    "同一用人单位与同一劳动者只能约定一次试用期。"
)


def _kb_has_article(monkeypatch, docs):
    """把「条文还在库里」钉成给定读数：时效判据读 `retrieval.exact_article_lookup`，
    直返历史上也读过 `main` 侧同名全局 ⇒ 两处都打，免得拦截归因到进程私有空库（假红）。"""
    monkeypatch.setattr(main, "exact_article_lookup", lambda src, art: docs)
    monkeypatch.setattr(retrieval, "exact_article_lookup", lambda src, art: docs)


def _prompt_text(messages) -> str:
    out = []
    for m in messages:
        c = getattr(m, "content", m)
        out.append(c if isinstance(c, str) else json.dumps(c, ensure_ascii=False))
    return "\n".join(out)


def _build_pre(q: str, hit) -> dict:
    return {
        "conv_id": 1,
        "intent": "legal_query",
        "image": None,
        "recent": [],
        "rewritten": q,
        "user_text": q,
        "summary": "",
        "qa_hit": hit,
        "context": "",
        "sources": [],
        "image_rel": None,
        "thumb_rel": None,
        "is_exam": False,
        "has_options": False,
        "contract_data": None,
    }


# ==================== 判据本体（纯函数，成对反例） ====================


def _meta(**over):
    hit = {
        "question": "q",
        "answer": ANSWER,
        "score": 0.99,
        "fingerprint": "",
        "evidence": EVIDENCE,
        "law_as_of_basis": "2026-08-23",
        "qa_candidate_id": 7,
    }
    hit.update(over)
    return hit


def test_predicate_reason_vocabulary_is_closed(monkeypatch):
    """拒绝必须落归因键，且键 ∈ 票面闭集；放行 reason 为空串。"""
    _kb_has_article(monkeypatch, [{"page_content": "第十九条 试用期……"}])  # 让放行腿穿过 citation
    ok_state = {"eligibility": "ok", "approval_source": "human", "vector_doc_id": "x", "status": "approved"}
    good = qe.qa_read_eligible(_meta(), ok_state)
    assert good.allow is True
    assert good.reason == ""
    for state, expected in (
        ({"eligibility": "revoked", "approval_source": "human", "status": "rejected"}, "state"),
        ({"eligibility": "quarantined", "approval_source": "human", "status": "approved"}, "state"),
        ({"eligibility": "ok", "approval_source": "unknown", "status": "approved"}, "provenance"),
    ):
        verdict = qe.qa_read_eligible(_meta(), state)
        assert verdict.allow is False, (state, verdict)
        assert verdict.reason in {"provenance", "citation", "state", "watershed", "fingerprint"}
        assert verdict.reason == expected, (state, verdict.reason)


def test_predicate_fail_closed_when_linked_row_unreadable():
    """§3①：带 qa_candidate_id 却读不到行 ⇒ fail-closed，不许「没有来源所以放行」。"""
    verdict = qe.qa_read_eligible(_meta(qa_candidate_id=42), None)
    assert verdict.allow is False
    assert verdict.reason == "state"


def test_predicate_paired_unknown_rejected_human_allowed(monkeypatch):
    """§4 项 3：同数据下 approval_source=unknown 拒、human 放行（成对）。"""
    _kb_has_article(monkeypatch, [{"page_content": "第十九条 试用期……"}])
    base = _meta(qa_candidate_id=7)
    unknown = qe.qa_read_eligible(base, {"eligibility": "ok", "approval_source": "unknown", "status": "approved"})
    human = qe.qa_read_eligible(base, {"eligibility": "ok", "approval_source": "human", "status": "approved"})
    assert unknown.allow is False and unknown.reason == "provenance"
    assert human.allow is True


def test_predicate_rejects_unverifiable_provenance_even_when_state_ok(monkeypatch):
    """§3④：来源/时效判定接进判据本体——引用为空 ⇒ provenance 拒（即使资格 ok）。"""
    verdict = qe.qa_read_eligible(
        _meta(evidence="[]"), {"eligibility": "ok", "approval_source": "human", "status": "approved"}
    )
    assert verdict.allow is False
    assert verdict.reason == "provenance"


def test_predicate_rejects_dead_citation_when_provenance_ok(monkeypatch):
    """§3④ 的另一半：引用给得出但条文查不在库 ⇒ citation 拒。"""
    _kb_has_article(monkeypatch, [])
    verdict = qe.qa_read_eligible(_meta(), {"eligibility": "ok", "approval_source": "human", "status": "approved"})
    assert verdict.allow is False
    assert verdict.reason == "citation"


def test_predicate_no_link_defers_to_provenance(monkeypatch):
    """对照腿：无 qa_candidate_id 的语料记录，来源可校验 + 引用在库 ⇒ 仍放行（不被「缺链」打死）。"""
    _kb_has_article(monkeypatch, [{"page_content": "第十九条"}])
    verdict = qe.qa_read_eligible(_meta(qa_candidate_id=None), None)
    assert verdict.allow is True


# ==================== §4 项 1：撤回后三条出口全部停服务 ====================


def test_reject_stops_all_three_read_exits(db, double_embeddings, monkeypatch):
    """approved 且已进向量的候选被拒绝后：直返／prompt 注入／回答缓存三条出口都 miss。"""
    q = "撤回三出口甲：已自动收录再被拒绝的候选还能被服务吗？"
    row = ks.create_candidate(db, q, ANSWER, 0.95, EVIDENCE)  # 自动收录 → 进向量 + SQL approved
    _kb_has_article(monkeypatch, [{"page_content": "第十九条 试用期……"}])

    # 回答缓存里先放一条（模拟该问句此前已产出并被缓存）
    cache_key = answer_cache.make_key(q, "legal_query", "2026-08-23", ["劳动合同法|第十九条"])
    answer_cache.put(cache_key, ANSWER, [])
    assert answer_cache.get(cache_key) is not None

    ks.decide_candidate(db, row.id, "rejected")

    # 存量隔离不删：向量记录仍在（search_qa 读得回），但资格已置 revoked
    hit = ks.search_qa(q)
    assert hit is not None, "记录被删了 ⇒ 违反形状 P（隔离不删）"
    assert hit["answer"] == ANSWER

    # 出口①：零模型直返 → miss
    assert main._qa_direct_return({"rewritten": q, "qa_hit": hit}) is None
    # 出口②：prompt 注入 → 不再出现「此前已确认的问答」
    prompt = _prompt_text(main._build_messages(_build_pre(q, hit)))
    assert "此前已确认的问答" not in prompt
    assert ANSWER not in prompt
    # 出口③：回答缓存 → reject 调 invalidate 连带清缓存 ⇒ miss
    assert answer_cache.get(cache_key) is None


def test_control_reject_leaves_vector_record_in_place(db, double_embeddings):
    """§4 项 1 的控制腿：撤回不删数据（形状 P），向量里那条题干仍在。"""
    q = "撤回三出口乙：拒绝会不会把向量记录一起删掉？"
    row = ks.create_candidate(db, q, ANSWER, 0.95, EVIDENCE)
    ks.decide_candidate(db, row.id, "rejected")
    data = ks._qa_store._collection.get(include=["documents"])
    assert q in {str(d).strip() for d in (data.get("documents") or [])}


# ==================== §4 项 2：读不到 SQL 状态 ⇒ 两出口都拒，日志只落归因键 ====================


@pytest.mark.parametrize("break_by", ["returns_none", "raises"])
def test_unreadable_state_rejects_both_exits_and_logs_only_reason(db, double_embeddings, monkeypatch, break_by, caplog):
    q = "撤回读不到状态丙：SQL 查询挂掉时两出口都 miss 吗？"
    ks.create_candidate(db, q, ANSWER, 0.95, EVIDENCE)  # 只为造出带链记录，行对象本身不用
    _kb_has_article(monkeypatch, [{"page_content": "第十九条 试用期……"}])  # 让 citation 通过 ⇒ 拦截归因到 state
    hit = ks.search_qa(q)
    assert hit is not None and hit.get("qa_candidate_id") is not None

    if break_by == "returns_none":
        monkeypatch.setattr(qe, "load_read_state", lambda *a, **k: None)
    else:

        def _boom(*a, **k):
            raise RuntimeError("模拟 SQL 查询炸（库挂/连接锁死）")

        monkeypatch.setattr(qe, "load_read_state", _boom)

    assert main._qa_direct_return({"rewritten": q, "qa_hit": hit}) is None
    prompt = _prompt_text(main._build_messages(_build_pre(q, hit)))
    assert "此前已确认的问答" not in prompt

    messages = [r.getMessage() for r in caplog.records]
    assert any("qa_read_eligible_denied" in m and "state" in m for m in messages), messages
    # 日志只落归因键，不落问题原文
    assert all(q not in m for m in messages), messages


# ==================== 票 W06-FIX V2/F3：产生处与出口回同一个 reason ====================


def _fast_deps(**overrides):
    """快车道取数桩（接缝形状与 `FastPathDependencies` 一致，`cutoff` 关键字必收）。"""
    import request_bootstrap as rb

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


def _plain_bootstrap(q: str) -> object:
    """`prepare_fast_path` 需要的最小 bootstrap（非检索分支之外的键都取「不触发」的形状）。"""
    return SimpleNamespace(
        conv_id=1,
        raw_query=q,
        user_text=q,
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
        law_as_of=None,
        image=None,
        image_rel=None,
        thumb_rel=None,
    )


def _reason_in(records) -> str:
    """从留痕里取 `qa_eligibility_reason`（放行 ⇒ 没有任何一条 ⇒ 空串，与判据的 reason 同词汇）。"""
    reasons = [getattr(r, "qa_eligibility_reason", None) for r in records if getattr(r, "qa_eligibility_reason", None)]
    assert len(set(reasons)) <= 1, f"一次拒绝落了多个 reason ⇒ 判据又被抄了一份：{reasons}"
    return reasons[0] if reasons else ""


@pytest.mark.parametrize(
    "shape,expected",
    [
        ("ok", ""),
        ("revoked", "state"),
        ("broken_link", "state"),
        ("unknown_provenance", "provenance"),
        ("dead_citation", "citation"),
        # 排序钉：既被撤回、来源又是 unknown 的记录，两个判定点都必须报**状态轴**（不是 provenance）。
        # 这条就是 F3 说的「两处排序不一样」——改回任一处的老顺序，这条立刻红。
        ("revoked_and_unknown", "state"),
    ],
)
def test_producer_and_direct_return_exit_report_the_same_reason(db, double_embeddings, monkeypatch, shape, expected):
    """同一 meta 在**产生处**与**直返出口**必须回同一个 reason（票 W06-FIX V2 的字面要求）。

    两侧都是真跑：产生处走 `prepare_fast_path`（现在调 `qa_eligibility.qa_read_eligible`），
    出口走 `main._qa_direct_return`（状态轴→来源→…→引用，与合成判据同序）。
    reason 从**留痕**里读，不是从判据函数里读——读函数就成了拿自己证明自己。

    注入出口（`main._build_messages`）按在册口径只咨询状态轴，所以对它判两件事：
    ① 状态轴那一档（revoked/broken_link/revoked_and_unknown）它必须回**同一个 reason**；
    ② 来源/引用那一档它不重复判，但**产生处已经把它丢了** ⇒ 端到端不出现「此前已确认的问答」。
    把②写成「注入出口的 reason 也要等于 provenance/citation」是错的（那是要求它重复扫库，
    在册明令不做的代价），这条判据因此按**分档**写，而不是按"三个出口一视同仁"糊成一句。
    """
    import logging

    q = f"同序判据{shape}：这条记录在产生处与出口报的是同一个 reason 吗？"
    row = ks.create_candidate(db, q, ANSWER, 0.95, EVIDENCE)
    _kb_has_article(monkeypatch, [{"page_content": "第十九条 试用期……"}])

    if shape == "revoked":
        ks.decide_candidate(db, row.id, "rejected")
    elif shape == "revoked_and_unknown":
        ks.decide_candidate(db, row.id, "rejected")
        row.approval_source = "unknown"  # 两个轴同时不过 ⇒ 只能由排序决定报哪一个
        db.commit()
    elif shape == "unknown_provenance":
        row.approval_source = "unknown"
        db.commit()
    elif shape == "dead_citation":
        _kb_has_article(monkeypatch, [])
    elif shape == "broken_link":
        pass  # 链由 `_rescore` 改指到一个绝不存在的 id ⇒ 「带链却读不到行」的 fail-closed 档

    chat_logger = logging.getLogger("legal.chat")
    records: list[logging.LogRecord] = []

    class _Handler(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            records.append(record)

    handler = _Handler(level=logging.WARNING)
    previous = chat_logger.level
    chat_logger.addHandler(handler)
    chat_logger.setLevel(logging.WARNING)
    try:
        # ---- 产生处：真调 prepare_fast_path，桩只替「取语料」这一缝 ----
        hit_producer = ks.search_qa(q) or dict(_meta(qa_candidate_id=None))
        hit_producer = _rescore(hit_producer, shape, row.id)
        records.clear()
        pre = main_prepare_fast_path(hit_producer, q)
        producer_reason = _reason_in(records)
        assert producer_reason == expected, (shape, producer_reason, expected)
        assert (pre["qa_hit"] is None) == (expected != ""), "放行/丢弃与 reason 不一致 ⇒ 这道门在自说自话"

        # ---- 直返出口：同一形状的另一份对象（没有共享缓存，各判各的） ----
        records.clear()
        hit_exit = _rescore(ks.search_qa(q) or dict(_meta(qa_candidate_id=None)), shape, row.id)
        served = main._qa_direct_return({"rewritten": q, "qa_hit": hit_exit})
        exit_reason = _reason_in(records)
        assert exit_reason == producer_reason, (shape, "产生处报", producer_reason, "出口报", exit_reason)
        assert (served is None) == (expected != ""), (shape, served)

        # ---- 注入出口：状态轴那两档（撤回／未知来源）出口自查并回**同一个 reason**；
        # 引用档按在册口径**委托给产生处**（出口不重复扫库），所以这里判的是委托成立，不是让出口重判 ----
        records.clear()
        prompt = _prompt_text(main._build_messages(_build_pre(q, _rescore(hit_exit, shape, row.id))))
        injection_reason = _reason_in(records)
        end_to_end = _prompt_text(main._build_messages(pre))
        assert ("此前已确认的问答" in end_to_end) is (expected == ""), (
            shape,
            "经过产生处的 pre 仍把不可服务的问答递进了 prompt",
        )
        if expected in ("state", "provenance"):
            assert injection_reason == expected, (shape, injection_reason, expected)
        elif expected == "citation":
            assert injection_reason == "", (
                "引用档出口开始自判 ⇒ 在册的「注入出口不重复扫库」口径已经变了，"
                "同步改这条与 qa_eligibility 的模块 docstring，别把它当噪音删掉"
            )
            assert "此前已确认的问答" in prompt, (
                "注入出口单独喂（绕过产生处）现在连引用都拦得住 ⇒ 委托关系变了，同上：改口径而不是删判据"
            )
        else:
            assert injection_reason == ""
            assert "此前已确认的问答" in prompt
    finally:
        chat_logger.removeHandler(handler)
        chat_logger.setLevel(previous)


def _rescore(hit, shape, cand_id):
    """把取回的语料记录整成**可比较**的形状：分数抬到直返阈值之上（判据分档与分数无关），
    链指向本用例那一行（broken_link 例外——它要的是「带链却读不到行」，用一个绝不存在的 id）。"""
    if hit is None:
        return None
    out = dict(hit)
    out["score"] = 0.99
    out["qa_candidate_id"] = int(cand_id) + 100000 if shape == "broken_link" else int(cand_id)
    if shape == "broken_link":
        out["law_as_of_basis"] = out["law_as_of_basis"] or "2026-08-23"
    return out


def main_prepare_fast_path(hit, q: str):
    """真调产生处（`request_bootstrap.prepare_fast_path`），只把「取语料」这一缝换成给定记录。"""
    import request_bootstrap as rb

    return rb.prepare_fast_path(_plain_bootstrap(q), _deps=_fast_deps(search_qa=lambda query: hit))


# ==================== 票 W06-FIX V10/F10：拒绝留痕两键一起落 ====================


def test_denial_log_carries_reason_and_candidate_id_and_survives_the_formatter(db, double_embeddings, monkeypatch):
    """F10：注释写着「落归因键 + 候选行 id」，字节里却只有归因键 ⇒ 归因指不到行。现在两键必须一起落，
    且必须能被 JSON formatter 带出来（白名单外的键会被静默丢弃 ⇒ 只在 LogRecord 对象上断言等于没断言）。
    """
    import logging

    from observability import _JsonFormatter

    q = "留痕双键：拒绝日志能不能指到具体那一行？"
    row = ks.create_candidate(db, q, ANSWER, 0.95, EVIDENCE)
    _kb_has_article(monkeypatch, [{"page_content": "第十九条"}])
    ks.decide_candidate(db, row.id, "rejected")
    hit = ks.search_qa(q)
    assert hit is not None and hit["qa_candidate_id"] == row.id

    chat_logger = logging.getLogger("legal.chat")
    records: list[logging.LogRecord] = []

    class _Handler(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            records.append(record)

    handler = _Handler(level=logging.WARNING)
    previous = chat_logger.level
    chat_logger.addHandler(handler)
    chat_logger.setLevel(logging.WARNING)
    try:
        assert main._qa_direct_return({"rewritten": q, "qa_hit": dict(hit)}) is None
    finally:
        chat_logger.removeHandler(handler)
        chat_logger.setLevel(previous)

    denied = [r for r in records if getattr(r, "qa_eligibility_reason", None)]
    assert len(denied) == 1, f"一次拒绝应当只留一条痕，现量 {len(denied)} 条：{[r.getMessage() for r in records]}"
    payload = json.loads(_JsonFormatter().format(denied[0]))
    assert payload["qa_eligibility_reason"] == "state", payload
    assert payload["qa_candidate_id"] == row.id, f"日志指不到行（两键没一起落）：{payload}"
    assert q not in payload["msg"] and q not in json.dumps(payload, ensure_ascii=False), "日志落了题干（AUTH-3）"


# ==================== 票 W06-FIX V8/F9：一次请求一条 session（计数判据，不是读代码） ====================


def test_one_sql_state_session_per_qa_bearing_request(db, double_embeddings, monkeypatch):
    """F9：每个带 QA 命中的请求此前开**两条** `SessionLocal()`（注入出口＋直返出口各一条）。

    判据是**计数替身**：把 `database.SessionLocal` 换成会数数的工厂，跑一遍真实形状
    （产生处 + 直返出口 + 注入出口三个判定点，读的是**同一条** `search_qa` 出来的记录），
    要求整个请求只开 **1** 条。改前这里是 2（两个出口各自 `load_read_state`）。

    反空跑对照（同一条用例里，不另开文件）：把那条记录复制成 **plain dict**（没有请求内状态槽，
    即评测探针直接构造 `pre` 的形状）再跑两个出口 ⇒ 计数必须**各读一次**（+2）。
    这半条同时证明：①计数器真的在数判据点的那次 SELECT（不是数别的），②省下来的那次读
    来自共享槽而不是来自"出口不判了"——自查一条没少。
    """
    import database

    q = "计数判据：一次带语料命中的请求到底开了几条 session？"
    ks.create_candidate(db, q, ANSWER, 0.95, EVIDENCE)
    _kb_has_article(monkeypatch, [{"page_content": "第十九条 试用期……"}])
    hit = ks.search_qa(q)
    assert hit is not None, "语料没命中 ⇒ 本条判据没有对象"

    real_factory = database.SessionLocal
    counter = {"n": 0}

    def counting_factory():
        counter["n"] += 1
        return real_factory()

    monkeypatch.setattr(database, "SessionLocal", counting_factory)

    counter["n"] = 0
    pre = main_prepare_fast_path(hit, q)
    assert pre["qa_hit"] is not None, "这条记录本该可服务，却被丢了 ⇒ 计数腿测的不再是「活请求」"
    main._qa_direct_return(pre)
    main._build_messages(pre)
    assert counter["n"] == 1, (
        f"一次请求开了 {counter['n']} 条 session（期望 1 条）⇒ "
        "状态装载没有请求内复用，或某个判定点开始各读各的（票 W06-FIX F9）"
    )

    counter["n"] = 0
    probe_pre = _build_pre(q, dict(hit))
    main._qa_direct_return(probe_pre)
    main._build_messages(probe_pre)
    assert counter["n"] == 2, (
        f"探针形状（无状态槽的 plain dict）只读了 {counter['n']} 次（期望 2 次，两个出口各一次）"
        "⇒ 要么出口自查被删了（fail-open），要么计数器数的不是判据点（本条不可信）"
    )


# ==================== §4 项 4：单一真源 AST 守卫（无第二份判据，带阳性对照） ====================

# 尺子判的是**类**，不是语法（票 W06-FIX F4/V5）：属性名三选一 × 形状五选一 × 词表值。
STATE_ATTRS = frozenset({"status", "eligibility", "approval_source"})
STATE_VOCAB = frozenset(
    {
        "revoked",
        "quarantined",
        "ok",
        "approved",
        "rejected",
        "pending",
        "unknown",
        "human",
        "auto_by_score_inferred",
    }
)
# 属性名 × 词表值**成对判**，不是「任何属性碰上任何词」：`status` 是全仓最通用的列名
# （`scripts/backup_data.py` 的备份清单项、`scripts/capture_eval.py` 的评测行都在读 `status == "ok"`，
# 那是**另一套词汇**，不是候选状态轴）。把它们也算成判据，尺子就变成见谁都咬、
# 下一轮只能整条删掉——所以 `status` 这一列不收 `"ok"`，其余两列名字无歧义、词表全收。
STATE_VALUES_BY_ATTR: dict[str, frozenset[str]] = {
    "eligibility": STATE_VOCAB,
    "approval_source": STATE_VOCAB,
    "status": STATE_VOCAB - {"ok"},
}
SHAPES = ("attribute", "membership", "alias", "getattr", "subscript")


def _eligibility_compare_nodes(source: str, filename: str, skip: tuple[str, ...] = ()) -> list[int]:
    """返回「把资格/审批来源/候选状态当判据读出来」的 Compare 行号（票 W06-FIX F4/V5：**按类判，不按语法形状判**）。

    改前这把尺子只咬一种语法：同一个 `Compare` 节点里同时出现 `eligibility`/`approval_source`
    属性**与**词表字面量。实测漏三种（票面 F4，本文件的正对照逐条会红）：
      · `row.status == "rejected"`（`status` 不在属性名表、`rejected` 不在词表）
      · `st = row.eligibility` 之后再 `if st == "revoked"`（改名/别名后比较）
      · `getattr(row, "approval_source") == "unknown"`（属性名藏在字符串参数里）
    现在判的是**「读状态轴的哪个属性 × 用哪种形状读 × 跟哪个词表值比」这一类**：
      属性名三选一：`status` / `eligibility` / `approval_source`
      形状五选一：直接比 attribute / 成员判定 membership / 别名后比 alias / getattr / 字典取值 subscript
      词表：revoked|quarantined|ok|approved|rejected|pending|unknown|human|auto_by_score_inferred
      （属性名与值**成对判**，理由见 `STATE_VALUES_BY_ATTR` 的注释）
    写侧赋值（`r.eligibility = "revoked"`）不是判据 ⇒ 不命中。
    SQLAlchemy 列表达式（`QaCandidate.status == "pending"` 这种**类名.列**、喂给 `.filter()` 的查询条件）
    也不命中：它当布尔用会直接 TypeError（列表达式没有真值），它不是第二份 Python 判据。
    `skip` 是给正对照用的「把某一条腿拆掉」开关（只在本文件的对照用例里传）：
    拆掉哪条腿，那一腿的样本必须漏检 ⇒ 证明这条腿真的在咬东西，而不是五条腿共享一次恒真。
    """
    shapes = set(SHAPES) - set(skip)

    def _reads_state(node: ast.AST, aliases: dict[str, str]) -> str | None:
        """这一侧是否在**读**三个属性名之一？读出的是哪一个（成对判要用它）。"""
        if isinstance(node, ast.Attribute) and "attribute" in shapes and node.attr in STATE_ATTRS:
            # 类名.列 ＝ SQLAlchemy 列表达式（管理面的查询条件），不是 Python 判据
            if isinstance(node.value, ast.Name) and node.value.id[:1].isupper():
                return None
            return node.attr
        if isinstance(node, ast.Subscript) and "subscript" in shapes:
            sl = node.slice
            if isinstance(sl, ast.Constant) and sl.value in STATE_ATTRS:
                return str(sl.value)
            return None
        if isinstance(node, ast.Call) and node.args:
            func = node.func
            if isinstance(func, ast.Attribute) and func.attr == "get" and "subscript" in shapes:
                first = node.args[0]
                if isinstance(first, ast.Constant) and first.value in STATE_ATTRS:
                    return str(first.value)
                return None
            if isinstance(func, ast.Name) and func.id == "getattr" and "getattr" in shapes:
                if len(node.args) > 1 and isinstance(node.args[1], ast.Constant) and node.args[1].value in STATE_ATTRS:
                    return str(node.args[1].value)
                return None
        if isinstance(node, ast.Name) and "alias" in shapes:
            return aliases.get(node.id)
        return None

    def _vocab_values(node: ast.AST) -> set[str]:
        if isinstance(node, ast.Constant):
            return {node.value} if node.value in STATE_VOCAB else set()
        if "membership" in shapes and isinstance(node, (ast.Tuple, ast.List, ast.Set)):
            return {e.value for e in node.elts if isinstance(e, ast.Constant) and e.value in STATE_VOCAB}
        return set()

    nodes = list(ast.walk(ast.parse(source)))  # 走两遍（先收别名再比），必须先物化成 list：生成器会被第一遍吃掉
    assigns = [n for n in nodes if isinstance(n, ast.Assign)]

    def _collect_aliases() -> dict[str, str]:
        """别名闭包：`a = row.eligibility` ⇒ a→eligibility；`b = a` ⇒ b→eligibility
        （有界迭代到不动点，两跳改名也咬得住）。"""
        if "alias" not in shapes:
            return {}
        found: dict[str, str] = {}
        for _round in range(len(assigns) + 2):
            added = False
            for asn in assigns:
                if not (len(asn.targets) == 1 and isinstance(asn.targets[0], ast.Name)):
                    continue
                name = asn.targets[0].id
                if name in found:
                    continue
                attr = _reads_state(asn.value, found)
                if attr is not None:
                    found[name] = attr
                    added = True
            if not added:
                break
        return found

    aliases = _collect_aliases()
    hits: list[int] = []
    for cmp in nodes:
        if not isinstance(cmp, ast.Compare):
            continue
        operands = [cmp.left, *cmp.comparators]
        attrs = {a for a in (_reads_state(o, aliases) for o in operands) if a}
        values: set[str] = set()
        for o in operands:
            values |= _vocab_values(o)
        if attrs and values and any(v in STATE_VALUES_BY_ATTR[a] for a in attrs for v in values):
            hits.append(cmp.lineno)
    del filename
    return hits


def test_no_second_copy_of_the_eligibility_predicate():
    """全仓穷举：除 qa_eligibility.py 本体与 tests/ 外，没有第二份资格判据。"""
    root = Path(__file__).resolve().parents[1]
    offenders: list[str] = []
    for py in sorted(root.rglob("*.py")):
        rel = py.relative_to(root).as_posix()
        if "tests" in py.parts or "__pycache__" in py.parts:
            continue
        if rel == "qa_eligibility.py":
            continue
        src = py.read_text(encoding="utf-8")
        lines = _eligibility_compare_nodes(src, rel)
        if lines:
            offenders.append(f"{rel}:{lines}")
    assert offenders == [], f"发现第二份读取资格判据：{offenders}"


# 三属性 × 五形状：每一格都是「生产里真可能这么写」的样本，且都必须被抓到。
_SHAPE_SAMPLES: dict[str, str] = {
    "attribute": 'def f(row, v):\n    if row.{attr} == "{value}":\n        return v\n    return None\n',
    "membership": 'def f(row, v):\n    if row.{attr} in {{"{value}", "其它"}}:\n        return v\n    return None\n',
    "alias": 'def f(row, v):\n    held = row.{attr}\n    if held == "{value}":\n        return v\n    return None\n',
    "getattr": 'def f(row, v):\n    if getattr(row, "{attr}") == "{value}":\n        return v\n    return None\n',
    "subscript": 'def f(meta, v):\n    if meta.get("{attr}") == "{value}":\n        return v\n    return None\n',
}
_VALUE_BY_ATTR = {
    "status": "rejected",
    "eligibility": "revoked",
    "approval_source": "unknown",
}


@pytest.mark.parametrize("shape", sorted(SHAPES))
@pytest.mark.parametrize("attr", sorted(STATE_ATTRS))
def test_guard_catches_every_attribute_times_shape_combination(attr, shape):
    """V5 的正对照矩阵：三属性 × 五形状 = 15 格，每格一条**会红的样本**。

    每一格还带一条**拆腿对照**：把负责这一格的形状腿拆掉（`skip=(shape,)`），样本必须漏检 ⇒
    证明这一格是被这条腿咬住的，而不是被别的腿顺手咬住的（否则「15 格全过」可能只是 1 条腿在撑）。
    抽掉任一条判据都会有对应的一格红，这就是票面 V5 要的那句。
    """
    src = _SHAPE_SAMPLES[shape].format(attr=attr, value=_VALUE_BY_ATTR[attr])
    hits = _eligibility_compare_nodes(src, "shadow.py")
    assert hits, f"{attr}/{shape} 的第二份判据没被抓到 ⇒ 尺子漏这一类：\n{src}"
    assert not _eligibility_compare_nodes(src, "shadow.py", skip=(shape,)), (
        f"{attr}/{shape} 这一格被别的腿咬住了 ⇒ 形状腿「{shape}」是空跑的，本条判据不可信"
    )


def test_guard_positive_control_actually_fires():
    """阳性对照（保留原腿，另补漏掉的三种形状）：守卫不是空扫。

    原对照只喂它能咬的那一种形状（`state["eligibility"] == "revoked"`）——那等于
    「用尺子能量到的东西证明尺子有效」。现在四样一起喂：
    字典取值（原腿）、`row.status == "rejected"`、别名后比、`getattr` 后比，
    外加写侧赋值这条**反向**腿（写不是判据，不许误伤）。
    """
    bad = 'def _copy(state):\n    if state["eligibility"] == "revoked":\n        return False\n    return True\n'
    assert _eligibility_compare_nodes(bad, "shadow.py"), "阳性对照打空 ⇒ 守卫形同虚设"
    benign = 'r.eligibility = "revoked"\n'  # 写侧赋值不是判据
    assert _eligibility_compare_nodes(benign, "writer.py") == []
    # 改前漏的三形状（票面 F4），逐条必须被抓到
    for label, src in {
        "status 属性 + rejected 词表": 'if row.status == "rejected":\n    pass\n',
        "别名后比": 'held = row.approval_source\nif held == "unknown":\n    pass\n',
        "getattr 后比": 'if getattr(row, "eligibility") in {"revoked", "quarantined"}:\n    pass\n',
        "字典下标后比": 'if meta["status"] == "pending":\n    pass\n',
        "两跳改名": 'a = row.eligibility\nb = a\nif b == "quarantined":\n    pass\n',
    }.items():
        assert _eligibility_compare_nodes(src, "shadow.py"), f"改前漏的形状如今又漏了：{label}"
    # 反向腿：SQLAlchemy 列表达式（类名.列，喂给 .filter() 的查询条件）不是 Python 判据
    column_expr = 'q = db.query(QaCandidate).filter(QaCandidate.status == "pending")\n'
    assert _eligibility_compare_nodes(column_expr, "admin.py") == [], "列表达式被误判成第二份判据 ⇒ 尺子会咬管理面"
    # 反向腿：成对判（`status` 是全仓通用列名，`"ok"` 属备份/评测那套词汇；`eligibility` 无歧义所以全收）
    assert _eligibility_compare_nodes('if item["status"] == "ok":\n    pass\n', "backup.py") == []
    assert _eligibility_compare_nodes('if state["eligibility"] == "ok":\n    pass\n', "shadow.py"), (
        "eligibility == ok 漏检 ⇒ 放行侧的第二份判据抓不住"
    )


# ==================== §4 项 5：id 链闭合（双向对得上），对不上 fail-closed ====================


def test_new_auto_curated_qa_has_bidirectional_link(db, double_embeddings, monkeypatch):
    """新收录：SQL 有 vector_doc_id，向量 metadata 有 qa_candidate_id，两者对得上。"""
    q = "链闭合甲：自动收录的新 QA 两边能对上吗？"
    row = ks.create_candidate(db, q, ANSWER, 0.95, EVIDENCE)
    assert row.approval_source == "auto_by_score_inferred"
    assert row.vector_doc_id, "SQL 没记下 vector_doc_id ⇒ 链没闭合"

    data = ks._qa_store._collection.get(ids=[row.vector_doc_id], include=["metadatas"])
    assert data["ids"], "SQL 记的 vector_doc_id 在向量里找不到那条 ⇒ 两侧对不上"
    meta = (data["metadatas"] or [{}])[0]
    assert meta.get("qa_candidate_id") == row.id, (meta, row.id)


def test_human_approval_records_source_and_link(db, double_embeddings, monkeypatch):
    """人工采纳：approval_source=human + reviewed_by/at 落库，链同样闭合。"""
    q = "链闭合乙：人工采纳的候选怎么标来源？"
    row = ks.create_candidate(db, q, ANSWER, 0.55, EVIDENCE)  # 待审
    assert row.status == "pending"
    decided = ks.decide_candidate(db, row.id, "approved", reviewed_by=99)
    assert decided.status == "approved"
    assert decided.approval_source == "human"
    assert decided.reviewed_by == 99
    assert decided.reviewed_at is not None
    assert decided.vector_doc_id, "采纳没写 vector_doc_id ⇒ 链没闭合"
    meta = (ks._qa_store._collection.get(ids=[decided.vector_doc_id], include=["metadatas"])["metadatas"] or [{}])[0]
    assert meta.get("qa_candidate_id") == decided.id


def test_mismatched_existing_row_is_fail_closed_not_served(db, double_embeddings, monkeypatch):
    """§4 项 5 后半：qa_candidate_id 指向不存在的行 ⇒ fail-closed，不被读成放行。"""
    q = "链闭合丙：指向空行的记录会 fail-closed 吗？"
    row = ks.create_candidate(db, q, ANSWER, 0.95, EVIDENCE)
    _kb_has_article(monkeypatch, [{"page_content": "第十九条"}])
    hit = ks.search_qa(q)
    assert hit is not None
    # 把题干指向一个绝不存在的候选行（模拟存量错链）
    broken = dict(hit, qa_candidate_id=int(row.id) + 100000)
    assert main._qa_direct_return({"rewritten": q, "qa_hit": broken}) is None
    prompt = _prompt_text(main._build_messages(_build_pre(q, broken)))
    assert "此前已确认的问答" not in prompt


# ==================== 票 W06-FIX V4/F2②：`quarantined` 现在没有生产者（一根**必须变红**的钉子）====================


def _quarantined_write_nodes(source: str) -> list[int]:
    """找出**把 `eligibility` 写成 `quarantined`** 的行（写形状闭包＋别名闭包）。

    只认「写」：属性赋值 / 下标赋值 / `setattr(obj, "eligibility", …)` / ORM `update`+`values`
    的字典项或关键字 / 元数据字典项 / 裸 SQL（`execute("… eligibility = ?", ("quarantined",))`）。
    比较（`== "quarantined"`）与文档字符串不算——那是**读**与**说明**。

    票 R2-F6（复核第二轮）：改前只认**字面量**，于是 `Q = "quarantined"; r.eligibility = Q`、
    `setattr(...)`、裸 SQL 三种写法都能带着「零生产者」那条钉子变绿——而读侧尺子（同文件
    `_state_reads`）早就做过别名闭包，写侧却没做。同一族尺子不能一头闭一头开。
    """
    nodes = list(ast.walk(ast.parse(source)))
    names: set[str] = set()
    for _ in range(6):  # 别名闭包到定点：`Q = "quarantined"`、`R = Q`、`S = R` 都要认
        grew = False
        for node in nodes:
            if not isinstance(node, ast.Assign):
                continue
            direct = isinstance(node.value, ast.Constant) and node.value.value == "quarantined"
            via_alias = isinstance(node.value, ast.Name) and node.value.id in names
            if not (direct or via_alias):
                continue
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id not in names:
                    names.add(target.id)
                    grew = True
        if not grew:
            break

    def is_quarantined(value: ast.expr) -> bool:
        if isinstance(value, ast.Constant):
            return value.value == "quarantined"
        return isinstance(value, ast.Name) and value.id in names

    def mentions_eligibility(subtree: ast.AST) -> bool:
        return any(
            isinstance(n, ast.Constant) and isinstance(n.value, str) and "eligibility" in n.value
            for n in ast.walk(subtree)
        )

    hits: list[int] = []
    for node in nodes:
        # ① 赋值：`r.eligibility = "quarantined"` / `row["eligibility"] = Q`
        if isinstance(node, ast.Assign) and is_quarantined(node.value):
            for target in node.targets:
                if (isinstance(target, ast.Attribute) and target.attr == "eligibility") or (
                    isinstance(target, ast.Subscript)
                    and isinstance(target.slice, ast.Constant)
                    and target.slice.value == "eligibility"
                ):
                    hits.append(node.lineno)
                    break
        # ② ORM 批量写 / 元数据字典项：`{"eligibility": "quarantined"}`、`values(eligibility=Q)`
        if isinstance(node, ast.Dict):
            for k, v in zip(node.keys, node.values, strict=True):
                if isinstance(k, ast.Constant) and k.value == "eligibility" and is_quarantined(v):
                    hits.append(node.lineno)
        if isinstance(node, ast.Call):
            func = node.func
            # ③ setattr(obj, "eligibility", "quarantined")
            if isinstance(func, ast.Name) and func.id == "setattr" and len(node.args) >= 3:
                if (
                    isinstance(node.args[1], ast.Constant)
                    and node.args[1].value == "eligibility"
                    and is_quarantined(node.args[2])
                ):
                    hits.append(node.lineno)
            if isinstance(func, ast.Attribute) and func.attr in ("update", "values"):
                for kw in node.keywords:
                    if kw.arg == "eligibility" and is_quarantined(kw.value):
                        hits.append(node.lineno)
            # ④ 裸 SQL：语句文本里出现 eligibility，同一次调用里出现 quarantined（含别名）
            if isinstance(func, (ast.Name, ast.Attribute)) and (
                getattr(func, "id", getattr(func, "attr", "")) in ("execute", "executemany", "text")
            ):
                args = list(node.args) + [kw.value for kw in node.keywords]
                has_el = any(mentions_eligibility(a) for a in args)
                has_q = any(
                    is_quarantined(n) for a in args for n in ast.walk(a) if isinstance(n, (ast.Constant, ast.Name))
                )
                if has_el and has_q:
                    hits.append(node.lineno)
    return sorted(set(hits))


_QUARANTINE_WRITE_SAMPLES = {
    "attr_assign": 'r.eligibility = "quarantined"\n',
    "subscript_assign": 'row["eligibility"] = "quarantined"\n',
    "orm_update_dict": 'db.query(QaCandidate).update({"eligibility": "quarantined"})\n',
    "orm_values_kwarg": 'db.query(QaCandidate).filter(x).values(eligibility="quarantined")\n',
    "metadata_dict": 'meta = {"answer": "a", "eligibility": "quarantined"}\n',
    # R2-F6 补的三形：别名 / setattr / 裸 SQL——改前这三形都能带着「零生产者」那条钉子变绿
    "alias_chain": 'Q = "quarantined"\nR = Q\nr.eligibility = R\n',
    "setattr_form": 'setattr(row, "eligibility", "quarantined")\n',
    "raw_sql_form": 'con.execute("update qa_candidates set eligibility = ?", ("quarantined",))\n',
}


@pytest.mark.parametrize("label", sorted(_QUARANTINE_WRITE_SAMPLES))
def test_quarantined_write_scanner_catches_every_write_shape(label):
    """这条是下一条的**阳性对照**：写入扫描器必须真能认出每一种写形状。

    没有这半条，「零生产者」会因为「扫描器根本没在找东西」而恒真（本仓教训：
    「没有 X」型判据必须配一条「X 长什么样都能抓到」的对照）。
    """
    src = _QUARANTINE_WRITE_SAMPLES[label]
    assert _quarantined_write_nodes(src), f"写入形状漏检：{label}"
    # 反向：把值换成别的词 ⇒ 不该命中（证明咬的是「quarantined 被写」，不是「eligibility 被写」）
    assert not _quarantined_write_nodes(src.replace("quarantined", "revoked")), f"{label} 误报：写 revoked 也算生产者"


def test_quarantined_has_exactly_one_producer_file_and_it_is_the_backfill_registration():
    """**原钉**「全仓没有任何一处把 `eligibility` 写成 `quarantined`（这是根预期红，backfill 落地那天应当红）」
    ⇒ **现钉**「写 `quarantined` 的文件恰为 `scripts/backfill_qa_link.py` 一只，写入点恰 2 处」。

    理由：票 `dispatch/w06-backfill-ticket.md` 已于 2026-10-18 交付，那根预期红**如期红了**
    （见 `evidence/VERIFY-R2-and-backfill-targeted.log`：`1 failed, 167 passed`，红的就是旧措辞这条）。
    按旧 docstring 自己写明的处置转义成正向判据——**没有删**，因为这条存在的全部意义是防"隔离无声上线/无声下线"：
    现在多一个生产者它红，backfill 被改回不写隔离它同样红。
    扫描器本身由上面那条参数化对照钉住（八种写形状，含别名／`setattr`／裸 SQL，R2-F6）。

    2 处写入点＝`build_plan` 里孤儿登记与重复(superseded)登记这两条 `new_rows` 字典。
    同步面：`docs/capability-matrix.md` 的「隔离半边」行按本轮现量改写。
    """
    root = Path(__file__).resolve().parents[1]
    producers: dict[str, int] = {}
    for py in sorted(root.rglob("*.py")):
        rel = py.relative_to(root).as_posix()
        if "tests" in py.parts or "__pycache__" in py.parts:
            continue
        if rel == "qa_eligibility.py":  # 判据本体只有**读**
            continue
        lines = _quarantined_write_nodes(py.read_text(encoding="utf-8"))
        if lines:
            producers[rel] = len(lines)
    assert producers == {"scripts/backfill_qa_link.py": 2}, (
        f"`quarantined` 的生产者面与在册不符：{producers}。"
        "期望恰为回填脚本的孤儿/重复两处登记 ⇒ 多出来＝第二个隔离生产者未经登记就上线（票面 §2 要求先计数再动手）；"
        "少了＝backfill 被无声改回不写隔离 ⇒ 隔离半边又变回空话。"
    )


def test_list_candidates_exposes_the_six_state_columns(db, double_embeddings):
    """V4 的另一半（F2①）：管理面 DTO 必须带那六列，否则「隔离」将来在管理面上**看不见**。"""
    q = "管理面可见性：列表 DTO 有没有把资格六列带出来？"
    row = ks.create_candidate(db, q, ANSWER, 0.55, EVIDENCE)
    ks.decide_candidate(db, row.id, "approved", reviewed_by=7)
    rows = ks.list_candidates(db)
    assert rows, "列表为空 ⇒ 下面的键断言没有对象"
    got = next(r for r in rows if r["id"] == row.id)
    for key in ("approval_source", "reviewed_by", "reviewed_at", "eligibility", "eligibility_version", "vector_doc_id"):
        assert key in got, f"DTO 缺列 {key} ⇒ 隔离/撤回在管理面不可见：{sorted(got)}"
    assert got["approval_source"] == "human" and got["eligibility"] == "ok"
    assert got["vector_doc_id"] == row.vector_doc_id, "DTO 的链与 SQL 不一致 ⇒ 可见性是假的"
    assert got["eligibility_version"] >= 1


# ==================== 票 W06-FIX V3/F1：无链写入是**有名有数**的状态 ====================


def test_unlinked_qa_write_lights_the_registered_key_and_the_count(db, double_embeddings, monkeypatch):
    """V3/F1：`qa_seeds.py:62` 与 `scripts/gen_qa_corpus.py:178` 这两只在册写入者**不带链**——
    本票不发明语义，只把「未链」变成有名有数的状态：
    ① 落一只**已登记**的归因键 `qa_write_unlinked`（未登记会被 JSON formatter 静默丢弃），
    ② 计数与键一致（DTO 读数），
    ③ 判据不许把它读成「放行」，只许读成「**不可撤回的语料**」。

    正对照＝**造一条无链写入**（`add_qa_pair` 不传 cand_id），键必须亮、计数必须 +1；
    反对照＝带链写入（自动收录那条路径）键不许亮、计数不许动。
    """
    import logging

    import observability
    from observability import _JsonFormatter

    assert "qa_write_unlinked" in observability._ACCOUNT_FIELDS, "键没登记 ⇒ 会被 JSON formatter 静默丢弃（白写）"

    chat_logger = logging.getLogger("legal.chat")
    records: list[logging.LogRecord] = []

    class _Handler(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            records.append(record)

    handler = _Handler(level=logging.WARNING)
    previous = chat_logger.level
    chat_logger.addHandler(handler)
    chat_logger.setLevel(logging.WARNING)
    try:
        # ---- 反对照：带链写入（自动收录）不该亮键、不该动计数 ----
        linked_q = "无链可见甲：自动收录的写入不该算未链。"
        before_linked = ks.qa_write_counts()["linked"]
        before_unlinked = ks.qa_write_counts()["unlinked"]
        ks.create_candidate(db, linked_q, ANSWER, 0.95, EVIDENCE)
        assert not [r for r in records if getattr(r, "qa_write_unlinked", False)], "带链写入亮了未链键"
        assert ks.qa_write_counts()["linked"] == before_linked + 1
        assert ks.qa_write_counts()["unlinked"] == before_unlinked

        # ---- 正对照：无链写入（种子/生成脚本那两只的形状）键必须亮 ----
        records.clear()
        q = "无链可见乙：种子脚本那种不带 cand_id 的写入会不会留下读数？"
        ks.add_qa_pair(q, ANSWER, EVIDENCE)  # 与 qa_seeds.py / gen_qa_corpus.py 同样的调用形状
        lit = [r for r in records if getattr(r, "qa_write_unlinked", False)]
        assert len(lit) == 1, f"未链写入没留痕（现量 {len(lit)} 条）⇒ 「有名有数」这一半没成立"
        payload = json.loads(_JsonFormatter().format(lit[0]))
        assert payload["qa_write_unlinked"] is True, payload
        assert ks.qa_write_counts()["unlinked"] == before_unlinked + 1, "计数与键不一致 ⇒ 读数不能当指标"
        assert q not in json.dumps(payload, ensure_ascii=False), "日志落了题干（AUTH-3）"

        # ---- 判据侧（F1 的「不许读成放行」）：缺链**不是**放行信号，只是状态轴不适用 ----
        # 「无链 ⇒ 按来源/引用判定」这一放行面由 `test_qa_provenance_guard.py`／
        # `test_qa_citation_gate_symmetry.py` 钉死，不许打掉；这里判的是另一半：**没有链不等于可以服务**。
        # 反证：同样无链、但引用为空的一条必须被拒（reason=provenance），
        # 也就是说判据从没把「缺链」 itself 当成通过的理由。
        hit = ks.search_qa(q)
        assert hit is not None and hit.get("qa_candidate_id") is None, "无链记录应当没有候选 id"
        assert qe.qa_read_eligible(dict(hit, evidence="[]"), None).reason == "provenance", (
            "无链记录被读成放行 ⇒ 判据把「没有链」当成了「可以服务」"
        )
        # 状态轴对无链记录**不适用**（放行面），于是也没有任何一行 SQL 能被置成 revoked ⇒
        # 这批语料是**不可撤回**的，唯一的读数就是刚亮的这只键。
        assert qe.evaluate_revocation_state(hit).allow is True, "状态轴应当对无链记录不适用（放行面不许改）"
        assert ks.search_qa(q)["qa_candidate_id"] is None
        assert ks.qa_write_counts()["unlinked"] >= before_unlinked + 1
    finally:
        chat_logger.removeHandler(handler)
        chat_logger.setLevel(previous)
