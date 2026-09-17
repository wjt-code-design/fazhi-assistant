"""T8 改动集的前后对照（同模型 qwen3.8-flash、同 10 题、唯一变量 = 候选）。

**V2-T8 收尾（2026-09-10）**：查询逻辑已收敛到 `backend/scripts/run_evidence.py`（单一真源）。
此前的手写 SQL 曾有三类口径 bug（UUID 字典序 / DATETIME 亲和性 / 预运行失败导致的位置错配），
现由 `run_evidence` 的被测实现统一承担（`tests/test_run_evidence.py` 锁死三条）。

基线 = gate5-dev-run-13-qwen38（T7 轮，改动前）　新轮 = gate5-dev-run-14-qwen38-t8（T8 改动后）
"""

from __future__ import annotations

import json
import os
import pathlib
import re
import sqlite3
import subprocess
import sys
from typing import Any

HERE = pathlib.Path(__file__).resolve()
ROOT = HERE.parents[2]
BACKEND = ROOT / "backend"
EV = ROOT / "release-evidence" / "legal-agent-v1-complex-v1-20260907"
CASES = [f"C{i:02d}" for i in range(1, 11)]
BASE = sys.argv[1] if len(sys.argv) > 1 else "gate5-dev-run-13-qwen38"
NEW = sys.argv[2] if len(sys.argv) > 2 else "gate5-dev-run-14-qwen38-t8"

sys.path.insert(0, str(BACKEND))
os.chdir(BACKEND)

from scripts.run_evidence import (  # noqa: E402  —— 收敛到单一真源（勿再手写 SQL）
    case_by_conversation,
    claim_start,
    iter_arm_runs,
    squeeze,
    upper_bound_for,
)


def question_map() -> dict[str, str]:
    raw = json.loads((EV / "frozen-cases-v1.json").read_text(encoding="utf-8"))
    cases = raw if isinstance(raw, list) else raw.get("cases", raw)
    items = cases.items() if isinstance(cases, dict) else [(c["id"], c) for c in cases]
    return {squeeze(case["initial_question"]): str(cid) for cid, case in items}


def required_issues() -> dict[str, int]:
    raw = json.loads((EV / "frozen-cases-v1.json").read_text(encoding="utf-8"))
    cases = raw if isinstance(raw, list) else raw.get("cases", raw)
    items = cases.items() if isinstance(cases, dict) else [(c["id"], c) for c in cases]
    return {str(cid): len(case.get("required_issues") or []) for cid, case in items}


