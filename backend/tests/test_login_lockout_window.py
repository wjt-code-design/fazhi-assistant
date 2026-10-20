"""R04（2026-10-20）：登录失败锁定改为滚动窗口，窗口过期后新失败能**重新**锁定。

**这条审查项的形状**：旧实现把每次失败记成 `(cnt, ts if cnt > 0 else now)`——`ts` 恒为**首次**
失败时刻，判据 `now < ts + 300`。后果：锁定窗口过期后 `cnt` 仍是 ≥ 上限，但 `ts` 不再前移，
后续失败既不加锁也永不重置，账号**永远不再锁定**（直到一次成功登录清记录）⇒ 爆破防护在窗口
过后失效。修复：记**窗口内失败时刻列表**（滚动窗口），锁定时长为最近窗口内的失败数是否达到上限。

两条腿成对：
1. `test_login_relocks_after_lock_window_expires`——黑盒驱动真实登录路由：首窗 5 次失败后锁定；
   推进 301 秒后窗口清空、再次累计 5 次失败必须**重新**锁定（旧实现此处恒 401 ⇒ 红）。
2. `test_recent_login_failures_prunes_only_stale_entries`——纯函数语义（窗口边界）。
"""

from __future__ import annotations

import time as _real_time
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

import main

T0 = 1_700_000_000.0


@pytest.fixture
def client(monkeypatch):
    """内存 sqlite + 关路由；不碰宿主 app.db（与 R01 测试同法）。"""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    import database
    import settings as _settings
    from models import Base

    monkeypatch.setattr(_settings.settings, "feature_router", False)
    eng = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(eng)
    sm = sessionmaker(bind=eng, autoflush=False, autocommit=False)
    monkeypatch.setattr(database, "SessionLocal", sm)
    monkeypatch.setattr(main, "SessionLocal", sm)

    main._LOGIN_FAILURES.clear()  # 模块级全局跨测试残留，必须清
    with TestClient(main.app) as c:
        yield c
    main._LOGIN_FAILURES.clear()


@pytest.fixture
def clock(monkeypatch):
    """把 main 命名空间里的 time 换成可控时钟；monotonic/perf_counter 仍委托真实模块（启动期用）。"""
    holder = [T0]
    monkeypatch.setattr(
        main,
        "time",
        SimpleNamespace(
            time=lambda: holder[0],
            monotonic=_real_time.monotonic,
            perf_counter=_real_time.perf_counter,
        ),
    )
    return holder


def _login(client, username: str, password: str) -> int:
    return client.post("/api/auth/login", json={"username": username, "password": password}).status_code


def test_login_relocks_after_lock_window_expires(client, clock):
    client.post("/api/auth/register", json={"username": "r04_user", "password": "password123"})

    # 第一扇窗：连续 5 次错误口令 ⇒ 每次 401；第 6 次在同一窗内 ⇒ 锁定 429。
    first = [_login(client, "r04_user", "wrong-pass") for _ in range(5)]
    assert first == [401] * 5, f"前 5 次失败应为 401，实测 {first}"
    assert _login(client, "r04_user", "wrong-pass") == 429, "首窗内 5 次失败后未锁定"

    # 推进 301 秒：窗口内旧失败全部过期 ⇒ 解锁；再累计 5 次失败后必须**重新**锁定。
    clock[0] = T0 + 301
    second = [_login(client, "r04_user", "wrong-pass") for _ in range(5)]
    assert second == [401] * 5, f"窗口过期后应重新累计（401×5），实测 {second}"
    assert _login(client, "r04_user", "wrong-pass") == 429, (
        "窗口过期后新失败未重新锁定 ⇒ 爆破防护在窗口过后失效（R04 未修）"
    )


def test_recent_login_failures_prunes_only_stale_entries():
    now = T0 + 400
    kept = main._recent_login_failures([T0, T0 + 100, T0 + 200, T0 + 500], now)
    # cutoff = now - 300 = T0+100；严格大于 ⇒ T0 与 T0+100（恰落界）被丢，保留 T0+200、T0+500。
    assert kept == [T0 + 200, T0 + 500], f"窗口裁剪口径错误：{kept}"
