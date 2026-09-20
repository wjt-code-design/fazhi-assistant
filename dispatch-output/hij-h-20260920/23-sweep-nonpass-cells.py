"""补扫：登记表里还有哪些格子**本身就在暗示未完成的工作**（只读）。

为什么要这一步：之前的 T1–T8 是**两轮启发式**扫出来的（票 H/J 里撞到的 + 针对已知类别做的定向 grep），
不是穷举。本脚本把"登记表"这个**结构化真源**扫一遍，回答一个可验证的问题：
**除 PASS/NA 之外，还有哪些格子带着"未完成/有残留"的语义？**

口径（判据，不是感觉）：
  ① 状态 ≠ PASS/NA 的格子全列出（分状态计数）；
  ② 状态 == PASS 但取证文本里出现"未完成语义"关键词的，也列出（PASS 但带尾巴的最容易漏）。
    关键词表：遗留 / 残留 / 未覆盖 / 未量 / 未证 / 今天不生效 / 零流量 / 待 / BLOCKED / 不含 / 打折
③ 只读：不写任何产品文件，只落自己的 JSON。

用法：backend/venv/Scripts/python.exe dispatch-output/hij-h-20260920/23-sweep-nonpass-cells.py
"""

from __future__ import annotations

import json
import pathlib
import sys
from collections import Counter

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "backend"))

import gate_exit_registry as G

TAIL_WORDS = (
    "遗留",
    "残留",
    "未覆盖",
    "未量",
    "未证",
    "今天不生效",
    "零流量",
    "BLOCKED",
    "打折",
    "不含",
    "不许",
)

RED_BY_STATUS = {"GAP-TODO", "GAP-ACCEPTED", "BLOCKED", "DISABLED"}


def main() -> int:
    by_status: Counter[str] = Counter()
    non_pass: list[dict] = []
    pass_with_tail: list[dict] = []
    for row in G.EXITS:
        eid = row["id"]
        for col, (status, why) in row["cells"].items():
            by_status[status] += 1
            item = {
                "exit": eid,
                "where": row["where"],
                "traffic": row.get("traffic", ""),
                "col": col,
                "status": status,
                "why_head": why[:160],
            }
            if status in RED_BY_STATUS:
                non_pass.append(item)
            elif status == "PASS":
                hits = [w for w in TAIL_WORDS if w in why]
                if hits:
                    item["tail_words"] = hits
                    pass_with_tail.append(item)

    out = {
        "cells_by_status": dict(by_status),
        "n_exits": len(G.EXITS),
        "non_pass_cells": non_pass,
        "pass_cells_with_unfinished_wording": pass_with_tail,
        "n_non_pass": len(non_pass),
        "n_pass_with_tail": len(pass_with_tail),
    }
    (HERE / "23-sweep-nonpass-cells.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8", newline=""
    )
    print(json.dumps(out["cells_by_status"], ensure_ascii=False))
    print(
        f"n_exits={len(G.EXITS)}  n_non_pass={len(non_pass)}  n_pass_with_tail={len(pass_with_tail)}"
    )
    print("--- 非 PASS/NA 的格子（exit / col / status）---")
    for it in non_pass:
        print(
            f"  {it['exit']:>4} | {it['col']:<8} | {it['status']:<12} | {it['traffic']}"
        )
    print("--- PASS 但带未完成语义的格子（最容易漏的那类）---")
    for it in pass_with_tail:
        print(f"  {it['exit']:>4} | {it['col']:<8} | 关键词={it['tail_words']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
