"""writer 轴验收审计（只读）：逐 required 法条判定断链层，并输出双集 HIT 率与预登记判定。

required 法条来源（与 run 对应）：
  - 评测集 run → frozen-cases-v1.json
  - 留出集 run → holdout-cases-v1.json（SHA256 734f0f11…44cd7d2，冻结于实现之前）
引用提取用 gate5_judge._extract_citations（冻结的权威规范化，与 judge 同口径）。
"""

from __future__ import annotations

import json
import os
import pathlib
import sqlite3
import sys
from collections import Counter

HERE = pathlib.Path(__file__).resolve()
ROOT = HERE.parents[2]
BACKEND = ROOT / "backend"
EV = ROOT / "release-evidence" / "legal-agent-v1-complex-v1-20260907"

sys.path.insert(0, str(BACKEND))
os.chdir(BACKEND)

from scripts.gate5_judge import _LAW_ALIAS, _cn_to_num, _extract_citations  # noqa: E402
from scripts.run_evidence import (  # noqa: E402
    case_by_conversation,
    claim_start,
    iter_arm_runs,
    squeeze,
    upper_bound_for,
)

RUNS: list[tuple[str, str]] = [
    ("gate5-dev-run-15-qwen38-t8b", "frozen-cases-v1.json"),
    ("gate5-dev-run-17-qwen38-waxis", "frozen-cases-v1.json"),
    ("gate5-dev-run-17-holdout-waxis", "holdout-cases-v1.json"),
]


def requirements(req_file: str) -> tuple[dict[str, str], dict[str, dict]]:
    raw = json.loads((EV / req_file).read_text(encoding="utf-8"))
    cases = raw["cases"] if isinstance(raw, dict) else raw
    qmap: dict[str, str] = {}
    reqs: dict[str, dict] = {}
    for c in cases:
        cid = str(c["id"])
        qmap[squeeze(c["initial_question"])] = cid
        reqs[cid] = c
    return qmap, reqs


def collect(con: sqlite3.Connection, run: str, qmap: dict[str, str]) -> dict[str, dict]:
    lo, hi = claim_start(run, EV), upper_bound_for(run, EV)
    out: dict[str, dict] = {}
    for _rid, _run_id, conv, _created, state_json in iter_arm_runs(con, (lo, hi)):
        cid = case_by_conversation(con, conv, qmap)
        if cid is None or cid in out:
            continue
        out[cid] = json.loads(state_json)
    return out


def audit(
    con: sqlite3.Connection, run: str, req_file: str, lines: list[str], totals: Counter
) -> dict[str, int]:
    qmap, reqs = requirements(req_file)
    states = collect(con, run, qmap)
    sess_file = EV / f"gate2-run-{run}-sessions.json"
    sess = json.loads(sess_file.read_text(encoding="utf-8"))["results"] if sess_file.exists() else {}
    lines.append(f"### {run}（题集 {req_file}，状态记录 {len(states)} 题）")
    agg: Counter = Counter()
    for cid in sorted(states):
        st = states[cid]
        req = [(str(x[0]), int(x[1])) for x in (reqs.get(cid, {}).get("required_laws") or [])]
        ev_nums: set[tuple[str, int]] = set()
        for e in st.get("evidence") or []:
            if str(e.get("source_type", "")).lower() == "statute":
                ref = e.get("source_ref") or e.get("source_id") or ""
                if "#" in ref:
                    law, art = ref.split("#", 1)
                    law = _LAW_ALIAS.get(law.strip(), law.strip())
                    try:
                        num = _cn_to_num(art.strip())
                    except Exception:  # noqa: BLE001
                        continue
                    if num > 0:
                        ev_nums.add((law, num))
        final = (sess.get(cid) or {}).get("final_text") or ""
        cited = set(_extract_citations(final))
        lines.append(
            f"  {cid}（issues={len(st.get('issues') or [])}, 证据={len(st.get('evidence') or [])}）required={len(req)}"
        )
        for law, n in req:
            if (law, n) in cited:
                cls = "HIT"
            elif (law, n) in ev_nums:
                cls = "WRITER_MISS"
            else:
                cls = "EVIDENCE_MISS"
            agg[cls] += 1
            lines.append(f"    {law}第{n}条 → {cls}")
    lines.append(f"  小计: {dict(agg)}")
    lines.append("")
    totals.update(agg)
    return dict(agg)


def main() -> None:
    con = sqlite3.connect(BACKEND / "app.db")
    con.row_factory = sqlite3.Row
    lines: list[str] = ["writer 轴验收审计（双集 + 预登记判定）", ""]
    totals: Counter = Counter()
    results: dict[str, dict[str, int]] = {}
    for run, req_file in RUNS:
        results[run] = audit(con, run, req_file, lines, totals)
    lines.append("### 预登记判定（waxis-verification-preregistration.json）")
    base = results.get("gate5-dev-run-15-qwen38-t8b", {})
    ev = results.get("gate5-dev-run-17-qwen38-waxis", {})
    ho = results.get("gate5-dev-run-17-holdout-waxis", {})

    def rate(d: dict[str, int]) -> tuple[int, int, float]:
        n = sum(d.values())
        hit = d.get("HIT", 0)
        return hit, n, (hit / n * 100 if n else 0.0)

    b_hit, b_n, b_rate = rate(base)
    e_hit, e_n, e_rate = rate(ev)
    h_hit, h_n, h_rate = rate(ho)
    lines.append(f"  基线 run-15（评测集） : HIT {b_hit}/{b_n} = {b_rate:.0f}%")
    lines.append(f"  本轮 run-17（评测集） : HIT {e_hit}/{e_n} = {e_rate:.0f}%")
    if h_n:
        lines.append(f"  本轮 run-17（留出集） : HIT {h_hit}/{h_n} = {h_rate:.0f}%")
    lines.append("")
    ok1 = e_rate > 32.0
    lines.append(f"  命题①评测集 HIT 上升（>32%）  : {'✅ 未被证伪' if ok1 else '❌ 被证伪'}")
    if h_n:
        ok2 = h_rate >= e_rate - 10.0
        lines.append(f"  命题②泛化（留出 ≥ 评测−10pp）: {'✅ 未被证伪' if ok2 else '❌ 判过拟合'}")
    else:
        lines.append("  命题②泛化                    : 悬置（留出集无记录）")
    lines.append(f"  WRITER_MISS 合计              : {totals.get('WRITER_MISS', 0)}（预登记守卫：必须 = 0）")
    lines.append(f"  EVIDENCE_MISS 合计            : {totals.get('EVIDENCE_MISS', 0)}")

    out = HERE.parent / "writer-axis-verification.txt"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines[-30:]), flush=True)
    print(f"\n[log] {out}", flush=True)


if __name__ == "__main__":
    main()
