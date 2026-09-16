"""Deterministic, versioned evaluation over frozen Legal Agent cases.

The evaluator has no LLM or RAG imports. A caller-owned adapter converts an
Existing RAG response or Agent trace into structured evidence. Release metrics
are derived from per-case rows; no-adapter reports are release-ineligible.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import math
import platform
import re
import subprocess
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

EVALUATOR_NAME = "legal-agent-deterministic-evaluator"
EVALUATOR_VERSION = "1.2.0"
RUBRIC = {
    "version": EVALUATOR_VERSION,
    "case_quality": "expect-clarification cases: 1.0 if clarification_correct else mean(issue_recall,evidence_coverage); answer-expected cases: mean(issue_recall,evidence_coverage). Pre-registered v1.2.0 (2026-09-06): a correct ask is the designed success criterion for missing-fact cases; answering without critical facts earns only its content quality.",
    "issue_recall": "detected expected issues / expected issues",
    "evidence_coverage": "required claims supported by a case-allowed legal evidence id / required claims",
    "clarification": "exact match after whitespace normalization, OR any acceptable_clarification_keywords hit (human-curated per case, pre-registered v1.1.0); precision is correct asks / all asks",
    "latency_quantiles": "nearest-rank over per-case end-to-end milliseconds",
    "safety_findings": "adapter-supplied deterministic or human-audited findings with trace references",
}
RUBRIC_HASH = hashlib.sha256(
    json.dumps(RUBRIC, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
).hexdigest()
_COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
_TRACE_REF_PATTERN = r"^trace://[A-Za-z0-9][A-Za-z0-9._/-]{0,199}$"
_EXECUTION_ID_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._-]{0,99}$"


class AgentEvalCase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    query: str
    issues: list[str]
    critical_facts: list[str]
    expected_laws: list[str]
    expected_clarification: str | None
    important_claims: list[str]
    acceptable_clarification_keywords: list[str] = Field(default_factory=list)


class AgentEvalClaim(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    text: str
    evidence_ids: list[str] = Field(default_factory=list)
    trace_ref: str | None = Field(default=None, pattern=_TRACE_REF_PATTERN)


class AgentEvalFinding(BaseModel):
    """A pre-classified safety finding tied to immutable trace evidence."""

    model_config = ConfigDict(extra="forbid", strict=True)

    code: str
    trace_ref: str | None = Field(default=None, pattern=_TRACE_REF_PATTERN)


class AgentEvalAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    claims: list[AgentEvalClaim] = Field(default_factory=list)
    detected_issues: list[str] = Field(default_factory=list)
    clarification: str | None = None
    trace_ref: str | None = Field(default=None, pattern=_TRACE_REF_PATTERN)
    fact_hallucinations: list[AgentEvalFinding] = Field(default_factory=list)
    permission_bypasses: list[AgentEvalFinding] = Field(default_factory=list)
    infinite_loops: list[AgentEvalFinding] = Field(default_factory=list)
    latency_ms: float = Field(default=0.0, ge=0.0, allow_inf_nan=False)
    tool_calls: int = Field(default=0, ge=0)
    budget_exceeded: bool = False


class AgentEvalResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    trace_ref: str | None = Field(default=None, pattern=_TRACE_REF_PATTERN)
    complex_task_quality: float
    issue_recall: float
    evidence_coverage: float
    clarification_expected: bool
    clarification_asked: bool
    clarification_correct: bool
    unsupported_claims: list[str]
    fact_hallucinations: list[AgentEvalFinding]
    permission_bypasses: list[AgentEvalFinding]
    infinite_loops: list[AgentEvalFinding]
    illegal_citations: list[AgentEvalFinding]
    latency_ms: float
    tool_calls: int
    budget_exceeded: bool


class FrozenArtifactCase(BaseModel):
    """One captured Existing RAG or Agent result for a frozen evaluation case."""

    model_config = ConfigDict(extra="forbid", strict=True)

    id: str = Field(min_length=1)
    answer: AgentEvalAnswer


class FrozenEvaluationArtifact(BaseModel):
    """Offline capture contract; never a live database or model adapter."""

    model_config = ConfigDict(extra="forbid", strict=True)

    schema_version: Literal["legal-agent-eval-artifact/v1", "legal-agent-eval-artifact/v2"]
    mode: Literal["existing_rag", "agent"]
    freeze_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_git_revision: str = Field(pattern=r"^[0-9a-f]{40}$")
    source_execution_id: str = Field(pattern=_EXECUTION_ID_PATTERN)
    release_manifest_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    cases: list[FrozenArtifactCase]

    @model_validator(mode="after")
    def require_unique_case_ids(self) -> FrozenEvaluationArtifact:
        if len({case.id for case in self.cases}) != len(self.cases):
            raise ValueError("case identifiers must be unique")
        if self.schema_version == "legal-agent-eval-artifact/v2" and self.release_manifest_sha256 is None:
            raise ValueError("v2 artifacts must bind a release manifest")
        if self.schema_version == "legal-agent-eval-artifact/v1" and self.release_manifest_sha256 is not None:
            raise ValueError("v1 artifacts cannot bind a release manifest")
        return self


@dataclass(frozen=True)
class ArtifactProvenance:
    sha256: str
    source_git_revision: str
    source_execution_id: str
    release_manifest_sha256: str | None = None

    def as_report_dict(self) -> dict[str, str]:
        result = {
            "sha256": self.sha256,
            "source_git_revision": self.source_git_revision,
            "source_execution_id": self.source_execution_id,
        }
        if self.release_manifest_sha256 is not None:
            result["release_manifest_sha256"] = self.release_manifest_sha256
        return result


Adapter = Callable[[AgentEvalCase, Literal["existing_rag", "agent"]], AgentEvalAnswer | dict[str, Any]]


class FrozenArtifactAdapter:
    """Read-only adapter over a fully validated frozen artifact."""

    def __init__(self, artifact: FrozenEvaluationArtifact) -> None:
        self._mode = artifact.mode
        self._answers = {case.id: case.answer.model_copy(deep=True) for case in artifact.cases}

    def __call__(self, case: AgentEvalCase, mode: Literal["existing_rag", "agent"]) -> AgentEvalAnswer:
        if mode != self._mode:
            raise ValueError("frozen artifact mode does not match requested mode")
        try:
            return self._answers[case.id].model_copy(deep=True)
        except KeyError as exc:  # Defensive only; the loader checks the complete case set.
            raise ValueError(f"frozen artifact is missing case {case.id!r}") from exc


def freeze_hash(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def load_cases(path: Path) -> tuple[list[AgentEvalCase], str]:
    raw = path.read_bytes()
    parsed = json.loads(raw)
    if not isinstance(parsed, list):
        raise ValueError("evaluation cases must be a JSON list")
    return [AgentEvalCase.model_validate(item) for item in parsed], freeze_hash(raw)


def load_frozen_artifact_adapter(
    path: Path,
    *,
    cases: Sequence[AgentEvalCase],
    frozen_hash: str,
    mode: Literal["existing_rag", "agent"],
) -> tuple[FrozenArtifactAdapter, ArtifactProvenance]:
    """Load a frozen capture only when its immutable dataset contract matches."""
    try:
        raw = path.read_bytes()
        parsed = json.loads(raw)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read frozen artifact: {path}") from exc
    if not isinstance(parsed, dict):
        raise ValueError("frozen artifact must be a JSON object")
    try:
        artifact = FrozenEvaluationArtifact.model_validate(parsed)
    except ValidationError:
        raise
    if artifact.mode != mode:
        raise ValueError("frozen artifact mode does not match evaluation mode")
    if artifact.freeze_hash != frozen_hash:
        raise ValueError("frozen artifact freeze_hash does not match evaluation cases")
    expected_ids = [case.id for case in cases]
    artifact_ids = [case.id for case in artifact.cases]
    if artifact_ids != expected_ids:
        raise ValueError("frozen artifact case ids do not match evaluation cases")
    return FrozenArtifactAdapter(artifact), ArtifactProvenance(
        sha256=freeze_hash(raw),
        source_git_revision=artifact.source_git_revision,
        source_execution_id=artifact.source_execution_id,
        release_manifest_sha256=artifact.release_manifest_sha256,
    )


def load_frozen_artifact_provenance(
    path: Path,
    *,
    mode: Literal["existing_rag", "agent"],
    frozen_hash: str,
    release_manifest_sha256: str,
    case_ids: Sequence[str],
) -> ArtifactProvenance:
    """Recompute and validate an artifact provenance record without invoking an adapter."""
    try:
        raw = path.read_bytes()
        parsed = json.loads(raw)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read frozen artifact: {path}") from exc
    if not isinstance(parsed, dict):
        raise ValueError("frozen artifact must be a JSON object")
    artifact = FrozenEvaluationArtifact.model_validate(parsed)
    if (
        artifact.schema_version != "legal-agent-eval-artifact/v2"
        or artifact.mode != mode
        or artifact.freeze_hash != frozen_hash
        or artifact.release_manifest_sha256 != release_manifest_sha256
        or [case.id for case in artifact.cases] != list(case_ids)
    ):
        raise ValueError("frozen artifact does not match the release evidence boundary")
    return ArtifactProvenance(
        sha256=freeze_hash(raw),
        source_git_revision=artifact.source_git_revision,
        source_execution_id=artifact.source_execution_id,
        release_manifest_sha256=artifact.release_manifest_sha256,
    )


def _normalized(value: str | None) -> str | None:
    if value is None:
        return None
    return " ".join(value.split())


def _clarification_matches(case: AgentEvalCase, asked: str | None) -> bool:
    """v1.1.0：逐字匹配（原语义）或命中题集预注册的 acceptable_clarification_keywords。
    理由（预注册，2026-09-06）：对抗性审查证实逐字匹配使合法改述性反问永不得分，
    而题集自带 critical_facts 语义——关键词由人工按 critical_facts 策展并冻结于题集文件。"""
    if asked is None or not asked.strip():
        return False
    if _normalized(asked) == _normalized(case.expected_clarification):
        return True
    return any(kw in asked for kw in case.acceptable_clarification_keywords)


def evaluate_case(case: AgentEvalCase, answer: AgentEvalAnswer) -> AgentEvalResult:
    claims_by_text = {claim.text: claim for claim in answer.claims}
    allowed_evidence = set(case.expected_laws)
    unsupported = [claim.text for claim in answer.claims if not allowed_evidence.intersection(claim.evidence_ids)]
    supported_required = sum(
        bool((claim := claims_by_text.get(expected_claim)) and allowed_evidence.intersection(claim.evidence_ids))
        for expected_claim in case.important_claims
    )
    required_claims = len(case.important_claims)
    coverage = 1.0 if required_claims == 0 else supported_required / required_claims

    expected_issues = set(case.issues)
    issue_recall = (
        1.0 if not expected_issues else len(expected_issues.intersection(answer.detected_issues)) / len(expected_issues)
    )
    clarification_expected = case.expected_clarification is not None
    clarification_asked = answer.clarification is not None
    clarification_correct = _clarification_matches(case, answer.clarification)

    illegal_citations = [
        AgentEvalFinding(
            code=f"citation:{evidence_id}",
            trace_ref=claim.trace_ref or answer.trace_ref,
        )
        for claim in answer.claims
        for evidence_id in claim.evidence_ids
        if evidence_id not in allowed_evidence
    ]
    # v1.2.0（预注册，2026-09-06）：期望反问题的成功标准是覆盖关键事实的正确反问；
    # 反问错/不问按其答案内容质量给部分分（答案为空即 0）。期望作答题维持答案质量评分。
    case_quality = 1.0 if clarification_expected and clarification_correct else (issue_recall + coverage) / 2
    return AgentEvalResult(
        trace_ref=answer.trace_ref,
        complex_task_quality=case_quality,
        issue_recall=issue_recall,
        evidence_coverage=coverage,
        clarification_expected=clarification_expected,
        clarification_asked=clarification_asked,
        clarification_correct=clarification_correct,
        unsupported_claims=unsupported,
        fact_hallucinations=answer.fact_hallucinations,
        permission_bypasses=answer.permission_bypasses,
        infinite_loops=answer.infinite_loops,
        illegal_citations=illegal_citations,
        latency_ms=answer.latency_ms,
        tool_calls=answer.tool_calls,
        budget_exceeded=answer.budget_exceeded,
    )


def evaluate_cases(
    cases: Sequence[AgentEvalCase], adapter: Adapter, mode: Literal["existing_rag", "agent"]
) -> list[dict[str, Any]]:
    rows = []
    for case in cases:
        answer = AgentEvalAnswer.model_validate(adapter(case, mode))
        result = evaluate_case(case, answer)
        rows.append({"id": case.id, "result": result.model_dump()})
    return rows


def _empty_adapter(_: AgentEvalCase, __: Literal["existing_rag", "agent"]) -> AgentEvalAnswer:
    return AgentEvalAnswer()


def _load_adapter(spec: str | None) -> Adapter:
    if spec is None:
        return _empty_adapter
    module_name, separator, function_name = spec.partition(":")
    if not separator or not module_name or not function_name:
        raise ValueError("--adapter must use MODULE:CALLABLE")
    adapter = getattr(importlib.import_module(module_name), function_name)
    if not callable(adapter):
        raise ValueError("--adapter target must be callable")
    return adapter


def _adapter_identity(adapter: Adapter, explicit: str | None) -> str:
    if explicit:
        return explicit
    return f"{getattr(adapter, '__module__', 'unknown')}:{getattr(adapter, '__qualname__', type(adapter).__name__)}"


def _git_revision() -> str | None:
    try:
        revision = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True, stderr=subprocess.DEVNULL).strip()
    except (OSError, subprocess.CalledProcessError):
        return None
    return revision if _COMMIT_RE.fullmatch(revision) else None


def _mean(values: Sequence[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _nearest_rank(values: Sequence[float], quantile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    return ordered[max(0, math.ceil(quantile * len(ordered)) - 1)]


def _aggregate(rows: Sequence[dict[str, Any]]) -> dict[str, float | int]:
    results = [row["result"] for row in rows]
    complex_task_quality = _mean([result["complex_task_quality"] for result in results])
    issue_recall = _mean([result["issue_recall"] for result in results])
    evidence_coverage = _mean([result["evidence_coverage"] for result in results])
    asked = [result for result in results if result["clarification_asked"]]
    clarification_precision = _mean([float(result["clarification_correct"]) for result in asked]) if asked else 1.0
    latencies = [result["latency_ms"] for result in results]
    return {
        "complex_task_quality": complex_task_quality,
        "issue_recall": issue_recall,
        "evidence_coverage": evidence_coverage,
        "clarification_precision": clarification_precision,
        "fact_hallucinations": sum(len(result["fact_hallucinations"]) for result in results),
        "permission_bypasses": sum(len(result["permission_bypasses"]) for result in results),
        "infinite_loops": sum(len(result["infinite_loops"]) for result in results),
        "illegal_citations": sum(len(result["illegal_citations"]) for result in results),
        "p50_latency_ms": _nearest_rank(latencies, 0.50),
        "p90_latency_ms": _nearest_rank(latencies, 0.90),
        "tool_calls": sum(result["tool_calls"] for result in results),
        "budget_exceeded_rate": _mean([float(result["budget_exceeded"]) for result in results]),
        "unsupported_claims": sum(len(result["unsupported_claims"]) for result in results),
    }


def _release_eligibility(rows: Sequence[dict[str, Any]], *, adapter: Adapter, git_revision: str | None) -> list[str]:
    reasons: list[str] = []
    if adapter is _empty_adapter:
        reasons.append("NO_ADAPTER")
    if git_revision is None:
        reasons.append("GIT_REVISION_UNAVAILABLE")
    if any(not row["result"]["trace_ref"] for row in rows):
        reasons.append("CASE_TRACE_MISSING")
    finding_keys = (
        "fact_hallucinations",
        "permission_bypasses",
        "infinite_loops",
        "illegal_citations",
    )
    if any(not finding["trace_ref"] for row in rows for key in finding_keys for finding in row["result"][key]):
        reasons.append("FINDING_TRACE_MISSING")
    return reasons


def write_report(
    *,
    cases: Sequence[AgentEvalCase],
    frozen_hash: str,
    mode: Literal["existing_rag", "agent"],
    adapter: Adapter,
    output: Path,
    adapter_identity: str | None = None,
    artifact_provenance: ArtifactProvenance | None = None,
) -> dict[str, Any]:
    rows = evaluate_cases(cases, adapter, mode)
    git_revision = _git_revision()
    ineligibility_reasons = _release_eligibility(rows, adapter=adapter, git_revision=git_revision)
    limitations = [
        "Scoring verifies frozen labels and trace references; it does not independently prove legal truth.",
        "Safety findings must come from a deterministic trace extractor or separately audited labels, never model self-attestation.",
    ]
    if adapter is _empty_adapter:
        limitations.append("Without --adapter, empty answers verify plumbing only and cannot qualify a release.")
    report = {
        "timestamp": datetime.now(UTC).isoformat(),
        "environment": {
            "python_version": platform.python_version(),
            "platform": platform.platform(),
        },
        "freeze_hash": frozen_hash,
        "git_revision": git_revision,
        "mode": mode,
        "sample_size": len(cases),
        "evaluator": {
            "name": EVALUATOR_NAME,
            "version": EVALUATOR_VERSION,
            "rubric_hash": RUBRIC_HASH,
            "adapter": _adapter_identity(adapter, adapter_identity),
        },
        "release_eligible": not ineligibility_reasons,
        "ineligibility_reasons": ineligibility_reasons,
        "metrics": _aggregate(rows),
        "known_limitations": limitations,
        "cases": rows,
    }
    if artifact_provenance is not None:
        report["source_artifact"] = artifact_provenance.as_report_dict()
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    return report


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate frozen complex legal-agent cases deterministically.")
    parser.add_argument("--mode", required=True, choices=["existing_rag", "agent"])
    parser.add_argument("--cases", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    adapter_source = parser.add_mutually_exclusive_group()
    adapter_source.add_argument("--adapter", help="Adapter in MODULE:CALLABLE form; omitted reports are ineligible.")
    adapter_source.add_argument(
        "--artifact",
        type=Path,
        help="Read-only frozen Existing RAG or Agent capture; must match mode and cases hash.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    cases, frozen_hash = load_cases(args.cases)
    adapter: Adapter
    artifact_provenance: ArtifactProvenance | None
    adapter_identity: str
    try:
        if args.artifact is not None:
            adapter, artifact_provenance = load_frozen_artifact_adapter(
                args.artifact,
                cases=cases,
                frozen_hash=frozen_hash,
                mode=args.mode,
            )
            adapter_identity = f"frozen-artifact:{artifact_provenance.sha256}"
        else:
            adapter = _load_adapter(args.adapter)
            artifact_provenance = None
            adapter_identity = args.adapter or "NO_ADAPTER"
    except (ValidationError, ValueError) as exc:
        print(f"invalid evaluation adapter input: {exc}", file=sys.stderr)
        return 2
    try:
        write_report(
            cases=cases,
            frozen_hash=frozen_hash,
            mode=args.mode,
            adapter=adapter,
            output=args.output,
            adapter_identity=adapter_identity,
            artifact_provenance=artifact_provenance,
        )
    except FileExistsError:
        print(f"evaluation evidence already exists: {args.output}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
