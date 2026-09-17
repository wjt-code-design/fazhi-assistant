"""只读核查 §5.1（full_closure）与 §5.3（"5 争点需 19 步"= run-15 C08）。

§5.3 潜在矛盾：B1 复算 run-15 C08 = 4 争点，而 §5.3 称"5 争点需 19 步（run-15 C08）"。
本脚本从 DB 取 C08 在 run-15 窗口的 state_json，直接数 issues 与 steps。
"""

from __future__ import annotations

import json
import pathlib
import re
import sqlite3

ROOT = pathlib.Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
EV = ROOT / "release-evidence" / "legal-agent-v1-complex-v1-20260907"

RUN15 = "gate5-dev-run-15-qwen38-t8b"
RUN14 = "gate5-dev-run-14-qwen38-t8"


def claim_start(arm: str) -> str:
    d = json.loads((EV / f"gate2-run-{arm}.claim.json").read_text(encoding="utf-8"))
    return d["started_at"].replace("T", " ").replace("+00:00", "").split(".")[0]


def norm(s: str) -> str:
    return re.sub(r"\s+", "", s)


raw = json.loads((EV / "frozen-cases-v1.json").read_text(encoding="utf-8"))
cases = raw["cases"] if isinstance(raw, dict) and "cases" in raw else raw
qmap = {norm(c["initial_question"]): str(c["id"]) for c in cases}

con = sqlite3.connect(f"file:{BACKEND / 'app.db'}?mode=ro", uri=True)
con.row_factory = sqlite3.Row

print("=" * 74)
print("§5.1 — full_closure 字段定位（checkpoint.json results）")
print("=" * 74)
for label, run in (("run-14", RUN14), ("run-15", RUN15)):
    d = json.loads((EV / f"gate2-run-{run}-checkpoint.json").read_text(encoding="utf-8"))
    res = d["results"]
    print(f"--- {label} checkpoint.results ---")
    print(f"    条目数 = {len(res)}")
    k0 = sorted(res.keys())[0]
    v0 = res[k0]
    if isinstance(v0, dict):
        print(f"    results[{k0}] 键 = {sorted(v0.keys())}")
        for k, v in sorted(v0.items()):
            sv = str(v)
            print(f"        {k:<32} = {sv[:70]}{'…' if len(sv) > 70 else ''}")
    else:
        print(f"    results[{k0}] = {v0!r}")
    # 统计 full_closure
    if isinstance(v0, dict):
        for cand in ("full_closure", "closure", "fully_closed"):
            if cand in v0:
                n = sum(1 for v in res.values() if v.get(cand))
                print(f"    >>> {cand} = {n}/{len(res)}")
    print()

print("=" * 74)
print("§5.3 — run-15 C08：争点数与步数（直接查 DB）")
print("=" * 74)
lo = claim_start(RUN15)
hi = "2099-12-31 23:59:59"
print(f"  窗口 = [{lo}, {hi})")
rows = con.execute(
    "SELECT rowid, id, conversation_id, status, state_version, created_at, state_json "
    "FROM agent_runs WHERE created_at>=? AND created_at<? ORDER BY rowid",
    (lo, hi),
).fetchall()
print(f"  窗口内 agent_runs 行数 = {len(rows)}")
print()
for r in rows:
    f = con.execute(
        "SELECT content FROM messages WHERE conversation_id=? AND role='user' "
        "ORDER BY id LIMIT 1",
        (r["conversation_id"],),
    ).fetchone()
    cid = qmap.get(norm(f["content"])) if f and f["content"] else None
    st = json.loads(r["state_json"])
    issues = st.get("issues") or []
    steps = st.get("steps") or st.get("history") or st.get("trace") or []
    budgets = st.get("budgets") or {}
    if cid == "C08" or cid is None:
        print(f"  rowid={r['rowid']} conv={r['conversation_id']} cid={cid} status={r['status']}")
        print(f"      state_version={r['state_version']} created_at={r['created_at']}")
        print(f"      issues 数 = {len(issues)}")
        print(f"      state_json 顶层键 = {sorted(st.keys())}")
        print(f"      budgets = {budgets}")
        for k in ("steps", "history", "trace", "tool_calls", "actions"):
            if k in st:
                v = st[k]
                print(f"      {k} 长度 = {len(v) if isinstance(v, (list, dict)) else v}")
        print()

print("--- run-15 全部题的 issues 数与可用步数字段 ---")
for r in rows:
    f = con.execute(
        "SELECT content FROM messages WHERE conversation_id=? AND role='user' "
        "ORDER BY id LIMIT 1",
        (r["conversation_id"],),
    ).fetchone()
    cid = qmap.get(norm(f["content"])) if f and f["content"] else None
    st = json.loads(r["state_json"])
    issues = st.get("issues") or []
    stepish = {k: len(v) for k, v in st.items()
               if isinstance(v, list) and k not in ("issues", "messages")}
    print(f"  {cid or '(未映射)':<10} issues={len(issues):<3} 列表型字段长度={stepish}")
