"""轻量、幂等的 schema 迁移（SQLite）。

设计目标：在已有 app.db 上启动时，安全地"补列 + 建新表"，不丢旧数据。
企业阶段再上 Alembic。

- 新表：依赖 Base.metadata.create_all（幂等）。
- 已有表新增列：用 PRAGMA table_info 检测，缺则 ALTER TABLE ADD COLUMN。
  只有 `duplicate column name`（并发启动真幂等场景）被容忍，其余 SQLite 错误**照抛**——
  吞掉的后果是升级库悄悄少一列（`tests/test_migration_schema_parity.py` 钉这条）。
  注意 SQLite 的 ADD COLUMN 对默认值有限制，last_active_at 用无默认(NULL)，排序时用 COALESCE 兜底。
"""

import uuid

from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from database import Base, engine

# (table, column, ddl_type, default_sql_or_None)
_COLUMN_MIGRATIONS = [
    # R01（2026-10-20）：用户对外身份（JWT 主体）。**无默认** ⇒ 存量行先落 NULL，
    # 由 `_backfill_user_public_ids` 逐行补随机值（SQL 无法生成 UUID，且 NOT NULL 的
    # ADD COLUMN 在 SQLite 上要求常量默认值）。
    ("users", "public_id", "VARCHAR(36)", None),
    ("conversations", "title", "VARCHAR(200)", "''"),
    ("conversations", "summary", "TEXT", "''"),
    ("conversations", "message_count", "INTEGER", "0"),
    ("conversations", "summary_upto", "INTEGER", "0"),
    ("conversations", "last_active_at", "DATETIME", None),
    ("messages", "image_desc", "TEXT", None),
    # T1（2026-09-16）：Agent 终稿消息关联 run（历史会话覆盖投影用）；无默认（NULL）
    ("messages", "agent_run_id", "VARCHAR(36)", None),
    # W06-IMPL（2026-10-17，C03=形状 P）：`qa_candidates` 的资格六列。
    # 默认值逐字对应 P 的口径——存量行**先按"来源未知"隔离待判**（`approval_source='unknown'`），
    # 但不是 revoked：状态轴上它们仍是 ok，等 backfill 按审计行分类后才决定去留（删数据不可撤销，所以不删）。
    ("qa_candidates", "approval_source", "VARCHAR(32)", "'unknown'"),
    ("qa_candidates", "reviewed_by", "INTEGER", None),
    ("qa_candidates", "reviewed_at", "DATETIME", None),
    ("qa_candidates", "eligibility", "VARCHAR(16)", "'ok'"),
    ("qa_candidates", "eligibility_version", "INTEGER", "1"),
    ("qa_candidates", "vector_doc_id", "VARCHAR(64)", None),
    # W06-C（2026-10-18，§5.1）：来源包三列。**无默认(NULL)** ⇒ 旧行来源未知，
    # 绝不用 complete=true 空依赖批量洗白；内容/摘要/排序原样保留，只是多一列内部来源。
    ("messages", "qa_provenance", "TEXT", None),
    ("conversations", "summary_provenance", "TEXT", None),
    ("qa_candidates", "qa_provenance", "TEXT", None),
]

# 补索引清单（表, 列, 是否唯一）：名字固定成 `ix_<表>_<列>`，与 SQLAlchemy `index=True` 的默认命名同一个形状，
# 否则"新建库有的索引"和"升级库有的索引"会长成两副样子，而没人会去比。
# `users.public_id` 必须**唯一**（R01）：重复身份会让一枚令牌匹配到多行，随机碰撞概率虽低，
# 但身份唯一性是正确性属性、不该靠概率兜底。
_INDEX_MIGRATIONS = [
    ("qa_candidates", "vector_doc_id", False),
    ("users", "public_id", True),
]


def _existing_columns(conn, table: str) -> set:
    try:
        rows = conn.execute(text(f"PRAGMA table_info({table})")).fetchall()
        return {r[1] for r in rows}
    except Exception:
        return set()


def run_migrations(bind=None) -> None:
    # `bind` 形参是为**可测**加的：迁移逻辑过去只能对"模块级那台引擎"跑，
    # 于是"旧库升级后有没有长出索引"这类判据要么测不到，要么测在错误的库上（假绿）。
    # 默认值不变 ⇒ 生产调用点（database.init_db）一个字都不用改。
    target = engine if bind is None else bind
    # 确保模型已注册到 Base.metadata（调用方通常已 import models，这里兜底）
    import models  # noqa: F401

    # 1) 建新表（幂等）
    Base.metadata.create_all(bind=target)

    # 2) 已有表补列（幂等）
    with target.connect() as conn:
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

    # 2b) 存量用户补对外身份（幂等）：SQLite 的 ALTER 加不了动态默认值，故逐行补随机 UUID。
    # 先补值再建唯一索引（顺序错了会因 NULL 重复而建索引失败）。空表/新库无行 ⇒ 静默跳过。
    with target.connect() as conn:
        _backfill_user_public_ids(conn)

    # 3) 补索引（幂等）——**这一步不是可选优化**：`create_all` 只给"它新建的表"建索引，
    # 而现网的 `qa_candidates` 早就存在（列是 ALTER 补上来的）⇒ 模型上写了 index=True 也不会凭空长出索引。
    # 票 C20 形状①让读出口每次命中按 `vector_doc_id` 回查一次，缺索引就是每次命中全表扫。
    with target.connect() as conn:
        for table, col, unique in _INDEX_MIGRATIONS:
            existing = {r[1] for r in conn.execute(text(f"PRAGMA index_list({table})")).fetchall()}
            if f"ix_{table}_{col}" in existing:
                continue
            kind = "UNIQUE INDEX" if unique else "INDEX"
            conn.execute(text(f"CREATE {kind} IF NOT EXISTS ix_{table}_{col} ON {table} ({col})"))
            conn.commit()


def _backfill_user_public_ids(conn) -> None:
    """给 `users.public_id` 仍为空的存量行补随机身份（幂等，可重复启动）。

    只碰 `public_id IS NULL OR public_id = ''` 的行——已有的值绝不改写（改写等于把该用户
    在途的合法令牌一起作废）。
    """
    if "public_id" not in _existing_columns(conn, "users"):
        return
    rows = conn.execute(text("SELECT id FROM users WHERE public_id IS NULL OR public_id = ''")).fetchall()
    for (user_id,) in rows:
        conn.execute(
            text("UPDATE users SET public_id = :pid WHERE id = :uid"),
            {"pid": uuid.uuid4().hex, "uid": user_id},
        )
    if rows:
        conn.commit()
