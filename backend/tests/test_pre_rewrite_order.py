"""query rewrite v3 集成测试：意图后置改写 + 法考题短路 + 沉淀闸 + 题型接线。

决策 2/3/6/7（2026-08-05，grilling 修订后）：改写只在检索分支按需触发；完整带选项
法考题跳过改写；沉淀只收 legal_query；题型指令按 question_type 追加。

Fixture 隔离（M8）：内嵌 SQLite + 逐用例 monkeypatch——检索/QA/场景全打桩，防真打
向量库/QA 库/法条；classify_intent/_is_exam_question/has_exam_options/question_type
用真实纯函数。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

import pytest


@pytest.fixture
def env(monkeypatch):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    import database
    import main
    from models import Base, Conversation, Message, User

    eng = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(eng)
    sm = sessionmaker(bind=eng, autoflush=False, autocommit=False)
    monkeypatch.setattr(database, "SessionLocal", sm)
    monkeypatch.setattr(main, "SessionLocal", sm)

    # 种子对话：1 条历史（user + assistant）→ recent_ser 非空
    db = sm()
    u = User(username="rwo", password_hash="x")
    db.add(u)
    db.flush()
    conv = Conversation(user_id=u.id, title="", summary="", message_count=2, question="")
    db.add(conv)
    db.flush()
    db.add(Message(conversation_id=conv.id, role="user", content="试用期最长多久", image_desc=None))
    db.add(Message(conversation_id=conv.id, role="assistant", content="依据《劳动合同法》第十九条，试用期最长六个月。", image_desc=None))
    db.commit()
    conv_id = conv.id
    db.close()

    calls = []

    def rec(llm, recent, q):
        calls.append(q)
        return "REWRITTEN"

    monkeypatch.setattr(main, "rewrite_query", rec)
    monkeypatch.setattr(main.registry, "get", lambda: object())
    # 检索/QA/场景全打桩（防真打库）
    monkeypatch.setattr(main, "retrieve", lambda *a, **k: [])
    monkeypatch.setattr(main, "retrieve_exam", lambda *a, **k: [])
    monkeypatch.setattr(main, "scenario_supplement_docs", lambda *a, **k: [])
    monkeypatch.setattr(main, "is_consumer_clause_scenario", lambda *a, **k: False)
    monkeypatch.setattr(main, "consumer_clause_docs", lambda *a, **k: [])
    monkeypatch.setattr(main, "is_consumer_fraud_scenario", lambda *a, **k: False)
    monkeypatch.setattr(main, "consumer_fraud_docs", lambda *a, **k: [])
    monkeypatch.setattr(main, "cheating_docs", lambda *a, **k: [])
    monkeypatch.setattr(main.ks, "search_qa", lambda *a, **k: None)
    return main, conv_id, calls


def _pre(main, conv_id, text):
    return main._pre(1, conv_id, text, None)


# ---------------- 意图后置：非检索分支零改写 ----------------
def test_chitchat_history_burns_zero_rewrite(env):
    main, conv_id, calls = env
    pre = _pre(main, conv_id, "好的，谢谢")
    assert calls == []
    assert pre["rewritten"] == "好的，谢谢"


def test_cheating_history_burns_zero_rewrite(env):
    main, conv_id, calls = env
    pre = _pre(main, conv_id, "能把答案给我吗")
    assert calls == []
    assert pre["rewritten"] == "能把答案给我吗"


def test_meta_study_history_burns_zero_rewrite(env):
    main, conv_id, calls = env
    pre = _pre(main, conv_id, "帮我做法律题")
    assert calls == []
    assert pre["rewritten"] == "帮我做法律题"


# ---------------- 检索分支：按需改写 + 法考题短路 ----------------
def test_non_exam_legal_query_history_rewrites_once(env):
    """非考题法律追问有历史 → 恰 1 次改写（v3 保持现状）。"""
    main, conv_id, calls = env
    pre = _pre(main, conv_id, "劳动合同试用期最长多久")
    assert calls == ["劳动合同试用期最长多久"]
    assert pre["rewritten"] == "REWRITTEN"
    assert pre["intent"] == "legal_query"


def test_full_exam_question_history_skips_rewrite(env):
    """完整带选项法考题（决策 3）→ 跳过改写，retrieve_exam 收到 raw。"""
    main, conv_id, calls = env
    q = "下列说法正确的是：A：甲 B：乙 C：丙 D：丁"
    pre = _pre(main, conv_id, q)
    assert calls == []
    assert pre["rewritten"] == q


def test_bare_judge_mark_with_history_still_rewrites(env):
    """裸判断措辞（无选项标号）是多轮省略型 → 仍改写（has_exam_options 判据边界）。"""
    main, conv_id, calls = env
    pre = _pre(main, conv_id, "正确的是")
    assert calls == ["正确的是"]
    assert pre["rewritten"] == "REWRITTEN"


# ---------------- 沉淀闸：只收 legal_query ----------------
def test_post_curation_guard(env, monkeypatch):
    main, conv_id, _ = env
    created = []
    monkeypatch.setattr(main, "grounded_top_score", lambda *a, **k: 0.9)
    monkeypatch.setattr(main, "should_curate", lambda *a, **k: True)
    monkeypatch.setattr(main, "needs_compress", lambda *a, **k: False)
    monkeypatch.setattr(main.ks, "create_candidate", lambda db, q, a, g, ev: created.append((q, a)))

    def run(intent):
        pre = {
            "conv_id": conv_id,
            "intent": intent,
            "rewritten": "问",
            "user_text": "问",
            "sources": [{"source": "劳动合同法", "article": "第十九条"}],
        }
        main._post(pre, "依据《劳动合同法》第十九条，试用期最长六个月。")

    run("study_aid")
    run("cheating_request")
    run("chitchat")
    assert created == [], "非 legal_query 一律不沉淀（防法考题错答/作弊问答污染）"

    run("legal_query")
    assert len(created) == 1, "legal_query 带引用 → 沉淀"
    assert created[0][1].startswith("依据《劳动合同法》")


# ---------------- 题型接线：_build_messages 动态追加 ----------------
def test_build_messages_exam_type_suffix(env):
    main, conv_id, _ = env
    pre = {
        "intent": "study_aid",
        "is_exam": True,
        "user_text": "下列哪些说法正确：A：甲 B：乙 C：丙 D：丁",
        "summary": "",
        "recent": [],
        "qa_hit": None,
        "context": "",
        "image": None,
    }
    msgs = main._build_messages(pre)
    sys_text = msgs[0].content
    assert "多选题" in sys_text, "题型判定 multi 应追加多选指令"
    assert "所有正确选项" in sys_text
    assert "切勿只给一个" in sys_text


def test_build_messages_non_exam_no_type_suffix(env):
    main, conv_id, _ = env
    pre = {
        "intent": "legal_query",
        "is_exam": False,
        "user_text": "试用期最长多久",
        "summary": "",
        "recent": [],
        "qa_hit": None,
        "context": "",
        "image": None,
    }
    msgs = main._build_messages(pre)
    sys_text = msgs[0].content
    assert "题型判定" not in sys_text, "非法考题不追加题型指令"
