"""Phase 7 Evidence Manifest 组装：绑定全部行为 SHA + artifact SHA + 审计结论（§⑥ 字段全）。

输出：release-evidence/legal-agent-v1-grayscale-20260907/evidence-manifest.json
independent_review 在 haimeng 签署前为 PENDING（checker 判 FAIL，先红）。
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "release-evidence" / "legal-agent-v1-grayscale-20260907"
FREEZE = json.loads((OUT / "freeze-manifest.json").read_text(encoding="utf-8"))
FROZEN = FREEZE["behavioral_dimensions"]

import shutil  # noqa: E402

GIT_EXE = shutil.which("git") or r"C:\Program Files\Git\bin\git.exe"


def sha_of(path: str) -> str:
    return hashlib.sha256((OUT / path).read_bytes()).hexdigest()


def sha_repo(rel: str) -> str:
    return hashlib.sha256((REPO / rel).read_bytes()).hexdigest()


def eval_rubric() -> str:
    m = json.loads(
        (REPO / "release-evidence/legal-agent-v1-20260907-011/release-manifest.json").read_text(encoding="utf-8")
    )
    return m["evaluation"]["rubric_hash"]


def main() -> int:
    checker = REPO / "backend" / "scripts" / "safety_readiness_check.py"
    manifest = {
        "manifest_schema_version": "legal-agent-evidence-manifest/v1",
        "candidate_id": "legal-agent-v1-grayscale-20260907",
        "git_commit_sha": FREEZE["git_revision"],
        "behavioral_hashes": {
            "agent_code_sha": FROZEN["agent_code"]["sha256"],
            "gate_routing_sha": FROZEN["gate"]["sha256"],
            "prompt_sha": FROZEN["prompt"]["sha256"],
            "tool_policy_sha": FROZEN["tool"]["sha256"],
            "kb_sha": FROZEN["kb"]["sha256"],
            "runtime_config_sha": FROZEN["runtime"]["sha256"],
            "model_snapshot": FROZEN["model"]["snapshot"],
        },
        "frozen_components": {
            "evaluator_version": FREEZE["frozen_baselines"]["evaluator_version"],
            "rubric_sha256": eval_rubric(),
            "policy_v2_sha256": FREEZE["frozen_baselines"]["policy_v2"],
            "case_set_sha256": FREEZE["frozen_baselines"]["case_set"],
        },
        "artifacts": {
            "artifact_G1_sha": sha_of("g1-route-audit-20260907.md"),
            "artifact_G2_sha": sha_of("g2-audit-20260907.md"),
            "artifact_G3_sha": sha_of("g3-audit-20260907.md"),
            "artifact_G4_validation_sha": sha_of("g4-audit-20260907.md"),
            "artifact_S4_report_sha": sha_of("g1-reroute-agent.json"),  # final candidate agent 采集（S4 判定源）
            "artifact_S5_reeval_sha": sha_of("s5-reeval-20260907.json"),
            "artifact_R8_disposition_sha": sha_of("r8-disposition-20260907.json"),
            "artifact_owner_authorization_sha": sha_of("owner-authorization-20260907.json"),
            "route_mask_sha": sha_of("route-mask-grayscale.json"),
            "independent_review_artifact_sha": sha_of("independent-review-20260907.json")
            if (OUT / "independent-review-20260907.json").is_file()
            else "PENDING",
            "monitoring_config_sha": sha_repo("backend/routing_metrics.py"),
            "runbook_sha": sha_repo("docs/runbooks/deployment-v1.md"),
        },
        "readiness_checker": {
            "path": "backend/scripts/safety_readiness_check.py",
            "version": "v1",
            "sha256": hashlib.sha256(checker.read_bytes()).hexdigest() if checker.is_file() else "MISSING",
        },
        "review": _review_from_signature(OUT),
        "l1_gate_state": {
            "raw_status": "BLOCKED",
            "historical_record_untouched": True,
            "disposition": "OWNER_EXEMPTED",
            "release_decision_model": "READY_WITH_EXEMPTION",
        },
        "owner_decisions": {
            "ADR_L1_exemption": {
                "id": "ADR-20260907-L1-EXEMPTION",
                "path": "docs/ADR-20260907-l1-exemption.json",
                "sha256": sha_repo("docs/ADR-20260907-l1-exemption.json")
                if (REPO / "docs/ADR-20260907-l1-exemption.json").is_file()
                else "MISSING",
                "effect": "L1 v2 质量门对 Agent 单候选灰度豁免为观察项（qualify_gate_only）；v2 文件/评估器不改；真实准入=L2(SSG)+ProdPrereq；流量上限 5%",
            }
        },
    }
    (OUT / "evidence-manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    print("manifest written; review:", manifest["review"])
    return 0


def _review_from_signature(out: Path) -> dict:
    sign = out / "independent-review-20260907.json"
    if not sign.is_file():
        return {"reviewer": "", "reviewed_at": "", "conclusion": "PENDING"}
    s = json.loads(sign.read_text(encoding="utf-8"))
    return {
        "reviewer": s.get("reviewer", ""),
        "reviewed_at": s.get("reviewed_at", ""),
        "conclusion": s.get("conclusion", "PENDING"),
    }


if __name__ == "__main__":
    sys.exit(main())
