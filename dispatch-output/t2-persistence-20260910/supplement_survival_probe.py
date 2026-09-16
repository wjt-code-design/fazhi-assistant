"""§2.1 谜题探针（只读）：对 run-17 两臂逐题回答——每条 EVIDENCE_MISS 的 required 法条，
**注入到底触发没有**？（fired = 该题 issue 问句按映射表应注入且包含此法条）

  fired & absent  → 文档死在 retrieve_laws 与 state.evidence 之间（map_document/观测路径）★
  not-fired       → 关键词覆盖缺口（issue 问句没打中映射关键词）
"""

from __future__ import annotations

import json
import os
import pathlib
import sqlite3
import sys
from itertools import chain

HERE = pathlib.Path(__file__).resolve()
ROOT = HERE.parents[2]
BACKEND = ROOT / "backend"
EV = ROOT / "release-evidence" / "legal-agent-v1-complex-v1-20260907"

sys.path.insert(0, str(BACKEND))
os.chdir(BACKEND)

import domain_rules  # noqa: E402
from scripts.gate5_judge import _LAW_ALIAS, _cn_to_num  # noqa: E402
from scripts.run_evidence import case_by_conversation, claim_start, iter_arm_runs, squeeze, upper_bound_for  # noqa: E402

RUNS: list[tuple[str, str]] = [
    ("gate5-dev-run-17-qwen38-waxis", "frozen-cases-v1.json"),
    ("gate5-dev-run-17-holdout-waxis", "holdout-cases-v1.json"),
]


def reqs_of(req_file: str) -> tuple[dict[str, str], dict[str, dict]]:
    raw = json.loads((EV / req_file).read_text(encoding="utf-8"))
    cases = raw["cases"] if isinstance(raw, dict) else raw
    qmap, reqs = {}, {}
    for c in cases:
        cid = str(c["id"])
        qmap[squeeze(c["initial_question"])] = cid
        reqs[cid] = c
    return qmap, reqs


def main() -> None:
    con = sqlite3.connect(BACKEND / "app.db")
    con.row_factory = sqlite3.Row
    lines: list[str] = ["§2.1 探针：EVIDENCE_MISS 的 required 法条，注入触发了吗？", ""]
    summary = {"fired_absent": [], "not_fired": [], "fired_present": []}
    for run, req_file in RUNS:
        qmap, reqs = reqs_of(req_file)
        lo, hi = claim_start(run, EV), upper_bound_for(run, EV)
        states: dict[str, dict] = {}
        conv_issue_texts: dict[str, list[str]] = {}
        for _rid, _run_id, conv, _created, state_json in iter_arm_runs(con, (lo, hi)):
            cid = case_by_conversation(con, conv, qmap)
            if cid is None or cid in states:
                continue
            st = json.loads(state_json)
            states[cid] = st
            conv_issue_texts[cid] = [
                (i.get("question") or i.get("title") or "") for i in (st.get("issues") or [])
            ]
        sess_file = EV / f"gate2-run-{run}-sessions.json"
        sess = json.loads(sess_file.read_text(encoding="utf-8"))["results"] if sess_file.exists() else {}
        lines.append(f"### {run}（题集 {req_file}，case 数 {len(states)}）")
        for cid in sorted(states):
            st = states[cid]
            req = [(str(x[0]), int(x[1])) for x in (reqs.get(cid, {}).get("required_laws") or [])]
            # 注入触发集 = 该题所有 issue 问句按映射表应注入的法条（映射去重前合并）
            fired: set[tuple[str, int]] = set()
            for q in conv_issue_texts.get(cid, []):
                for d in domain_rules.statute_supplement_docs(q) or []:
                    law = _LAW_ALIAS.get(str(d.metadata.get("source", "")).strip(), str(d.metadata.get("source", "")).strip())
                    try:
                        num = _cn_to_num(str(d.metadata.get("article", "")))
                    except Exception:  # noqa: BLE001
                        continue
                    if num > 0:
                        fired.add((law, num))
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
            lines.append(f"  {cid}（issues={len(conv_issue_texts.get(cid, []) or [])}, 证据={len(st.get('evidence') or [])}）required={len(req)}")
            for law, n in req:
                in_ev = (law, n) in ev_nums
                was_fired = (law, n) in fired
                if in_ev:
                    cls = "present"
                    bucket = summary["fired_present"] if was_fired else summary["not_fired"]
                elif was_fired:
                    cls = "fired_absent ★"
                    bucket = summary["fired_absent"]
                else:
                    cls = "not_fired"
                    bucket = summary["not_fired"]
                bucket.append(f"{cid}:{law}{n}")
                lines.append(f"    {law}第{n}条 → {cls}{'（EVIDENCE_MISS）' if cls != 'present' else ''}")
        lines.append("")
    lines.append("### 汇总（仅 EVIDENCE_MISS 的条目）")
    lines.append(f"  fired_absent ★（注入触发了但没进证据）: {len(summary['fired_absent'])} → {summary['fired_absent']}")
    lines.append(f"  not_fired（关键词没打中，注入没触发）: {len(summary['not_fired'])} → {summary['not_fired']}")
    out = HERE.parent / "supplement-survival-probe.txt"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines[-14:]), flush=True)
    print(f"\n[log] {out}", flush=True)


if __name__ == "__main__":
    main()
