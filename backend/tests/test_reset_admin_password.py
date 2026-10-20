"""D-35(a) / B-44：管理员口令重置入口。

钉四件事：口令不走 argv、不回落到 .env 的旧值、默认预览不写库、改密落审计且不外泄口令。
最后一条 `test_reset_does_not_revoke_already_issued_token` 钉的是**限制**本身：
改口令不会作废已签发的 JWT ⇒ 只重置口令不足以收口，必须另换 JWT_SECRET。
"""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from auth import PUBLIC_DEFAULT_PASSWORD as PUBLIC_DEFAULT

BACKEND = Path(__file__).resolve().parents[1]
SCRIPT_PATH = BACKEND / "scripts" / "reset_admin_password.py"

OLD_PASSWORD = "old-value-being-retired"
NEW_PASSWORD = "new-value-after-reset"
# PUBLIC_DEFAULT 与产品判据同源（独立复核 B 路 2026-10-16 抓到这里原本是第三份手抄拷贝）。
# "它仍然是仓库里泄漏的那个值"由
# test_admin_credential_guards.py::test_public_default_constant_is_the_known_leaked_value 钉住。

_counter = iter(range(1, 10_000))


def _name(prefix: str) -> str:
    return f"{prefix}-{next(_counter)}"


def _load_script():
    spec = importlib.util.spec_from_file_location("reset_admin_password_under_test", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def script():
    from database import init_db

    init_db()
    return _load_script()


def _create_user(username: str, password: str, *, role: str = "admin", is_active: bool = True) -> None:
    from auth import hash_password
    from database import SessionLocal
    from models import User

    db = SessionLocal()
    try:
        db.add(User(username=username, password_hash=hash_password(password), role=role, is_active=is_active))
        db.commit()
    finally:
        db.close()


def _snapshot(username: str) -> dict:
    """纯数据快照：避免会话关闭后取属性踩 DetachedInstanceError。"""
    from database import SessionLocal
    from models import User

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == username).first()
        if user is None:
            return {}
        return {
            "id": user.id,
            "username": user.username,
            "password_hash": user.password_hash,
            "role": user.role,
            "is_active": user.is_active,
        }
    finally:
        db.close()


def _audit_rows(action: str, *, username: str | None = None) -> list[dict]:
    """按用户名收窄：临时库在同进程跨用例共享，不收窄会把别人的审计读成自己的。"""
    from database import SessionLocal
    from models import AuditLog

    db = SessionLocal()
    try:
        query = db.query(AuditLog).filter(AuditLog.action == action)
        if username is not None:
            query = query.filter(AuditLog.target == username)
        return [
            {"admin_id": row.admin_id, "action": row.action, "target": row.target, "detail": row.detail}
            for row in query.all()
        ]
    finally:
        db.close()


def _count_users() -> int:
    from database import SessionLocal
    from models import User

    db = SessionLocal()
    try:
        return db.query(User).count()
    finally:
        db.close()


def _invoke(script, argv, passwords, monkeypatch):
    """跑 CLI：口令只从 getpass 进（生产里不回显），其余参数走 argv。"""
    answers = list(passwords)
    prompts: list[str] = []

    def fake_getpass(prompt="", *args, **kwargs):
        prompts.append(str(prompt))
        if not answers:
            raise AssertionError("getpass called more times than the test supplied passwords")
        return answers.pop(0)

    monkeypatch.setattr(script.getpass, "getpass", fake_getpass)
    try:
        code = script.main(argv)
    except SystemExit as exc:  # argparse 自身的报错路径
        code = exc.code
    return (0 if code is None else code), prompts


def test_importing_script_does_not_repoint_the_database():
    """脚本 import 期会 load_dotenv()；conftest 已无条件固定 DATABASE_URL ⇒ 真实库指不到。

    这条是本文件其余测试能安全 import 被测脚本的前置闸门：conftest 若哪天改成
    setdefault，真实 backend/app.db 就会被测试进程接上，这条先红。
    """
    _load_script()
    from database import DB_URL

    assert DB_URL == os.environ["DATABASE_URL"]
    assert "app.db" not in DB_URL


def test_argv_cannot_carry_the_password(script, monkeypatch):
    name = _name("argv-user")
    _create_user(name, OLD_PASSWORD)
    before = _snapshot(name)["password_hash"]

    code, _ = _invoke(script, ["--username", name, "--password", NEW_PASSWORD], [], monkeypatch)

    assert code != 0
    assert _snapshot(name)["password_hash"] == before


def test_env_admin_password_is_not_applied_as_the_new_value(script, monkeypatch):
    """退役中的旧值可能还留在 backend/.env：脚本不得拿它当新密码写回库里。"""
    name = _name("env-user")
    _create_user(name, OLD_PASSWORD)
    monkeypatch.setenv("ADMIN_PASSWORD", OLD_PASSWORD)

    code, _ = _invoke(script, ["--username", name, "--write"], [NEW_PASSWORD, NEW_PASSWORD], monkeypatch)

    assert code == 0
    from auth import verify_password

    stored = _snapshot(name)["password_hash"]
    assert verify_password(NEW_PASSWORD, stored)
    assert not verify_password(OLD_PASSWORD, stored)


