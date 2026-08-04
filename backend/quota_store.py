"""模型配额运行态持久化（独立 SQLite 文件，不碰 ORM 迁移）。

记录「运行期间累计扣减」runtime_used；真实已用 = 配置 initial_used + runtime_used。
重启从本文件恢复 runtime_used，不丢（满足"用完即止不重置"）。

纯 stdlib sqlite3；写频低（每次回答一次），每次操作短连接 + WAL，简单线程安全。
"""
import os
import sqlite3
import threading

HERE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.getenv("QUOTA_DB", os.path.join(HERE, "..", "data", "quota_used.sqlite"))

_lock = threading.Lock()
_inited = False


def _connect() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    con = sqlite3.connect(DB_PATH, timeout=10)
    con.execute("PRAGMA journal_mode=WAL")
    return con


def _ensure() -> None:
    global _inited
    if _inited:
        return
    with _lock:
        if _inited:
            return
        con = _connect()
        try:
            con.execute("CREATE TABLE IF NOT EXISTS quota (key TEXT PRIMARY KEY, used INTEGER NOT NULL)")
            con.commit()
        finally:
            con.close()
        _inited = True


def get_used(key: str) -> int:
    """读取某模型运行期累计扣减；不存在返回 0。"""
    _ensure()
    con = _connect()
    try:
        row = con.execute("SELECT used FROM quota WHERE key=?", (key,)).fetchone()
        return int(row[0]) if row else 0
    finally:
        con.close()


def record_delta(key: str, delta: int) -> int:
    """累加扣减 delta（>=0），返回新的累计值。"""
    if delta <= 0:
        return get_used(key)
    _ensure()
    with _lock:
        con = _connect()
        try:
            cur = con.execute("SELECT used FROM quota WHERE key=?", (key,))
            row = cur.fetchone()
            new = (int(row[0]) if row else 0) + int(delta)
            con.execute(
                "INSERT INTO quota(key, used) VALUES(?, ?) ON CONFLICT(key) DO UPDATE SET used=excluded.used",
                (key, new),
            )
            con.commit()
            return new
        finally:
            con.close()


def used_map() -> dict[str, int]:
    """全部 key → 累计扣减（管理员审计/调试）。"""
    _ensure()
    con = _connect()
    try:
        return {k: int(v) for k, v in con.execute("SELECT key, used FROM quota")}
    finally:
        con.close()


_INIT_PREFIX = "init:"  # 校准行前缀（初始用量覆盖，管理员从控制台读数后写入）


def set_initial(key: str, initial_used: int) -> None:
    """校准持久化：记录某模型校准后的初始用量（quota_left = total - initial - runtime）。"""
    _ensure()
    with _lock:
        con = _connect()
        try:
            con.execute(
                "INSERT INTO quota(key, used) VALUES(?, ?) ON CONFLICT(key) DO UPDATE SET used=excluded.used",
                (_INIT_PREFIX + key, max(0, int(initial_used))),
            )
            con.commit()
        finally:
            con.close()


def initial_override(key: str) -> int | None:
    """读取某模型校准后的初始用量覆盖；无 → None。"""
    _ensure()
    con = _connect()
    try:
        row = con.execute("SELECT used FROM quota WHERE key=?", (_INIT_PREFIX + key,)).fetchone()
        return int(row[0]) if row else None
    finally:
        con.close()


def reset(key: str | None = None) -> None:
    """测试/重置用：清空某 key 或全部运行期累计。"""
    _ensure()
    with _lock:
        con = _connect()
        try:
            if key:
                con.execute("DELETE FROM quota WHERE key=?", (key,))
            else:
                con.execute("DELETE FROM quota")
            con.commit()
        finally:
            con.close()
