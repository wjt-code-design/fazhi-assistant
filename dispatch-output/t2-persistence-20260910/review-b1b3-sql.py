"""B1 + B3 独立复算。

与验收包 §3.5 的实现刻意不同：
  - 文档用 Python 循环逐 conversation 查首条用户消息、手工去重、手工累加；
  - 本脚本把"窗口过滤 + 首条用户消息匹配 + 同题取首条 + issues 计数"
    全部下沉到**一条 SQL**（CTE + ROW_NUMBER 窗口函数），
    Python 只负责从 JSON 读入题目文本（数据准备，不参与计数逻辑）。
  - 数据库以 URI mode=ro 只读打开。

口径遵循 §3.5：
  题号映射 = 会话首条用户消息 ⨯ 冻结题 initial_question（空白归一后全等）
  每臂窗口 = [该轮 claim 起点, 全部已知轮次中紧邻的下一轮起点)
  排序用 rowid（不用 id 的 UUID 字典序）；上界用同格式时间字符串（不用纯数字）
"""

from __future__ import annotations

import json
import pathlib
import re
import sqlite3
from collections import Counter

ROOT = pathlib.Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
EV = ROOT / "release-evidence" / "legal-agent-v1-complex-v1-20260907"

ARMS = [
    ("qwen38(T7候选)", "gate5-dev-run-13-qwen38", 18, [1, 4, 3, 1, 1, 3, 1, 1, 2, 1]),
    ("qwen36(T7候选)", "gate5-dev-modelarm-qwen36", 24, [3, 4, 4, 2, 2, 3, None, 2, 2, 2]),
    ("run-14(T8)", "gate5-dev-run-14-qwen38-t8", 32, [4, 3, 4, 4, 4, None, 1, 5, 3, 4]),
    ("run-15(T8收尾)", "gate5-dev-run-15-qwen38-t8b", 37, [5, 5, 2, 2, 4, 5, 2, 4, 4, 4]),
]

# SQLite 版空白归一：等价于 Python 的 re.sub(r"\s+", "", s)
SQL_NORM = "replace(replace(replace(replace(replace({x},' ',''),char(9),''),char(10),''),char(13),''),char(12),'')"


def claim_start(arm: str) -> str:
    """claim.json 的 started_at → 'YYYY-MM-DD HH:MM:SS'（去 T、去时区、去微秒）。"""
    d = json.loads((EV / f"gate2-run-{arm}.claim.json").read_text(encoding="utf-8"))
    return d["started_at"].replace("T", " ").replace("+00:00", "").split(".")[0]


def load_cases() -> list[tuple[str, str]]:
    raw = json.loads((EV / "frozen-cases-v1.json").read_text(encoding="utf-8"))
    cases = raw["cases"] if isinstance(raw, dict) and "cases" in raw else raw
    out = []
    for c in cases:
        cid = c["id"]
        nq = re.sub(r"\s+", "", c["initial_question"])
        out.append((str(cid), nq))
    return sorted(out, key=lambda t: t[0])


SQL = f"""
WITH cases(cid, nq) AS (
    VALUES {",".join(f"(:cid{i},:nq{i})" for i in range(10))}
),
firstuser AS (
    SELECT m.conversation_id AS conv, {SQL_NORM.format(x="m.content")} AS nq
    FROM messages m
    WHERE m.role = 'user'
      AND m.id = (SELECT MIN(m2.id) FROM messages m2
                  WHERE m2.conversation_id = m.conversation_id AND m2.role = 'user')
),
win AS (
    SELECT ar.rowid AS rid, ar.conversation_id AS conv, ar.state_json AS sj
    FROM agent_runs ar
    WHERE ar.created_at >= :lo AND ar.created_at < :hi
),
matched AS (
    SELECT w.rid AS rid, c.cid AS cid,
           COALESCE(json_array_length(json_extract(w.sj, '$.issues')), 0) AS n
    FROM win w
    JOIN firstuser f ON f.conv = w.conv
    JOIN cases c     ON c.nq  = f.nq
),
ranked AS (
    SELECT rid, cid, n, ROW_NUMBER() OVER (PARTITION BY cid ORDER BY rid) AS rn
    FROM matched
)
SELECT cid, n FROM ranked WHERE rn = 1 ORDER BY cid
"""


