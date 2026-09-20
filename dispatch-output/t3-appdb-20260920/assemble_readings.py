"""T3 readings 汇总：读入 readings-r1.json / readings-r2.json，输出唯一交付件 readings.json。

只做文件读取与 JSON 组装，零写库、零 git、零 backend 改动。
"""

from __future__ import annotations

import datetime
import json
import pathlib

OUT = pathlib.Path(
    r"C:\Users\33393\Desktop\ai-legal-helper\dispatch-output\t3-appdb-20260920"
)
r1 = json.loads((OUT / "readings-r1.json").read_text(encoding="utf-8"))
r2 = json.loads((OUT / "readings-r2.json").read_text(encoding="utf-8"))

# 对齐判定：两次读数逐字段相同（cc/size/mtime 是关键判据）
aligned = True
diffs = []
for name in r1:
    for k in (
        "change_counter",
        "size_bytes",
        "mtime_epoch",
        "wal_mode",
        "header_synced",
        "exists",
    ):
        if r1[name].get(k) != r2[name].get(k):
            aligned = False
            diffs.append((name, k, r1[name].get(k), r2[name].get(k)))


# 与生产真源 / 是否今天被写的判定（按真实路径，不靠"宿主/容器内"标签）
def derive(name: str, rec: dict) -> dict:
    d = {"path": rec["path"]}
    if not rec.get("exists"):
        d["note"] = "文件不存在"
        return d
    d["change_counter"] = rec["change_counter"]
    d["size_bytes"] = rec["size_bytes"]
    d["mtime_human"] = rec["mtime_human"]
    d["wal_mode"] = rec["wal_mode"]
    d["header_synced"] = rec["header_synced"]
    # 非 WAL 库：每提交一个事务 cc 必增 → cc 不变即没有写事务
    d["no_write_since_mtime"] = rec["change_counter"] == rec["version_valid_for"]
    return d


derived = {name: derive(name, r1[name]) for name in r1}

payload = {
    "task": "t3-appdb-20260920",
    "method": "open(path,'rb').read(100) 纯字节读 SQLite 头 + os.stat；未 import sqlite3 / 未 connect / 未开事务 / 未 VACUUM / 未改 schema",
    "reading_r1_at": "2026-09-20 (see readings-r1.json mtime)",
    "reading_r2_at": "2026-09-20 (see readings-r2.json mtime)",
    "alignment": {
        "aligned": aligned,
        "diffs": diffs,
        "verdict": "两次读数对齐，终止条件满足"
        if aligned
        else "两次读数不一致，需复核",
    },
    "readings_r1": r1,
    "readings_r2": r2,
    "derived": derived,
    "assembled_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
}

(OUT / "readings.json").write_text(
    json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
)
print("readings.json written. aligned =", aligned, "| diffs =", diffs)
