"""**老库升级**路径的判据：模型加了列，但 `_COLUMN_MIGRATIONS` 没补 ⇒ 第一次读就炸。

为什么单独立一只文件（不并进 `test_migration_schema_parity.py`）：那只钉的是**反方向**
（"清单里的每一列都得是模型认识的列"）。它咬不到真发生事故的那个方向——
**模型有新列、清单里却没有**。2026-10-17 W06 给 `QaCandidate` 加了 6 列时，
`test_migration_schema_parity` 六条全绿，而真实 `backend/app.db` 的 `qa_candidates`
现量只有 7 列（`id/question/answer/grounded_score/evidence/status/created_at`，759 行）：
新代码第一次 `db.get(QaCandidate, ...)` 就会在缺列上抛 OperationalError。
⇒ 恒不命中的判据比没有判据更危险，这里补的正是缺的那半条。

两条腿成对：
① `test_legacy_qa_candidates_upgrade_gains_the_eligibility_columns`——按现役库的真实形状建一只老库，
   跑 `run_migrations()`，然后**真的按 ORM 读一遍**（红的时候是 OperationalError）。
② `test_canary_directional_ruler_fires_when_a_model_column_has_no_migration`——证明①那把尺子会红：
   临时从清单里抽掉一条，判据必须变红（否则①也可能只是恒真）。
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from sqlalchemy import create_engine

import migrations as M
import models  # noqa: F401  确保 ORM 已注册到 Base.metadata
from database import Base

# 现役库现量（只读 PRAGMA 抄下来的形状，不是想象）：老库里 qa_candidates 就这 7 列
LEGACY_QA_DDL = """
CREATE TABLE qa_candidates (
    id INTEGER NOT NULL,
    question TEXT NOT NULL,
    answer TEXT NOT NULL,
    grounded_score FLOAT,
    evidence TEXT,
    status VARCHAR(16),
    created_at DATETIME,
    PRIMARY KEY (id)
)
"""
LEGACY_QA_COLUMNS = {"id", "question", "answer", "grounded_score", "evidence", "status", "created_at"}
NEW_QA_COLUMNS = {
    "approval_source",
    "reviewed_by",
    "reviewed_at",
    "eligibility",
    "eligibility_version",
    "vector_doc_id",
}


def _make_legacy_db(path: Path) -> sqlite3.Connection:
    con = sqlite3.connect(path)
    con.execute(LEGACY_QA_DDL)
    con.execute(
        "INSERT INTO qa_candidates (id, question, answer, grounded_score, evidence, status, created_at)"
        " VALUES (1, '老问题', '老答案', 0.95, '[]', 'approved', '2026-09-21 02:06:00')"
    )
    con.commit()
    return con


def test_legacy_qa_candidates_upgrade_gains_the_eligibility_columns(tmp_path, monkeypatch):
    """老库跑完迁移 ⇒ 新增的资格列必须在，且 ORM 真读得动（不是只查 PRAGMA 看个形状）。"""
    db_file = tmp_path / "app.db"
    con = _make_legacy_db(db_file)
    con.close()
    engine = create_engine(f"sqlite:///{db_file}")
    monkeypatch.setattr(M, "engine", engine)

    M.run_migrations()

    cols = {r[1] for r in sqlite3.connect(db_file).execute("PRAGMA table_info(qa_candidates)")}
    assert NEW_QA_COLUMNS <= cols, f"老库升级后仍缺列：{sorted(NEW_QA_COLUMNS - cols)} ⇒ 新代码第一次读就炸"
    # 存量行的默认值必须是"可服务但来源未知"的 P 口径，不能默认成 human / 也不能默认成 revoked
    Session = pytest.importorskip("sqlalchemy.orm").sessionmaker(bind=engine)
    row = Session().query(models.QaCandidate).one()
    assert row.eligibility == "ok", row.eligibility
    assert row.approval_source == "unknown", row.approval_source
    assert row.vector_doc_id is None


# 2026-10-17 从**现役库**只读 PRAGMA 抄下来的形状（不是想象的"最初建表形状"）。
# 用它当基线的理由：线上库就是这个样子，任何比它新的列都只能靠 `_COLUMN_MIGRATIONS` 补——
# 抄成快照而不是猜，是为了让这条判据咬得住"这一轮新加列忘了补清单"这一类事故。
DEPLOYED_SHAPE_20261017 = {
    "conversations": {
        "answer",
        "created_at",
        "id",
        "last_active_at",
        "message_count",
        "question",
        "summary",
        "summary_upto",
        "title",
        "user_id",
    },
    "messages": {
        "agent_run_id",
        "content",
        "conversation_id",
        "created_at",
        "id",
        "image_desc",
        "image_ref",
        "role",
        "thumb_ref",
        "token_est",
    },
    "qa_candidates": {"answer", "created_at", "evidence", "grounded_score", "id", "question", "status"},
}


def test_directional_ruler_lists_every_new_model_column():
    """缺的那半条判据：已部署表上的**每一列**都得要么在快照里、要么在补列清单里。

    `test_migration_schema_parity.py` 钉的是反方向（清单里的列模型得认识），它咬不到
    "模型加了列、清单没补"——而后者才是会让线上第一次读就炸的那一类。
    """
    covered = {(t, c) for t, c, _ddl, _d in M._COLUMN_MIGRATIONS}
    gaps = []
    for table, deployed in DEPLOYED_SHAPE_20261017.items():
        for col in Base.metadata.tables[table].columns.keys():
            if col in deployed or (table, col) in covered:
                continue
            gaps.append((table, col))
    assert not gaps, (
        f"这些列在已部署表上但补列清单里没有：{sorted(gaps)}（升级库会少列，ORM 第一次读就抛 no such column）"
    )
    # 快照本身不许腐烂：删掉一位会在下面这条里露出来（表被改名/删表时 ORM 侧先找不到）
    for table in DEPLOYED_SHAPE_20261017:
        assert table in Base.metadata.tables, f"快照里的表 {table} 在模型里不存在了 ⇒ 同步快照，别删这条判据"


def test_canary_directional_ruler_fires_when_a_model_column_has_no_migration(monkeypatch):
    """正对照：抽掉一条**不在已部署快照里**的清单行，静态判据必须变红（否则它可能是恒真钉子）。

    挑的不是 conversations 那些老行——它们的列已经在快照里，抽掉不会露出缺口。
    要抽的是"列比库新"的那一类（本轮就是 W06 加的六列），这才是这条判据存在的理由。
    """
    kept = list(M._COLUMN_MIGRATIONS)
    target = next(
        (row for row in kept if row[1] not in DEPLOYED_SHAPE_20261017.get(row[0], set())),
        None,
    )
    assert target is not None, "清单里每条的列都已在快照中 ⇒ 本条对照失去对象：加一列新列时同步修这条，别删"
    monkeypatch.setattr(M, "_COLUMN_MIGRATIONS", [row for row in kept if row is not target])
    with pytest.raises(AssertionError, match="补列清单里没有"):
        test_directional_ruler_lists_every_new_model_column()


def test_canary_upgrade_test_fires_on_a_db_missing_the_new_columns(tmp_path, monkeypatch):
    """另一侧对照：真库形状缺列时，①那条必须红——用"跑迁移前就断一次 ORM 读"复现事故本身。"""
    db_file = tmp_path / "app.db"
    con = _make_legacy_db(db_file)
    con.close()
    engine = create_engine(f"sqlite:///{db_file}")
    monkeypatch.setattr(M, "engine", engine)
    # 故意**不**跑迁移：这就是加列没补清单时线上第一次读的形状
    Session = pytest.importorskip("sqlalchemy.orm").sessionmaker(bind=engine)
    with pytest.raises(Exception) as exc:
        Session().query(models.QaCandidate).one()
    assert "no such column" in str(exc.value).lower(), f"炸是炸了，但不是缺列那一类：{exc.value}"
