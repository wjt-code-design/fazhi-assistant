"""账号边界第 4 轮 B01–B03 的定向回归。

判据来源：docs/reviews/account-boundaries-readonly-review-round4.md。
- B01：字符长度不等于 UTF-8 字节长度；>72 字节必须在散列前被拒。
- B02：并发失败读改写必须原子，6 次并发后计数应为 6，下一次登录被锁。
- B03：未知用户名不落失败状态；过期记录会被回收；登录用户名有长度上限。
"""

from __future__ import annotations

import sys
import threading

import pytest
from pydantic import ValidationError

import main
from auth import hash_password
from schemas import LoginIn, RegisterIn

PASSWORD_72_BYTES = "密" * 24  # 24 × 3 = 72
PASSWORD_75_BYTES = "密" * 25  # 25 × 3 = 75


def _clear_login_failures() -> None:
    with main._LOGIN_FAILURES_LOCK:
        main._LOGIN_FAILURES.clear()


def test_b01_72_byte_password_is_accepted_and_hashes() -> None:
    body = RegisterIn(username="boundary72", password=PASSWORD_72_BYTES)
    assert len(body.password.encode("utf-8")) == 72
    assert hash_password(body.password)


@pytest.mark.parametrize("password", [PASSWORD_72_BYTES, "🔒" * 18, "a" * 64])
def test_b01_72_byte_and_ascii_passwords_are_accepted(password: str) -> None:
    """24 汉字 / 18 个四字节 emoji / 64 ASCII 都是 72 字节边界内的合法密码。"""
    body = RegisterIn(username="boundary72x", password=password)
    assert len(body.password.encode("utf-8")) <= 72
    assert hash_password(body.password)


@pytest.mark.parametrize("password", [PASSWORD_75_BYTES, "🔒" * 19])
def test_b01_over_72_byte_passwords_are_rejected(password: str) -> None:
    with pytest.raises(ValidationError):
        RegisterIn(username="boundary75", password=password)


def test_b01_hash_password_rejects_over_72_bytes() -> None:
    """CLI（seed/reset）绕过 schema 时也要得到可读错误，而不是半个用户。"""
    with pytest.raises(ValueError):
        hash_password(PASSWORD_75_BYTES)


def test_b01_register_returns_422_not_500_for_over_72_bytes() -> None:
    """原缺陷是接口 500；schema 层拒绝后必须是可理解的输入错误。"""
    from fastapi.testclient import TestClient

    with TestClient(main.app) as client:
        res = client.post("/api/auth/register", json={"username": "too-long-pwd", "password": PASSWORD_75_BYTES})
    assert res.status_code == 422


def test_b02_concurrent_failures_are_not_lost() -> None:
    """固定并发交错：无锁的 get→+1→set 会丢更新；持锁后计数必须精确。"""
    _clear_login_failures()
    threads_n = 16
    per_thread = 100
    barrier = threading.Barrier(threads_n)
    old_interval = sys.getswitchinterval()
    sys.setswitchinterval(1e-6)

    def worker() -> None:
        barrier.wait()
        for _ in range(per_thread):
            main._record_login_failure("alice", 1000.0)

    try:
        threads = [threading.Thread(target=worker) for _ in range(threads_n)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
    finally:
        sys.setswitchinterval(old_interval)

    assert main._LOGIN_FAILURES["alice"] == (threads_n * per_thread, 1000.0)
    assert main._login_locked("alice", 1000.0) is True


def test_b02_success_clears_failures() -> None:
    _clear_login_failures()
    for _ in range(5):
        main._record_login_failure("bob", 1000.0)
    assert main._login_locked("bob", 1000.0) is True
    main._clear_login_failures("bob")
    assert main._login_locked("bob", 1000.0) is False


def test_b02_lock_expires_and_purge_removes_entry() -> None:
    _clear_login_failures()
    for _ in range(5):
        main._record_login_failure("carol", 1000.0)
    assert main._login_locked("carol", 1000.0 + main._LOGIN_LOCK_SECONDS - 1) is True
    assert main._login_locked("carol", 1000.0 + main._LOGIN_LOCK_SECONDS) is False
    with main._LOGIN_FAILURES_LOCK:
        main._purge_expired_login_failures(1000.0 + main._LOGIN_LOCK_SECONDS)
    assert "carol" not in main._LOGIN_FAILURES


@pytest.mark.parametrize("previous_failures", [4, 5])
def test_b02_expired_failures_start_a_new_lockout_window(previous_failures: int) -> None:
    _clear_login_failures()
    for _ in range(previous_failures):
        main._record_login_failure("expired", 1000.0)
    now = 1000.0 + main._LOGIN_LOCK_SECONDS
    assert main._login_locked("expired", now) is False

    main._record_login_failure("expired", now)
    assert main._LOGIN_FAILURES["expired"] == (1, now)
    assert main._login_locked("expired", now) is False
    for _ in range(main._LOGIN_MAX_ATTEMPTS - 1):
        main._record_login_failure("expired", now)
    assert main._login_locked("expired", now) is True
    assert main._login_locked("expired", now + main._LOGIN_LOCK_SECONDS) is False


def test_b03_login_username_is_length_capped() -> None:
    with pytest.raises(ValidationError):
        LoginIn(username="u" * 33, password="whatever123")


def test_b03_unknown_username_does_not_create_failure_state() -> None:
    """未知用户名的随机尝试不落状态；正常账号的锁定不受清理策略影响。"""
    _clear_login_failures()
    from fastapi.testclient import TestClient

    with TestClient(main.app) as client:
        for _ in range(5):
            res = client.post("/api/auth/login", json={"username": "no-such-user-xyz", "password": "wrongpass123"})
            assert res.status_code == 401
    assert "no-such-user-xyz" not in main._LOGIN_FAILURES


def test_b03_purge_keeps_active_lock() -> None:
    _clear_login_failures()
    main._record_login_failure("dave", 1000.0)
    main._record_login_failure("old", 1.0)
    with main._LOGIN_FAILURES_LOCK:
        main._purge_expired_login_failures(1000.0)
    assert "dave" in main._LOGIN_FAILURES
    assert "old" not in main._LOGIN_FAILURES
