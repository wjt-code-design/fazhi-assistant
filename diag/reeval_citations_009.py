"""009 冻结采集引用精度重评（2026-09-07 法条引用精度修复的验收脚本）。

用途：
- 用 retrieval.classify_answer_citations（归一化三态：ok / article_missing / source_missing）
  对 009 冻结的 60 个回答（30 rag + 30 agent）重新做"引用存在性"判定；
- 修复前 quality_eval 的 citations_not_in_kb 用"精确条号在库"单一判据，
  导致 ASCII 记法变体（第801条 vs 第八百零一条）被误报为不在库；
- 修复后：记法变体 → ok；真条号错误 → article_missing（硬问题）；库外/已废止法 → source_missing（WARN）。

诚实披露：本脚本只重评冻结回答的判定，不重采集、不改回答；答案仍是 009 镜像生成。
输出到 quality-eval-20260907-reeval/ 新目录，不覆盖原始 quality-eval-20260907/。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

R = Path("C:/Users/33393/Desktop/ai-legal-helper")
sys.path.insert(0, str(R / "backend"))

from dotenv import load_dotenv

load_dotenv(R / "backend" / ".env")

import retrieval as RTL


def main() -> int:
    rows: list[dict] = []
    for mode in ("rag", "agent"):
        for r in json.loads((R / f"diag/official-capture-009-{mode}/rows.json").read_text(encoding="utf-8")):
            rows.append({"mode": mode, **r})

    out = []
    issue_article: list[str] = []  # 真条号错误（mode/id）
    issue_source: list[str] = []  # 库外/已废止法 WARN
    for row in rows:
        answer = row.get("answer", "") or ""
        classified = RTL.classify_answer_citations(answer)
        not_ok = [c for c in classified if c["status"] != RTL.REF_OK]
        entry = {
            "mode": row["mode"],
            "id": row["id"],
            "citations": [c["literal"] for c in classified],
            "not_ok": not_ok,
        }
        if not_ok:
            if any(c["status"] == RTL.REF_ARTICLE_MISSING for c in not_ok):
                issue_article.append(f"{row['mode']}/{row['id']}")
            if any(c["status"] == RTL.REF_SOURCE_MISSING for c in not_ok):
                issue_source.append(f"{row['mode']}/{row['id']}")
        out.append(entry)

    out_dir = R / "diag/quality-eval-20260907-reeval"
    out_dir.mkdir(parents=True, exist_ok=True)
    summary = {
        "method": "retrieval.classify_answer_citations（归一化三态，2026-09-07 修复版）",
        "total_answers": len(out),
        "article_missing_issue_answers": len(set(issue_article)),
        "article_missing_ids": sorted(set(issue_article)),
        "source_missing_warn_answers": len(set(issue_source)),
        "source_missing_ids": sorted(set(issue_source)),
        "article_issue_before_fix": 3,
        "article_issue_after_fix": len(set(issue_article)),
    }
    (out_dir / "reeval-summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    (out_dir / "reeval-detail.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())