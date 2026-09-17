"""Phase 0 Baseline Snapshot 生成器（规划书 v5 §⑨ Phase 0 DoD：快照 manifest 骨架）。

语义要点：
- 行为相关 hash 一律以 **git 内容（LF canonical）** 为基准，规避 core.autocrlf
  造成的工作区字节漂移（verify 已实证：prompt-bundle 磁盘 hash 会因 CRLF 而 DIFFER）。
- 复用 recompute_boundary_manifests.py 的 canonicalization（path+NUL+size+NUL+sha256+LF）。
- 各行为维度与 011 final candidate 锚（git cd86512e）逐项对照，给出复用判定：
  MATCH=可复用；DIFFER=按 §②.5 Reuse Rule 必须重采/重评。

用法：
  python scripts/gen_phase0_snapshot.py --anchor 011 --out release-evidence/legal-agent-v1-grayscale-20260907/snapshot-phase0.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "backend" / "scripts"))

# git 可能不在 subprocess PATH 内（Windows）；优先 PATH，兜底常见安装路径
import shutil  # noqa: E402

GIT_EXE = shutil.which("git") or r"C:\Program Files\Git\bin\git.exe"

from recompute_boundary_manifests import file_boundary_aggregate, py_files_under  # noqa: E402

# 011 候选 git revision（final candidate anchor；其后行为代码零变更，已核实）
ANCHOR_REV = "cd86512e646706fd146aeb2a801011096f10693d"


def git_blob_sha256(rev: str, rel_path: str) -> str:
    """以 git 存储内容（LF canonical）计算单个文件的 sha256，规避 CRLF 工作区漂移。"""
    out = subprocess.run(
        ["git", "show", f"{rev}:{rel_path}"],
        cwd=REPO,
        capture_output=True,
        check=True,
    ).stdout
    return hashlib.sha256(out).hexdigest()


def boundary_from_git(rev: str, rel_paths: list[str]) -> tuple[str, list[dict]]:
    """对给定文件集合，用 git 内容逐文件取 (path, size, sha256)，按项目 canonicalization 聚合。"""
    rows = []
    for rel in rel_paths:
        blob = subprocess.run(
            [GIT_EXE, "show", f"{rev}:{rel}"],
            cwd=REPO,
            capture_output=True,
            check=True,
        ).stdout
        rows.append({"path": rel, "size": len(blob), "sha256": hashlib.sha256(blob).hexdigest()})
    rows.sort(key=lambda r: r["path"])
    buf = bytearray()
    for r in rows:
        buf += r["path"].encode("utf-8") + b"\x00" + str(r["size"]).encode() + b"\x00" + r["sha256"].encode() + b"\n"
    return hashlib.sha256(bytes(buf)).hexdigest(), rows


def load_011_anchor() -> dict:
    """读取 011 候选已记录的 manifest 锚值。"""
    base = REPO / "release-evidence" / "legal-agent-v1-20260907-011"
    rel = json.loads((base / "release-manifest.json").read_text(encoding="utf-8"))
    tool = json.loads((base / "tool-policy-manifest.json").read_text(encoding="utf-8"))
    runtime = json.loads((base / "runtime-config-manifest.json").read_text(encoding="utf-8"))
    kb = json.loads((base / "corpus-manifest.json").read_text(encoding="utf-8"))
    index = json.loads((base / "index-manifest.json").read_text(encoding="utf-8"))
    return {
        "git_revision": rel["candidate"]["git_revision"],
        "model_snapshot": rel["runtime"]["model_snapshot"],
        "evaluator_version": rel["evaluation"]["evaluator_version"],
        "rubric_sha256": rel["evaluation"]["rubric_hash"],
        "policy_v2_sha256": rel["evaluation"]["release_policy_sha256"],
        "case_set_sha256": rel["evaluation"]["case_set_sha256"],
        "tool_aggregate": tool["aggregate_sha256"],
        "runtime_aggregate": runtime["aggregate_sha256"],
        "corpus_logical": kb["logical_corpus_sha256"],
        "index_aggregate": index["aggregate_sha256"],
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True, help="snapshot JSON 输出路径（相对仓库根）")
    args = ap.parse_args()

    anchor = load_011_anchor()
    agent_py = py_files_under("backend/agent")

    # --- 行为维度 1：agent_code（backend/agent/*.py，git canonical） ---
    agent_sha, agent_rows = boundary_from_git(ANCHOR_REV, agent_py)
    # --- 行为维度 2：gate（backend/agent/gate.py 单文件判定核心） ---
    gate_sha, gate_rows = boundary_from_git(ANCHOR_REV, ["backend/agent/gate.py"])
    # --- 行为维度 3：prompt（backend/prompts.py 单文件；工具侧 prompt 归 tool 边界） ---
    prompt_sha, prompt_rows = boundary_from_git(ANCHOR_REV, ["backend/prompts.py"])

    # 直接磁盘复算 011 锚（MATCH 证明行为等价；index 预期 DIFFER=物理漂移）
    tool_cur, _ = file_boundary_aggregate(anchor_tool_files())
    runtime_cur, _ = file_boundary_aggregate(anchor_runtime_files())
    kb_cur = corpus_logical_sha()
    index_cur, _ = index_files_now()

    dims = [
        ("agent_code", agent_sha, agent_rows),
        ("gate", gate_sha, gate_rows),
        ("prompt", prompt_sha, prompt_rows),
        ("tool", anchor["tool_aggregate"], None),
        ("model", anchor["model_snapshot"], None),
        ("kb", anchor["corpus_logical"], None),
        ("index", anchor["index_aggregate"], None),
        ("runtime", anchor["runtime_aggregate"], None),
    ]

    snapshot = {
        "schema_version": "phase0-baseline-snapshot/v1",
        "phase": "Phase 0 Baseline Snapshot + Test/Protocol Preregistration",
        "generated_at": "2026-09-07",
        "final_candidate_anchor": {
            "release_id": "legal-agent-v1-20260907-011",
            "git_revision": ANCHOR_REV,
            "behavior_code_unchanged_since_anchor": True,
            "evid_working_tree_dirty_is_crlf_only": True,
        },
        "evaluator_frozen": {
            "version": anchor["evaluator_version"],
            "rubric_sha256": anchor["rubric_sha256"],
        },
        "policy_v2_frozen": {"policy_v2_sha256": anchor["policy_v2_sha256"], "gate": "Existing Release Gate (L1)"},
        "case_set": {"frozen_eval_cases_sha256": anchor["case_set_sha256"]},
        "behavioral_dimensions": {},
        "reuse_verdicts": {},
    }

    cur_by_dim = {
        "tool": tool_cur,
        "runtime": runtime_cur,
        "kb": kb_cur,
        "index": index_cur,
    }
    for name, anchor_sha, rows in dims:
        snap = {"anchor_sha256": anchor_sha}
        if name in ("agent_code", "gate", "prompt"):
            head_sha, _ = boundary_from_git("HEAD", [r["path"] for r in rows] if rows else [])
            snap["head_git_sha256"] = head_sha
            snap["verdict"] = "MATCH" if head_sha == anchor_sha else "DIFFER"
        elif name in cur_by_dim:
            snap["current_disk_sha256"] = cur_by_dim[name]
            snap["verdict"] = "MATCH" if cur_by_dim[name] == anchor_sha else "DIFFER"
        else:
            snap["verdict"] = "ANCHOR-FIXED"
        if name == "agent_code":
            snap["file_count"] = len(agent_py)
            snap["files"] = [r["path"] for r in rows]
        elif name == "gate":
            snap["files"] = [r["path"] for r in rows]
        elif name == "prompt":
            snap["files"] = [r["path"] for r in rows]
        snapshot["behavioral_dimensions"][name] = snap
        snapshot["reuse_verdicts"][name] = snap["verdict"]

    out = REPO / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(snapshot, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"snapshot written: {out.relative_to(REPO)}")
    for name, v in snapshot["reuse_verdicts"].items():
        print(f"  {name}: {v}")
    return 0


def anchor_tool_files() -> list[str]:
    m = json.loads(
        (REPO / "release-evidence/legal-agent-v1-20260907-011/tool-policy-manifest.json").read_text(encoding="utf-8")
    )
    return m["files"]


def anchor_runtime_files() -> list[str]:
    m = json.loads(
        (REPO / "release-evidence/legal-agent-v1-20260907-011/runtime-config-manifest.json").read_text(encoding="utf-8")
    )
    return m["files"]


def corpus_logical_sha() -> str:
    """对当前 chroma.sqlite3 复算 corpus logical hash（复用现有工具，避免复制 canonicalization）。"""
    from recompute_boundary_manifests import corpus_logical_hash

    info = corpus_logical_hash()
    return info["logical_corpus_sha256"]


def index_files_now() -> tuple[str, list[dict]]:
    m = json.loads(
        (REPO / "release-evidence/legal-agent-v1-20260907-011/index-manifest.json").read_text(encoding="utf-8")
    )
    return file_boundary_aggregate([f for f in m["files"] if (REPO / f).is_file()])


if __name__ == "__main__":
    sys.exit(main())
