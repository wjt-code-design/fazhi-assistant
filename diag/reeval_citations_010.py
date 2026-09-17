"""010 冻结采集引用精度评估（2026-09-07，引用精度修复候选的生成端实证）。

用 retrieval.classify_answer_citations（归一化三态）对 010 采集的
30 rag + 30 agent 回答做引用存在性判定，与 009 基线对比：
- 009 重评基线：article_missing=1（rag/criminal-civil-boundary-20）
- 目标（交接 4.1.1）：010 引用问题 ≤ 009（真条号错不新增），
  且生成端约束（SYSTEM_BASE 核对纪律）生效后 17-20% 比例收敛。
输出到 diag/quality-eval-20260907-reeval-010/。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

R = Path("C:/Users/33393/Desktop/ai-legal-helper")
sys.path.insert(0, str(R / "backend"))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(R / "backend" / ".env")

import retrieval as RTL  # noqa: E402

EVID = R / "release-evidence/legal-agent-v1-20260907-010-v2"
DIAC = R / "diag/official-capture-010-rag"
DIAA = R / "diag/official-capture-010-agent"


def main() -> int:
    rows: list[dict] = []
    for mode, d in (("rag", DIAC), ("agent", DIAA)):
        for r in json.loads((d / "rows.json").read_text(encoding="utf-8")):
            rows.append({"mode": mode, **r})

    out = []
    issue_article: list[str] = []
    issue_source: list[str] = []
    for row in rows:
        answer = row.get("answer", "") or ""
        classified = RTL.classify_answer_citations(answer)
        not_ok = [c for c in classified if c["status"] != RTL.REF_OK]
        entry = {"mode": row["mode"], "id": row["id"], "citations": [c["literal"] for c in classified], "not_ok": not_ok}
        if not_ok:
            if any(c["status"] == RTL.REF_ARTICLE_MISSING for c in not_ok):
                issue_article.append(f"{row['mode']}/{row['id']}")
            if any(c["status"] == RTL.REF_SOURCE_MISSING for c in not_ok):
                issue_source.append(f"{row['mode']}/{row['id']}")
        out.append(entry)

    out_dir = R / "diag/quality-eval-20260907-reeval-010"
    out_dir.mkdir(parents=True, exist_ok=True)
    summary = {
        "method": "retrieval.classify_answer_citations（归一化三态，2026-09-07 修复版）",
        "total_answers": len(out),
        "article_missing_issue_answers": len(set(issue_article)),
        "article_missing_ids": sorted(set(issue_article)),
        "source_missing_warn_answers": len(set(issue_source)),
        "source_missing_ids": sorted(set(issue_source)),
        "baseline_009_article_missing": 1,
        "baseline_009_ids": ["rag/criminal-civil-boundary-20"],
    }
    (out_dir / "reeval-summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    (out_dir / "reeval-detail.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())