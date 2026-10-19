"""W06-C Task 6/7：来源包契约、模型上下文投影与落盘来源（H01/H02/H03/H06 的合成控制）。

判据对象是**产品函数**：`qa_eligibility.serialize_provenance/parse_provenance/build_provenance/
dependencies_for_reuse/has_self_reference`、`memory.load_model_context/load_model_context_bootstrap/
load_context`、`main._post`。不是测试自造的等价物。

隔离：conftest 的 tmp SQLite（`db`）+ tmp CHROMA_DIR；不读真实会话/实库，不联网，不落问句/答案原文。
H07（旧未知来源输入规则）在本票**不裁**，其行为记为 BLOCKED_OWNER（见报告），此处只钉"未知不被
静默屏蔽、也不被签成可信空集"这两条已实现的边界。
"""

import json
import os
import sys
import uuid

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

import main  # noqa: E402
import memory  # noqa: E402
import qa_eligibility as qe  # noqa: E402
from models import Conversation, Message, QaCandidate, User  # noqa: E402

ANSWER = "《劳动合同法》第十九条：试用期最长不得超过六个月。"
EVIDENCE = json.dumps([{"source": "中华人民共和国劳动合同法", "article": "第十九条"}], ensure_ascii=False)


def _dep(cid=7, doc="a", ver=1, digest="d" * 64):
    return qe.QaDependency(cid, doc, ver, digest)


# ==================== 契约：序列化 / 解析（唯一入口） ====================


def test_serialize_parse_round_trip_is_the_single_entry():
    prov = qe.Provenance(True, (_dep(), _dep(cid=8, doc="b")), (1, 2))
    text = qe.serialize_provenance(prov)
    assert isinstance(text, str)
    assert qe.parse_provenance(text) == prov
    # 键序不同的等价 JSON 也解析成同一对象（解析只认字段，不认字节序）
    shuffled = json.dumps(json.loads(text), ensure_ascii=False)
    assert qe.parse_provenance(shuffled) == prov


def test_parse_unknown_states_never_become_empty():
    assert qe.parse_provenance(None) is None  # 列 NULL＝旧来源未知
    assert qe.parse_provenance("") is None
    assert qe.parse_provenance("{not json") is None
    assert qe.parse_provenance(json.dumps(["not", "a", "dict"])) is None
    # 未来未支持的 schema 版本 ⇒ 未知（不作可信空集）
    assert qe.parse_provenance(json.dumps({"schema_version": 99, "complete": True, "qa_dependencies": []})) is None
    # 坏形状：类型不对
    assert qe.parse_provenance(json.dumps({"schema_version": "1", "complete": True, "qa_dependencies": []})) is None
    assert qe.parse_provenance(json.dumps({"schema_version": 1, "complete": "yes", "qa_dependencies": []})) is None
    assert qe.parse_provenance(json.dumps({"schema_version": 1, "complete": True, "qa_dependencies": "x"})) is None
    assert (
        qe.parse_provenance(
            json.dumps({"schema_version": 1, "complete": True, "qa_dependencies": [{"candidate_id": 1}]})
        )
        is None
    )
    # complete=false 仍可解析成对象，但复用面判为未知
    p = qe.parse_provenance(json.dumps({"schema_version": 1, "complete": False, "qa_dependencies": []}))
    assert p is not None and p.complete is False
    assert qe.dependencies_for_reuse(p) is None


def test_known_empty_tuple_is_not_unknown():
    empty = qe.build_provenance(())
    assert empty is not None and empty.complete and empty.qa_dependencies == ()
    assert qe.dependencies_for_reuse(empty) == ()  # 已证明无 QA 祖先
    assert qe.dependencies_for_reuse(None) is None  # 未知 ≠ 空
    assert qe.build_provenance(None) is None  # 本次 QA 未知 ⇒ 整体未知


