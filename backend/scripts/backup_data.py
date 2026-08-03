"""数据备份 + 恢复验证（阶段4）。

- SQLite：sqlite3 backup API（WAL 安全，备份为单文件）。
- 恢复验证：备份后自动把备份复制到临时库跑 `PRAGMA integrity_check`，失败标红——
  光备份不验证等于没备份。
- Chroma：复制 chroma_db 目录 + 可选导出 collection 元数据 JSON（可读索引）。

用法：
  python scripts/backup_data.py                          # 默认备份到 ../backups/<时间戳>/
  python scripts/backup_data.py --out D:/backup_manual   # 指定目录
  python scripts/backup_data.py --skip-chroma-export     # 跳过 JSON 导出（大库省时）

注意：备份前建议先停后端（manage.py stop），避免备份与运行写竞争（SQLite backup API
本身 WAL 安全，但 Chroma 目录复制在运行中复制可能不一致）。
"""

import argparse
import json
import os
import shutil
import sqlite3
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.dirname(HERE)
sys.path.insert(0, BACKEND)
os.chdir(BACKEND)

DEFAULT_BACKUP_ROOT = os.path.join(BACKEND, "..", "backups")
CHROMA_DIR = os.path.join(BACKEND, "chroma_db")
# database.py 支持 DATABASE_URL；这里解析出 sqlite 文件路径，默认 backend/app.db
DB_URL = os.getenv("DATABASE_URL", "")
if DB_URL.startswith("sqlite:///"):
    DB_PATH = DB_URL[len("sqlite:///") :]
    if not os.path.isabs(DB_PATH):
        DB_PATH = os.path.join(BACKEND, DB_PATH)
else:
    DB_PATH = os.path.join(BACKEND, "app.db")


def _timestamp() -> str:
    return time.strftime("%Y%m%d_%H%M%S")


def backup_sqlite(db_path: str, dest_dir: str) -> str:
    """sqlite3 backup API：源库在线备份到单文件（WAL 安全，不复制 -wal/-shm）。"""
    os.makedirs(dest_dir, exist_ok=True)
    out = os.path.join(dest_dir, "app.db")
    src = sqlite3.connect(db_path)
    dst = sqlite3.connect(out)
    try:
        with dst:
            src.backup(dst)
    finally:
        dst.close()
        src.close()
    return out


def verify_sqlite(db_file: str) -> tuple[bool, str]:
    """恢复验证：复制备份到临时库跑 PRAGMA integrity_check（不污染备份文件）。"""
    tmp = db_file + ".verify.tmp"
    shutil.copyfile(db_file, tmp)
    try:
        con = sqlite3.connect(tmp)
        try:
            row = con.execute("PRAGMA integrity_check").fetchone()
        finally:
            con.close()
        return row and row[0] == "ok", (row[0] if row else "no-row")
    finally:
        os.remove(tmp)


def export_chroma_json(dest_dir: str) -> str:
    """导出 collection 条文元数据为 JSON（可读备份，用于核对条数/source 分布）。"""
    import chromadb

    from rag_chain import COLLECTION_NAME  # 与检索库单一来源（code-review：避免字面量重复）

    client = chromadb.PersistentClient(path=CHROMA_DIR)
    col = client.get_collection(COLLECTION_NAME)
    meta = col.get(include=["metadatas"], limit=100000)
    metas = meta["metadatas"] or []
    rows = []
    for i, mid in enumerate(meta["ids"]):
        m = metas[i] or {}
        rows.append({"id": mid, "source": m.get("source", ""), "article": m.get("article", "")})
    out = os.path.join(dest_dir, "chroma_index.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump({"count": len(rows), "items": rows}, f, ensure_ascii=False, indent=1)
    return out


def main():
    ap = argparse.ArgumentParser(description="数据备份 + 恢复验证")
    ap.add_argument("--out", default=None, help="备份目标目录（默认 ../backups/<时间戳>/）")
    ap.add_argument("--skip-chroma-export", action="store_true", help="跳过 Chroma JSON 导出")
    args = ap.parse_args()

    ts = _timestamp()
    out = args.out or os.path.join(DEFAULT_BACKUP_ROOT, ts)
    os.makedirs(out, exist_ok=True)
    print(f"备份目录：{out}")

    # ---- SQLite ----
    if os.path.exists(DB_PATH):
        db_backup = backup_sqlite(DB_PATH, out)
        ok, msg = verify_sqlite(db_backup)
        mark = "PASS" if ok else f"FAIL（{msg}）"
        print(f"[SQLite] {db_backup}  integrity_check={mark}")
        if not ok:
            print("  ⚠ 备份文件损坏！请检查磁盘/原库，勿使用此备份。")
    else:
        print("[SQLite] 未找到数据库文件，跳过")

    # ---- Chroma ----
    if os.path.isdir(CHROMA_DIR):
        shutil.copytree(CHROMA_DIR, os.path.join(out, "chroma_db"))
        print(f"[Chroma] 目录复制完成：{os.path.join(out, 'chroma_db')}")
        if not args.skip_chroma_export:
            try:
                idx = export_chroma_json(out)
                print(f"[Chroma] 元数据导出：{idx}")
            except Exception as e:
                print(f"[Chroma] JSON 导出失败（可加 --skip-chroma-export 跳过）：{e}")
    else:
        print("[Chroma] 未找到 chroma_db 目录，跳过")

    print("备份完成。恢复：停后端 → 将备份文件放回对应位置 → 启动后验证检索。")
    print("提示：备份前建议先 manage.py stop，避免运行中复制 Chroma 目录不一致。")


if __name__ == "__main__":
    main()
