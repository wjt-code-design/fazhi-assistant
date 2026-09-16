"""Validate the immutable release boundary for Legal Agent evidence.

The manifest deliberately contains hashes and non-secret identifiers only.  It
does not inspect a live database, invoke a model, read environment variables,
or infer provenance from the local checkout.  Capture and release commands use
the manifest's byte hash as the single reference to this frozen boundary.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections.abc import Sequence
from datetime import date
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.capture_protocol import load_capture_protocol
from scripts.release_policy import load_release_policy

_COMMIT_PATTERN = r"^[0-9a-f]{40}$"
_SHA256_PATTERN = r"^[0-9a-f]{64}$"
_BUILD_DIGEST_PATTERN = r"^sha256:[0-9a-f]{64}$"
_RELEASE_ID_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._-]{0,99}$"
_NON_EMPTY_LINE_PATTERN = r"^[^\r\n]+$"
_SEMVER_PATTERN = r"^\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?$"


class CandidateBoundary(BaseModel):
    """The code image that produced both sides of one comparison."""

    model_config = ConfigDict(extra="forbid", strict=True)

    git_revision: str = Field(pattern=_COMMIT_PATTERN)
    build_digest: str = Field(pattern=_BUILD_DIGEST_PATTERN)


class EvaluationBoundary(BaseModel):
    """The independent case set, evaluator and predeclared policy."""

    model_config = ConfigDict(extra="forbid", strict=True)

    case_set_sha256: str = Field(pattern=_SHA256_PATTERN)
    evaluator_name: str = Field(min_length=1, max_length=200, pattern=_NON_EMPTY_LINE_PATTERN)
    evaluator_version: str = Field(pattern=_SEMVER_PATTERN)
    rubric_hash: str = Field(pattern=_SHA256_PATTERN)
    release_policy_sha256: str = Field(pattern=_SHA256_PATTERN)


class KnowledgeBoundary(BaseModel):
    """The legal corpus/index state and applicable legal-time boundary."""

    model_config = ConfigDict(extra="forbid", strict=True)

    corpus_manifest_sha256: str = Field(pattern=_SHA256_PATTERN)
    index_manifest_sha256: str = Field(pattern=_SHA256_PATTERN)
    jurisdictions: list[str] = Field(min_length=1, max_length=20)
    law_as_of: date

    @field_validator("law_as_of", mode="before")
    @classmethod
    def parse_iso_law_date(cls, value: object) -> date:
        if isinstance(value, date):
            return value
        if not isinstance(value, str):
            raise ValueError("law_as_of must be an ISO-8601 date")
        try:
            return date.fromisoformat(value)
        except ValueError as exc:
            raise ValueError("law_as_of must be an ISO-8601 date") from exc

    @field_validator("jurisdictions")
    @classmethod
    def require_unique_jurisdictions(cls, value: list[str]) -> list[str]:
        if any(not item or "\n" in item or "\r" in item for item in value):
            raise ValueError("jurisdictions must be non-empty single-line identifiers")
        if len(set(value)) != len(value):
            raise ValueError("jurisdictions must be unique")
        return value


class RuntimeBoundary(BaseModel):
    """Non-secret model, prompt, tool and configuration identifiers."""

    model_config = ConfigDict(extra="forbid", strict=True)

    provider: str = Field(min_length=1, max_length=200, pattern=_NON_EMPTY_LINE_PATTERN)
    model: str = Field(min_length=1, max_length=300, pattern=_NON_EMPTY_LINE_PATTERN)
    model_snapshot: str = Field(min_length=1, max_length=300, pattern=_NON_EMPTY_LINE_PATTERN)
    prompt_bundle_sha256: str = Field(pattern=_SHA256_PATTERN)
    tool_policy_sha256: str = Field(pattern=_SHA256_PATTERN)
    config_sha256: str = Field(pattern=_SHA256_PATTERN)


class CaptureBoundary(BaseModel):
    """The reproducibility controls for a controlled offline dual-run."""

    model_config = ConfigDict(extra="forbid", strict=True)

    protocol_sha256: str = Field(pattern=_SHA256_PATTERN)
    retry_policy_sha256: str = Field(pattern=_SHA256_PATTERN)
    timeout_seconds: int = Field(ge=1, le=3600)
    concurrency: int = Field(ge=1, le=32)
    cache_policy: Literal["disabled", "frozen"]
    network_policy: Literal["frozen-knowledge-only", "offline"]


class ReleaseManifest(BaseModel):
    """A strict, non-secret release boundary; unknown fields are unsafe."""

    model_config = ConfigDict(extra="forbid", strict=True)

    schema_version: Literal["legal-agent-release-manifest/v1"]
    release_id: str = Field(pattern=_RELEASE_ID_PATTERN)
    candidate: CandidateBoundary
    evaluation: EvaluationBoundary
    knowledge: KnowledgeBoundary
    runtime: RuntimeBoundary
    capture: CaptureBoundary


def load_release_manifest(path: Path) -> tuple[ReleaseManifest, str]:
    """Load a JSON manifest and return it with the SHA-256 of its exact bytes."""
    try:
        raw = Path(path).read_bytes()
        parsed = json.loads(raw)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read release manifest: {path}") from exc
    if not isinstance(parsed, dict):
        raise ValueError("release manifest must be a JSON object")
    return ReleaseManifest.model_validate(parsed), hashlib.sha256(raw).hexdigest()


def validate_release_dependencies(
    manifest_path: Path, release_policy_path: Path, capture_protocol_path: Path
) -> tuple[ReleaseManifest, str]:
    """Verify that frozen policy and protocol bytes are exactly those named by a manifest."""
    manifest, manifest_sha256 = load_release_manifest(manifest_path)
    _, policy_sha256 = load_release_policy(release_policy_path)
    protocol, protocol_sha256 = load_capture_protocol(capture_protocol_path)
    if manifest.evaluation.release_policy_sha256 != policy_sha256:
        raise ValueError("release manifest policy hash does not match release policy")
    if manifest.capture.protocol_sha256 != protocol_sha256:
        raise ValueError("release manifest protocol hash does not match capture protocol")
    if manifest.capture.retry_policy_sha256 != protocol_sha256:
        raise ValueError("release manifest retry-policy hash must bind the frozen capture protocol")
    if manifest.evaluation.case_set_sha256 != protocol.case_set_sha256:
        raise ValueError("release manifest case-set hash does not match capture protocol")
    return manifest, manifest_sha256


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate a Legal Agent release manifest without accessing live services."
    )
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--release-policy", required=True, type=Path)
    parser.add_argument("--capture-protocol", required=True, type=Path)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        manifest, sha256 = validate_release_dependencies(args.manifest, args.release_policy, args.capture_protocol)
    except (ValidationError, ValueError) as exc:
        print(f"invalid release manifest: {exc}", file=sys.stderr)
        return 2
    print(
        json.dumps(
            {
                "release_id": manifest.release_id,
                "sha256": sha256,
                "candidate_git_revision": manifest.candidate.git_revision,
                "case_set_sha256": manifest.evaluation.case_set_sha256,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())


__all__ = ["ReleaseManifest", "load_release_manifest", "main", "validate_release_dependencies"]
