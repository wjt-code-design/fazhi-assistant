"""回滚恢复演练：从备份验证「可恢复 + 可查询」两层。

- SQLite 业务库：从备份副本只读打开 + 行数验证（恢复后可服务业务）
- Chroma 向量库：从备份副本打开 collection 计数（恢复后检索可用）
输出：release-evidence/legal-agent-v1-grayscale-20260907/restore-drill-20260907.json
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def drill_sqlite(backup_dir: Path) -> dict:
    db = backup_dir / "app.db"
    assert db.is_file(), f"备份缺少 SQLite: {db}"
    con = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)
    try:
        cur = con.cursor()
        tables = [r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table'")]
        conv = cur.execute("SELECT COUNT(*) FROM conversations").fetchone()[0] if "conversations" in tables else "NA"
        integrity = cur.execute("PRAGMA integrity_check").fetchone()[0]
    finally:
        con.close()
    return {"open": True, "tables": len(tables), "conversations": conv, "integrity_check": integrity}


def drill_chroma(backup_dir: Path) -> dict:
    import chromadb

    client = chromadb.PersistentClient(path=str(backup_dir / "chroma_db"))
    cols = {c.name: c.count() for c in client.list_collections()}
    return {"collections": cols}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--backup", default=f"{REPO / 'backend' / 'backups'}", help="备份根目录（取最新时间戳子目录之外第一个显式目录）"
    )
    ap.add_argument("--backup-dir", help="显式指定某个备份目录")
    args = ap.parse_args()
    bdir = Path(args.backup_dir) if args.backup_dir else sorted(Path(args.backup).iterdir(), key=lambda p: p.name)[-1]
    result = {"schema_version": "phase9-restore-drill/v1", "backup_dir": str(bdir), "sqlite": drill_sqlite(bdir)}
    try:
        result["chroma"] = drill_chroma(bdir)
    except Exception as exc:  # noqa: BLE001
        result["chroma"] = {"error": str(exc)[:200]}
    out = REPO / "release-evidence/legal-agent-v1-grayscale-20260907/restore-drill-20260907.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
