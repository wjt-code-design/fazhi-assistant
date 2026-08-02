"""阶段3 测试：可观测/健康检查/契约（mock LLM，内存 DB 隔离，不调真实 LLM）。"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


@pytest.fixture
def client(monkeypatch):
    from sqlalchemy.pool import StaticPool

    import database
    import main
    import settings as _settings
    from models import Base

    # 既有 chat 测试只验证持久化/契约，关掉多模型路由走 legacy 流式（配合 make_chain mock）
    monkeypatch.setattr(_settings.settings, "feature_router", False)

    eng = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(eng)
    sm = sessionmaker(bind=eng, autoflush=False, autocommit=False)
    monkeypatch.setattr(database, "SessionLocal", sm)
    monkeypatch.setattr(main, "SessionLocal", sm)
    from fastapi.testclient import TestClient

    with TestClient(main.app) as c:
        yield c


def _login(client, username="user1"):
    client.post("/api/auth/register", json={"username": username, "password": "password123"})
    return client.post("/api/auth/login", json={"username": username, "password": "password123"}).json()["token"]


def test_healthz_components(client):
    r = client.get("/healthz")
    assert r.status_code == 200
    j = r.json()
    assert j["db"] is True and j["vector"] is True
    assert j["status"] == "ok"


def test_chat_streams_persists_and_request_id(client, monkeypatch):
    import main
    from database import SessionLocal
    from models import Conversation, Message

    class FakeChain:
        async def astream(self, messages):
            for p in ["假", "答案"]:
                yield p

    monkeypatch.setattr(main, "make_chain", lambda llm: FakeChain())
    tok = _login(client)
    headers = {"Authorization": f"Bearer {tok}"}

    with client.stream("POST", "/api/chat", json={"content": "试用期最长多久"}, headers=headers) as r:
        assert r.status_code == 200
        assert r.headers.get("x-request-id"), "响应应带 x-request-id"
        body = "".join(r.iter_text())

    import json as _json

    contents = []
    for line in body.splitlines():
        if line.startswith("data: ") and line[6:] != "[DONE]":
            try:
                contents.append(_json.loads(line[6:])["content"])
            except Exception:
                pass
    assert "".join(contents) == "假答案"
    assert "data: [DONE]" in body

    db = SessionLocal()
    try:
        assert db.query(Conversation).count() == 1
        assert db.query(Message).count() == 2  # user + assistant
    finally:
        db.close()


def test_admin_403_for_normal_user(client):
    tok = _login(client, username="user2")
    assert client.get("/api/admin/stats", headers={"Authorization": f"Bearer {tok}"}).status_code == 403


def test_admin_audit_records_action_and_forbids_user(client):
    from auth import hash_password
    from database import SessionLocal
    from models import User

    db = SessionLocal()
    try:
        db.add(User(username="adminx", password_hash=hash_password("password123"), role="admin"))
        db.commit()
    finally:
        db.close()

    tok = client.post("/api/auth/login", json={"username": "adminx", "password": "password123"}).json()["token"]
    headers = {"Authorization": f"Bearer {tok}"}

    cur = client.get("/api/admin/stats", headers=headers).json()["llm_model"]
    assert client.post("/api/admin/llm", json={"model": cur}, headers=headers).status_code == 200

    rows = client.get("/api/admin/audit", headers=headers).json()
    actions = [x["action"] for x in rows]
    assert "llm.switch" in actions
    assert rows[0]["admin"] == "adminx"

    # 非管理员禁止访问审计
    client.post("/api/auth/register", json={"username": "normuser", "password": "password123"})
    ntok = client.post("/api/auth/login", json={"username": "normuser", "password": "password123"}).json()["token"]
    assert client.get("/api/admin/audit", headers={"Authorization": f"Bearer {ntok}"}).status_code == 403


def test_feedback_down_creates_candidate_up_does_not(client):
    from auth import hash_password
    from database import SessionLocal
    from models import User

    db = SessionLocal()
    try:
        db.add(User(username="adminfb", password_hash=hash_password("password123"), role="admin"))
        db.commit()
    finally:
        db.close()

    client.post("/api/auth/register", json={"username": "fbuser", "password": "password123"})
    tok = client.post("/api/auth/login", json={"username": "fbuser", "password": "password123"}).json()["token"]
    headers = {"Authorization": f"Bearer {tok}"}
    atok = client.post("/api/auth/login", json={"username": "adminfb", "password": "password123"}).json()["token"]
    ah = {"Authorization": f"Bearer {atok}"}

    before = len(client.get("/api/admin/qa/candidates", params={"status": "pending"}, headers=ah).json())
    r = client.post(
        "/api/feedback",
        headers=headers,
        json={"question": "试用期多久", "answer": "错误的回答", "rating": "down", "correction": "应为六个月"},
    )
    assert r.status_code == 200
    after = client.get("/api/admin/qa/candidates", params={"status": "pending"}, headers=ah).json()
    assert len(after) == before + 1
    assert after[0]["answer"] == "应为六个月"

    b2 = len(client.get("/api/admin/qa/candidates", params={"status": "pending"}, headers=ah).json())
    assert (
        client.post("/api/feedback", headers=headers, json={"question": "x", "answer": "y", "rating": "up"}).status_code
        == 200
    )
    assert len(client.get("/api/admin/qa/candidates", params={"status": "pending"}, headers=ah).json()) == b2

    fbs = client.get("/api/admin/feedback", headers=ah).json()
    assert any(f["rating"] == "down" and f["correction"] == "应为六个月" for f in fbs)

    assert client.post("/api/feedback", json={"question": "a", "answer": "b", "rating": "up"}).status_code in (401, 403)
