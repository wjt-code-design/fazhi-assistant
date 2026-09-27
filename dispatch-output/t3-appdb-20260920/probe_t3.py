"""T3 只读读数脚本（绝对只读）。

只做一件事：用 open(path, 'rb').read(100) 纯字节读 SQLite 头部，外加 os.stat 取 size/mtime。
绝不 import sqlite3、绝不 connect、绝不开事务、绝不 VACUUM、绝不改 schema —— §0 边界要求。

读取目标（两份 app.db + 一份配额库，按真实路径区分，不靠"宿主/容器内"这种会漂移的标签）：
  1. backend/app.db            —— backend 根目录那份（live uvicorn 默认回落 DATABASE_URL 指向它）
  2. backend/data/app.db       —— backend/data 下那份（docker-compose 把容器 /data/app.db 挂到这里）
  3. backend/data/quota_used.sqlite

用法：backend/venv/Scripts/python.exe probe_t3.py <label>
产物：t3-appdb-20260920/readings-<label>.json（同时打印到 stdout）
"""

from __future__ import annotations

import datetime
import json
import pathlib
import struct
import sys

REPO = pathlib.Path(r"C:\Users\33393\Desktop\ai-legal-helper")
OUT = REPO / "dispatch-output" / "t3-appdb-20260920"

# 用真实路径做键，避免"宿主/容器内"标签歧义。
TARGETS = {
    "backend/app.db": REPO / "backend" / "app.db",
    "backend/data/app.db": REPO / "backend" / "data" / "app.db",
    "backend/data/quota_used.sqlite": REPO / "backend" / "data" / "quota_used.sqlite",
}

MAGIC = b"SQLite format 3\x00"


def human_mtime(secs: float) -> str:
    return (
        datetime.datetime.fromtimestamp(secs, tz=datetime.timezone.utc)
        .astimezone()
        .strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    )


def read_one(name: str, path: pathlib.Path) -> dict:
    rec = {"name": name, "path": str(path)}
    if not path.exists():
        rec["exists"] = False
        return rec
    rec["exists"] = True
    st = path.stat()
    with path.open("rb") as fh:
        head = fh.read(100)
    rec["size_bytes"] = st.st_size
    rec["mtime_epoch"] = st.st_mtime
    rec["mtime_human"] = human_mtime(st.st_mtime)
    if len(head) >= 100:
        rec["magic_ok"] = head[0:16] == MAGIC
        rec["page_size"] = struct.unpack(">H", head[16:18])[0]
        rec["read_format"] = head[18]
        rec["write_format"] = head[19]
        rec["change_counter"] = struct.unpack(">I", head[24:28])[0]
        rec["schema_cookie"] = struct.unpack(">I", head[40:44])[0]
        rec["version_valid_for"] = struct.unpack(">I", head[92:96])[0]
        # WAL 模式判定：write_format>=2 即曾经/当前 WAL
        rec["wal_mode"] = head[19] >= 2
        # 头部自洽：change_counter == version_valid_for 说明头页没撕裂
        rec["header_synced"] = rec["change_counter"] == rec["version_valid_for"]
    else:
        rec["magic_ok"] = False
        rec["header_truncated"] = True
    return rec


def main() -> int:
    label = sys.argv[1] if len(sys.argv) > 1 else "unlabeled"
    # 按固定顺序读取，避免任何"探测顺序"带来的偏差
    data = {name: read_one(name, p) for name, p in TARGETS.items()}
    out = OUT / f"readings-{label}.json"
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(data, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
