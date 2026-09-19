"""数据备份 + 恢复验证（阶段4）。

- SQLite：sqlite3 backup API（WAL 安全，备份为单文件）。
- 恢复验证：备份后自动把备份复制到临时库跑 `PRAGMA integrity_check`，失败标红——
  光备份不验证等于没备份。
- Chroma：复制 chroma_db 目录 + 可选导出 collection 元数据 JSON（可读索引）。
- 附属面（S4）：`quota_used.sqlite`（token 账本）、`data_app.db`（compose 挂进容器的那份库）、
  `media/`（上传件）。两份附属库同样跑 integrity_check；缺件逐条说出来，不静默跳过。
- 清单（S7）：全部成功时在包内最后写 `backup_manifest.json`，逐条记下包内目标的名字、字节数、
  （库/文件的）sha256 与 integrity 结论——它回答"这个包里到底有什么、恢复时放回哪儿"。
  **任何失败返回路径都不写清单**：清单是"这个包可用"的凭证，坏包里放一份看起来完整的清单，
  等于把"没备份成"洗成"备份过了"。

用法：
  python scripts/backup_data.py                          # 默认备份到 ../backups/<时间戳>/
  python scripts/backup_data.py --out D:/backup_manual   # 指定目录
  python scripts/backup_data.py --skip-chroma            # 明确只备份 SQLite
  python scripts/backup_data.py --skip-chroma-export     # 跳过 JSON 导出（大库省时）

注意：备份前建议先停后端（manage.py stop），避免备份与运行写竞争（SQLite backup API
本身 WAL 安全，但 Chroma 目录复制在运行中复制可能不一致）。
"""

import argparse
import hashlib
import json
import os
import shutil
import sqlite3
import sys
import time
from pathlib import Path

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
# 目录与"包内名 → 源文件名"分开钉（S7）：测试只 patch DATA_DIR，映射本身因此第一次进入被测面 ——
# 此前两侧混在同一份字典里，测试只能整份替换，于是"把 A 库备份成 B"这类错**原理上不可能变红**。
DATA_DIR = os.path.join(BACKEND, "data")
EXTRA_SQLITE = {  # 包内名 -> 源文件（名字即契约，restore 时放回 DATA_DIR/<value>）
    "quota_used.sqlite": "quota_used.sqlite",
    "data_app.db": "app.db",
}
MEDIA_DIR = os.path.join(BACKEND, "media")
# 应用侧的账本路径由 QUOTA_DB 环境变量决定（见 quota_store.py），本脚本按上面的固定映射取。
# 二者分歧 ⇒ 备份会静默作用在错误的库上，所以由 _check_env_contract() 拒绝执行（判例见 chroma_dir_guard）。
QUOTA_SOURCE = os.path.join(DATA_DIR, EXTRA_SQLITE["quota_used.sqlite"])

MANIFEST_NAME = "backup_manifest.json"
MEDIA_ITEM_HASH_LIMIT = 5000  # 超过就退化为只记计数：逐个哈希 media 会把备份 I/O 翻倍


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
    """CLI 前置守卫：CHROMA_DIR / QUOTA_DB 与本脚本固定目标分歧时拒绝跑（不放 main() 里，理由见 chroma_dir_guard）。"""
    chroma_dir_guard.assert_matches(CHROMA_DIR, "backup_data")
    chroma_dir_guard.assert_matches(QUOTA_SOURCE, "backup_data", env_name="QUOTA_DB")


def _extra_record(dest: str, status: str, source: str, integrity: str | None) -> dict:
    """一条附属件记录 —— 清单直接消费它，不必为拿 integrity 结论再跑一次校验。"""
    return {"dest": dest, "status": status, "source": source, "integrity_check": integrity}


def backup_extras(dest_dir: str) -> list:
    """把 quota 账本 / 容器侧库 / media 也收进同一个备份包，返回逐件记录。

    缺件**不让整个备份失败**（干净机器上可能就没有 media 或容器侧库），但**逐条说出来**——
    静默跳过会让人以为包里全都有。每条记录 = ``{dest, status, source, integrity_check}``，
    status ∈ ok/skipped/failed；调用方取 ``status`` 判失败关闭，取其余字段写清单。
    """
    records = []
    for name, fname in EXTRA_SQLITE.items():
        src = os.path.join(DATA_DIR, fname)
        if not os.path.exists(src):
            print(f"[Extras] 跳过（源不存在）：{name} <- {src}")
            records.append(_extra_record(name, "skipped", src, None))
            continue
        try:
            out_file = backup_sqlite(src, dest_dir, name)
        except (OSError, sqlite3.Error) as exc:
            print(f"[Extras] ERROR {name} 备份失败：{exc}")
            records.append(_extra_record(name, "failed", src, None))
            continue
        try:
            ok, msg = verify_sqlite(out_file)
        except (OSError, sqlite3.Error) as exc:
            # 与主库那条对齐（fail-closed 对称）：验证**跑不动**不等于验证**通过了**。
            print(f"[Extras] ERROR {name} 恢复验证执行失败：{exc}")
            records.append(_extra_record(name, "failed", src, f"error: {exc}"))
            continue
        print(f"[Extras] {name} 备份={'PASS' if ok else f'FAIL（{msg}）'}")
        records.append(_extra_record(name, "ok" if ok else "failed", src, msg))
    if os.path.isdir(MEDIA_DIR):
        media_dst = os.path.join(dest_dir, "media")
        try:
            shutil.copytree(MEDIA_DIR, media_dst)
            print(f"[Extras] media 目录复制完成：{media_dst}")
            records.append(_extra_record("media", "ok", MEDIA_DIR, None))
        except OSError as exc:
            print(f"[Extras] ERROR media 复制失败：{exc}")
            records.append(_extra_record("media", "failed", MEDIA_DIR, None))
    else:
        print(f"[Extras] 跳过（源不存在）：media <- {MEDIA_DIR}")
        records.append(_extra_record("media", "skipped", MEDIA_DIR, None))
    return records


