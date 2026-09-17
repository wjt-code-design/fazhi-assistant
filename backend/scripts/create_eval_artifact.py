"""Create a strict offline evaluation artifact from separately captured answers.

This utility never imports live runtime services, queries a database, reads a
user session, or calls a model. Its input is a human-reviewed, de-identified
JSON capture with only frozen case ids and structured evaluator answers.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.eval_agent import FrozenArtifactCase, FrozenEvaluationArtifact, load_cases
from scripts.release_manifest import load_release_manifest, validate_release_dependencies

_EXECUTION_ID_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._-]{0,99}$"


class CapturedAnswers(BaseModel):
    """Strict, de-identified input supplied by a separately controlled capture."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["legal-agent-eval-answers/v1"]
    cases: list[FrozenArtifactCase]


class CaptureProvenance(BaseModel):
    """Opaque capture provenance; never infer provenance from local machine state."""

    model_config = ConfigDict(extra="forbid")

    source_git_revision: str = Field(pattern=r"^[0-9a-f]{40}$")
    source_execution_id: str = Field(pattern=_EXECUTION_ID_PATTERN)


def _load_captured_answers(path: Path) -> CapturedAnswers:
    try:
        raw = path.read_bytes()
        parsed = json.loads(raw)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read captured answers: {path}") from exc
    if not isinstance(parsed, dict):
        raise ValueError("captured answers must be a JSON object")
    return CapturedAnswers.model_validate(parsed)


def create_frozen_artifact(
    *,
    cases_path: Path,
    answers_path: Path,
    mode: Literal["existing_rag", "agent"],
    source_git_revision: str,
    source_execution_id: str,
    release_manifest: Path | None = None,
    output: Path,
) -> FrozenEvaluationArtifact:
    """Bind strict offline answers to the exact raw frozen-case file once."""
    cases, frozen_hash = load_cases(cases_path)
    captured = _load_captured_answers(answers_path)
    provenance = CaptureProvenance(
        source_git_revision=source_git_revision,
        source_execution_id=source_execution_id,
    )
    manifest_sha256: str | None = None
    if release_manifest is not None:
        manifest, manifest_sha256 = load_release_manifest(release_manifest)
        if manifest.candidate.git_revision != provenance.source_git_revision:
            raise ValueError("release manifest candidate revision does not match capture provenance")
        if manifest.evaluation.case_set_sha256 != frozen_hash:
            raise ValueError("release manifest case-set hash does not match evaluation cases")
    expected_ids = [case.id for case in cases]
    captured_ids = [case.id for case in captured.cases]
    if len(set(expected_ids)) != len(expected_ids):
        raise ValueError("evaluation case ids must be unique")
    if captured_ids != expected_ids:
        raise ValueError("captured answer case ids do not match evaluation cases")
    artifact = FrozenEvaluationArtifact(
        schema_version="legal-agent-eval-artifact/v2"
        if manifest_sha256 is not None
        else "legal-agent-eval-artifact/v1",
        mode=mode,
        freeze_hash=frozen_hash,
        source_git_revision=provenance.source_git_revision,
        source_execution_id=provenance.source_execution_id,
        release_manifest_sha256=manifest_sha256,
        cases=captured.cases,
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(artifact.model_dump(), ensure_ascii=False, indent=2) + "\n")
    return artifact


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create a strict offline Legal Agent evaluation artifact.")
    parser.add_argument("--mode", required=True, choices=["existing_rag", "agent"])
    parser.add_argument("--cases", required=True, type=Path)
    parser.add_argument("--answers", required=True, type=Path)
    parser.add_argument("--source-git-revision", required=True)
    parser.add_argument("--source-execution-id", required=True)
    parser.add_argument("--release-manifest", required=True, type=Path, help="Validated non-secret release boundary.")
    parser.add_argument("--release-policy", type=Path, help="Frozen release policy named by the manifest.")
    parser.add_argument("--capture-protocol", type=Path, help="Frozen capture protocol named by the manifest.")
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        if args.release_policy is None or args.capture_protocol is None:
            raise ValueError("release policy and capture protocol are required for artifact creation")
        validate_release_dependencies(args.release_manifest, args.release_policy, args.capture_protocol)
        create_frozen_artifact(
            cases_path=args.cases,
            answers_path=args.answers,
            mode=args.mode,
            source_git_revision=args.source_git_revision,
            source_execution_id=args.source_execution_id,
            release_manifest=args.release_manifest,
            output=args.output,
        )
    except (ValidationError, ValueError) as exc:
        print(f"invalid offline capture input: {exc}", file=sys.stderr)
        return 2
    except FileExistsError:
        print(f"evaluation artifact already exists: {args.output}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
