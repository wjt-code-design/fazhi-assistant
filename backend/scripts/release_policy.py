"""Validate predeclared Legal Agent release thresholds without running an evaluation.

The policy is intentionally declarative.  It records who owns each decision,
how the metric is aggregated, the minimum denominator, and the rollback rule
before either Existing RAG or Agent results are observed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

_IDENTIFIER_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._-]{0,99}$"
_NON_EMPTY_LINE_PATTERN = r"^[^\r\n]+$"


class ReleaseMetricPolicy(BaseModel):
    """One predeclared measurement and the action it controls."""

    model_config = ConfigDict(extra="forbid", strict=True)

    name: str = Field(pattern=_IDENTIFIER_PATTERN)
    unit: str = Field(min_length=1, max_length=100, pattern=_NON_EMPTY_LINE_PATTERN)
    direction: Literal["higher-is-better", "lower-is-better", "must-equal"]
    threshold: str = Field(min_length=1, max_length=500, pattern=_NON_EMPTY_LINE_PATTERN)
    aggregation: str = Field(min_length=1, max_length=300, pattern=_NON_EMPTY_LINE_PATTERN)
    minimum_sample_size: int = Field(ge=1, le=1_000_000)
    observation_window: str = Field(min_length=1, max_length=300, pattern=_NON_EMPTY_LINE_PATTERN)
    exclusions: list[str] = Field(default_factory=list, max_length=50)
    data_source: str = Field(min_length=1, max_length=300, pattern=_NON_EMPTY_LINE_PATTERN)
    owner: str = Field(min_length=1, max_length=200, pattern=_NON_EMPTY_LINE_PATTERN)
    rollback_condition: str = Field(min_length=1, max_length=500, pattern=_NON_EMPTY_LINE_PATTERN)

    @field_validator("exclusions")
    @classmethod
    def require_explicit_exclusions(cls, value: list[str]) -> list[str]:
        if any(not item or "\n" in item or "\r" in item for item in value):
            raise ValueError("exclusions must be non-empty single-line descriptions")
        if len(set(value)) != len(value):
            raise ValueError("exclusions must be unique")
        return value


class ReleasePolicy(BaseModel):
    """Strict policy that must be frozen before a controlled dual-run."""

    model_config = ConfigDict(extra="forbid", strict=True)

    schema_version: Literal["legal-agent-release-policy/v1"]
    policy_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    scope: Literal["controlled-offline-dual-run", "gate-shadow", "canary-rollout"]
    metrics: list[ReleaseMetricPolicy] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def require_unique_metric_names(self) -> ReleasePolicy:
        names = [metric.name for metric in self.metrics]
        if len(set(names)) != len(names):
            raise ValueError("metric names must be unique")
        return self


def load_release_policy(path: Path) -> tuple[ReleasePolicy, str]:
    """Load a strict policy and return the SHA-256 of its exact bytes."""
    try:
        raw = Path(path).read_bytes()
        parsed = json.loads(raw)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read release policy: {path}") from exc
    if not isinstance(parsed, dict):
        raise ValueError("release policy must be a JSON object")
    return ReleasePolicy.model_validate(parsed), hashlib.sha256(raw).hexdigest()


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate a predeclared Legal Agent release policy.")
    parser.add_argument("--policy", required=True, type=Path)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        policy, sha256 = load_release_policy(args.policy)
    except (ValidationError, ValueError) as exc:
        print(f"invalid release policy: {exc}", file=sys.stderr)
        return 2
    print(json.dumps({"policy_id": policy.policy_id, "scope": policy.scope, "sha256": sha256}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())


__all__ = ["ReleasePolicy", "load_release_policy", "main"]
