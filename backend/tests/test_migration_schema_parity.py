"""`migrations.run_migrations()` 的两件事：补列清单不许与模型漂移，ALTER 失败不许被吞。

**为什么这只文件存在**（不是给已有测试补覆盖率）：产品只有一条建库路径
（`database.py:33` → `run_migrations()`，内部 `create_all` ＋幂等补列），
所以"两条路径 schema 不一致"这种事故在这里不会发生；会发生的是另外两种，
都藏在那条唯一路径里：

1. `_COLUMN_MIGRATIONS` 是**手抄清单**。它和模型对不上时（列不存在／类型不一致），
   升级出来的库与新建出来的库形状不同，而且没有任何东西会响——ORM 不认识多出来的列，
   缺列则要到第一次读写才炸。今天实测 7/7 逐字一致，所以这一组是**防漂移的钉子**，
   不是发现现存缺陷；钉子必须能红，见 `test_canary_*` 两条与变异矩阵。
2. 补列的 `except Exception` 只 print 就继续。它上面已经用 `PRAGMA table_info` 判过
   "列已存在"，所以**能走到 except 的绝大多数不是那个借口**——表名打错、DDL 写错、
   锁冲突都在这一格里被吞成一行日志 ⇒ 升级库悄悄少一列。这条现在就是红的。

`duplicate column name` 仍要容忍：并发启动时两个进程可能同时 ALTER，那是真幂等场景。
"""

from __future__ import annotations

import pytest
from sqlalchemy.dialects import sqlite

import migrations as M
from database import Base


def _model_column(table: str, col: str):
    t = Base.metadata.tables.get(table)
    if t is None:
        return None
    return t.columns.get(col)


def test_every_column_migration_targets_a_real_model_column():
    missing = [(t, c) for t, c, _ddl, _d in M._COLUMN_MIGRATIONS if _model_column(t, c) is None]
    assert not missing, f"补列清单里有模型不认识的表/列：{missing}（升级库会多出/少掉 ORM 不管的列）"


def test_column_migration_ddl_matches_the_model_type():
    dial = sqlite.dialect()
    bad = []
    for table, col, ddl, _default in M._COLUMN_MIGRATIONS:
        c = _model_column(table, col)
        if c is None:
            continue
        want = c.type.compile(dialect=dial).strip().upper()
        if want != ddl.strip().upper():
            bad.append((table, col, ddl, want))
    assert not bad, f"补列 DDL 与模型类型不一致：{bad} ⇒ 升级库与新建库形状不同"


def test_alter_failure_for_a_missing_table_is_not_swallowed(monkeypatch, capsys):
    """表名不存在 ⇒ 必须抛。今天它被 `except Exception` 吞成一行 print，升级库悄悄少一列。"""
    monkeypatch.setattr(M, "_COLUMN_MIGRATIONS", [("no_such_table_here", "col", "VARCHAR(10)", None)])
    with pytest.raises(Exception) as exc:
        M.run_migrations()
    assert "no such table" in str(exc.value).lower()
    assert "skip" not in capsys.readouterr().out, "仍然走了 print 兜底 ⇒ 失败没被硬显现"


def test_duplicate_column_alter_is_still_tolerated(monkeypatch):
    """阳性控制：真·幂等场景（并发启动时列已存在）不许变成崩。"""
    import models  # noqa: F401

    monkeypatch.setattr(M, "_existing_columns", lambda conn, table: set())
    monkeypatch.setattr(M, "_COLUMN_MIGRATIONS", [("conversations", "title", "VARCHAR(200)", "''")])
    M.run_migrations()  # 不抛即通过：ALTER 会报 duplicate column name，那一类必须继续容忍


def test_canary_parity_guard_detects_a_tampered_ddl(monkeypatch):
    """钉子能红的自证（一）：把 DDL 改成与模型不符，判据必须红。"""
    monkeypatch.setattr(M, "_COLUMN_MIGRATIONS", [("conversations", "title", "VARCHAR(9)", None)])
    with pytest.raises(AssertionError):
        test_column_migration_ddl_matches_the_model_type()


def test_canary_parity_guard_detects_an_unknown_column(monkeypatch):
    """钉子能红的自证（二）：清单里塞一个模型没有的列，判据必须红。"""
    monkeypatch.setattr(M, "_COLUMN_MIGRATIONS", [("messages", "not_in_the_model", "TEXT", None)])
    with pytest.raises(AssertionError):
        test_every_column_migration_targets_a_real_model_column()
