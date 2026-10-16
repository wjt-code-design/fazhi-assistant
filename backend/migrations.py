"""轻量、幂等的 schema 迁移（SQLite）。

设计目标：在已有 app.db 上启动时，安全地"补列 + 建新表"，不丢旧数据。
企业阶段再上 Alembic。

- 新表：依赖 Base.metadata.create_all（幂等）。
- 已有表新增列：用 PRAGMA table_info 检测，缺则 ALTER TABLE ADD COLUMN。
  只有 `duplicate column name`（并发启动真幂等场景）被容忍，其余 SQLite 错误**照抛**——
  吞掉的后果是升级库悄悄少一列（`tests/test_migration_schema_parity.py` 钉这条）。
  注意 SQLite 的 ADD COLUMN 对默认值有限制，last_active_at 用无默认(NULL)，排序时用 COALESCE 兜底。
"""

from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from database import Base, engine

# (table, column, ddl_type, default_sql_or_None)
_COLUMN_MIGRATIONS = [
    ("conversations", "title", "VARCHAR(200)", "''"),
    ("conversations", "summary", "TEXT", "''"),
    ("conversations", "message_count", "INTEGER", "0"),
    ("conversations", "summary_upto", "INTEGER", "0"),
    ("conversations", "last_active_at", "DATETIME", None),
    ("messages", "image_desc", "TEXT", None),
    # T1（2026-09-16）：Agent 终稿消息关联 run（历史会话覆盖投影用）；无默认（NULL）
    ("messages", "agent_run_id", "VARCHAR(36)", None),
]


def _existing_columns(conn, table: str) -> set:
    try:
        rows = conn.execute(text(f"PRAGMA table_info({table})")).fetchall()
        return {r[1] for r in rows}
    except Exception:
        return set()


def run_migrations() -> None:
    # 确保模型已注册到 Base.metadata（调用方通常已 import models，这里兜底）
    import models  # noqa: F401

    # 1) 建新表（幂等）
    Base.metadata.create_all(bind=engine)

    # 2) 已有表补列（幂等）
    with engine.connect() as conn:
        for table, col, ddl, default in _COLUMN_MIGRATIONS:
            if col in _existing_columns(conn, table):
                continue
            stmt = f"ALTER TABLE {table} ADD COLUMN {col} {ddl}"
            if default is not None:
                stmt += f" DEFAULT {default}"
            try:
                conn.execute(text(stmt))
                conn.commit()
            except OperationalError as e:
                # 只容忍真·幂等那一类：并发启动时另一个进程已经加过这列。
                # 原先是 `except Exception` 一律 print 继续——可上面已经用 PRAGMA 判过"列已存在"，
                # 走到这里的绝大多数是**别的错**（表名打错、DDL 写错、锁冲突），
                # 吞掉的后果是升级库悄悄少一列，要到第一次读写才炸。失败必须响。
                if "duplicate column name" not in str(e).lower():
                    raise
                print(f"[migrations] skip {table}.{col}: {e}")
