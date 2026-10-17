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


# ==================== §4 项 4：单一真源 AST 守卫（无第二份判据，带阳性对照） ====================


def _eligibility_compare_nodes(source: str, filename: str) -> list[int]:
    """返回「把资格/审批来源当判据读出来」的 Compare 行号：

    命中形状 = 某比较的一侧访问了 `eligibility`/`approval_source`（属性或下标/get），
    另一侧是与票面词表（revoked/quarantined/ok/approved/unknown/human/auto_by_score_inferred）
    相等的字符串常量，或对该词表做成员判定。写侧赋值（`r.eligibility = "revoked"`）不算判据 ⇒ 不命中。
    """
    vocab = {"revoked", "quarantined", "ok", "approved", "unknown", "human", "auto_by_score_inferred"}
    state_keys = {"eligibility", "approval_source"}

    def _reads_state(node: ast.expr) -> bool:
        if isinstance(node, ast.Attribute):
            return node.attr in state_keys
        if isinstance(node, ast.Subscript):
            sl = node.slice
            return isinstance(sl, ast.Constant) and sl.value in state_keys
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "get":
            if node.args and isinstance(node.args[0], ast.Constant):
                return node.args[0].value in state_keys
        return False

    hits: list[int] = []
    tree = ast.parse(source)
    for cmp in ast.walk(tree):
        if not isinstance(cmp, ast.Compare):
            continue
        operands = [cmp.left, *cmp.comparators]
        touches_state = any(_reads_state(o) for o in operands)
        touches_vocab = False
        for o in operands:
            if isinstance(o, ast.Constant) and o.value in vocab:
                touches_vocab = True
            if isinstance(o, (ast.Tuple, ast.List, ast.Set)) and any(
                isinstance(e, ast.Constant) and e.value in vocab for e in o.elts
            ):
                touches_vocab = True
        if touches_state and touches_vocab:
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


def test_guard_positive_control_actually_fires():
    """阳性对照：守卫不是空扫——喂一份「自己拼资格判据」的样本必须被抓到（否则上一条恒真）。"""
    bad = 'def _copy(state):\n    if state["eligibility"] == "revoked":\n        return False\n    return True\n'
    assert _eligibility_compare_nodes(bad, "shadow.py"), "阳性对照打空 ⇒ 守卫形同虚设"
    benign = 'r.eligibility = "revoked"\n'  # 写侧赋值不是判据
    assert _eligibility_compare_nodes(benign, "writer.py") == []


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
