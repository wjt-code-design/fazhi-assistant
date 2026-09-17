"""T7 逐题留证：为指定 run 的 10 题导出可复算的证据块（只读，不改任何数据）。

每题输出：
- runner 侧：error_codes / final_chars / agent_completed / rounds
- 引擎侧（app.db）：issues 数 / 证据覆盖 / backfill 是否触发 / 决策序列 / 终止决策
- judge 侧：机械层各项 + missing 法条 + unbound + redline（调用冻结 gate5_judge.py）

题号映射用「会话首条用户消息 ⨯ 冻结题 initial_question 逐字匹配」（预运行失败不落库，位置切分会错位）。
"""

from __future__ import annotations

import json
import pathlib
import re
import sqlite3
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
EV = ROOT / "release-evidence" / "legal-agent-v1-complex-v1-20260907"
CASES = [f"C{i:02d}" for i in range(1, 11)]
ARM = sys.argv[1] if len(sys.argv) > 1 else "gate5-dev-run-13-qwen38"


def norm(t: str) -> str:
    return re.sub(r"\s+", "", t or "")


def main() -> None:
    raw = json.loads((EV / "frozen-cases-v1.json").read_text(encoding="utf-8"))
    cases = raw if isinstance(raw, list) else raw.get("cases", raw)
    items = cases.items() if isinstance(cases, dict) else [(c["id"], c) for c in cases]
    qmap = {norm(c["initial_question"]): cid for cid, c in items}
    req = {cid: len(c.get("required_issues") or []) for cid, c in items}

    claim = json.loads((EV / f"gate2-run-{ARM}.claim.json").read_text(encoding="utf-8"))
    lo = claim["started_at"].replace("T", " ").replace("+00:00", "").split(".")[0]

    con = sqlite3.connect(BACKEND / "app.db")
    con.row_factory = sqlite3.Row

    by_case: dict[str, dict] = {}
    for row in con.execute(
        "SELECT rowid,id,conversation_id,status,state_version,created_at,state_json "
        "FROM agent_runs WHERE created_at>=? ORDER BY rowid",
        (lo,),
    ):
        first = con.execute(
            "SELECT content FROM messages WHERE conversation_id=? AND role='user' ORDER BY id LIMIT 1",
            (row["conversation_id"],),
        ).fetchone()
        cid = qmap.get(norm(first["content"])) if first else None
        if cid is None or cid in by_case:
            continue
        state = json.loads(row["state_json"])
        issues = state.get("issues") or []
        linked = {
            o.get("issue_id")
            for o in (state.get("observations") or [])
            if o.get("status") == "succeeded" and o.get("evidence_ids")
        }
        steps = con.execute(
            "SELECT id,state_version,decision,reason_code,tool_name FROM agent_steps "
            "WHERE agent_run_id=? ORDER BY id",
            (row["id"],),
        ).fetchall()
        by_case[cid] = {
            "run_id": row["id"],
            "conv": row["conversation_id"],
            "status": row["status"],
            "state_version": row["state_version"],
            "issues": len(issues),
            "covered": sum(1 for i in issues if i.get("issue_id") in linked),
            "tool_calls": state.get("tool_calls"),
            "steps": state.get("steps"),
            "clar": state.get("clarifications"),
            "backfill": any(s["decision"] == "backfill_retrieval" for s in steps),
            "trace": " › ".join(
                (s["decision"] or "?") for s in steps
            ),
            "last": (steps[-1]["decision"], steps[-1]["reason_code"]) if steps else (None, None),
            "n_steps": len(steps),
        }

    # sessions 可能不存在（例如 arm 被中途中止，只有 checkpoint）→ 回落到 checkpoint。
    sess_path = EV / f"gate2-run-{ARM}-sessions.json"
    ckpt_path = EV / f"gate2-run-{ARM}-checkpoint.json"
    if sess_path.exists():
        sess = json.loads(sess_path.read_text(encoding="utf-8"))["results"]
        partial_note = ""
    elif ckpt_path.exists():
        sess = json.loads(ckpt_path.read_text(encoding="utf-8")).get("results", {})
        partial_note = "> ⚠️ 无 `-sessions.json`（该 arm 被中途中止）→ runner 侧数据取自 checkpoint，**本文件为 PARTIAL**，不得当作整轮。\n"
    else:
        raise SystemExit(f"既无 sessions 也无 checkpoint：{ARM}")

    judge_lines: dict[str, str] = {}
    judge_summary = "(未跑 judge：无 sessions.json)"
    if sess_path.exists():
        proc = subprocess.run(
            [sys.executable, "scripts/gate5_judge.py", str(sess_path)],
            cwd=BACKEND, capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
        judge_lines = {m.group(1): m.group(0) for m in re.finditer(r"^\[(C\d\d)\].*$", proc.stdout or "", re.M)}
        tail = re.search(r"mechanical_pass_count=.*", proc.stdout or "")
        judge_summary = f"`{tail.group(0)}`" if tail else "(judge 输出未匹配)"

    L: list[str] = []
    L.append(f"# T7 逐题留证 — run `{ARM}`")
    L.append("")
    if partial_note:
        L.append(partial_note)
    for cid in CASES:
        s = sess.get(cid, {})
        e = by_case.get(cid)
        L.append(f"### {cid}")
        L.append(f"- runner: rounds={len(s.get('rounds') or [])} final_chars={s.get('final_chars')} "
                 f"completed={s.get('agent_completed')} errors={s.get('error_codes') or []}")
        if e is None:
            L.append("- 引擎侧：**无 agent_run 记录**（预运行失败，未 create_run）")
            L.append(f"- judge: {judge_lines.get(cid, '(无)')}")
            L.append("")
            continue
        L.append(f"- 引擎侧：run={e['run_id'][:8]} conv={e['conv']} status={e['status']} v={e['state_version']} "
                 f"| issues={e['issues']}/{req.get(cid, 0)} 覆盖={e['covered']} backfill={'Y' if e['backfill'] else '-'} "
                 f"clar={e['clar']} tools={e['tool_calls']} steps={e['steps']}")
        L.append(f"- 结束于：`{e['last'][0]}` / `{e['last'][1]}`（共 {e['n_steps']} 步）")
        L.append(f"- 决策序列：{e['trace']}")
        L.append(f"- judge: {judge_lines.get(cid, '(无)')}")
        L.append("")

    L.append(f"## judge 汇总\n\n{judge_summary}")

    out = pathlib.Path(__file__).parent / f"t7-per-case-evidence-{ARM}.md"
    out.write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L), flush=True)
    print(f"\n[log] {out}", flush=True)


if __name__ == "__main__":
    main()
