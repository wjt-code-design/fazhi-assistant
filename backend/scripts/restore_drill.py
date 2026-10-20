"""回滚恢复演练：从备份验证「可恢复 + 可查询」两层。

- SQLite 业务库：从备份副本只读打开 + 行数验证（恢复后可服务业务）
- Chroma 向量库：从备份副本打开 collection 计数（恢复后检索可用）
输出：release-evidence/legal-agent-v1-grayscale-20260907/restore-drill-20260907.json
"""

from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

# 业务库必须能服务业务：缺了会话表就取不出任何对话 ⇒ 演练判失败（旧版记 "NA" 后照样 return 0）。
REQUIRED_TABLE = "conversations"
OUT_PATH = REPO / "release-evidence/legal-agent-v1-grayscale-20260907/restore-drill-20260907.json"


def drill_sqlite(backup_dir: Path) -> tuple[dict, list[str]]:
    """只读打开备份里的业务库并验证。返回 (读数, 失败清单)；失败清单非空即判演练失败。"""
    db = backup_dir / "app.db"
    if not db.is_file():
        return {"open": False}, [f"备份缺少 SQLite：{db}"]
    try:
        con = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)
    except sqlite3.Error as exc:
        # 打不开的库不是"演练成功"：与 backup_data.verify_sqlite 那条对称地判失败。
        return {"open": False}, [f"SQLite 演练失败：{type(exc).__name__}: {exc}"]
    try:
        cur = con.cursor()
        try:
            tables = [r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table'")]
            integrity = cur.execute("PRAGMA integrity_check").fetchone()[0]
            conv: int | str = "NA"
            if REQUIRED_TABLE in tables:
                conv = cur.execute("SELECT COUNT(*) FROM conversations").fetchone()[0]
        except sqlite3.Error as exc:
            return {"open": False}, [f"SQLite 演练失败：{type(exc).__name__}: {exc}"]
    finally:
        con.close()
    failures: list[str] = []
    # integrity_check 旧版只记录不判失败 ⇒ 一个损坏的备份照样输出 pass。
    if integrity != "ok":
        failures.append(f"SQLite integrity_check 非 ok：{integrity}")
    if REQUIRED_TABLE not in tables:
        failures.append(f"业务表缺失：{REQUIRED_TABLE}（恢复后服务不了业务）")
    return {"open": True, "tables": len(tables), "conversations": conv, "integrity_check": integrity}, failures


def drill_chroma(backup_dir: Path) -> tuple[dict, list[str]]:
    """验证备份内向量库「可查询」。返回 (读数, 失败清单)；任何异常即判演练失败。

    注意：`PersistentClient` 会**创建**不存在的目录 ⇒ 备份里若根本没有向量库，它不会抛异常，
    而是给出空 collection 列表——这正是最隐蔽的"假绿"，故空列表同样判失败。
    """
    import chromadb

    client = chromadb.PersistentClient(path=str(backup_dir / "chroma_db"))
    cols = {c.name: c.count() for c in client.list_collections()}
    if not cols:
        return {"collections": cols}, ["Chroma 备份不含任何 collection（恢复后检索不可用）"]
    return {"collections": cols}, []


def run_drill(bdir: Path) -> tuple[dict, list[str]]:
    """在备份的**副本**上演练：drill 打开库会写 `chroma_db`（sqlite/索引）⇒ 直接开原备份会污染它。

    `ignore_cleanup_errors=True`：与 `scripts/chroma_dir_guard.py:isolated_chroma` 同款先例——
    Windows 上 Chroma 会持有 `chroma.sqlite3` 的文件锁，临时目录清理时 rmtree 抛
    NotADirectoryError；chromadb 0.4.24 的 `PersistentClient` 无 `close()`，故按既有做法让清理容错。
    """
    with tempfile.TemporaryDirectory(prefix="fazhi-restore-drill-", ignore_cleanup_errors=True) as lane:
        copy = Path(lane) / "pkg"
        shutil.copytree(bdir, copy)
        sqlite_result, sqlite_failures = drill_sqlite(copy)
        try:
            chroma_result, chroma_failures = drill_chroma(copy)
        except Exception as exc:  # noqa: BLE001 演练失败必须映射为失败结论，不是静默 error 字段
            chroma_result, chroma_failures = (
                {"error": str(exc)[:200]},
                [f"Chroma 演练失败：{type(exc).__name__}: {str(exc)[:200]}"],
            )
    result = {"schema_version": "phase9-restore-drill/v1", "backup_dir": str(bdir), "sqlite": sqlite_result}
    result["chroma"] = chroma_result
    return result, sqlite_failures + chroma_failures


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--backup", default=f"{REPO / 'backend' / 'backups'}", help="备份根目录（取最新时间戳子目录之外第一个显式目录）"
    )
    ap.add_argument("--backup-dir", help="显式指定某个备份目录")
    args = ap.parse_args()
    bdir = Path(args.backup_dir) if args.backup_dir else sorted(Path(args.backup).iterdir(), key=lambda p: p.name)[-1]
    result, failures = run_drill(bdir)
    result["failures"] = failures
    result["ok"] = not failures
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=1))
    # 失败必须映射为**非零退出**：旧版无论 SQLite/Chroma 怎么坏都 return 0，演练结论永远"通过"。
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
