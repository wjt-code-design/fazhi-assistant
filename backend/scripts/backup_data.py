"""数据备份 + 恢复验证（阶段4）。

- SQLite：sqlite3 backup API（WAL 安全，备份为单文件）。
- 恢复验证：备份后自动把备份复制到临时库跑 `PRAGMA integrity_check`，失败标红——
  光备份不验证等于没备份。
- Chroma：复制 chroma_db 目录 + 可选导出 collection 元数据 JSON（可读索引）。

用法：
  python scripts/backup_data.py                          # 默认备份到 ../backups/<时间戳>/
  python scripts/backup_data.py --out D:/backup_manual   # 指定目录
  python scripts/backup_data.py --skip-chroma            # 明确只备份 SQLite
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

from scripts import chroma_dir_guard  # noqa: E402

DEFAULT_BACKUP_ROOT = os.path.join(
    BACKEND, "backups"
)  # 对抗审计 v2 #22：与 compose 卷 ./backend/backups:/app/backups 一致
CHROMA_DIR = os.path.join(BACKEND, "chroma_db")
# database.py 支持 DATABASE_URL；这里解析出 sqlite 文件路径，默认 backend/app.db
DB_URL = os.getenv("DATABASE_URL", "")
if DB_URL.startswith("sqlite:///"):
    DB_PATH = DB_URL[len("sqlite:///") :]
    if not os.path.isabs(DB_PATH):
        DB_PATH = os.path.join(BACKEND, DB_PATH)
else:
    DB_PATH = os.path.join(BACKEND, "app.db")

# 备份面补全（S4，2026-09-19 实测缺口）：此前整个工具只产出 app.db + chroma_db + chroma_index.json，
# 而这三件从不进任何备份包 —— quota_used.sqlite 是"谁烧了多少 token"的唯一账本，
# data/app.db 是 compose 挂进容器的那份库，media/ 是上传件（3.4M / 58 个文件）。
EXTRA_SQLITE = {
    "quota_used.sqlite": os.path.join(BACKEND, "data", "quota_used.sqlite"),
    "data_app.db": os.path.join(BACKEND, "data", "app.db"),
}
MEDIA_DIR = os.path.join(BACKEND, "media")


def _timestamp() -> str:
    return time.strftime("%Y%m%d_%H%M%S")


def backup_sqlite(db_path: str, dest_dir: str, dest_name: str = "app.db") -> str:
    """sqlite3 backup API：源库在线备份到单文件（WAL 安全，不复制 -wal/-shm）。"""
    os.makedirs(dest_dir, exist_ok=True)
    out = os.path.join(dest_dir, dest_name)
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


def _check_env_contract() -> None:
    """CLI 前置守卫：CHROMA_DIR 与本脚本固定目标分歧时拒绝跑（不放 main() 里，理由见 chroma_dir_guard）。"""
    chroma_dir_guard.assert_matches(CHROMA_DIR, "backup_data")


def backup_extras(dest_dir: str) -> list:
    """把 quota 账本 / 容器侧库 / media 也收进同一个备份包。

    缺件**不让整个备份失败**（干净机器上可能就没有 media 或容器侧库），但**逐条说出来**——
    静默跳过会让人以为包里全都有。返回 [(名字, 状态)]，状态 ∈ ok/skipped/failed。
    """
    results = []
    for name, src in EXTRA_SQLITE.items():
        if not os.path.exists(src):
            print(f"[Extras] 跳过（源不存在）：{name} <- {src}")
            results.append((name, "skipped"))
            continue
        try:
            out_file = backup_sqlite(src, dest_dir, name)
        except (OSError, sqlite3.Error) as exc:
            print(f"[Extras] ERROR {name} 备份失败：{exc}")
            results.append((name, "failed"))
            continue
        ok, msg = verify_sqlite(out_file)
        print(f"[Extras] {name} 备份={'PASS' if ok else f'FAIL（{msg}）'}")
        results.append((name, "ok" if ok else "failed"))
    if os.path.isdir(MEDIA_DIR):
        media_dst = os.path.join(dest_dir, "media")
        try:
            shutil.copytree(MEDIA_DIR, media_dst)
            print(f"[Extras] media 目录复制完成：{media_dst}")
            results.append(("media", "ok"))
        except OSError as exc:
            print(f"[Extras] ERROR media 复制失败：{exc}")
            results.append(("media", "failed"))
    else:
        print(f"[Extras] 跳过（源不存在）：media <- {MEDIA_DIR}")
        results.append(("media", "skipped"))
    return results


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="数据备份 + 恢复验证")
    ap.add_argument("--out", default=None, help="备份目标目录（默认 ../backups/<时间戳>/）")
    ap.add_argument("--skip-chroma", action="store_true", help="明确跳过 Chroma 目录备份和导出")
    ap.add_argument("--skip-chroma-export", action="store_true", help="跳过 Chroma JSON 导出")
    args = ap.parse_args(argv)

    ts = _timestamp()
    out = args.out or os.path.join(DEFAULT_BACKUP_ROOT, ts)
    try:
        os.makedirs(out, exist_ok=False)
    except FileExistsError:
        print(f"ERROR 备份目录已存在，拒绝覆盖：{out}")
        return 2
    print(f"备份目录：{out}")

    # ---- SQLite ----
    if os.path.exists(DB_PATH):
        try:
            db_backup = backup_sqlite(DB_PATH, out)
        except (OSError, sqlite3.Error) as exc:
            print(f"[SQLite] ERROR 备份失败：{exc}")
            return 1
        try:
            ok, msg = verify_sqlite(db_backup)
        except (OSError, sqlite3.Error) as exc:
            print(f"[SQLite] ERROR 恢复验证执行失败：{exc}")
            return 1
        mark = "PASS" if ok else f"FAIL（{msg}）"
        print(f"[SQLite] {db_backup}  integrity_check={mark}")
        if not ok:
            print("  ERROR 备份文件损坏！请检查磁盘/原库，勿使用此备份。")
            return 1
    else:
        print(f"[SQLite] ERROR 未找到数据库文件：{DB_PATH}")
        return 1

    # ---- Chroma ----
    if args.skip_chroma:
        print("[Chroma] 已按显式 --skip-chroma 跳过")
    elif os.path.isdir(CHROMA_DIR):
        chroma_backup = os.path.join(out, "chroma_db")
        try:
            shutil.copytree(CHROMA_DIR, chroma_backup)
        except OSError as exc:
            print(f"[Chroma] ERROR 目录复制失败：{exc}")
            return 1
        print(f"[Chroma] 目录复制完成：{chroma_backup}")
        if not args.skip_chroma_export:
            try:
                idx = export_chroma_json(out)
                print(f"[Chroma] 元数据导出：{idx}")
            except Exception as exc:
                print(f"[Chroma] ERROR JSON 导出失败（仅显式 --skip-chroma-export 可跳过）：{exc}")
                return 1
    else:
        print(f"[Chroma] ERROR 未找到 chroma_db 目录：{CHROMA_DIR}")
        return 1

    # ---- 附属产物：quota 账本 / 容器侧库 / media ----
    extras = backup_extras(out)
    if any(status == "failed" for _, status in extras):
        print("ERROR 附属产物备份失败，勿使用该备份包。")
        return 1

    print("备份完成。恢复：停后端 → 将备份文件放回对应位置 → 启动后验证检索。")
    print("提示：备份前建议先 manage.py stop，避免运行中复制 Chroma 目录不一致。")
    return 0


if __name__ == "__main__":
    _check_env_contract()
    sys.exit(main())
