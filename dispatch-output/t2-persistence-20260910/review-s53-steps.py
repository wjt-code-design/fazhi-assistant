"""只读核查：run-15 各题 steps 明细 + full_closure 的真实来源。

目的：
  1) 定位 §5.3 "5 争点需 19 步" 究竟对应哪一题（run-15 C08 实测 4 争点 / 16 步）；
  2) 查明 §5.1 声称的 full_closure = 0/10 由哪个产物提供（sessions/checkpoint 均无此字段）。
"""

from __future__ import annotations

import json
import pathlib
import re
import sqlite3

ROOT = pathlib.Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
EV = ROOT / "release-evidence" / "legal-agent-v1-complex-v1-20260907"


def claim_start(arm: str) -> str:
    d = json.loads((EV / f"gate2-run-{arm}.claim.json").read_text(encoding="utf-8"))
    return d["started_at"].replace("T", " ").replace("+00:00", "").split(".")[0]


raw = json.loads((EV / "frozen-cases-v1.json").read_text(encoding="utf-8"))
cases = raw["cases"] if isinstance(raw, dict) and "cases" in raw else raw
qmap = {re.sub(r"\s+", "", c["initial_question"]): str(c["id"]) for c in cases}
con = sqlite3.connect(f"file:{BACKEND / 'app.db'}?mode=ro", uri=True)
con.row_factory = sqlite3.Row

RUNS = [
    ("run-13", "gate5-dev-run-13-qwen38", "2026-09-10 07:34:01"),
    ("run-14", "gate5-dev-run-14-qwen38-t8", "2026-09-10 10:37:52"),
    ("run-15", "gate5-dev-run-15-qwen38-t8b", "2099-12-31 23:59:59"),
]

def size(v) -> tuple[str, int]:
    """steps 在不同轮次形态不同：list（明细）或 int（计数器）。两者都要如实报告。"""
    if v is None:
        return "none", 0
    if isinstance(v, int):
        return "int", v
    if isinstance(v, (list, dict)):
        return "list", len(v)
    return type(v).__name__, -1


for label, arm, hi in RUNS:
    lo = claim_start(arm)
    print("=" * 78)
    print(f"{label}  窗口 [{lo}, {hi})")
    print("=" * 78)
    print(f"  {'题':<6}{'issues':>7}{'steps':>7}{'(形态)':>8}"
          f"{'tool_calls':>11}{'state_ver':>10}  status")
    hits = []
    for r in con.execute(
        "SELECT conversation_id,status,state_version,state_json FROM agent_runs "
        "WHERE created_at>=? AND created_at<? ORDER BY rowid",
        (lo, hi),
    ):
        f = con.execute(
            "SELECT content FROM messages WHERE conversation_id=? AND role='user' "
            "ORDER BY id LIMIT 1",
            (r["conversation_id"],),
        ).fetchone()
        cid = qmap.get(re.sub(r"\s+", "", f["content"])) if f and f["content"] else None
        st = json.loads(r["state_json"])
        ni = len(st.get("issues") or [])
        skind, ns = size(st.get("steps"))
        tkind, nt = size(st.get("tool_calls"))
        print(f"  {cid or '(未映射)':<6}{ni:>7}{ns:>7}{skind:>8}"
              f"{nt:>11}{r['state_version']:>10}  {r['status']}")
        if ni == 5:
            hits.append((cid, ns, skind, r["state_version"]))
    if hits:
        print(f"  >>> issues=5 的题: {hits}")
    print()

print("=" * 78)
print("full_closure 的真实来源（gate5_judge.py 为冻结物）")
print("=" * 78)
gj = BACKEND / "scripts" / "gate5_judge.py"
text = gj.read_text(encoding="utf-8")
for i, line in enumerate(text.splitlines(), 1):
    if "full_closure" in line:
        print(f"  L{i}: {line.rstrip()}")
print()
print("--- release-evidence 下是否存在 gate5 judge 产物 ---")
cands = sorted(
    p.relative_to(ROOT).as_posix()
    for p in EV.rglob("*")
    if p.is_file() and ("judge" in p.name.lower() or "closure" in p.name.lower())
)
print(f"  命中 {len(cands)} 个")
for c in cands[:25]:
    print(f"    {c}")
