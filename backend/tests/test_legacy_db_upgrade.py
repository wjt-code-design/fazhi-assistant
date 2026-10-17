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


# ==================== 票 W06-FIX V7/F8：升级行＋链 ⇒ 判据必须拒（backfill 当天的爆炸半径） ====================


def _upgrade_legacy_engine(tmp_path, monkeypatch):
    """按现役库真实形状建老库 → 跑迁移 → 把 `database.SessionLocal` 接到这只**临时**引擎。

    只写 tmp_path 下的 app.db，绝不碰真实 `backend/app.db`（红线）。
    """
    import database

    db_file = tmp_path / "app.db"
    con = _make_legacy_db(db_file)
    con.close()
    engine = create_engine(f"sqlite:///{db_file}")
    monkeypatch.setattr(M, "engine", engine)
    M.run_migrations()
    sessions = pytest.importorskip("sqlalchemy.orm").sessionmaker(bind=engine)
    monkeypatch.setattr(database, "SessionLocal", sessions)  # 判据里的 load_read_state 走同一只引擎
    return engine, sessions


def test_upgraded_legacy_row_is_rejected_by_the_predicate_once_linked(tmp_path, monkeypatch):
    """V7/F8：把**判据真的跑在升级出来的存量行上**——它必须被拒，而且拒得很响。

    改前的事实（票面 F8）：`test_legacy_qa_candidates_upgrade_gains_the_eligibility_columns` 只断言
    默认值 `approval_source='unknown'` + `eligibility='ok'`，**从没拿判据跑过这条行**。
    于是 backfill（`dispatch/w06-backfill-ticket.md`）一旦给存量补上链，
    「来源未知＝不可服务」这条规则会把**整库 759 行存量**从「无链⇒按来源可校验判定」
    瞬间翻成「带链却来源未知⇒整片停服」——这个悬崖今天没有任何测试会提前响。本条就是那声警报。

    同时给出 backfill 动手前必须有的**计数**形状（backfill 票 §2）：
    有多少行的 `approval_source` 还是 `unknown`，就有多少行会在这次补链里翻面。
    """
    import qa_eligibility as qe

    _engine, sessions = _upgrade_legacy_engine(tmp_path, monkeypatch)
    db = sessions()
    try:
        row = db.query(models.QaCandidate).one()
        # ① 升级行的默认形状（原钉的那两条断言在这里**一字不动**地成立——本条不替换它们，只加另一半）
        assert row.eligibility == "ok" and row.approval_source == "unknown" and row.vector_doc_id is None

        # ② 没链时：状态轴不适用（放行面），这条行现在**看不见**判据 ⇒ 这正是悬崖前的平静
        unlinked = qe.qa_read_eligible({"qa_candidate_id": None, "evidence": "[]"}, qe.load_read_state(row.id))
        assert unlinked.reason == "provenance", "引用为空那条本该被来源档拒（与链无关）"
        assert qe._state_axis({"qa_candidate_id": None}, qe.load_read_state(row.id)) is None

        # ③ backfill 那天：链补上了，来源却还是 unknown ⇒ 判据必须**拒**，reason=provenance
        row.vector_doc_id = "backfill-写进来的-doc-id"
        db.commit()
        meta = {
            "question": "老问题",
            "answer": "老答案",
            "evidence": "中华人民共和国劳动合同法|第十九条",
            "law_as_of_basis": "2026-08-23",
            "qa_candidate_id": row.id,
        }
        verdict = qe.qa_read_eligible(meta, qe.load_read_state(row.id))
        assert verdict.allow is False, "升级行带链却被放行 ⇒ 未知来源这条规则没在状态轴里生效"
        assert verdict.reason == "provenance", verdict

        # ④ 爆炸半径的计数形状（backfill 票 §2：先出数，再动手）
        unknown_rows = db.query(models.QaCandidate).filter(models.QaCandidate.approval_source == "unknown").count()
        assert unknown_rows == 1, f"本夹具里的存量行数变了（现量 {unknown_rows}）⇒ 计数形状失去对象，同步改这条"
        print(
            f"\n[backfill 爆炸半径] 本夹具 1 行；现役库 qa_candidates 现量 759 行（本文件头部注释的抄自 PRAGMA 的数）"
            f"⇒ 补链那一天这 {unknown_rows} 行会从「无链放行」翻成「带链即拒」"
        )

        # ⑤ 对照腿：backfill 若同时把来源也标上（这里标 human），同一行就应当**过**状态轴
        #    ——证明上面那一拒来自 `approval_source`，不是来自「带链」本身（防止把悬崖修成「带链就打死」）。
        import retrieval

        monkeypatch.setattr(retrieval, "exact_article_lookup", lambda src, art: [{"page_content": "第十九条"}])
        row.approval_source = "human"
        db.commit()
        assert qe.qa_read_eligible(meta, qe.load_read_state(row.id)).allow is True
    finally:
        db.close()


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
