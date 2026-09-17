# -*- coding: utf-8 -*-
"""baseline-v2 结果采集与判定（确定性金标，不用 LLM judge）。多源合并：

run-1（宿主 18126）：C01-C08 有效；C09/C10 与 E 系全部为宿主连接池污染的
技术失败（APIConnectionError→PLANNER_PARSE_ERROR），不作能力信号。
run-2（宿主 18127，连接池干净）：重跑 C09/C10 + E01-E10，优先采用。

判定（工程侧 0/1，语义侧仅记录）：
- agent_completed / rounds / error_codes / 红线（>2 轮）
- required_in_pool：required_laws ⊆ 本案例证据池 source_ref（端到端并集口径）
- forbidden_cited：forbidden_articles 出现在终稿《法名》第X条引用 → FAIL
- scope 一致性：澄清 prompt 含「本次请求分解出」 ↔ 案例 scope_trigger
输出 baseline-verdict.json（UTF-8）。
"""
from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
RUN1_DIR = REPO / "dispatch-output" / "agent-baseline-v2-20260913"
RUN2_DIR = REPO / "dispatch-output" / "agent-baseline-v2-r2-20260913"
RUN3_DIR = REPO / "dispatch-output" / "agent-baseline-v2-r3-20260913"
SOURCES = [
    (RUN3_DIR / "gate2-run-baseline-v2-d-sessions.json", RUN3_DIR / "evaluation.sqlite", "run-4"),
    (RUN3_DIR / "gate2-run-baseline-v2-c-sessions.json", RUN3_DIR / "evaluation.sqlite", "run-3"),
    (RUN2_DIR / "gate2-run-baseline-v2-b-sessions.json", RUN2_DIR / "evaluation.sqlite", "run-2"),
    (RUN1_DIR / "gate2-run-baseline-v2-20260913-sessions.json", RUN1_DIR / "evaluation.sqlite", "run-1"),
]
# 各 run 中判定为非能力信号的案例（连接故障窗口 / 旧 runner scope 协议盲区），跳过等后续有效数据
TECH_SKIP = {
    "run-1": {"C09", "C10"} | {f"E{i:02d}" for i in range(1, 11)},
    "run-2": {"E02"} | {f"E{i:02d}" for i in range(6, 11)},
    "run-3": {"E06"},
}

CASES = json.loads((REPO / "evals" / "frozen-cases-v2.json").read_text(encoding="utf-8"))["cases"]
BY_ID = {c["id"]: c for c in CASES}

_ART_RE = re.compile(r"[《【]([^》】]+)[》】]\s*(第[零〇○一二三四五六七八九十百千万0-9]+条(?:之[零〇一二三四五六七八九十百千万0-9]+)?)")


def _num_to_cn(n: int) -> str:
    """标准中文数字（与 KB article 存储形态一致：122→一百二十二、51→五十一）。"""
    digits = "零一二三四五六七八九"
    if n < 10:
        return digits[n]
    units = ["", "十", "百", "千"]
    s = str(n)
    parts: list[str] = []
    for i, ch in enumerate(s):
        d = int(ch)
        pos = len(s) - 1 - i
        if d == 0:
            if parts and any(int(c) for c in s[i + 1:]):
                parts.append("零")
        else:
            parts.append(digits[d] + units[pos])
    out = "".join(parts).replace("零零", "零")
    return out[1:] if out.startswith("一十") else out


def _judge(cid: str, r: dict, case: dict, cur) -> dict:
    pool: set[str] = set()
    conv_id = r.get("conv_id")
    if conv_id:
        for (prov,) in cur.execute(
            "SELECT DISTINCT e.provenance FROM agent_evidence e "
            "JOIN agent_runs ar ON ar.id=e.agent_run_id WHERE ar.conversation_id=?",
            (conv_id,),
        ):
            try:
                ref = json.loads(prov or "{}").get("source_ref")
            except json.JSONDecodeError:
                ref = None
            if ref:
                pool.add(ref)
    final_text = r.get("final_text") or ""
    cites = {(s, a) for s, a in _ART_RE.findall(final_text)}
    req = {f"{src}#第{_num_to_cn(n)}条": (f"{src}#第{_num_to_cn(n)}条" in pool) for src, n in case.get("required_laws", [])}
    forb = {
        f"{src}#第{_num_to_cn(n)}条": ((src, f"第{_num_to_cn(n)}条") in cites)
        for src, n in case.get("forbidden_articles", [])
    }
    scope_seen = any("本次请求分解出" in (q.get("prompt") or "") for q in r.get("asked", []))
    return {
        "domain": case.get("domain"),
        "agent_completed": bool(r.get("agent_completed")),
        "rounds": max(len(r.get("rounds", [])) - 1, 0),
        "clar_rounds": sum(1 for rd in r.get("rounds", [])[1:] if "clarification" in rd.get("event_types", [])),
        "error_codes": sorted({e for rd in r.get("rounds", []) for e in rd.get("error_codes", []) if e}),
        "redline_over_2_rounds": bool(r.get("redline_candidate_over_2_rounds")),
        "final_chars": r.get("final_chars"),
        "required_in_pool": req,
        "forbidden_cited_in_final": forb,
        "scope_clarification_seen": scope_seen,
        "scope_trigger_expected": bool(case.get("scope_trigger", False)),
    }


def main() -> int:
    verdict: dict[str, dict] = {}
    source_of: dict[str, str] = {}
    for path, db_path, label in SOURCES:
        if not path.exists() or not db_path.exists():
            print(f"SKIP source {label}: 文件缺失")
            continue
        sessions = json.loads(path.read_text(encoding="utf-8"))["results"]
        con = sqlite3.connect(db_path)
        cur = con.cursor()
        for cid, r in sessions.items():
            if cid in verdict:
                continue  # 先到先得：run-3 > run-2 > run-1
            if cid in TECH_SKIP.get(label, ()):
                continue  # 连接故障窗口的结果不进基线（等后一 run 有效数据）
            verdict[cid] = _judge(cid, r, BY_ID[cid], cur)
            source_of[cid] = label
        con.close()

    missing = sorted(set(BY_ID) - set(verdict))
    tally = {
        "n": len(verdict),
        "completed": sum(v["agent_completed"] for v in verdict.values()),
        "forbidden_fail": sum(any(v["forbidden_cited_in_final"].values()) for v in verdict.values()),
        "scope_mismatch": sum(v["scope_clarification_seen"] != v["scope_trigger_expected"] for v in verdict.values()),
        "required_pool_hits": sum(sum(v["required_in_pool"].values()) for v in verdict.values()),
        "required_total": sum(len(v["required_in_pool"]) for v in verdict.values()),
        "missing": missing,
    }
    out = {"run": "baseline-v2 merged (run-1 + run-2)", "source_of": source_of, "tally": tally, "per_case": verdict}
    (RUN1_DIR / "baseline-verdict.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print("TALLY:", json.dumps(tally, ensure_ascii=False))
    for cid, v in sorted(verdict.items()):
        flags = []
        if not v["agent_completed"]:
            flags.append("INCOMPLETE:" + ",".join(v["error_codes"]))
        if any(v["forbidden_cited_in_final"].values()):
            flags.append("FORBIDDEN_CITED")
        if v["scope_clarification_seen"] != v["scope_trigger_expected"]:
            flags.append("SCOPE_MISMATCH")
        print(f"{cid} [{source_of[cid]}] completed={v['agent_completed']} rounds={v['rounds']} "
              f"req={sum(v['required_in_pool'].values())}/{len(v['required_in_pool'])} {' '.join(flags)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
