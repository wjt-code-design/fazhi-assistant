"""Phase 5 Final Candidate Freeze：以 HEAD（final candidate 代码）冻结全部行为 SHA + 失效矩阵重判记录。

复用 gen_phase0_snapshot 的 git-canonical 边界计算（LF 基准，规避 CRLF 漂移）。
输出：release-evidence/legal-agent-v1-grayscale-20260907/freeze-manifest.json
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "backend" / "scripts"))

import shutil  # noqa: E402

GIT_EXE = shutil.which("git") or r"C:\Program Files\Git\bin\git.exe"

from gen_phase0_snapshot import (  # noqa: E402
    boundary_from_git,
    load_011_anchor,
    py_files_under,
)
from recompute_boundary_manifests import (  # noqa: E402
    corpus_logical_hash,
    file_boundary_aggregate,
)

OUT = REPO / "release-evidence" / "legal-agent-v1-grayscale-20260907"


def head_rev() -> str:
    out = subprocess.run([GIT_EXE, "-C", str(REPO), "rev-parse", "HEAD"], capture_output=True, check=True).stdout
    return out.decode().strip()


def main() -> int:
    rev = head_rev()
    anchor = load_011_anchor()
    agent_py = py_files_under("backend/agent")
    agent_sha, agent_rows = boundary_from_git(rev, agent_py)
    gate_sha, gate_rows = boundary_from_git(rev, ["backend/agent/gate.py"])
    prompt_sha, _ = boundary_from_git(rev, ["backend/prompts.py"])

    tool_sha, runtime_sha = None, None
    for manifest, key in (("tool-policy", "tool"), ("runtime-config", "runtime")):
        m = json.loads(
            (REPO / f"release-evidence/legal-agent-v1-20260907-011/{manifest}-manifest.json").read_text(
                encoding="utf-8"
            )
        )
        agg, _ = file_boundary_aggregate(m["files"])
        if key == "tool":
            tool_sha = agg
        else:
            runtime_sha = agg
    kb = corpus_logical_hash()["logical_corpus_sha256"]

    freeze = {
        "schema_version": "final-candidate-freeze/v1",
        "phase": "Phase 5 Final Candidate Freeze",
        "frozen_at": "2026-09-07",
        "git_revision": rev,
        "gate_hardening_included": True,
        "behavioral_dimensions": {
            "agent_code": {"sha256": agent_sha, "file_count": len(agent_py), "files": [r["path"] for r in agent_rows]},
            "gate": {
                "sha256": gate_sha,
                "files": [r["path"] for r in gate_rows],
                "note": "含 CRIMINAL_CIVIL_BOUNDARY 加固",
            },
            "prompt": {"sha256": prompt_sha},
            "tool": {"sha256": tool_sha},
            "kb": {"sha256": kb},
            "runtime": {"sha256": runtime_sha},
            "model": {"snapshot": anchor["model_snapshot"]},
        },
        "frozen_baselines": {
            "evaluator_version": anchor["evaluator_version"],
            "rubric_sha256": anchor["rubric_sha256"],
            "policy_v2": anchor["policy_v2_sha256"],
            "case_set": anchor["case_set_sha256"],
        },
        "invalidation_review": {
            "gate_change": "gate.py 新增 CRIMINAL_CIVIL_BOUNDARY（加固）→ §⑦ 生效：G-1 重跑（PASS）、G-2/S9 重跑（PASS）、G-3 新候选上已跑（PASS）",
            "index_differ": "index 物理 DIFFER（corpus 逻辑 MATCH）→ §②.5：S5 引用 reeval 必须基于当前 index 重跑，挂账本 Freeze 后动作",
            "s4": "11 report（4 类安全项 0）+ 新 routed 澄清题机械判定 0；全量 evaluator 重评挂账（S4=0 且澄清题 0，不构成阻塞，但记录待办）",
            "prompt_tool_model_runtime": "未变更，对应证据不失效",
        },
        "open_items": [
            "S5 引用 reeval（基于当前 index）——Phase 7 前必须完成",
            "S4 全量 evaluator 重评（routed corpus 7 题）——Phase 7 前完成或明确引用本判定",
        ],
    }
    (OUT / "freeze-manifest.json").write_text(json.dumps(freeze, ensure_ascii=False, indent=1), encoding="utf-8")
    print("frozen rev:", rev)
    print("agent_code:", agent_sha[:12], "gate:", gate_sha[:12], "prompt:", prompt_sha[:12])
    print("written:", OUT / "freeze-manifest.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
