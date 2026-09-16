"""Strict, human-authored audit evidence for Legal Agent release decisions.

This module never classifies an answer itself.  It only validates that an
independent reviewer supplied a complete, traceable decision for every case.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

_TRACE_REF_PATTERN = r"^trace://[A-Za-z0-9][A-Za-z0-9._/-]{0,199}$"
_OPAQUE_IDENTIFIER_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._-]{0,99}$"


class AuditReviewer(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    id: str = Field(pattern=_OPAQUE_IDENTIFIER_PATTERN)
    role: Literal["independent-legal-reviewer", "independent-safety-reviewer", "joint-independent-review"]


class AuditFinding(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    code: str = Field(pattern=_OPAQUE_IDENTIFIER_PATTERN)
    trace_ref: str = Field(pattern=_TRACE_REF_PATTERN)


class AuditCase(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    id: str = Field(min_length=1)
    trace_ref: str = Field(pattern=_TRACE_REF_PATTERN)
    decision: Literal["pass", "finding"]
    findings: list[AuditFinding] = Field(default_factory=list)

    @model_validator(mode="after")
    def require_consistent_decision(self) -> AuditCase:
        if self.decision == "pass" and self.findings:
            raise ValueError("pass decisions cannot contain findings")
        if self.decision == "finding" and not self.findings:
            raise ValueError("finding decisions require at least one finding")
        return self


class AgentAuditEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    schema_version: Literal["legal-agent-agent-audit/v1"]
    release_manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    mode: Literal["agent"]
    reviewer: AuditReviewer
    reviewed_at: str = Field(min_length=1)
    cases: list[AuditCase] = Field(min_length=1)

    @model_validator(mode="after")
    def require_complete_unique_cases_and_timestamp(self) -> AgentAuditEvidence:
        try:
            parsed = datetime.fromisoformat(self.reviewed_at)
        except ValueError as exc:
            raise ValueError("reviewed_at must be ISO-8601") from exc
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ValueError("reviewed_at must include a UTC offset")
        ids = [case.id for case in self.cases]
        if len(set(ids)) != len(ids):
            raise ValueError("audit case ids must be unique")
        return self


def load_agent_audit_evidence(path: Path) -> tuple[AgentAuditEvidence, str]:
    try:
        raw = Path(path).read_bytes()
        parsed = json.loads(raw)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read agent audit evidence: {path}") from exc
    if not isinstance(parsed, dict):
        raise ValueError("agent audit evidence must be a JSON object")
    return AgentAuditEvidence.model_validate(parsed), hashlib.sha256(raw).hexdigest()


__all__ = ["AgentAuditEvidence", "load_agent_audit_evidence"]
