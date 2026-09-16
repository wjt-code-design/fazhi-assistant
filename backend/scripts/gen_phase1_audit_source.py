"""Phase 1 审计表素材：输出 30 题 gold 标注底稿 + 011 实际路由 + S9 澄清记录。

黄金路由标注规则（§ Phase 0 协议预注册 G-1）：
  POLICY_*/多争点/多阶段/缺关键事实/文档审查/精确法条 → agent；单争点简单问答 → RAG。
标注者在本表补充每题的 expected_route 与 critical_high 标记。

输出：release-evidence/legal-agent-v1-grayscale-20260907/g1-audit-source.md
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "release-evidence" / "legal-agent-v1-grayscale-20260907"


def main() -> int:
    mask = json.loads((OUT / "route-mask-011.json").read_text(encoding="utf-8"))
    rows = {r["id"]: r for r in mask["rows"]}

    cases = json.loads(
        (REPO / "release-evidence/legal-agent-v1-20260907-011/frozen-eval-cases.json").read_text(encoding="utf-8")
    )
    # case-set 结构可能是 {"cases": [...]} 或 list
    case_list = cases["cases"] if isinstance(cases, dict) and "cases" in cases else cases

    lines = [
        "# G-1 审计底稿素材（Phase 1）",
        "",
        "> 说明：actual_route 取自 011 正常模式采集（routed_agent 字段）；expected_route 由标注者按预注册规则填写；",
        "> critical_high = 该题风险分级（Crit/High → S1 硬规则适用）。",
        "",
        "| id | 题目摘要 | actual(011 gate) | expected(黄金) | critical_high | 备注 |",
        "|---|---|---|---|---|---|",
    ]
    for c in case_list:
        cid = c.get("id") or c.get("case_id")
        text = (
            c.get("query") or c.get("question") or c.get("prompt") or c.get("text") or json.dumps(c, ensure_ascii=False)
        )[:120]
        txt = text.replace("|", "\\|").replace("\n", " ")
        r = rows.get(cid, {})
        clarify = r.get("clarification") or ""
        note = ""
        if clarify:
            note = f"澄清: {clarify}"
        lines.append(f"| {cid} | {txt} | {r.get('routed_agent', 'N/A')} |  |  | {note} |")

    # S9 素材：缺关键事实 → 应澄清
    clarify_rows = [r for r in mask["rows"] if r.get("clarification")]
    lines += ["", "## S9 澄清记录素材（缺关键事实必反问）", ""]
    lines += [f"- {r['id']}: {r.get('clarification')}" for r in clarify_rows]

    (OUT / "g1-audit-source.md").write_text("\n".join(lines), encoding="utf-8")
    print("written:", OUT / "g1-audit-source.md", f"({len(case_list)} cases)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
