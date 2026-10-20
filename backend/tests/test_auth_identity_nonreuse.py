"""R01（2026-10-20）：用户对外身份不可复用，旧令牌失效。

**这条审查项的形状**：`User.id` 是自增整型主键、无防复用身份字段；JWT 主体 `sub=str(user.id)`。
SQLite 的 `INTEGER PRIMARY KEY` 是 rowid 别名、**不带 AUTOINCREMENT** ⇒ 删掉当前最大 id 的行后，
下一次插入会复用它。管理员硬删用户后，新注册者可能拿到同一个数字 id，于是**上一个用户还握着的
旧令牌**会被认证成新用户（越权）。修复：加随机不可复用 `public_id` 当 JWT 主体；旧令牌（sub 为
纯数字）在 `get_current_user` 里找不到对应行 ⇒ fail-closed 401。

三条腿成对：
1. `test_legacy_numeric_subject_token_is_rejected`——按**旧口径**签一枚 token（sub=数字 id）也必须被拒。
2. `test_token_subject_is_public_id_and_survives_numeric_id_reuse`——数字 id 被复用后，旧令牌不许
   认证成新用户（本条先断言复用真发生，否则测试失去对象）。
3. `test_legacy_users_table_backfills_public_id`——老库升级路径：补列 + 逐行补值 + 唯一索引。
"""

from __future__ import annotations

import os
import sqlite3
import time
from pathlib import Path

import jwt
import pytest

LEGACY_USERS_DDL = """
CREATE TABLE users (
    id INTEGER NOT NULL,
    username VARCHAR(64) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(16) NOT NULL,
    is_active BOOLEAN NOT NULL,
    created_at DATETIME,
    PRIMARY KEY (id),
    UNIQUE (username)
)
"""


@pytest.fixture
def client(monkeypatch):
    """内存 sqlite + 关路由；不碰宿主 app.db（与 test_auth_c_ownership_probes 同法）。"""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    import database
    import main
    import settings as _settings
    from models import Base

    monkeypatch.setattr(_settings.settings, "feature_router", False)
    eng = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(eng)
    sm = sessionmaker(bind=eng, autoflush=False, autocommit=False)
    monkeypatch.setattr(database, "SessionLocal", sm)
    monkeypatch.setattr(main, "SessionLocal", sm)
    from fastapi.testclient import TestClient

    with TestClient(main.app) as c:
        yield c


def _register(client, username: str) -> str:
    client.post("/api/auth/register", json={"username": username, "password": "password123"})
    return client.post("/api/auth/login", json={"username": username, "password": "password123"}).json()["token"]


def test_legacy_numeric_subject_token_is_rejected(client):
    """旧口径令牌（sub=数字 id，升级前签发的那种）必须 fail-closed，不许回退按 id 放行。"""
    client.post("/api/auth/register", json={"username": "r01_legacy", "password": "password123"})
    from database import SessionLocal
    from models import User

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == "r01_legacy").one()
        legacy = jwt.encode(
            {
                "sub": str(user.id),  # 旧口径：纯数字 id
                "username": user.username,
                "role": user.role,
                "exp": int(time.time()) + 3600,
            },
            os.environ["JWT_SECRET"],
            algorithm="HS256",
        )
    finally:
        db.close()

    r = client.get("/api/auth/me", headers={"Authorization": f"Bearer {legacy}"})
    assert r.status_code == 401, f"旧令牌（数字 sub）被放行了（实测 {r.status_code}）⇒ 复用面未关"


def test_token_subject_is_public_id_and_survives_numeric_id_reuse(client):
    """数字 id 被复用后，前一位用户的令牌不许认证成新用户。"""
    old_token = _register(client, "r01_first")
    from database import SessionLocal
    from models import User

    db = SessionLocal()
    try:
        first = db.query(User).filter(User.username == "r01_first").one()
        first_id = first.id
        assert first.public_id, "新建用户没有 public_id ⇒ 主体口径没接上"
        db.delete(first)
        db.commit()
    finally:
        db.close()

    # 新注册一名用户；SQLite 会复用被删掉的最大 id（不带 AUTOINCREMENT）——这是攻击前提。
    _register(client, "r01_second")
    db = SessionLocal()
    try:
        second = db.query(User).filter(User.username == "r01_second").one()
    finally:
        db.close()
    assert second.id == first_id, (
        f"数字 id 未被复用（first={first_id} second={second.id}）⇒ 本测试失去对象，"
        "要么轮换造数使之复用，要么承认此前提不成立而不能声称验证了复用面"
    )

    reused = client.get("/api/auth/me", headers={"Authorization": f"Bearer {old_token}"})
    assert reused.status_code == 401, f"旧令牌在 id 复用后认证成了新用户（实测 {reused.status_code}）⇒ R01 未修"
    assert second.username not in reused.text, "401 却把新用户身份带出去了"


def test_legacy_users_table_backfills_public_id(tmp_path, monkeypatch):
    """老库 users 表没有 public_id ⇒ 迁移后必须补列、逐行补值、建唯一索引，且 ORM 读得动。"""
    from sqlalchemy import create_engine

    import migrations as M
    import models  # noqa: F401  确保 ORM 已注册

    db_file: Path = tmp_path / "app.db"
    con = sqlite3.connect(db_file)
    con.execute(LEGACY_USERS_DDL)
    con.execute(
        "INSERT INTO users (id, username, password_hash, role, is_active, created_at)"
        " VALUES (1, 'legacy_admin', 'x', 'admin', 1, '2026-01-01 00:00:00')"
    )
    con.commit()
    con.close()

    engine = create_engine(f"sqlite:///{db_file}")
    monkeypatch.setattr(M, "engine", engine)
    M.run_migrations()
    M.run_migrations()  # 幂等：第二次不许改写已有值

    cols = {r[1] for r in sqlite3.connect(db_file).execute("PRAGMA table_info(users)")}
    assert "public_id" in cols, "老库升级后仍缺 public_id 列 ⇒ 新代码第一次读就炸"

    idx = {r[1]: r[2] for r in sqlite3.connect(db_file).execute("PRAGMA index_list(users)")}
    assert idx.get("ix_users_public_id") == 1, f"public_id 唯一索引缺失/不唯一：{idx}"

    Session = pytest.importorskip("sqlalchemy.orm").sessionmaker(bind=engine)
    db = Session()
    try:
        row = db.query(models.User).one()
        assert row.public_id and row.public_id != "legacy_admin", "存量行没补上随机身份"
        before = row.public_id
    finally:
        db.close()

    M.run_migrations()  # 再跑一次：已有值不许被改写
    db = Session()
    try:
        assert db.query(models.User).one().public_id == before, "重复迁移改写了已有身份 ⇒ 会作废在途合法令牌"
    finally:
        db.close()
