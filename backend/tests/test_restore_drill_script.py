"""R12：`scripts/restore_drill.py` 的失败关闭契约（合成备份，全程不接触真实库）。

改前的形状（对 `ee5bfef` 静态核对）：
- Chroma 演练抛异常 → 只写 `result["chroma"]["error"]`，`main()` 仍 `return 0`；
- SQLite `PRAGMA integrity_check` 只**记录**结果、不据此失败；
- 业务表缺失时 `conversations` 记 `"NA"` 后照样 `return 0`；
- 直接对**备份目录**开 `PersistentClient`（演练进程会写库，污染被演练的备份）。

⇒ "演练结论永远通过"：一个损坏/不完整的备份也能拿到 exit 0 的"可恢复"报告。
本文件把这四条各钉一条，并证明正常备份仍返回 0、且**不改动被演练的备份字节**。
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import sys
from pathlib import Path

import chromadb
import pytest

from scripts import restore_drill

EMB = [1.0] + [0.0] * 7


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _snapshot(root: Path) -> dict:
    return {str(p.relative_to(root)): _sha(p) for p in sorted(root.rglob("*")) if p.is_file()}


def _make_business_db(path: Path, *, with_conversations: bool = True) -> None:
    con = sqlite3.connect(path)
    with con:
        con.execute("CREATE TABLE laws (law_name TEXT, article TEXT)")
        if with_conversations:
            con.execute("CREATE TABLE conversations (id INTEGER PRIMARY KEY, title TEXT)")
            con.execute("INSERT INTO conversations (title) VALUES ('合成会话')")
    con.close()


def _make_chroma(root: Path, collections: int = 1) -> None:
    root.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(root))
    for i in range(collections):
        col = client.get_or_create_collection(f"probe-{i}", metadata={"hnsw:space": "cosine"})
        col.add(ids=["a", "b"], embeddings=[EMB, EMB], documents=["甲", "乙"])
        assert col.count() == 2


def _backup_root(tmp_path: Path, *, with_conversations: bool = True, collections: int = 1) -> Path:
    bdir = tmp_path / "pkg"
    bdir.mkdir()
    _make_business_db(bdir / "app.db", with_conversations=with_conversations)
    _make_chroma(bdir / "chroma_db", collections=collections)
    return bdir


@pytest.fixture()
def out_path(tmp_path, monkeypatch):
    """把模块级输出路径改到 tmp：否则 main() 会写进仓库 release-evidence。"""
    target = tmp_path / "drill.json"
    monkeypatch.setattr(restore_drill, "OUT_PATH", target)
    return target


def _run(tmp_path, bdir: Path, monkeypatch, argv: list[str] | None = None) -> int:
    monkeypatch.setattr(sys, "argv", ["restore_drill.py", "--backup-dir", str(bdir), *(argv or [])])
    return restore_drill.main()


def test_healthy_backup_returns_zero_and_reports_ok(tmp_path, monkeypatch, out_path):
    bdir = _backup_root(tmp_path)
    rc = _run(tmp_path, bdir, monkeypatch)
    assert rc == 0
    result = json.loads(out_path.read_text(encoding="utf-8"))
    assert result["ok"] is True and result["failures"] == []
    assert result["sqlite"]["conversations"] == 1
    assert result["chroma"]["collections"]  # 至少一个 collection 被数出来


def test_missing_business_table_maps_to_nonzero(tmp_path, monkeypatch, out_path):
    """旧版把缺 `conversations` 记成 `"NA"` 后照样成功；这里必须判失败。"""
    bdir = _backup_root(tmp_path, with_conversations=False)
    rc = _run(tmp_path, bdir, monkeypatch)
    assert rc == 1, "缺业务表却报成功 ⇒ 演练结论撒谎"
    result = json.loads(out_path.read_text(encoding="utf-8"))
    assert result["ok"] is False
    assert any("conversations" in f for f in result["failures"]), result["failures"]


def test_missing_sqlite_file_maps_to_nonzero(tmp_path, monkeypatch, out_path):
    bdir = _backup_root(tmp_path)
    (bdir / "app.db").unlink()
    assert _run(tmp_path, bdir, monkeypatch) == 1


def test_unreadable_sqlite_maps_to_nonzero(tmp_path, monkeypatch, out_path):
    """不是 sqlite 库的 `app.db`：旧版会抛 traceback（既不是成功也不是结论），这里映射为失败。"""
    bdir = _backup_root(tmp_path)
    (bdir / "app.db").write_bytes(b"this is not a sqlite database")
    rc = _run(tmp_path, bdir, monkeypatch)
    assert rc == 1
    result = json.loads(out_path.read_text(encoding="utf-8"))
    assert any("SQLite 演练失败" in f for f in result["failures"]), result["failures"]


def test_chroma_drill_exception_maps_to_nonzero(tmp_path, monkeypatch, out_path):
    """旧版把 Chroma 异常写进 `error` 字段后仍 return 0（演练结论永远通过）。"""
    bdir = _backup_root(tmp_path)

    def boom(*_a, **_k):
        raise RuntimeError("chroma unavailable")

    monkeypatch.setattr(chromadb, "PersistentClient", boom)
    rc = _run(tmp_path, bdir, monkeypatch)
    assert rc == 1
    result = json.loads(out_path.read_text(encoding="utf-8"))
    assert any("Chroma 演练失败" in f for f in result["failures"]), result["failures"]


def test_empty_chroma_backup_maps_to_nonzero(tmp_path, monkeypatch, out_path):
    """假绿通道：`PersistentClient` 会**创建**不存在的目录 ⇒ 备份里没有向量库也不抛异常，只有空列表。"""
    bdir = tmp_path / "pkg"
    bdir.mkdir()
    _make_business_db(bdir / "app.db")
    rc = _run(tmp_path, bdir, monkeypatch)
    assert rc == 1, "备份里根本不含向量库却报成功 ⇒ 检索层不可恢复被洗成通过"
    result = json.loads(out_path.read_text(encoding="utf-8"))
    assert any("collection" in f for f in result["failures"]), result["failures"]


def test_drill_runs_on_a_copy_and_leaves_the_backup_untouched(tmp_path, monkeypatch, out_path):
    """副本演练：drill 打开向量库会写 `chroma_db`，直接开原备份就会改动被演练的包。"""
    bdir = _backup_root(tmp_path)
    before = _snapshot(bdir)
    assert _run(tmp_path, bdir, monkeypatch) == 0
    assert _snapshot(bdir) == before, "演练改动了备份包字节（应始终在副本上跑）"