def test_unknown_ancestor_propagates_unknown():
    known = qe.build_provenance(())
    assert qe.build_provenance((), ancestors=(known, None)) is None
    incomplete = qe.Provenance(False, (), ())
    assert qe.build_provenance((), ancestors=(incomplete,)) is None


def test_dedup_and_capacity_never_truncate_then_claim_complete():
    dep = _dep()
    merged = qe.build_provenance((dep, dep), ancestors=(qe.Provenance(True, (dep,), (5,)),))
    assert merged is not None and merged.qa_dependencies == (dep,)
    assert merged.input_message_ids == (5,)
    over = tuple(_dep(cid=i) for i in range(qe.MAX_QA_DEPENDENCIES + 1))
    assert qe.build_provenance(over) is None, "容量超限必须保守判未知，不许截断后仍称完整"
    stored_over = json.dumps(
        {
            "schema_version": 1,
            "complete": True,
            "qa_dependencies": [
                {"candidate_id": i, "vector_doc_id": "d", "eligibility_version": 1, "record_digest": "x"}
                for i in range(qe.MAX_QA_DEPENDENCIES + 1)
            ],
            "input_message_ids": [],
        }
    )
    assert qe.parse_provenance(stored_over) is None


def test_self_reference_is_detected():
    prov = qe.Provenance(True, (_dep(cid=7),), ())
    assert qe.has_self_reference(prov, 7) is True
    assert qe.has_self_reference(prov, 8) is False
    assert qe.has_self_reference(None, 7) is False


# ==================== 投影：已知失效来源不进模型上下文 ====================


def _seed_conv(db, *messages):
    from datetime import datetime, timedelta

    user = User(username=f"provenance-{uuid.uuid4().hex[:8]}", password_hash="x")
    db.add(user)
    db.flush()
    conv = Conversation(user_id=user.id, title="", summary="", message_count=len(messages))
    db.add(conv)
    db.flush()
    base = datetime(2026, 1, 1)
    for i, (role, content, prov) in enumerate(messages):
        db.add(
            Message(
                conversation_id=conv.id,
                role=role,
                content=content,
                qa_provenance=prov,
                created_at=base + timedelta(seconds=i),
            )
        )
    db.commit()
    db.refresh(conv)
    return conv


