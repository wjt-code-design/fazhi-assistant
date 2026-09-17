"""Strict offline dual-run capture protocol; never executes a model call."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class CaptureControls(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    timeout_seconds: int = Field(ge=1, le=3600)
    total_timeout_seconds: int = Field(ge=1, le=86_400)
    max_retries: int = Field(ge=0, le=10)
    concurrency: int = Field(ge=1, le=32)
    cache_policy: Literal["disabled", "frozen"]
    network_policy: Literal["offline", "frozen-knowledge-only"]
    max_output_tokens: int = Field(ge=1, le=100_000)
    max_tool_calls: int = Field(ge=0, le=1000)
    retain_failure_rows: Literal[True]

    @model_validator(mode="after")
    def require_total_timeout_to_cover_one_case(self) -> CaptureControls:
        if self.total_timeout_seconds < self.timeout_seconds:
            raise ValueError("total timeout cannot be below per-case timeout")
        return self


class CaptureProtocol(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    schema_version: Literal["legal-agent-capture-protocol/v1"]
    protocol_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,99}$")
    case_set_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    modes: list[Literal["existing_rag", "agent"]] = Field(min_length=2, max_length=2)
    controls: CaptureControls

    @model_validator(mode="after")
    def require_existing_then_agent_modes(self) -> CaptureProtocol:
        if self.modes != ["existing_rag", "agent"]:
            raise ValueError("modes must be existing_rag followed by agent")
        return self


def load_capture_protocol(path: Path) -> tuple[CaptureProtocol, str]:
    try:
        raw = Path(path).read_bytes()
        parsed = json.loads(raw)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read capture protocol: {path}") from exc
    if not isinstance(parsed, dict):
        raise ValueError("capture protocol must be a JSON object")
    return CaptureProtocol.model_validate(parsed), hashlib.sha256(raw).hexdigest()


__all__ = ["CaptureProtocol", "load_capture_protocol"]