def file_sha256(path: str) -> str:
    """流式 sha256：备份包里的库是几十 MB 级，不能整份读进内存。"""
    with open(path, "rb") as fh:
        return hashlib.file_digest(fh, "sha256").hexdigest()


def dir_stats(root: str) -> tuple[int, int, list]:
    """目录读数 ``(文件数, 总字节, [(posix 相对路径, 字节)])``。"""
    base = Path(root)
    sizes = [(p.relative_to(base).as_posix(), p.stat().st_size) for p in base.rglob("*") if p.is_file()]
    return len(sizes), sum(n for _, n in sizes), sorted(sizes)


def _sqlite_entry(out_dir: str, dest: str, source: str, integrity: str | None) -> dict:
    """一条 sqlite 条目 —— 哈希对象是**包内文件**，它要回答的是"这个包里到底有什么"。"""
    path = os.path.join(out_dir, dest)
    return {
        "kind": "sqlite",
        "dest": dest,
        "source": source,
        "bytes": os.path.getsize(path),
        "sha256": file_sha256(path),
        "integrity_check": integrity,
    }


def _file_entry(out_dir: str, dest: str, source: str) -> dict:
    """一条派生文件条目（``source`` = 它由哪个目录导出）。"""
    path = os.path.join(out_dir, dest)
    return {
        "kind": "file",
        "dest": dest,
        "source": source,
        "bytes": os.path.getsize(path),
        "sha256": file_sha256(path),
    }


def _dir_entry(out_dir: str, dest: str, hash_items: bool = False) -> dict:
    """一条目录条目。默认**不逐个哈希**：真实 chroma_db 362MB，哈希会把备份的 I/O 翻倍。"""
    n, total, per_file = dir_stats(os.path.join(out_dir, dest))
    entry = {"kind": "dir", "dest": dest, "files": n, "bytes": total}
    if hash_items:
        if n > MEDIA_ITEM_HASH_LIMIT:
            print("[Manifest] media 文件过多，仅记计数")
        else:
            entry["items"] = [
                {"path": rel, "bytes": size, "sha256": file_sha256(os.path.join(out_dir, dest, rel))}
                for rel, size in per_file
            ]
    return entry


def manifest_entries(
    out_dir: str,
    skip_chroma: bool,
    skip_chroma_export: bool,
    main_integrity: str | None,
    extra_records: list,
) -> list:
    """收集包内条目，**只来自本脚本显式创建的目标名**（不 walk 备份目录）。

    不 walk 的理由：``verify_sqlite`` 会在备份文件旁留 ``.verify.tmp``，它 ``finally`` 里删，
    但只要它自己抛异常就残留 —— walk 会把残留当成产物记进清单，等于给坏包发凭证。
    """
    by_dest = {rec["dest"]: rec for rec in extra_records}
    entries = [_sqlite_entry(out_dir, "app.db", DB_PATH, main_integrity)]
    if not skip_chroma:
        entries.append(_dir_entry(out_dir, "chroma_db"))
        if not skip_chroma_export:
            entries.append(_file_entry(out_dir, "chroma_index.json", CHROMA_DIR))
    entries += [
        _sqlite_entry(out_dir, name, by_dest[name]["source"], by_dest[name]["integrity_check"])
        for name in EXTRA_SQLITE
        if by_dest.get(name, {}).get("status") == "ok"
    ]
    if by_dest.get("media", {}).get("status") == "ok":
        entries.append(_dir_entry(out_dir, "media", hash_items=True))
    return sorted(entries, key=lambda e: e["dest"])


def write_manifest(out_dir: str, entries: list) -> str:
    """写 ``backup_manifest.json``（只在所有失败分支之后调用 —— 失败路径不落清单）。"""
    path = os.path.join(out_dir, MANIFEST_NAME)
    payload = {
        "version": 1,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "entries": entries,
    }
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=1)
    return path


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
    extra_records = backup_extras(out)
    extras = [(rec["dest"], rec["status"]) for rec in extra_records]
    if any(status == "failed" for _, status in extras):
        print("ERROR 附属产物备份失败，勿使用该备份包。")
        return 1

    # ---- 清单：走到这里才写 —— 上面每条 return 都是"包不可用"，坏包不该带一份看起来完整的凭证 ----
    entries = manifest_entries(
        out,
        args.skip_chroma,
        args.skip_chroma_export,
        msg,
        extra_records,
    )
    manifest = write_manifest(out, entries)
    print(f"[Manifest] {manifest}  entries={len(entries)}  " + " ".join(f"{e['dest']}:{e['kind']}" for e in entries))

    print(
        f"备份完成。恢复：停后端 → 照 {MANIFEST_NAME} 逐条把 dest 放回 source 位置（附属库放回 {DATA_DIR}/<包内名对应源>）→ 启动后验证检索。"
    )
    print("提示：备份前建议先 manage.py stop，避免运行中复制 Chroma 目录不一致。")
    return 0


if __name__ == "__main__":
    _check_env_contract()
    sys.exit(main())