def _approved_dep(db, question):
    """合成一条可服务候选并返回其不可变依赖（向量链闭合，读侧能复核）。"""
    doc_id = uuid.uuid4().hex
    row = QaCandidate(
        question=question,
        answer=ANSWER,
        grounded_score=0.9,
        evidence=EVIDENCE,
        status="approved",
        approval_source="human",
        vector_doc_id=doc_id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    dep = qe.QaDependency(
        row.id, doc_id, int(row.eligibility_version or 1), qe._record_digest(row.question, row.answer, row.evidence)
    )
    return row, dep


def test_projection_drops_known_revoked_assistant_but_ui_keeps_original(db):
    row, dep = _approved_dep(db, "投影控制题：这条结论还作数吗？")
    prov_text = qe.serialize_provenance(qe.Provenance(True, (dep,), ()))
    conv = _seed_conv(db, ("user", "用户事实：合同三个月", None), ("assistant", "旧法律结论（来自 G）", prov_text))

    # UI/审计接口保留原文（历史不删改）
    _summary, ui = memory.load_context(db, conv)
    assert [m.content for m in ui] == ["用户事实：合同三个月", "旧法律结论（来自 G）"]

    # 未撤回：投影保留（先证明对象真实存在，避免阴性假绿）
    ctx = memory.load_model_context(db, conv)
    assert [m.content for m in ctx.recent if m.reusable] == ["用户事实：合同三个月", "旧法律结论（来自 G）"]

    # 撤回 G：投影剔除失效助手，用户事实保留；UI 仍见原文
    row.eligibility = "revoked"
    db.commit()
    ctx2 = memory.load_model_context(db, conv)
    assert [m.content for m in ctx2.recent if m.reusable] == ["用户事实：合同三个月"]
    assert any(m.content == "旧法律结论（来自 G）" and not m.reusable for m in ctx2.recent)
    _summary2, ui2 = memory.load_context(db, conv)
    assert [m.content for m in ui2] == ["用户事实：合同三个月", "旧法律结论（来自 G）"]


def test_unknown_provenance_assistant_not_handed_as_trusted_db(db):
    """H07（Owner 已裁）：未知来源 assistant **不作为已确认依据交给模型**（剔除），用户事实保留。

    既不是「全量屏蔽历史」，也不是「默认放行未知」：未知被剔除但**仍不签成可信空集**（聚合记 None）。
    """
    conv = _seed_conv(db, ("user", "事实", None), ("assistant", "未追溯旧结论", None))
    ctx = memory.load_model_context(db, conv)
    assert [m.content for m in ctx.recent if m.reusable] == ["事实"], "未知来源助手结论不得作为已确认依据交给模型"
    dropped = [m for m in ctx.recent if m.role == "assistant"]
    assert dropped and dropped[0].state == "unknown" and dropped[0].reusable is False
    assert ctx.unknown_history is True
    assert ctx.dependencies is None, "未知祖先 ⇒ 聚合依赖未知，不得降成空 tuple"
    # UI/审计仍保留原文
    _summary, ui = memory.load_context(db, conv)
    assert [m.content for m in ui] == ["事实", "未追溯旧结论"]


def test_h07_three_states_unknown_verified_revoked_are_distinguishable(db):
    """H07 判据：能分辨「未知 vs 已核验 vs 已撤回」三态，且都不是「全量屏蔽历史」。"""
    row_ok, dep_ok = _approved_dep(db, "三态：已核验")
    row_rev, dep_rev = _approved_dep(db, "三态：已撤回")
    row_rev.eligibility = "revoked"
    db.commit()
    prov_ok = qe.serialize_provenance(qe.Provenance(True, (dep_ok,), ()))
    prov_rev = qe.serialize_provenance(qe.Provenance(True, (dep_rev,), ()))
    conv = _seed_conv(
        db,
        ("user", "用户事实", None),
        ("assistant", "已核验结论", prov_ok),
        ("assistant", "已撤回结论", prov_rev),
        ("assistant", "未知来源结论", None),
    )
    ctx = memory.load_model_context(db, conv)
    states = {m.content: m.state for m in ctx.recent}
    assert states == {
        "用户事实": "user",
        "已核验结论": "verified",
        "已撤回结论": "revoked",
        "未知来源结论": "unknown",
    }
    assert [m.content for m in ctx.recent if m.reusable] == ["用户事实", "已核验结论"]
    assert ctx.dependencies == (dep_ok,) or ctx.dependencies is None  # 未知存在 ⇒ None 也是允许的保守口径
    # UI 原文四条全在
    _s, ui = memory.load_context(db, conv)
    assert [m.content for m in ui] == ["用户事实", "已核验结论", "已撤回结论", "未知来源结论"]


def test_h07_unknown_summary_not_handed_to_model_but_ui_keeps_it(db):
    """H07：来源未知的非空摘要 ⇒ 不进模型上下文（不作可信既有结论），原文/游标仍在库里可见。"""
    conv = _seed_conv(db, ("user", "用户事实", None))
    conv.summary = "来源未知的旧摘要"
    db.commit()
    db.refresh(conv)
    ctx = memory.load_model_context(db, conv)
    assert ctx.summary_state == "unknown" and ctx.summary_usable is False
    assert ctx.summary == "", "未知来源摘要不得作为可信既有结论交给模型"
    assert ctx.unknown_history is True
    _s, _ui = memory.load_context(db, conv)
    fresh = db.get(Conversation, conv.id)
    db.refresh(fresh)
    assert fresh.summary == "来源未知的旧摘要"


def test_projection_aggregate_dependencies_for_tracked_history(db):
    row, dep = _approved_dep(db, "投影聚合题：依赖怎么算？")
    prov_text = qe.serialize_provenance(qe.Provenance(True, (dep,), ()))
    conv = _seed_conv(db, ("user", "事实", None), ("assistant", "有链结论", prov_text))
    ctx = memory.load_model_context(db, conv)
    assert ctx.dependencies == (dep,), "有完整传递来源的历史应产出可复核的非空依赖"


# ==================== 落盘来源：_post 写消息 / 派生候选（Task 7） ====================


def _patch_post_env(db, monkeypatch):
    from sqlalchemy.orm import sessionmaker

    sf = sessionmaker(bind=db.get_bind(), autoflush=False, autocommit=False)
    monkeypatch.setattr(main, "SessionLocal", sf)
    monkeypatch.setattr(main, "needs_compress", lambda conv, recent: False)
    return sf


def _seed_conversation(db, prov_text=None):
    user = User(username=f"post-{uuid.uuid4().hex[:8]}", password_hash="x")
    db.add(user)
    db.flush()
    conv = Conversation(user_id=user.id, title="", summary="", message_count=0)
    db.add(conv)
    db.flush()
    if prov_text is not None:
        db.add(Message(conversation_id=conv.id, role="user", content="上一轮问题", qa_provenance=None))
        db.add(Message(conversation_id=conv.id, role="assistant", content="上一轮结论", qa_provenance=prov_text))
        conv.message_count = 2
    db.commit()
    db.refresh(conv)
    return conv.id


def test_post_writes_known_empty_provenance_for_first_turn(db, monkeypatch):
    _patch_post_env(db, monkeypatch)
    cid = _seed_conversation(db)
    pre = {
        "conv_id": cid,
        "intent": "chitchat",
        "rewritten": "你好",
        "user_text": "你好",
        "sources": [],
        "qa_hit": None,
    }
    main._post(pre, "你好，我是法智助手。")
    msg = db.query(Message).filter(Message.conversation_id == cid, Message.role == "assistant").one()
    prov = qe.parse_provenance(msg.qa_provenance)
    assert prov is not None and prov.complete and prov.qa_dependencies == (), "第一轮无 QA、无历史 ⇒ 已知空来源包"
    assert db.query(QaCandidate).count() == 0


def test_post_inherits_ancestor_provenance_into_new_message(db, monkeypatch):
    _patch_post_env(db, monkeypatch)
    row, dep = _approved_dep(db, "继承题：上一轮结论还有效吗？")
    prov_text = qe.serialize_provenance(qe.Provenance(True, (dep,), ()))
    cid = _seed_conversation(db, prov_text)
    pre = {
        "conv_id": cid,
        "intent": "chitchat",
        "rewritten": "那下一步呢",
        "user_text": "那下一步呢",
        "sources": [],
        "qa_hit": None,
    }
    main._post(pre, "下一步建议……")
    msg = (
        db.query(Message)
        .filter(Message.conversation_id == cid, Message.role == "assistant")
        .order_by(Message.id.desc())
        .first()
    )
    prov = qe.parse_provenance(msg.qa_provenance)
    assert prov is not None and dep in prov.qa_dependencies, "新回答必须继承历史祖先依赖（H03）"


def test_post_new_candidate_inherits_provenance(db, monkeypatch):
    _patch_post_env(db, monkeypatch)
    monkeypatch.setattr(main, "grounded_top_score", lambda q: 0.9)
    monkeypatch.setattr(main, "should_curate", lambda g, a: True)
    row, dep = _approved_dep(db, "候选继承题：新候选会不会丢祖先？")
    prov_text = qe.serialize_provenance(qe.Provenance(True, (dep,), ()))
    cid = _seed_conversation(db, prov_text)
    pre = {
        "conv_id": cid,
        "intent": "legal_query",
        "rewritten": "试用期最长多久",
        "user_text": "试用期最长多久",
        "sources": [{"source": "劳动合同法", "article": "第十九条"}],
        "qa_hit": None,
    }
    main._post(pre, "依据《劳动合同法》第十九条，试用期最长六个月。")
    cand = db.query(QaCandidate).order_by(QaCandidate.id.desc()).first()
    prov = qe.parse_provenance(cand.qa_provenance)
    assert prov is not None and dep in prov.qa_dependencies, "派生候选未继承祖先⇒可借新 id 洗白撤回"


# ==================== H17：读侧传递依赖复核（防新 candidate 洗白撤回） ====================


def test_read_side_rejects_candidate_derived_from_revoked_ancestor(db):
    row_g, dep_g = _approved_dep(db, "祖先题：被撤回的 G")
    row_g.eligibility = "revoked"
    db.commit()
    # 派生候选 D：自身是 approved/human 且有向量链，但来源包指向已撤回的 G
    derived = QaCandidate(
        question="派生题：借新 id 能绕过撤回吗？",
        answer=ANSWER,
        grounded_score=0.9,
        evidence=EVIDENCE,
        status="approved",
        approval_source="human",
        vector_doc_id=uuid.uuid4().hex,
        qa_provenance=qe.serialize_provenance(qe.Provenance(True, (dep_g,), ())),
    )
    db.add(derived)
    db.commit()
    db.refresh(derived)
    verdict = qe._state_axis({"qa_candidate_id": derived.id}, qe.load_read_state(derived.id))
    assert verdict is not None and verdict.allow is False
    assert verdict.reason == "ancestor", f"失效祖先应经传递依赖拒绝，实际 {verdict!r}"

    # 阳性对照：祖先未撤回时同一派生记录放行（证明拒绝来自传递依赖，不是"带来源就打死"）
    row_g.eligibility = "ok"
    db.commit()
    assert qe._state_axis({"qa_candidate_id": derived.id}, qe.load_read_state(derived.id)) is None


# ==================== H06：合成旧 schema 升级两次（幂等 + 旧行 NULL） ====================


def test_provenance_columns_upgrade_idempotently_and_leave_old_rows_unknown(tmp_path):
    from sqlalchemy import create_engine, text

    import migrations

    engine = create_engine(f"sqlite:///{tmp_path / 'legacy.db'}")
    with engine.begin() as c:
        c.execute(
            text(
                "CREATE TABLE conversations (id INTEGER PRIMARY KEY, user_id INTEGER, question TEXT, "
                "answer TEXT, title VARCHAR(200), summary TEXT, message_count INTEGER, summary_upto INTEGER, "
                "last_active_at DATETIME, created_at DATETIME)"
            )
        )
        c.execute(
            text(
                "CREATE TABLE messages (id INTEGER PRIMARY KEY, conversation_id INTEGER, role VARCHAR(16), "
                "content TEXT, image_ref VARCHAR(500), thumb_ref VARCHAR(500), image_desc TEXT, "
                "agent_run_id VARCHAR(36), token_est INTEGER, created_at DATETIME)"
            )
        )
        c.execute(
            text(
                "CREATE TABLE qa_candidates (id INTEGER PRIMARY KEY, question TEXT, answer TEXT, grounded_score FLOAT, "
                "evidence TEXT, status VARCHAR(16), approval_source VARCHAR(32), reviewed_by INTEGER, "
                "reviewed_at DATETIME, eligibility VARCHAR(16), eligibility_version INTEGER, "
                "vector_doc_id VARCHAR(64), created_at DATETIME)"
            )
        )
        c.execute(
            text("INSERT INTO conversations (id,user_id,summary,message_count,summary_upto) VALUES (1,1,'旧摘要',3,0)")
        )
        c.execute(text("INSERT INTO messages (id,conversation_id,role,content) VALUES (1,1,'assistant','旧回答')"))
        c.execute(text("INSERT INTO qa_candidates (id,question,answer,status) VALUES (1,'q','a','approved')"))

    migrations.run_migrations(bind=engine)
    migrations.run_migrations(bind=engine)  # 幂等：连续两次不炸、不重复加列

    with engine.connect() as c:
        for table, col in (
            ("messages", "qa_provenance"),
            ("conversations", "summary_provenance"),
            ("qa_candidates", "qa_provenance"),
        ):
            cols = {r[1] for r in c.execute(text(f"PRAGMA table_info({table})")).fetchall()}
            assert col in cols, (table, col)
        # 旧行来源保持 NULL（未知）——不批量洗白成 complete=true 空依赖；旧正文原样
        assert c.execute(text("SELECT qa_provenance FROM messages WHERE id=1")).scalar() is None
        assert c.execute(text("SELECT summary_provenance FROM conversations WHERE id=1")).scalar() is None
        assert c.execute(text("SELECT qa_provenance FROM qa_candidates WHERE id=1")).scalar() is None
        assert c.execute(text("SELECT content FROM messages WHERE id=1")).scalar() == "旧回答"
        assert c.execute(text("SELECT summary FROM conversations WHERE id=1")).scalar() == "旧摘要"


# ==================== H05：缓存回放显式并入缓存条目依赖 ====================


def test_post_cache_replay_merges_cache_entry_dependencies(db, monkeypatch):
    """缓存回放（curate=False）时，缓存条目自身冻结的依赖显式并入新 assistant 来源。

    刻意让会话**没有历史 assistant**（排除"第 1 轮已带该依赖"这条路）：继承只能来自缓存条目。
    """
    _patch_post_env(db, monkeypatch)
    row, dep = _approved_dep(db, "H05 缓存回放题：缓存条目的依赖会继承吗？")
    cid = _seed_conversation(db)
    pre = {"conv_id": cid, "intent": "chitchat", "rewritten": "x", "user_text": "x", "sources": [], "qa_hit": None}
    main._post(pre, "缓存答案", False, qa_dependencies=(dep,))
    msg = db.query(Message).filter(Message.conversation_id == cid, Message.role == "assistant").one()
    prov = qe.parse_provenance(msg.qa_provenance)
    assert prov is not None and dep in prov.qa_dependencies, "缓存条目依赖未被显式并入新历史（H05）"

    # 撤回原 G ⇒ 后续模型投影拒绝这条已失效的新 assistant（继承链生效）
    row.eligibility = "revoked"
    db.commit()
    conv = db.get(Conversation, cid)
    ctx = memory.load_model_context(db, conv)
    assert not [m for m in ctx.recent if m.role == "assistant" and m.reusable], "继承失效祖先的消息仍交模型"


def test_post_cache_replay_without_deps_signs_known_empty(db, monkeypatch):
    """无依赖的缓存条目（已知空）回放 ⇒ 新 assistant 签已知空，不退化成未知。"""
    _patch_post_env(db, monkeypatch)
    cid = _seed_conversation(db)
    pre = {"conv_id": cid, "intent": "chitchat", "rewritten": "x", "user_text": "x", "sources": [], "qa_hit": None}
    main._post(pre, "缓存答案", False, qa_dependencies=())
    msg = db.query(Message).filter(Message.conversation_id == cid, Message.role == "assistant").one()
    prov = qe.parse_provenance(msg.qa_provenance)
    assert prov is not None and prov.complete and prov.qa_dependencies == ()


# ==================== L8：按实际生成输入签发，不从未清理的 pre 现算 ====================


def test_post_authoritative_deps_ignore_stale_uncleaned_pre_hit(db, monkeypatch):
    """L8：O 失效重建后调用方给的是**实际使用的 `ldeps`** ⇒ 不再从未清理的 `pre.qa_hit` 现算。

    否则会把本次并未使用、甚至已撤回的 QA 误签进新 assistant 的来源包。
    """
    _patch_post_env(db, monkeypatch)
    stale_dep = qe.QaDependency(4242, "stale-doc", 1, "d" * 64)
    captured = []

    def _fake_capture(hit):
        captured.append(hit)
        return stale_dep

    monkeypatch.setattr(qe, "capture_dependency", _fake_capture)
    cid = _seed_conversation(db)
    pre = {
        "conv_id": cid,
        "intent": "chitchat",
        "rewritten": "x",
        "user_text": "x",
        "sources": [],
        "qa_hit": {"qa_candidate_id": 4242, "question": "旧", "answer": "旧", "evidence": "旧"},  # 未清理的 stale hit
    }
    # 权威依赖＝空（O 失效重建后本次未使用任何 QA）
    main._post(pre, "重建后的回答", qa_dependencies=())
    assert captured == [], "给了权威依赖却仍从 stale pre 现算（L8 未修）"
    msg = db.query(Message).filter(Message.conversation_id == cid, Message.role == "assistant").one()
    prov = qe.parse_provenance(msg.qa_provenance)
    assert prov is not None and prov.qa_dependencies == (), f"误签了未使用的 QA 依赖：{prov!r}"

    # 反面腿：未给权威依赖时，仍会从 pre 现算（证明上一腿不是恒等式）
    cid2 = _seed_conversation(db)
    pre2 = dict(pre, conv_id=cid2)
    main._post(pre2, "非重建回答")
    assert captured, "未给权威依赖时应从 pre 现算（否则对照腿失去对象）"


def test_post_new_candidate_rejects_self_reference(db, monkeypatch):
    """L11：派生签发处调用循环/自引用拒绝；自引用时不写来源包（防借新 id 洗白撤回）。"""
    _patch_post_env(db, monkeypatch)
    monkeypatch.setattr(main, "grounded_top_score", lambda q: 0.9)
    monkeypatch.setattr(main, "should_curate", lambda g, a: True)
    _row, dep = _approved_dep(db, "L11 自引用题")
    prov_text = qe.serialize_provenance(qe.Provenance(True, (dep,), ()))
    cid = _seed_conversation(db, prov_text)
    monkeypatch.setattr(qe, "has_self_reference", lambda prov, cid: True)  # 强制判为自引用
    pre = {
        "conv_id": cid,
        "intent": "legal_query",
        "rewritten": "试用期最长多久",
        "user_text": "试用期最长多久",
        "sources": [{"source": "劳动合同法", "article": "第十九条"}],
        "qa_hit": None,
    }
    main._post(pre, "依据《劳动合同法》第十九条，试用期最长六个月。")
    cand = db.query(QaCandidate).order_by(QaCandidate.id.desc()).first()
    assert cand.qa_provenance is None, "自引用未被拒绝 ⇒ 来源包仍被写入（L11 未接线）"


# ==================== L10：记录摘要覆盖来源包与 schema 版本 ====================


def test_record_digest_covers_provenance_and_schema_version():
    base = qe._record_digest("q", "a", "e")
    assert base == qe._record_digest("q", "a", "e", None)  # NULL 来源与旧口径同值
    with_prov = qe._record_digest("q", "a", "e", '{"complete":true}')
    assert with_prov != base, "来源包变化未被摘要覆盖 ⇒ 祖先变了仍会复用旧快照（L10 未修）"


# ==================== L12：Agent 终稿声明真实来源覆盖 ====================


def test_declared_final_provenance_signs_known_or_unknown(db):
    """L12：Agent 终稿按会话模型上下文投影声明来源——完整已知（含空）才签，未追踪历史 ⇒ NULL。"""
    from agent.service import _declared_final_provenance

    clean = _seed_conv(db, ("user", "事实", None))
    prov = qe.parse_provenance(_declared_final_provenance(db, clean.id))
    assert prov is not None and prov.complete and prov.qa_dependencies == (), "干净会话应签已知空，不恒 NULL"

    unknown = _seed_conv(db, ("user", "事实", None), ("assistant", "未追溯旧结论", None))
    assert _declared_final_provenance(db, unknown.id) is None, "有未追踪历史应签未知，不假签空"

    row, dep = _approved_dep(db, "L12 有链题")
    tracked = _seed_conv(
        db,
        ("user", "事实", None),
        ("assistant", "有链结论", qe.serialize_provenance(qe.Provenance(True, (dep,), ()))),
    )
    prov3 = qe.parse_provenance(_declared_final_provenance(db, tracked.id))
    assert prov3 is not None and dep in prov3.qa_dependencies


# ==================== H16：同事务原子落盘 / 失败回滚 / Agent 幂等重放 ====================


def test_post_commit_failure_leaves_no_half_written_message(db, monkeypatch):
    """消息正文与来源**同一提交**落盘：提交失败 ⇒ 一行都不落（不出现「正文有、依赖丢」）。"""
    from sqlalchemy.orm import sessionmaker

    class _Boom(Exception):
        pass

    sf = sessionmaker(bind=db.get_bind(), autoflush=False, autocommit=False)
    state = {"n": 0}

    def factory():
        session = sf()
        real_commit = session.commit

        def commit():
            state["n"] += 1
            if state["n"] == 1:
                raise _Boom()
            return real_commit()

        session.commit = commit
        return session

    monkeypatch.setattr(main, "SessionLocal", factory)
    monkeypatch.setattr(main, "needs_compress", lambda conv, recent: False)
    cid = _seed_conversation(db)
    pre = {"conv_id": cid, "intent": "chitchat", "rewritten": "x", "user_text": "x", "sources": [], "qa_hit": None}
    with pytest.raises(_Boom):
        main._post(pre, "回答")
    assert db.query(Message).filter(Message.conversation_id == cid, Message.role == "assistant").count() == 0
    fresh = db.get(Conversation, cid)
    db.refresh(fresh)
    assert fresh.message_count == 0, "提交失败不该推进计数"


def test_post_success_writes_content_and_provenance_together(db, monkeypatch):
    """正常落盘阳性：正文与来源包同时出现（上一节 `test_post_writes_known_empty...` 已证内容+来源并存）。"""
    _patch_post_env(db, monkeypatch)
    cid = _seed_conversation(db)
    pre = {"conv_id": cid, "intent": "chitchat", "rewritten": "x", "user_text": "x", "sources": [], "qa_hit": None}
    main._post(pre, "回答")
    msg = db.query(Message).filter(Message.conversation_id == cid, Message.role == "assistant").one()
    assert msg.content == "回答"
    assert msg.qa_provenance is not None, "正文有了、依赖也必须在同一行（同事务）"


def test_agent_finalize_replay_is_idempotent_and_keeps_provenance(db):
    """H16：Agent 重复 finalize ⇒ 第二次 False，不重复写消息/不重复推进版本；来源包随第一条保留。"""
    from agent.chat_integration import persist_agent_final_once
    from agent.verifier import DeterministicVerifier
    from models import AgentRun
    from tests.test_agent_chat_integration import _records

    _row, dep = _approved_dep(db, "H16 Agent 幂等题")
    prov = qe.serialize_provenance(qe.Provenance(True, (dep,), ()))
    user, conv, run, state, draft = _records(db)
    verification = DeterministicVerifier().verify(state, draft)
    kwargs = dict(
        user_id=user.id,
        conversation_id=conv.id,
        run_id=run.id,
        expected_version=0,
        state=state,
        answer="借款本金为10000元，依据《民法典》第675条应按约返还。",
        verification=verification,
        qa_provenance=prov,
    )
    assert persist_agent_final_once(db, **kwargs) is True
    assert persist_agent_final_once(db, **kwargs) is False
    msgs = db.query(Message).filter_by(conversation_id=conv.id, role="assistant").all()
    assert len(msgs) == 1 and msgs[0].qa_provenance == prov
    saved = db.get(AgentRun, run.id)
    assert saved.state_version == 1, "重放不该重复推进版本"


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
