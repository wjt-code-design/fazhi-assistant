"""可复现的候选边界 manifest 重算/校验工具（阶段C 产品化，源自 diag/recompute_manifests.py）。

canonicalization 实现已对照 002 候选已记录值逐字节验证：
- corpus logical hash（锚点 record_count=10545, canonical_bytes=8840943）
- file-boundary（tool-policy 精确复现 f4e3e932…）

用法：
  python scripts/recompute_boundary_manifests.py verify --release-id legal-agent-v1-20260905-004
      —— 用本实现重算当前磁盘边界，与该候选已记录 manifest 对照（变化项会如实报告 DIFFER）
  python scripts/recompute_boundary_manifests.py gen --release-id <new-id> --image-sha256 <64hex>
      —— 生成新候选 evidence 目录的全部子 manifest + 冻结题集副本 + 校验过的 release-manifest
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]  # 仓库根（backend/scripts/ 上两级）
EV_LATEST = None

COLLECTIONS = ["legal_provisions_cos", "qa_pairs"]


def file_boundary_aggregate(rel_paths: list[str]) -> tuple[str, list[dict]]:
    """sort unique POSIX-relative paths; path + NUL + decimal size + NUL + lowercase sha256 + LF."""
    rows = []
    seen = set()
    for rel in rel_paths:
        p = REPO / rel
        if not p.is_file():
            raise FileNotFoundError(rel)
        norm = rel.replace("\\", "/")
        if norm in seen:
            continue
        seen.add(norm)
        digest = hashlib.sha256(p.read_bytes()).hexdigest()
        rows.append((norm, p.stat().st_size, digest))
    rows.sort()
    buf = bytearray()
    for path, size, digest in rows:
        buf += path.encode("utf-8") + b"\x00" + str(size).encode() + b"\x00" + digest.encode() + b"\n"
    return hashlib.sha256(bytes(buf)).hexdigest(), [{"path": p, "size": s, "sha256": d} for p, s, d in rows]


def py_files_under(rel_dir: str) -> list[str]:
    out = [
        str(p.relative_to(REPO)).replace("\\", "/")
        for p in (REPO / rel_dir).rglob("*.py")
        if "__pycache__" not in p.parts
    ]
    return out


def prompt_bundle_paths() -> list[str]:
    return py_files_under("backend/agent") + ["backend/prompts.py"]


def tool_policy_paths() -> list[str]:
    return py_files_under("backend/tools") + [
        "backend/agent/controller.py",
        "backend/agent/planner.py",
        "backend/agent/schemas.py",
    ]


def runtime_config_paths() -> list[str]:
    return [
        "backend/Dockerfile",
        "backend/llm_registry.py",
        "backend/settings.py",
        "docker-compose.yml",
    ]


def index_paths() -> list[str]:
    """active-local-chroma-index：chroma.sqlite3 + 活跃 collection 的 VECTOR segment 目录。"""
    db_path = REPO / "backend" / "chroma_db" / "chroma.sqlite3"
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    cur = con.cursor()
    segs = [
        r[0]
        for r in cur.execute(
            "SELECT s.id FROM segments s JOIN collections c ON s.collection = c.id "
            "WHERE c.name IN (?, ?) AND s.scope = 'VECTOR'",
            tuple(COLLECTIONS),
        ).fetchall()
    ]
    con.close()
    paths = ["backend/chroma_db/chroma.sqlite3"]
    for seg in segs:
        seg_dir = REPO / "backend" / "chroma_db" / seg
        paths.extend(str(p.relative_to(REPO)).replace("\\", "/") for p in seg_dir.rglob("*") if p.is_file())
    return paths


def corpus_logical_hash() -> dict:
    """join embeddings+segments+collections+embedding_metadata（m.id=e.id）；
    仅两个活跃 collection；记录键为 (collection, embedding_id)，payload 为
    {"collection","embedding_id","metadata"}；记录与 metadata 键均排序；
    裸数组 compact UTF-8 JSON (ensure_ascii=False) 后取 SHA-256。
    已在 002 记录值上验证：hash/bytes/count 三锚点精确复现。"""
    db_path = REPO / "backend" / "chroma_db" / "chroma.sqlite3"
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    cur = con.cursor()
    rows = cur.execute(
        """
        SELECT c.name, e.embedding_id, m.key, m.string_value, m.int_value,
               m.float_value, m.bool_value
        FROM embeddings e
        JOIN segments s ON e.segment_id = s.id
        JOIN collections c ON s.collection = c.id
        LEFT JOIN embedding_metadata m ON m.id = e.id
        WHERE c.name IN (?, ?)
        """,
        tuple(COLLECTIONS),
    ).fetchall()
    con.close()

    records: dict[tuple[str, str], dict] = {}
    for name, eid, key, sv, iv, fv, bv in rows:
        rec = records.setdefault((name, eid), {"collection": name, "embedding_id": eid, "metadata": {}})
        if key is not None:
            present = [(t, v) for t, v in (("s", sv), ("i", iv), ("f", fv), ("b", bv)) if v is not None]
            if present:
                t, raw = present[0]
                rec["metadata"][key] = (
                    bool(raw) if t == "b" else float(raw) if t == "f" else int(raw) if t == "i" else raw
                )

    out_records = []
    for k in sorted(records.keys()):
        rec = records[k]
        rec["metadata"] = dict(sorted(rec["metadata"].items()))
        out_records.append(rec)
    canonical = json.dumps(out_records, ensure_ascii=False, separators=(",", ":"))
    return {
        "record_count": len(out_records),
        "canonical_bytes": len(canonical.encode("utf-8")),
        "logical_corpus_sha256": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
    }


def manifest_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def compute_all(git_revision: str = "x") -> dict[str, dict]:
    prompt_agg, prompt_files = file_boundary_aggregate(prompt_bundle_paths())
    tool_agg, tool_files = file_boundary_aggregate(tool_policy_paths())
    cfg_agg, cfg_files = file_boundary_aggregate(runtime_config_paths())
    idx_agg, idx_files = file_boundary_aggregate(index_paths())
    corpus = corpus_logical_hash()
    return {
        "prompt_bundle": {"aggregate": prompt_agg, "files": prompt_files},
        "tool_policy": {"aggregate": tool_agg, "files": tool_files},
        "runtime_config": {"aggregate": cfg_agg, "files": cfg_files},
        "index": {"aggregate": idx_agg, "files": idx_files},
        "corpus": corpus,
    }


def verify() -> int:
    ev = EV_LATEST  # verify 的参照目录即 --release-id

    def load(name: str) -> dict:
        return json.loads((ev / f"{name}.json").read_text(encoding="utf-8"))

    cur = compute_all()
    checks = [
        (
            "prompt-bundle aggregate",
            load("prompt-bundle-manifest")["aggregate_sha256"],
            cur["prompt_bundle"]["aggregate"],
        ),
        ("tool-policy aggregate", load("tool-policy-manifest")["aggregate_sha256"], cur["tool_policy"]["aggregate"]),
        (
            "runtime-config aggregate",
            load("runtime-config-manifest")["aggregate_sha256"],
            cur["runtime_config"]["aggregate"],
        ),
        ("index aggregate", load("index-manifest")["aggregate_sha256"], cur["index"]["aggregate"]),
        ("corpus logical", load("corpus-manifest")["logical_corpus_sha256"], cur["corpus"]["logical_corpus_sha256"]),
        ("corpus bytes", str(load("corpus-manifest")["canonical_bytes"]), str(cur["corpus"]["canonical_bytes"])),
        ("corpus count", str(load("corpus-manifest")["record_count"]), str(cur["corpus"]["record_count"])),
    ]
    ok = True
    for name, recorded, mine in checks:
        match = mine == recorded
        ok &= match
        print(f"{name}: recorded={str(recorded)[:20]} mine={str(mine)[:20]} -> {'MATCH' if match else 'DIFFER'}")

    file_sets = [
        ("prompt-bundle", load("prompt-bundle-manifest")["files"], cur["prompt_bundle"]["files"]),
        ("tool-policy", load("tool-policy-manifest")["files"], cur["tool_policy"]["files"]),
        ("runtime-config", load("runtime-config-manifest")["files"], cur["runtime_config"]["files"]),
        ("index", load("index-manifest")["files"], cur["index"]["files"]),
    ]
    for name, old_files, mine_files in file_sets:
        old_paths = [f if isinstance(f, str) else f["path"] for f in old_files]
        mine_paths = [f["path"] for f in mine_files]
        match = old_paths == mine_paths
        ok &= match
        print(f"{name} file set: {'MATCH' if match else 'DIFFER'} ({len(mine_paths)} vs {len(old_paths)})")
    print("VERIFY_002:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


def gen(release_id: str, image_sha256: str | None = None) -> int:
    import subprocess

    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True, cwd=str(REPO)).strip()
    EV_LATEST.mkdir(parents=True, exist_ok=True)

    cur = compute_all(revision)

    def write(name: str, payload: dict) -> None:
        (EV_LATEST / name).write_text(json.dumps(payload, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    boundary_base = {
        "schema_version": "legal-agent-file-boundary/v1",
        "candidate_git_revision": revision,
    }
    write(
        "prompt-bundle-manifest.json",
        {
            **boundary_base,
            "boundary": "prompt-bundle",
            "selection": "all Python files in backend/agent plus backend/prompts.py",
            "canonicalization": "sort unique POSIX-relative paths; concatenate path + NUL + decimal byte size + NUL + lowercase file SHA-256 + LF; hash UTF-8 bytes with SHA-256",
            "aggregate_sha256": cur["prompt_bundle"]["aggregate"],
            "files": [f["path"] for f in cur["prompt_bundle"]["files"]],
        },
    )
    write(
        "tool-policy-manifest.json",
        {
            **boundary_base,
            "boundary": "tool-policy",
            "selection": "all Python files in backend/tools plus Agent controller, planner and schemas",
            "canonicalization": "sort unique POSIX-relative paths; concatenate path + NUL + decimal byte size + NUL + lowercase file SHA-256 + LF; hash UTF-8 bytes with SHA-256",
            "aggregate_sha256": cur["tool_policy"]["aggregate"],
            "files": [f["path"] for f in cur["tool_policy"]["files"]],
        },
    )
    write(
        "runtime-config-manifest.json",
        {
            **boundary_base,
            "boundary": "non-secret-runtime-config",
            "selection": "tracked runtime defaults and container configuration; .env files are excluded",
            "canonicalization": "sort unique POSIX-relative paths; concatenate path + NUL + decimal byte size + NUL + lowercase file SHA-256 + LF; hash UTF-8 bytes with SHA-256",
            "aggregate_sha256": cur["runtime_config"]["aggregate"],
            "files": [f["path"] for f in cur["runtime_config"]["files"]],
        },
    )
    write(
        "index-manifest.json",
        {
            **boundary_base,
            "boundary": "active-local-chroma-index",
            "active_collections": COLLECTIONS,
            "selection": "shared chroma.sqlite3 plus vector segment directories referenced by the active local collections",
            "canonicalization": "sort unique POSIX-relative paths; concatenate path + NUL + decimal byte size + NUL + lowercase file SHA-256 + LF; hash UTF-8 bytes with SHA-256",
            "aggregate_sha256": cur["index"]["aggregate"],
            "files": [f["path"] for f in cur["index"]["files"]],
        },
    )
    write(
        "corpus-manifest.json",
        {
            "schema_version": "legal-agent-corpus-manifest/v1",
            "candidate_git_revision": revision,
            "source": "backend/chroma_db/chroma.sqlite3",
            "active_collections": COLLECTIONS,
            "record_count": cur["corpus"]["record_count"],
            "canonical_bytes": cur["corpus"]["canonical_bytes"],
            "canonicalization": "join embeddings, segments, collections and embedding_metadata; select the two named collections; group metadata by collection and embedding_id; sort records and metadata keys; encode compact UTF-8 JSON with ensure_ascii=false",
            "logical_corpus_sha256": cur["corpus"]["logical_corpus_sha256"],
        },
    )

    # 冻结题集：v1.2 混合 30 题（006 预注册；002 为旧 20 题套件——2026-09-07 修正，
    # 此前硬编码 002 会把新候选的 capture-protocol 绑到错误题集 hash）
    src = EV_LATEST.parent / "legal-agent-v1-20260905-006" / "frozen-eval-cases.json"
    dst = EV_LATEST / "frozen-eval-cases.json"
    dst.write_bytes(src.read_bytes())
    case_sha = hashlib.sha256(dst.read_bytes()).hexdigest()
    print("frozen-eval-cases sha256:", case_sha)
    print("prompt-bundle:", cur["prompt_bundle"]["aggregate"])
    print("tool-policy  :", cur["tool_policy"]["aggregate"])
    print("runtime-config:", cur["runtime_config"]["aggregate"])
    print("index        :", cur["index"]["aggregate"])
    print("corpus       :", cur["corpus"]["logical_corpus_sha256"])

    # rubric hash 直接复用仓库实现
    sys.path.insert(0, str(REPO / "backend" / "scripts"))
    import eval_agent  # noqa: E402

    print("rubric       :", eval_agent.RUBRIC_HASH)
    print("OK sub-manifests written to", EV_LATEST)
    return 0


def _resolve_ev(release_id: str) -> Path:
    return REPO / "release-evidence" / release_id


def _main_cli() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Recompute/verify candidate boundary manifests.")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_v = sub.add_parser("verify")
    p_v.add_argument("--release-id", required=True)
    p_g = sub.add_parser("gen")
    p_g.add_argument("--release-id", required=True)
    p_g.add_argument("--image-sha256", default=None, help="可选：仅记录，release-manifest 由 assemble 脚本绑定")
    args = parser.parse_args()

    global EV_LATEST
    EV_LATEST = _resolve_ev(args.release_id)
    if args.cmd == "verify":
        return verify()
    if not (EV_LATEST / "release-manifest.json").exists():
        init = REPO / "backend" / "scripts" / "init_release_evidence.py"
        subprocess.check_call(
            [
                sys.executable,
                str(init),
                "--output",
                str(EV_LATEST),
                "--release-id",
                args.release_id,
            ]
        )
    gen(args.release_id)
    out = subprocess.check_output(
        [
            sys.executable,
            str(REPO / "backend" / "scripts" / "release_manifest.py"),
            "--manifest",
            str(EV_LATEST / "release-manifest.json"),
            "--release-policy",
            str(EV_LATEST / "release-policy.json"),
            "--capture-protocol",
            str(EV_LATEST / "capture-protocol.json"),
        ],
        text=True,
    )
    print(out)
    print("assemble release-manifest with image digest via diag/assemble_release_manifest.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main_cli())
