"""只读探查：B1/B3 复算所需的 DB schema 与证据文件结构。
不做任何计算，只摸清数据形态，为独立复算做准备。
"""

from __future__ import annotations

import json
import pathlib
import sqlite3

BACKEND = pathlib.Path(__file__).resolve().parents[2] / "backend"
EV = BACKEND.parent / "release-evidence" / "legal-agent-v1-complex-v1-20260907"

print("=" * 72)
print("DB schema")
print("=" * 72)
con = sqlite3.connect(f"file:{BACKEND / 'app.db'}?mode=ro", uri=True)
con.row_factory = sqlite3.Row
for row in con.execute(
    "SELECT name, sql FROM sqlite_master WHERE type='table' "
    "AND name IN ('agent_runs','messages') ORDER BY name"
):
    print(f"--- {row['name']} ---")
    print(row["sql"])
    print()

print("--- agent_runs 行数 / messages 行数 ---")
print("  agent_runs =", con.execute("SELECT COUNT(*) c FROM agent_runs").fetchone()["c"])
print("  messages   =", con.execute("SELECT COUNT(*) c FROM messages").fetchone()["c"])
print()
print("--- agent_runs 样例 1 行（列名 + 值前 60 字符）---")
r = con.execute("SELECT * FROM agent_runs ORDER BY rowid DESC LIMIT 1").fetchone()
for k in r.keys():
    v = str(r[k])
    print(f"  {k:<20} = {v[:60]}{'…' if len(v) > 60 else ''}")
print()
print("--- created_at 形态（最早/最晚）---")
print("  min =", con.execute("SELECT MIN(created_at) v FROM agent_runs").fetchone()["v"])
print("  max =", con.execute("SELECT MAX(created_at) v FROM agent_runs").fetchone()["v"])
print("  typeof(created_at) =", con.execute(
    "SELECT DISTINCT typeof(created_at) v FROM agent_runs").fetchall()[0]["v"])
print()
print("--- messages 表 role 分布 ---")
for row in con.execute("SELECT role, COUNT(*) c FROM messages GROUP BY role ORDER BY c DESC"):
    print(f"  {row['role']:<12} {row['c']}")
print()
print("--- messages.id 形态 ---")
r = con.execute("SELECT id, conversation_id, role FROM messages LIMIT 3").fetchall()
for row in r:
    print(f"  id={row['id']!r} conv={str(row['conversation_id'])[:20]!r} role={row['role']}")

print()
print("=" * 72)
print("claim.json started_at")
print("=" * 72)
arms = [
    "gate5-dev-run-13-qwen38",
    "gate5-dev-modelarm-qwen36",
    "gate5-dev-run-14-qwen38-t8",
    "gate5-dev-run-15-qwen38-t8b",
]
for a in arms:
    p = EV / f"gate2-run-{a}.claim.json"
    d = json.loads(p.read_text(encoding="utf-8"))
    print(f"  {a:<34} started_at={d.get('started_at')}")
    if a == arms[0]:
        print(f"      keys: {sorted(d.keys())}")

print()
print("=" * 72)
print("frozen-cases-v1.json 结构")
print("=" * 72)
raw = json.loads((EV / "frozen-cases-v1.json").read_text(encoding="utf-8"))
print(f"  顶层类型 = {type(raw).__name__}")
if isinstance(raw, dict):
    print(f"  顶层键   = {sorted(raw.keys())[:12]}")
    cases = raw.get("cases", raw)
else:
    cases = raw
print(f"  cases 类型 = {type(cases).__name__}")
items = cases.items() if isinstance(cases, dict) else [(c.get("id"), c) for c in cases]
items = list(items)
print(f"  题数 = {len(items)}")
for cid, c in items[:3]:
    print(f"    cid={cid!r} keys={sorted(c.keys())[:8]}")
    q = c.get("initial_question", "")
    print(f"      initial_question[:70] = {q[:70]!r}")

print()
print("=" * 72)
print("sessions.json 结构（B3 用）")
print("=" * 72)
for run in ("gate5-dev-run-14-qwen38-t8", "gate5-dev-run-15-qwen38-t8b"):
    p = EV / f"gate2-run-{run}-sessions.json"
    d = json.loads(p.read_text(encoding="utf-8"))
    print(f"--- {run} ---")
    print(f"  顶层键 = {sorted(d.keys())}")
    res = d.get("results")
    print(f"  results 类型 = {type(res).__name__}，条目数 = "
          f"{len(res) if res is not None else 0}")
    if isinstance(res, dict):
        k0 = sorted(res.keys())[0]
        print(f"  results[{k0!r}] 键 = {sorted(res[k0].keys())}")
        print(f"    error_codes = {res[k0].get('error_codes')}")
    print()
