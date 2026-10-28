"""Phase 1 G-1 路由审计数据准备：从 01x 历史 capture 提取真实 gate 路由掩码。

对 capture 集中每行的 routed_agent 统计——正常模式（bootstrap）采集的行即 gate 真实判定；
强制模式（agent/rag 分别采集）的行标记为 forced，不作为 gate 掩码依据。

用法：python scripts/gen_phase1_audit.py
输出：release-evidence/legal-agent-v1-grayscale-20260907/route-mask-011.json + 控制台摘要
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DIAG = REPO / "diag"
OUT = REPO / "release-evidence" / "legal-agent-v1-grayscale-20260907"


def load_rows(capture: str) -> list[dict]:
    p = DIAG / capture / "rows.json"
    if not p.is_file():
        return []
    return json.loads(p.read_text(encoding="utf-8"))


def main() -> int:
    captures = {
        "001": "official-capture-011-agent",
        "011-rag": "official-capture-011-rag",
        "011-retry2": "official-capture-011-agent-retry2",
    }
    for name, cap in captures.items():
        rows = load_rows(cap)
        if not rows:
            print(f"{name}: rows.json MISSING")
            continue
        routed = dict(Counter(r.get("routed_agent") for r in rows))
        print(f"{cap}: n={len(rows)} routed={routed}")

    # 011 agent capture 的快照（用于 S9 澄清记录与 routed 明细）
    rows = load_rows("official-capture-011-agent") or load_rows("official-capture-011-agent-retry2")
    summary = {
        "schema_version": "phase1-route-mask/v1",
        "evidence_note": "真实 gate 路由以 009/010/011 STATUS 一致记录 6/30 为准",
        "capture_set": "official-capture-011-agent(+retry2 R11 样本)",
        "rows": [
            {
                "id": r["id"],
                "status": r.get("status"),
                "routed_agent": r.get("routed_agent"),
                "clarification": r.get("clarification"),
                "error_codes": r.get("error_codes", []),
            }
            for r in rows
        ],
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "route-mask-011.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    print("written:", OUT / "route-mask-011.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
