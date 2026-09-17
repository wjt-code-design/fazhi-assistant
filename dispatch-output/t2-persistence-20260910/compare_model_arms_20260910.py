"""多模型臂对比（同候选 / 同 10 题 / 唯一变量 = 模型 id）。

用法：python compare_model_arms_20260910.py [arm1 arm2 ...]
不传参则用默认三臂。臂的时间窗由 `run_evidence.upper_bound_for` 界定
（= 全部已知轮次中紧邻的下一轮 claim 起点；最后一个臂用格式一致的远期哨兵）。

⚠️ 三类已踩过的口径坑（**查询逻辑已收敛到 `backend/scripts/run_evidence.py`**，
   由 `tests/test_run_evidence.py` 锁死，本脚本不再手写 SQL）：
1. `agent_runs.id` 是 UUID 字符串，`ORDER BY id` 是字典序、**无意义** → 用 rowid / created_at。
2. `agent_runs.created_at` 声明为 DATETIME（NUMERIC 亲和性）⇒ 纯数字哨兵 `'9999'` 会退化为
   TEXT vs INTEGER 比较 ⇒ **恒 0 行**；上界必须用格式一致的字符串。
3. **预运行失败（如 ISSUE_DECOMPOSITION_INVALID）不产生 agent_run 记录**（handoff §7）⇒
   位置切分必然错位 → 用**会话首条用户消息 ⨯ 冻结题 initial_question 逐字匹配**定题号。
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
DEFAULT_ARMS = ["gate5-dev-run-13-qwen38", "gate5-dev-modelarm-qwen36", "gate5-dev-modelarm-longcat"]
SHORT = {"qwen38": "qwen3.8-flash", "qwen36": "qwen3.6-flash", "longcat": "LongCat-2.0"}

sys.path.insert(0, str(BACKEND))
os.chdir(BACKEND)

from scripts.run_evidence import (  # noqa: E402  —— 收敛到单一真源（勿再手写 SQL）
    claim_start,
    iter_arm_runs,
    squeeze,
    upper_bound_for,
)


def arm_label(arm: str) -> str:
    tail = arm.split("-")[-1]
    return SHORT.get(tail, tail)


def frozen() -> tuple[dict[str, str], dict[str, int]]:
    raw = json.loads((EV / "frozen-cases-v1.json").read_text(encoding="utf-8"))
    cases = raw if isinstance(raw, list) else raw.get("cases", raw)
    items = cases.items() if isinstance(cases, dict) else [(c["id"], c) for c in cases]
    qmap = {squeeze(case["initial_question"]): str(cid) for cid, case in items}
    req = {str(cid): len(case.get("required_issues") or []) for cid, case in items}
    return qmap, req


def judge(arm: str) -> str:
    path = EV / f"gate2-run-{arm}-sessions.json"
    proc = subprocess.run(
        [sys.executable, "scripts/gate5_judge.py", str(path)],
        cwd=BACKEND, capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    m = re.search(
        r"mechanical_pass_count=(\d+)\s+full_closure_pass_count=(\d+)\s+full_closure_denominator=(\d+)",
        proc.stdout or "",
    )
    return f"mechanical={m.group(1)}  full_closure={m.group(2)}/{m.group(3)}" if m else "judge 输出未匹配"


def sessions(arm: str) -> dict[str, Any]:
    return json.loads((EV / f"gate2-run-{arm}-sessions.json").read_text(encoding="utf-8"))["results"]


def collect_arm(con: sqlite3.Connection, arm: str, qmap: dict[str, str]) -> dict[str, dict[str, Any]]:
    """某臂窗口内的逐题引擎数据（题号按文本映射；缺失题 = 预运行失败，显式缺失）。"""
    lo = claim_start(arm, EV)
    hi = upper_bound_for(arm, EV)
    out: dict[str, dict[str, Any]] = {}
    for _rowid, run_id, conv, _created, state_json in iter_arm_runs(con, (lo, hi)):
        first = con.execute(
            "SELECT content FROM messages WHERE conversation_id=? AND role='user' ORDER BY id LIMIT 1",
            (conv,),
        ).fetchone()
        cid = qmap.get(squeeze(first["content"])) if first is not None else None
        if cid is None or cid in out:
            continue
        state = json.loads(state_json)
        issues = state.get("issues") or []
        linked = {
            o.get("issue_id")
            for o in (state.get("observations") or [])
            if o.get("status") == "succeeded" and o.get("evidence_ids")
        }
        backfill = con.execute(
            "SELECT COUNT(*) c FROM agent_steps WHERE agent_run_id=? AND decision='backfill_retrieval'",
            (run_id,),
        ).fetchone()[0]
        out[cid] = {
            "issues": len(issues),
            "covered": sum(1 for i in issues if i.get("issue_id") in linked),
            "backfill": bool(backfill),
        }
    return out


def main() -> None:
    arms = sys.argv[1:] or DEFAULT_ARMS
    qmap, req = frozen()
    con = sqlite3.connect(BACKEND / "app.db")
    con.row_factory = sqlite3.Row

    engine: dict[str, dict[str, dict[str, Any]]] = {a: {} for a in arms}
    for arm in arms:
        lo = claim_start(arm, EV)
        hi = upper_bound_for(arm, EV)
        for row in con.execute(
            "SELECT rowid,id,conversation_id,created_at,state_json FROM agent_runs "
            "WHERE created_at>=? AND created_at<? ORDER BY rowid",
            (lo, hi),
        ):
            first = con.execute(
                "SELECT content FROM messages WHERE conversation_id=? AND role='user' ORDER BY id LIMIT 1",
                (row["conversation_id"],),
            ).fetchone()
            cid = qmap.get(squeeze(first["content"])) if first is not None else None
            if cid is None:
                continue
            if cid in engine[arm]:
                continue
            state = json.loads(row["state_json"])
            issues = state.get("issues") or []
            linked = {
                o.get("issue_id")
                for o in (state.get("observations") or [])
                if o.get("status") == "succeeded" and o.get("evidence_ids")
            }
            bf = con.execute(
                "SELECT COUNT(*) c FROM agent_steps WHERE agent_run_id=? AND decision='backfill_retrieval'",
                (row["id"],),
            ).fetchone()[0]
            engine[arm][cid] = {
                "issues": len(issues),
                "covered": sum(1 for i in issues if i.get("issue_id") in linked),
                "backfill": bool(bf),
            }

    sess = {a: sessions(a) for a in arms}

    L: list[str] = []
    L.append("多模型臂对比（同候选 / 同 10 题 / 唯一变量 = 模型 id）")
    L.append(f"应有争点(冻结题 required_issues) 合计 = {sum(req.values())} 个")
    for a in arms:
        L.append(f"  {arm_label(a):<14} run={a}  窗口起点={claim_start(a, EV)}")
    L.append("题号映射：会话首条用户消息 ⨯ 冻结题 initial_question 逐字匹配（非位置切分）")
    L.append("")

    cellw = 26
    L.append(f"{'case':<5}{'应有':<5}|" + "|".join(f" {arm_label(a)[:cellw-1]:<{cellw}}" for a in arms))
    L.append(f"{'':<10}|" + "|".join(f" {'iss/cov/bf  err':<{cellw-1}}" for _ in arms))
    L.append("-" * (10 + (cellw + 1) * len(arms)))

    tot = {a: 0 for a in arms}
    comp = {a: 0 for a in arms}
    bfc = {a: 0 for a in arms}
    for cid in CASES:
        cells = []
        for a in arms:
            data = engine[a].get(cid)
            err = ",".join(sess[a].get(cid, {}).get("error_codes") or []) or "-"
            comp[a] += bool(sess[a].get(cid, {}).get("agent_completed"))
            if data is None:
                cells.append(f" {'无记录':<{cellw-1}}")
            else:
                tot[a] += data["issues"]
                bfc[a] += data["backfill"]
                txt = f"{data['issues']}/{data['covered']}/{'Y' if data['backfill'] else '-'} {err}"
                cells.append(f" {txt[:cellw-1]:<{cellw-1}}")
        L.append(f"{cid:<5}{req.get(cid,0):<5}|" + "|".join(cells))

    L.append("")
    n = sum(req.values())
    L.append(f"{'指标':<16}" + "".join(f"{arm_label(a):<20}" for a in arms))
    L.append(f"{'争点总数':<16}" + "".join(f"{tot[a]}（缺{100*(1-tot[a]/n):.0f}%）".ljust(20) for a in arms))
    L.append(f"{'agent_completed':<16}" + "".join(f"{comp[a]}/10".ljust(20) for a in arms))
    L.append(f"{'backfill 触发':<16}" + "".join(f"{bfc[a]}/10".ljust(20) for a in arms))
    L.append(f"{'两层 judge':<16}" + "".join(judge(a).ljust(20) for a in arms))
    L.append("")
    L.append("错误码分布（题次）：")
    for a in arms:
        hist: dict[str, int] = {}
        for cid in CASES:
            for code in sess[a].get(cid, {}).get("error_codes") or ["(无错误码)"]:
                hist[code] = hist.get(code, 0) + 1
        L.append(f"  {arm_label(a):<14} " + ", ".join(f"{k}={v}" for k, v in sorted(hist.items(), key=lambda kv: -kv[1])))

    out = pathlib.Path(__file__).parent / "model_arm_comparison_20260910.txt"
    out.write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L), flush=True)
    print(f"\n[log] {out}", flush=True)


if __name__ == "__main__":
    main()
