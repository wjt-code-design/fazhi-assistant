"""引用卡快照：真实 HTTP 鉴权边界 + 隔离数据库，无向量库/模型调用。"""

from types import SimpleNamespace

from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

import main
from auth import get_current_user
from database import get_db
from models import Message
from tests.test_legal_workflow_chat_integration import _records


def test_run_snapshot_owned_and_not_current(db, monkeypatch):
    from langchain_core.documents import Document

    user, conversation, run, state, _ = _records(db)
    monkeypatch.setattr(main, "SessionLocal", sessionmaker(bind=db.get_bind()))
    monkeypatch.setattr(
        main,
        "exact_article_lookup",
        lambda *a, **kw: [Document(page_content="CURRENT-VERSION-NOT-THE-SNAPSHOT", metadata={"source": "民法典"})],
    )
    main.app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=user.id)
    main.app.dependency_overrides[get_db] = lambda: db
    db.add(Message(conversation_id=conversation.id, role="assistant", content="旧答复", agent_run_id=run.id))
    db.commit()
    client = TestClient(main.app)
    params = {"source": "民法典", "article": "第675条", "run_id": run.id}
    try:
        response = client.get("/api/law", params=params)
        assert response.status_code == 200
        assert response.json()["content"] == state.evidence[0].snippet
        assert response.json()["is_snapshot"] is True
        assert response.json()["law_as_of"] == run.law_as_of.isoformat()
        history = client.get(f"/api/conversations/{conversation.id}")
        assert history.status_code == 200
        assert history.json()["messages"][0]["agent_run_id"] == run.id
        assert client.get("/api/law", params={**params, "article": "第188条"}).status_code == 404
        assert client.get("/api/law", params={**params, "run_id": "missing"}).status_code == 404
        main.app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=user.id + 999)
        assert client.get("/api/law", params=params).status_code == 404
    finally:
        client.close()
        main.app.dependency_overrides.clear()


def test_legacy_lookup_still_uses_current_index(monkeypatch):
    from langchain_core.documents import Document

    monkeypatch.setattr(
        main,
        "exact_article_lookup",
        lambda *a, **kw: [
            Document(page_content="当前条文", metadata={"source": "民法典", "article": "第六百七十五条"})
        ],
    )
    main.app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=123)
    client = TestClient(main.app)
    try:
        response = client.get("/api/law", params={"source": "民法典", "article": "第675条"})
        assert response.status_code == 200
        assert response.json()["content"] == "当前条文"
        assert not response.json().get("is_snapshot")
    finally:
        client.close()
        main.app.dependency_overrides.clear()
