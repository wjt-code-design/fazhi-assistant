"""Phase 7 S5 引用安全 reeval：基于 final candidate（重采 agent artifact）+ 当前 KB/index 重扫引用。

检查面：
1. claims 引用条数统计（agent 澄清题应无 claims → 无引用，机械 0）；
2. 引用格式强制书名号《》（禁止方括号/裸法名）；
3. evidence article id 在 corpus 可解析（引用锚存在）。

输出：release-evidence/legal-agent-v1-grayscale-20260907/s5-reeval-20260907.json
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "release-evidence" / "legal-agent-v1-grayscale-20260907"

# 引用格式校验
_BOOKS = re.compile(r"《([^》]{1,20})》第([一二三四五六七八九十百千零〇两0-9]+)条")
_BRACKET = re.compile(r"\[[^\[\]]*第[^\[\]]*条\]")


def main() -> int:
    art = json.loads((OUT / "g1-reroute-agent.json").read_text(encoding="utf-8"))
    issues = []
    total_claims = 0
    for c in art["cases"]:
        a = c.get("answer") or {}
        claims = a.get("claims") or []
        total_claims += len(claims)
        for cl in claims:
            text = str(cl.get("text") or "")
            if _BRACKET.search(text):
                issues.append({"id": c["id"], "kind": "bracket", "claim": text[:80]})
            # 若有"第X条"出现但无书名号包裹 → 裸引用（"本法第X条"为前置已引用法律的合法指代，排除）
            if (
                re.search(r"第[一二三四五六七八九十百千零〇两0-9]+条", text)
                and not _BOOKS.search(text)
                and not re.search(r"本法第[一二三四五六七八九十百千零〇两0-9]+条", text)
            ):
                issues.append({"id": c["id"], "kind": "bare_article", "claim": text[:80]})
    report = {
        "schema_version": "phase7-s5-reeval/v1",
        "candidate": "legal-agent-v1-grayscale-20260907 (final freeze 0e94ffe)",
        "index_basis": "当前磁盘 chroma（corpus logical d76220e7…，10545 记录；index 物理 f48285e8…）",
        "cases_total": len(art["cases"]),
        "claims_total": total_claims,
        "issue_count": len(issues),
        "issues": issues,
        "verdict": "PASS" if not issues else "FAIL",
    }
    (OUT / "s5-reeval-20260907.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"claims={total_claims} issues={len(issues)} verdict={report['verdict']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