def main() -> None:
    cases = load_cases()
    con = sqlite3.connect(f"file:{BACKEND / 'app.db'}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row

    starts = {arm: claim_start(arm) for _, arm, _, _ in ARMS}
    all_starts = sorted(starts.values())

    print("=" * 78)
    print("B1 — 争点总数独立复算（单条 SQL 实现）")
    print("=" * 78)
    print("--- 各臂窗口（claim 起点 → 紧邻下一轮起点）---")
    for _, arm, _, _ in ARMS:
        lo = starts[arm]
        later = [s for s in all_starts if s > lo]
        hi = min(later) if later else "2099-12-31 23:59:59"
        print(f"  {arm:<34} [{lo} , {hi})")
    print()

    all_ok = True
    for label, arm, exp_total, exp_per in ARMS:
        lo = starts[arm]
        later = [s for s in all_starts if s > lo]
        hi = min(later) if later else "2099-12-31 23:59:59"

        params = {f"cid{i}": cid for i, (cid, _) in enumerate(cases)}
        params.update({f"nq{i}": nq for i, (_, nq) in enumerate(cases)})
        params.update({"lo": lo, "hi": hi})
        rows = con.execute(SQL, params).fetchall()
        per_map = {r["cid"]: r["n"] for r in rows}
        got_per = [per_map.get(f"C{i:02d}") for i in range(1, 11)]
        got_total = sum(v for v in got_per if v is not None)

        ok = got_total == exp_total and got_per == exp_per
        all_ok &= ok
        print(f"{'[OK]  ' if ok else '[FAIL]'} {label:<18} 总数={got_total:>3}  声明={exp_total:>3}")
        print(f"        逐题复算 = {got_per}")
        print(f"        逐题声明 = {exp_per}")
        if got_per != exp_per:
            diff = [
                f"C{i:02d}: 复算 {got_per[i-1]} vs 声明 {exp_per[i-1]}"
                for i in range(1, 11)
                if got_per[i - 1] != exp_per[i - 1]
            ]
            print(f"        差异: {'; '.join(diff)}")
        n_none = sum(1 for v in got_per if v is None)
        print(f"        该臂分母 = {10 - n_none} 题（None {n_none} 个 = 预运行失败）")
        print()

    # 交叉验证：用一条独立 SQL 数每臂窗口内的 agent_runs 总行数
    print("--- 交叉验证：各臂窗口内 agent_runs 行数 / 可映射题数 ---")
    for label, arm, _, _ in ARMS:
        lo = starts[arm]
        later = [s for s in all_starts if s > lo]
        hi = min(later) if later else "2099-12-31 23:59:59"
        n_rows = con.execute(
            "SELECT COUNT(*) c FROM agent_runs WHERE created_at>=? AND created_at<?",
            (lo, hi),
        ).fetchone()["c"]
        n_conv = con.execute(
            "SELECT COUNT(DISTINCT conversation_id) c FROM agent_runs "
            "WHERE created_at>=? AND created_at<?",
            (lo, hi),
        ).fetchone()["c"]
        print(f"  {label:<18} agent_runs 行={n_rows:<4} 去重会话={n_conv}")

    print()
    print("=" * 78)
    print("B3 — run-14 / run-15 错误码分布（sessions.json）")
    print("=" * 78)
    EXP_B3 = {
        "gate5-dev-run-14-qwen38-t8": {
            "(无码)": 7,
            "EVIDENCE_COVERAGE_DEFICIENT": 2,
            "ISSUE_DECOMPOSITION_INVALID": 1,
        },
        "gate5-dev-run-15-qwen38-t8b": {
            "(无码)": 6,
            "CROSS_ISSUE_EVIDENCE": 2,
            "NON_CANONICAL_CITATION": 1,
            "UNSUPPORTED_NUMERIC_TOKEN": 1,
        },
    }
    for run, exp in EXP_B3.items():
        d = json.loads((EV / f"gate2-run-{run}-sessions.json").read_text(encoding="utf-8"))
        res = d["results"]
        cnt: Counter[str] = Counter()
        detail: dict[str, list[str]] = {}
        for cid in sorted(res):
            codes = res[cid].get("error_codes") or []
            if not codes:
                cnt["(无码)"] += 1
                detail.setdefault("(无码)", []).append(cid)
            for code in codes:
                cnt[code] += 1
                detail.setdefault(code, []).append(cid)
        ok = dict(cnt) == exp
        all_ok &= ok
        print(f"{'[OK]  ' if ok else '[FAIL]'} {run}")
        print(f"        复算 = {dict(cnt)}")
        print(f"        声明 = {exp}")
        for code, cids in sorted(detail.items()):
            print(f"          {code:<32} {cids}")
        inv = cnt.get("ISSUE_DECOMPOSITION_INVALID", 0)
        print(f"        >>> ISSUE_DECOMPOSITION_INVALID 次数 = {inv}")
        print()

    print("=" * 78)
    print(f"B1/B3 总判定: {'全部一致' if all_ok else '存在不一致（见上 FAIL 项）'}")
    print("=" * 78)


if __name__ == "__main__":
    main()
