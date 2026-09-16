"""组装 release-manifest：从已生成的子 manifest 计算 SHA-256 并填入。

用法：python assemble_release_manifest.py <image-id-hex-64> <evidence-dir-name>
（如 legal-agent-v1-20260905-004；目录须已含全部子 manifest）
"""
import hashlib
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
EV = REPO / "release-evidence" / sys.argv[2]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _rubric_hash() -> str:
    import sys
    sys.path.insert(0, str(REPO / "backend"))
    from scripts.eval_agent import RUBRIC_HASH
    return RUBRIC_HASH


def _evaluator_version() -> str:
    import sys
    sys.path.insert(0, str(REPO / "backend"))
    from scripts.eval_agent import EVALUATOR_VERSION
    return EVALUATOR_VERSION


def main() -> None:
    image_hex = sys.argv[1].strip().lower().removeprefix("sha256:")
    assert "/" not in sys.argv[2], "pass dir name only"
    assert len(image_hex) == 64, "need 64-hex image id"

    release_id = sys.argv[2]
    revision = json.loads((EV / "corpus-manifest.json").read_text(encoding="utf-8"))[
        "candidate_git_revision"
    ]

    manifest = {
        "schema_version": "legal-agent-release-manifest/v1",
        "release_id": release_id,
        "candidate": {
            "git_revision": revision,
            "build_digest": f"sha256:{image_hex}",
        },
        "evaluation": {
            "case_set_sha256": sha(EV / "frozen-eval-cases.json"),
            "evaluator_name": "legal-agent-deterministic-evaluator",
            "evaluator_version": _evaluator_version(),
            "rubric_hash": _rubric_hash(),
            "release_policy_sha256": sha(EV / "release-policy.json"),
        },
        "knowledge": {
            "corpus_manifest_sha256": sha(EV / "corpus-manifest.json"),
            "index_manifest_sha256": sha(EV / "index-manifest.json"),
            "jurisdictions": ["CN"],
            "law_as_of": "2026-08-01",
        },
        "runtime": {
            "provider": "longcat-openai-compatible",
            "model": "LongCat-2.0",
            "model_snapshot": "LongCat-2.0",
            "prompt_bundle_sha256": sha(EV / "prompt-bundle-manifest.json"),
            "tool_policy_sha256": sha(EV / "tool-policy-manifest.json"),
            "config_sha256": sha(EV / "runtime-config-manifest.json"),
        },
        "capture": {
            "protocol_sha256": sha(EV / "capture-protocol.json"),
            "retry_policy_sha256": sha(EV / "capture-protocol.json"),
            "timeout_seconds": 90,
            "concurrency": 1,
            "cache_policy": "disabled",
            "network_policy": "frozen-knowledge-only",
        },
    }
    (EV / "release-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
    )
    print("release-manifest written, sha256:", sha(EV / "release-manifest.json"))


if __name__ == "__main__":
    main()