def test_preview_writes_nothing(script, monkeypatch):
    name = _name("preview-user")
    _create_user(name, OLD_PASSWORD)
    before = _snapshot(name)["password_hash"]

    code, _ = _invoke(script, ["--username", name], [NEW_PASSWORD, NEW_PASSWORD], monkeypatch)

    assert code == 0
    assert _snapshot(name)["password_hash"] == before
    assert _audit_rows("admin.password_reset", username=name) == []


def test_write_resets_and_keeps_role_and_active_flag(script, monkeypatch, capsys):
    name = _name("write-user")
    _create_user(name, OLD_PASSWORD, role="admin", is_active=True)

    code, prompts = _invoke(script, ["--username", name, "--write"], [NEW_PASSWORD, NEW_PASSWORD], monkeypatch)

    assert code == 0
    snap = _snapshot(name)
    from auth import verify_password

    assert verify_password(NEW_PASSWORD, snap["password_hash"])
    assert not verify_password(OLD_PASSWORD, snap["password_hash"])
    assert snap["role"] == "admin"
    assert snap["is_active"] is True

    rows = _audit_rows("admin.password_reset", username=name)
    assert len(rows) == 1
    assert rows[0]["admin_id"] == snap["id"]

    printed = "".join([capsys.readouterr().out, *prompts])
    assert NEW_PASSWORD not in printed
    assert OLD_PASSWORD not in printed
    assert snap["password_hash"] not in printed


def test_unknown_username_refuses_and_creates_no_user(script, monkeypatch):
    missing = _name("ghost-user")
    before = _count_users()

    code, _ = _invoke(script, ["--username", missing, "--write"], [NEW_PASSWORD, NEW_PASSWORD], monkeypatch)

    assert code != 0
    assert _count_users() == before


@pytest.mark.parametrize("rejected", ["", PUBLIC_DEFAULT])
def test_empty_and_public_default_password_refused(script, monkeypatch, rejected):
    name = _name("weak-user")
    _create_user(name, OLD_PASSWORD)
    before = _snapshot(name)["password_hash"]

    code, _ = _invoke(script, ["--username", name, "--write"], [rejected, rejected], monkeypatch)

    assert code != 0
    assert _snapshot(name)["password_hash"] == before


# C05/W09-E 续（2026-10-20 独立复核主审抓出的 Medium 项）：加宽判据必须同样覆盖**重置路径**。
@pytest.mark.parametrize("rejected", ["change_me", " Change_Me ", "CHANGEME", "password", "123456"])
def test_public_placeholder_passwords_refused(script, monkeypatch, rejected):
    """重置入口与 `seed_admin.py` 共用 `auth.is_public_default_password` 的加宽集合。

    先前实现只比 `auth.PUBLIC_DEFAULT_PASSWORD` 一个值 ⇒ `change_me`/`password`/`123456`
    仍能被 CLI「重置」回管理员账户，与 `auth.py`/`seed_admin.py` 的单一真源承诺相矛盾。
    """
    name = _name("placeholder-user")
    _create_user(name, OLD_PASSWORD)
    before = _snapshot(name)["password_hash"]

    code, _ = _invoke(script, ["--username", name, "--write"], [rejected, rejected], monkeypatch)

    assert code != 0
    assert _snapshot(name)["password_hash"] == before


def test_mismatched_confirmation_does_not_write(script, monkeypatch):
    name = _name("typo-user")
    _create_user(name, OLD_PASSWORD)
    before = _snapshot(name)["password_hash"]

    code, _ = _invoke(script, ["--username", name, "--write"], [NEW_PASSWORD, NEW_PASSWORD + "x"], monkeypatch)

    assert code != 0
    assert _snapshot(name)["password_hash"] == before


def test_reset_does_not_revoke_already_issued_token(script, monkeypatch):
    """限制本身钉成判据：改口令后**现役认证函数**仍放行旧 token ⇒ 收口必须同换 JWT_SECRET。"""
    from fastapi.security import HTTPAuthorizationCredentials

    from auth import create_token, get_current_user
    from database import SessionLocal
    from models import User

    name = _name("token-user")
    _create_user(name, OLD_PASSWORD)
    db = SessionLocal()
    try:
        row = db.query(User).filter(User.username == name).one()
        user_id = row.id
        # R01：令牌主体改用 public_id（随机不可复用身份）⇒ 造令牌的替身对象必须带该属性。
        token = create_token(SimpleNamespace(id=row.id, public_id=row.public_id, username=row.username, role=row.role))
    finally:
        db.close()

    code, _ = _invoke(script, ["--username", name, "--write"], [NEW_PASSWORD, NEW_PASSWORD], monkeypatch)
    assert code == 0

    db = SessionLocal()
    try:
        resolved = get_current_user(HTTPAuthorizationCredentials(scheme="Bearer", credentials=token), db)
    finally:
        db.close()
    assert resolved.id == user_id
