"""Phase 1 G-1 掩码重算：从重采 trace（SSE events）判定 routed_agent，生成新掩码。

判定与 capture_eval.is_agent_routed 一致：events 中出现 type=agent_status 即 ruted 到 Agent。
输出：release-evidence/legal-agent-v1-grayscale-20260907/route-mask-grayscale.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "release-evidence" / "legal-agent-v1-grayscale-20260907"
TRACE = REPO / "diag" / "grayscale-g1-reroute-agent-20260907"
REROUTE = OUT / "g1-reroute-agent.json"


def main() -> int:
    artifact = json.loads(REROUTE.read_text(encoding="utf-8"))
    cases = artifact["cases"]
    rows = []
    for c in cases:
        cid = c["id"]
        sse_path = TRACE / f"{cid}.sse.json"
        events = json.loads(sse_path.read_text(encoding="utf-8"))
        routed = any(e.get("type") == "agent_status" for e in events)
        a = c.get("answer") or {}
        rows.append(
            {
                "id": cid,
                "routed_agent": routed,
                "clarification": a.get("clarification"),
                "error_codes": c.get("error_codes", []),
                "status": "ok" if routed or a.get("claims") or a.get("clarification") else "empty",
            }
        )
    mask = {
        "schema_version": "phase1-route-mask-grayscale/v1",
        "evidence_note": "gate 加固后重采掩码（本地隔离，AGENT_ENABLED=100%）",
        "capture_set": "grayscale-g1-reroute-agent-20260907",
        "rows": rows,
    }
    (OUT / "route-mask-grayscale.json").write_text(json.dumps(mask, ensure_ascii=False, indent=1), encoding="utf-8")
    routed = [r["id"] for r in rows if r["routed_agent"]]
    print(f"routed({len(routed)}):", routed)
    return 0


if __name__ == "__main__":
    sys.exit(main())
