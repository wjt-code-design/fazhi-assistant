"""F4 沉淀拦截集成用例（2026-10-27）：矛盾答案不得进 qa_candidates；正常答案必须进。"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import main
from models import Base, Conversation


def _prepare(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    monkeypatch.setattr(main, "SessionLocal", session_factory)
    with session_factory() as db:
        db.add(Conversation(id=1, user_id=1, title="contradiction", message_count=0))
        db.add(Conversation(id=2, user_id=1, title="clean", message_count=0))
        db.commit()
    monkeypatch.setattr(main, "citation_grounding", lambda *args, **kwargs: None)
    monkeypatch.setattr(main, "grounded_top_score", lambda rewritten: 0.95)
    monkeypatch.setattr(main, "should_curate", lambda grounded, answer: True)
    monkeypatch.setattr(main, "recent_messages", lambda db, conv_id: [])
    monkeypatch.setattr(main, "needs_compress", lambda conv, recent: False)
    calls = []
    monkeypatch.setattr(main.ks, "create_candidate", lambda *args, **kwargs: calls.append(args))
    return session_factory, calls


def _pre(conv_id: int) -> dict:
    return {
        "conv_id": conv_id,
        "intent": "legal_query",
        "user_text": "故意伤害致人重伤怎么判？",
        "rewritten": "故意伤害致人重伤怎么判？",
        "sources": [{"source": "刑法", "article": "第二百三十四条"}],
    }


def test_post_skips_curation_on_contradiction(monkeypatch):
    session_factory, calls = _prepare(monkeypatch)

    main._post(_pre(1), "依据《刑法》第二百三十四条，构成故意伤害罪。第二百三十四条未提供全文。")

    assert calls == [], "矛盾答案不得进 qa_candidates"
    with session_factory() as db:
        assert db.query(main.Message).count() == 1, "_post 必须已执行（消息落库）"


def test_post_curates_clean_answer(monkeypatch):
    session_factory, calls = _prepare(monkeypatch)

    main._post(_pre(2), "依据《刑法》第二百三十四条，故意伤害他人身体的，处三年以下有期徒刑、拘役或者管制。")

    assert len(calls) == 1, "正常答案应进 qa_candidates（对照用例）"
    with session_factory() as db:
        assert db.query(main.Message).count() == 1
