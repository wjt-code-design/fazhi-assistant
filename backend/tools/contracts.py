"""Typed contracts for the legal-agent's read-only tool boundary."""

from __future__ import annotations

import hashlib
from datetime import date, datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, NonNegativeFloat, PositiveInt

ToolName = Literal[
    "retrieve_laws",
    "lookup_article",
    "analyze_contract",
    "retrieve_memory",
    "ask_user",
]


class ToolAuthorizationError(PermissionError):
    """A model attempted to cross a server-owned authorization boundary."""


class UnknownTool(LookupError):
    """The requested tool is not in the explicit server allowlist."""


class DuplicateToolCall(RuntimeError):
    """The same issue/tool/canonical arguments were already executed in this Gateway instance."""


class ToolContext(BaseModel):
    """Ownership and legal-time context constructed exclusively by trusted server code."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    user_id: PositiveInt
    conversation_id: PositiveInt
    run_id: str = Field(min_length=1)
    law_as_of: date
    # 本次工具调用的等待预算绝对截止点（time.monotonic() 基准，秒）。由 ToolGateway 在
    # 提交前注入；包装器必须在**启动新的远程调用之前**用它检查剩余时间，避免外层已放弃
    # 等待后内层还在开新请求。None = 无预算约束（历史调用方与测试替身行为完全不变）。
    tool_deadline_monotonic: float | None = None
    # R1-OB（2026-09-16 预注册）：判域输入扩展元信息（随 run.state 注入）。
    # case_domain=评测/灰度通道域码（tier-1）；user_question=本轮用户原始消息（tier-2 拼接源）。
    # 默认 None = 历史行为（判域退回纯 issue query 路径）。
    case_domain: str | None = None
    user_question: str | None = None


class EvidenceMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category: str | None = None
    version_id: str | None = None
    source_url: str | None = None
    source_document_sha256: str | None = None
    reviewed_at: date | None = None


class ToolEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_id: str | None = None
    source: str | None = None
    article: str | None = None
    snippet: str = Field(max_length=600)
    legal_validity: Literal["effective", "superseded", "unknown"] = "unknown"
    effective_date: date | None = None
    invalid_date: date | None = None
    score: NonNegativeFloat | None = None
    metadata: EvidenceMetadata = Field(default_factory=EvidenceMetadata)


class RetrievalMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str
    requested_k: PositiveInt
    returned_count: int = Field(ge=0)


class RetrieveLawsInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=1, max_length=4000)
    k: int = Field(default=4, ge=1, le=20)
    category: str | None = Field(default=None, max_length=100)


class RetrieveLawsOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["retrieve_laws"] = "retrieve_laws"
    statement: str = Field(min_length=1)
    evidence: list[ToolEvidence] = Field(default_factory=list)
    retrieval: RetrievalMetadata | None = None


class LookupArticleInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: str = Field(min_length=1, max_length=200)
    article: str = Field(min_length=1, max_length=100)


class LookupArticleOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["lookup_article"] = "lookup_article"
    statement: str = Field(min_length=1)
    evidence: list[ToolEvidence] = Field(default_factory=list)


class ContractInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1)


class ContractBlock(BaseModel):
    number: int = Field(alias="n", ge=1)
    label: str
    text: str
    articles: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid", populate_by_name=True, serialize_by_alias=True)


class ContractOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["analyze_contract"] = "analyze_contract"
    statement: str = Field(min_length=1)
    truncated: bool
    need_clarify: bool
    blocks: list[ContractBlock] = Field(default_factory=list)
    evidence: list[ToolEvidence] = Field(default_factory=list)
    risk_level: str | None = None
    basis: list[str] = Field(default_factory=list)


class RetrieveMemoryInput(BaseModel):
    """Model-visible memory controls; ownership always comes from ToolContext."""

    model_config = ConfigDict(extra="forbid")

    limit: int = Field(default=6, ge=1, le=20)


class MemoryMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message_id: int | None = None
    role: Literal["user", "assistant", "system"]
    content: str
    created_at: datetime | None = None


class RetrieveMemoryOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["retrieve_memory"] = "retrieve_memory"
    statement: str = Field(min_length=1)
    summary: str = ""
    messages: list[MemoryMessage] = Field(default_factory=list)


class AskUserInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str = Field(min_length=1, max_length=2000)


class AskUserOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["ask_user"] = "ask_user"
    statement: str = Field(min_length=1)
    question: str = Field(min_length=1)


ToolOutput = Annotated[
    RetrieveLawsOutput | LookupArticleOutput | ContractOutput | RetrieveMemoryOutput | AskUserOutput,
    Field(discriminator="kind"),
]


def __getattr__(name: str) -> Any:
    """Expose the canonical Observation lazily without creating a second DTO or import cycle."""

    if name == "Observation":
        from agent.schemas import Observation

        return Observation
    raise AttributeError(name)


def _date_value(value: Any) -> date | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def map_document(document: Any, law_as_of: date) -> ToolEvidence:
    """Copy only known provenance fields from a Document-like object."""

    metadata = getattr(document, "metadata", None) or {}
    content = str(getattr(document, "page_content", "") or "")
    effective_date = _date_value(metadata.get("effective_from") or metadata.get("effective_date"))
    invalid_date = _date_value(
        metadata.get("effective_to") or metadata.get("invalid_date") or metadata.get("expiry_date")
    )
    status = str(metadata.get("status") or "").strip()
    validity: Literal["effective", "superseded", "unknown"] = "unknown"
    if invalid_date is not None and invalid_date < law_as_of:
        validity = "superseded"
    elif status == "已废止" and invalid_date is None:
        validity = "superseded"
    elif (
        effective_date is not None
        and effective_date <= law_as_of
        and (invalid_date is None or law_as_of <= invalid_date)
    ):
        validity = "effective"
    elif status == "现行" and effective_date is None:
        validity = "effective"

    source_id = metadata.get("chunk_id") or metadata.get("id") or metadata.get("doc_id")
    if source_id in (None, ""):
        # 证据链断裂修复（Gate 5）：检索产物 metadata 只有 source/article，
        # 无 chunk_id/id/doc_id → 此前的 source_id 恒为 None → _convert_tool_evidence
        # 按 all() 校验全部丢弃 → evidence=0 → verifier 必 EVIDENCE_COVERAGE_DEFICIENT。
        # 用 (source, article, 内容前缀) 派生稳定 id（确定性、可追溯；chunk 内容变更即改变）。
        source_id = hashlib.sha256(
            f"law-v1|{metadata.get('source', '')}|{metadata.get('article', '')}|{content[:200]}".encode()
        ).hexdigest()[:24]
    raw_score = metadata.get("score")
    score = raw_score if isinstance(raw_score, (int, float)) and raw_score >= 0 else None
    return ToolEvidence(
        source_id=str(source_id) if source_id not in (None, "") else None,
        source=str(metadata["source"]) if metadata.get("source") not in (None, "") else None,
        article=str(metadata["article"]) if metadata.get("article") not in (None, "") else None,
        snippet=content[:600],
        legal_validity=validity,
        effective_date=effective_date,
        invalid_date=invalid_date,
        score=score,
        metadata=EvidenceMetadata(
            category=str(metadata["category"]) if metadata.get("category") not in (None, "") else None,
            version_id=str(metadata["version_id"]) if metadata.get("version_id") not in (None, "") else None,
            source_url=str(metadata["source_url"]) if metadata.get("source_url") not in (None, "") else None,
            source_document_sha256=(
                str(metadata["source_document_sha256"])
                if metadata.get("source_document_sha256") not in (None, "")
                else None
            ),
            reviewed_at=_date_value(metadata.get("reviewed_at")),
        ),
    )
