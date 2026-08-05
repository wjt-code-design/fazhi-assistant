"""chat/file 文件→文本端点测试（纯解析，内存 DB 隔离，零 LLM 零 BGE）。"""
import pytest


@pytest.fixture
def client(monkeypatch):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    import database
    import main
    from models import Base

    eng = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(eng)
    sm = sessionmaker(bind=eng, autoflush=False, autocommit=False)
    monkeypatch.setattr(database, "SessionLocal", sm)
    monkeypatch.setattr(main, "SessionLocal", sm)
    from fastapi.testclient import TestClient

    with TestClient(main.app) as c:
        yield c


def _login(client):
    client.post("/api/auth/register", json={"username": "user1", "password": "password123"})
    return client.post("/api/auth/login", json={"username": "user1", "password": "password123"}).json()["token"]


def test_upload_txt_parses(client):
    tok = _login(client)
    r = client.post(
        "/api/chat/file",
        headers={"Authorization": f"Bearer {tok}"},
        files={"file": ("租赁合同.txt", "房屋租赁合同\n第一条 租金2000元。".encode())},
    )
    assert r.status_code == 200
    j = r.json()
    assert j["ext"] == ".txt"
    assert "房屋租赁合同" in j["text"]
    assert j["chars"] > 0
    assert j["truncated"] is False


def test_upload_unsupported_ext_400(client):
    tok = _login(client)
    r = client.post(
        "/api/chat/file",
        headers={"Authorization": f"Bearer {tok}"},
        files={"file": ("evil.exe", b"MZ")},
    )
    assert r.status_code == 400


def test_upload_truncated_over_limit(client):
    tok = _login(client)
    big = "合同" * 12001  # 超过 contract_max_chars=12000
    r = client.post(
        "/api/chat/file",
        headers={"Authorization": f"Bearer {tok}"},
        files={"file": ("long.txt", big.encode("utf-8"))},
    )
    assert r.status_code == 200
    j = r.json()
    assert j["truncated"] is True
    assert len(j["text"]) <= 12000


def test_upload_requires_auth(client):
    r = client.post("/api/chat/file", files={"file": ("a.txt", b"hi")})
    assert r.status_code == 401


# ---------------- analysis_runs 审计记录 ----------------
def test_record_analysis_writes_row(client):
    import main
    from database import SessionLocal
    from models import AnalysisRun

    main._record_analysis(1, 2, "text", 3, 7, "高", False, 999)
    db = SessionLocal()
    try:
        row = db.query(AnalysisRun).filter_by(conversation_id=2).first()
        assert row is not None
        assert row.source_type == "text"
        assert row.clause_count == 3 and row.article_count == 7
        assert row.risk_level == "高"
        assert row.duration_ms == 999
    finally:
        db.close()


def test_analysis_runs_admin_endpoint(client):
    from auth import hash_password
    from database import SessionLocal
    from models import AnalysisRun, User

    db = SessionLocal()
    db.add(User(username="adminrun", password_hash=hash_password("password123"), role="admin"))
    db.commit()
    db.close()
    tok = client.post(
        "/api/auth/login", json={"username": "adminrun", "password": "password123"}
    ).json()["token"]
    db = SessionLocal()
    db.add(
        AnalysisRun(
            user_id=None, conversation_id=None, source_type="image",
            clause_count=5, article_count=13, risk_level="中", truncated=False, duration_ms=1234,
        )
    )
    db.commit()
    db.close()
    r = client.get("/api/admin/analysis-runs?limit=10", headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 200
    rows = r.json()
    assert len(rows) >= 1
    top = rows[0]
    assert top["source_type"] == "image"
    assert top["clause_count"] == 5 and top["article_count"] == 13
    assert top["risk_level"] == "中"


def test_analysis_runs_requires_admin(client):
    tok = _login(client)  # 普通用户
    r = client.get("/api/admin/analysis-runs", headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 403