def judge(arm: str) -> tuple[int, int, int]:
    proc = subprocess.run(
        [sys.executable, "scripts/gate5_judge.py", str(EV / f"gate2-run-{arm}-sessions.json")],
        cwd=BACKEND, capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    m = re.search(
        r"mechanical_pass_count=(\d+)\s+full_closure_pass_count=(\d+)\s+full_closure_denominator=(\d+)",
        proc.stdout or "",
    )
    return (int(m.group(1)), int(m.group(2)), int(m.group(3))) if m else (-1, -1, -1)


def collect(
    con: sqlite3.Connection,
    arm: str,
    qmap: dict[str, str],
    upper: str | None = None,
) -> dict[str, dict[str, Any]]:
    """逐题的 issues/steps/生效预算。窗口上界默认交给 `upper_bound_for`（防吞后续轮次）。"""
    lo = claim_start(arm, EV)
    hi = upper if upper is not None else upper_bound_for(arm, EV)
    out: dict[str, dict[str, Any]] = {}
    for _rowid, _run_id, conv, _created, state_json in iter_arm_runs(con, (lo, hi)):
        cid = case_by_conversation(con, conv, qmap)
        if cid is None or cid in out:
            continue  # 映射不上的 run 丢弃（不猜测题号）；重复题号保留先出现的
        state = json.loads(state_json)
        snap = con.execute(
            "SELECT budget_snapshot FROM agent_steps WHERE agent_run_id=? AND budget_snapshot IS NOT NULL "
            "ORDER BY id LIMIT 1",
            (_run_id,),
        ).fetchone()
        max_steps: int | None = None
        if snap is not None and snap["budget_snapshot"]:
            try:
                max_steps = json.loads(snap["budget_snapshot"]).get("max_steps")
            except Exception:  # noqa: BLE001
                max_steps = None
        out[cid] = {
            "issues": len(state.get("issues") or []),
            "steps": state.get("steps"),
            "max_steps": max_steps,
            "status": row_status(con, _run_id),
        }
    return out


def row_status(con: sqlite3.Connection, run_id: str) -> str:
    row = con.execute("SELECT status FROM agent_runs WHERE id=?", (run_id,)).fetchone()
    return row["status"] if row is not None else "?"


def sessions(arm: str) -> dict[str, Any]:
    return json.loads((EV / f"gate2-run-{arm}-sessions.json").read_text(encoding="utf-8"))["results"]


def main() -> None:
    con = sqlite3.connect(BACKEND / "app.db")
    con.row_factory = sqlite3.Row
    qmap = question_map()
    req = required_issues()
    base = collect(con, BASE, qmap)
    new = collect(con, NEW, qmap)
    sess_b, sess_n = sessions(BASE), sessions(NEW)

    L: list[str] = []
    L.append("T8 改动集前后对照（同模型 qwen3.8-flash / 同 10 题 / 唯一变量 = 候选）")
    L.append(f"  基线 BASE={BASE}（claim {claim_start(BASE, EV)}）")
    L.append(f"  新轮 NEW ={NEW}（claim {claim_start(NEW, EV)}）")
    L.append("")
    L.append(f"{'case':<5}{'应有':<5}| {'改动前 issues/steps/预算':<30}| {'改动后 issues/steps/预算':<30}| err(改后)")
    L.append("-" * 118)
    tb = tn = 0
    for cid in CASES:
        b, n = base.get(cid), new.get(cid)
        tb += b["issues"] if b else 0
        tn += n["issues"] if n else 0
        bs = f"{b['issues']}/{b['steps']}/{b['max_steps']}" if b else "无记录"
        ns = f"{n['issues']}/{n['steps']}/{n['max_steps']}" if n else "无记录"
        err = ",".join(sess_n.get(cid, {}).get("error_codes") or []) or "-"
        L.append(f"{cid:<5}{req.get(cid,0):<5}| {bs:<30}| {ns:<30}| {err[:26]}")
    total = sum(req.values())
    L.append("")
    L.append(f"争点总数：应有 {total} ｜ 改动前 {tb}（缺 {100*(1-tb/total):.0f}%）｜ 改动后 {tn}（缺 {100*(1-tn/total):.0f}%）")
    L.append(
        f"completed：改动前 {sum(1 for c in CASES if sess_b.get(c,{}).get('agent_completed'))}/10"
        f" ｜ 改动后 {sum(1 for c in CASES if sess_n.get(c,{}).get('agent_completed'))}/10"
    )
    jb, jn = judge(BASE), judge(NEW)
    L.append(
        f"两层 judge：改动前 mechanical={jb[0]} full_closure={jb[1]}/{jb[2]}"
        f" ｜ 改动后 mechanical={jn[0]} full_closure={jn[1]}/{jn[2]}"
    )
    L.append("")
    L.append("可机械推导的两项核对（**权威判据见本轮预登记文件**，不在此硬编码，避免残留过期措辞）：")
    L.append(f"  · 争点总数：{'上升 ✅' if tn > tb else ('持平' if tn == tb else '下降 ⚠️')}（{tb} → {tn}）")
    five = [c for c in CASES if (new.get(c) or {}).get("issues", 0) >= 5]
    five_done = [c for c in five if sess_n.get(c, {}).get("agent_completed")]
    L.append(f"  · ≥5 争点的题：{five or '无'}；其中 completed：{five_done or '无'}")
    L.append(
        f"  · 出现 AGENT_BUDGET_EXCEEDED 的题："
        f"{[c for c in CASES if 'AGENT_BUDGET_EXCEEDED' in (sess_n.get(c,{}).get('error_codes') or [])] or '无'}"
    )
    L.append("")
    L.append("错误码分布：")
    for label, sess in (("改动前", sess_b), ("改动后", sess_n)):
        hist: dict[str, int] = {}
        for cid in CASES:
            for code in sess.get(cid, {}).get("error_codes") or ["(无错误码)"]:
                hist[code] = hist.get(code, 0) + 1
        L.append(f"  {label}: " + ", ".join(f"{k}={v}" for k, v in sorted(hist.items(), key=lambda kv: -kv[1])))

    out = HERE.parent / f"comparison-{NEW}.txt"
    out.write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L), flush=True)
    print(f"\n[log] {out}", flush=True)


if __name__ == "__main__":
    main()
