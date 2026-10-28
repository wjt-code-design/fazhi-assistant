"""Pure, deterministic classification for Legal Agent V1 Shadow Mode.

Precedence is intentionally explicit: policy, non-agent intent, document work,
material complexity, exact-article lookup, then the single-issue default.  This
module owns the machine-readable Gate reason vocabulary; observers import the
technical-failure code from here instead of copying it.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, ConfigDict, field_validator

if TYPE_CHECKING:
    from request_bootstrap import RequestBootstrap

GateMode = Literal["fast_path", "agent_path", "clarify", "refuse"]
GateComplexity = Literal["simple", "complex", "policy"]
GateReason = Literal[
    "POLICY_CHEATING_REQUEST",
    "NON_AGENT_INTENT",
    "DOCUMENT_REVIEW",
    "DOCUMENT_COMPARISON",
    "MULTI_ISSUE",
    "MISSING_FACTS",
    "MULTI_STAGE",
    "MULTI_TURN_CONTEXT",
    "CRIMINAL_CIVIL_BOUNDARY",
    "EXACT_ARTICLE_LOOKUP",
    "SINGLE_ISSUE_QUERY",
]

POLICY_CHEATING_REQUEST: GateReason = "POLICY_CHEATING_REQUEST"
NON_AGENT_INTENT: GateReason = "NON_AGENT_INTENT"
DOCUMENT_REVIEW: GateReason = "DOCUMENT_REVIEW"
DOCUMENT_COMPARISON: GateReason = "DOCUMENT_COMPARISON"
MULTI_ISSUE: GateReason = "MULTI_ISSUE"
MISSING_FACTS: GateReason = "MISSING_FACTS"
MULTI_STAGE: GateReason = "MULTI_STAGE"
MULTI_TURN_CONTEXT: GateReason = "MULTI_TURN_CONTEXT"
CRIMINAL_CIVIL_BOUNDARY: GateReason = "CRIMINAL_CIVIL_BOUNDARY"
EXACT_ARTICLE_LOOKUP: GateReason = "EXACT_ARTICLE_LOOKUP"
SINGLE_ISSUE_QUERY: GateReason = "SINGLE_ISSUE_QUERY"
GATE_TECHNICAL_FAILURE = "GATE_TECHNICAL_FAILURE"

DECISION_REASON_CODE_ORDER: tuple[GateReason, ...] = (
    POLICY_CHEATING_REQUEST,
    NON_AGENT_INTENT,
    DOCUMENT_COMPARISON,
    DOCUMENT_REVIEW,
    MULTI_ISSUE,
    MISSING_FACTS,
    MULTI_STAGE,
    MULTI_TURN_CONTEXT,
    CRIMINAL_CIVIL_BOUNDARY,
    EXACT_ARTICLE_LOOKUP,
    SINGLE_ISSUE_QUERY,
)

_EXACT_ARTICLE_RE = re.compile(r"第\s*[一二三四五六七八九十百千万零〇两\d]+\s*条")
_STAGED_RE = re.compile(r"先.{0,40}(?:再|然后|之后)")
_DOCUMENT_TERMS = ("合同", "协议", "文书", "文件", "条款")
_COMPARISON_TERMS = ("比较", "对比", "差异", "区别", "两份")
_REVIEW_TERMS = ("审查", "审核", "评估", "风险", "看看")
_MULTI_TURN_TERMS = ("上面", "上述", "刚才", "前面", "之前说", "继续", "这个问题", "那份")
_EXPLICIT_FACT_GAPS = ("信息不足", "事实不清", "不清楚", "未说明", "没说明", "没有约定", "没约定")
_DUE_DATE_TERMS = ("还款日期", "还款期限", "到期日", "约定还款", "应当还款")

_CRIMINAL_CIVIL_TERMS = ("报警", "报案")
_CRIMINAL_CIVIL_PAIRS = (
    ("报警", "起诉"),
    ("报警", "仲裁"),
    ("报案", "起诉"),
    ("报案", "仲裁"),
    ("报警", "立案"),
    ("报案", "立案"),
)


class AgentGateDecision(BaseModel):
    """Strict immutable envelope for a Gate prediction."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    mode: GateMode
    complexity: GateComplexity
    reason_codes: tuple[GateReason, ...]

    @field_validator("reason_codes", mode="before")
    @classmethod
    def _freeze_reason_codes(cls, value: object) -> object:
        # Keep existing Python/JSON callers compatible while storing only an
        # immutable tuple inside the frozen decision envelope.
        return tuple(value) if isinstance(value, list) else value

    @field_validator("reason_codes")
    @classmethod
    def _validate_reason_codes(cls, value: tuple[GateReason, ...]) -> tuple[GateReason, ...]:
        if not value or len(value) != len(set(value)):
            raise ValueError("reason_codes must be non-empty and unique")
        expected = tuple(code for code in DECISION_REASON_CODE_ORDER if code in value)
        if value != expected:
            raise ValueError("reason_codes must follow the stable canonical order")
        return value


def _text(bootstrap: RequestBootstrap) -> str:
    return (bootstrap.user_text or bootstrap.raw_query or "").strip()


def _is_document_comparison(bootstrap: RequestBootstrap, text: str) -> bool:
    has_document = bootstrap.contract_mode or any(term in text for term in _DOCUMENT_TERMS)
    return has_document and any(term in text for term in _COMPARISON_TERMS)


def _is_document_review(bootstrap: RequestBootstrap, text: str) -> bool:
    if bootstrap.contract_mode:
        return True
    return any(term in text for term in _DOCUMENT_TERMS) and any(term in text for term in _REVIEW_TERMS)


def _has_multi_issue(text: str) -> bool:
    issue_signals = (
        bool(re.search(r"(?:[一二三四五六七八九十百千万两\d]+年(?:前|后)?|诉讼时效)", text)),
        any(term in text for term in ("承认债务", "承认过债务", "重新确认", "催款", "中断")),
        any(term in text for term in ("起诉", "仲裁", "执行", "上诉")),
    )
    if sum(issue_signals) >= 2:
        return True
    return any(term in text for term in ("同时", "并且", "另外", "还涉及", "以及")) and any(
        term in text for term in ("能否", "是否", "怎么办", "责任", "赔偿", "起诉", "仲裁")
    )


def _has_missing_facts(text: str) -> bool:
    if any(term in text for term in _EXPLICIT_FACT_GAPS):
        return True
    loan_with_elapsed_time = any(term in text for term in ("借钱", "借款", "欠款", "债务")) and bool(
        re.search(r"(?:[一二三四五六七八九十百千万两\d]+年(?:前|后)?|诉讼时效)", text)
    )
    return loan_with_elapsed_time and not any(term in text for term in _DUE_DATE_TERMS)


def _has_multi_stage(text: str) -> bool:
    if _STAGED_RE.search(text):
        return True
    stage_count = sum(term in text for term in ("仲裁", "起诉", "一审", "二审", "执行", "申请复议"))
    return stage_count >= 2 and any(term in text for term in ("步骤", "流程", "阶段", "如何办理"))


def _has_material_multi_turn(bootstrap: RequestBootstrap, text: str) -> bool:
    return bool(bootstrap.recent or bootstrap.recent_messages) and any(term in text for term in _MULTI_TURN_TERMS)


def _is_criminal_civil_boundary(text: str) -> bool:
    """报案救济 vs 民事救济分叉问询 → agent（可出现 MISSING_FACTS 澄清）。"""
    if not any(term in text for term in _CRIMINAL_CIVIL_TERMS):
        return False
    return any(a in text and b in text for a, b in _CRIMINAL_CIVIL_PAIRS)


def _complex_reason_codes(bootstrap: RequestBootstrap, text: str) -> tuple[GateReason, ...]:
    detected = {
        code
        for code, present in (
            (MULTI_ISSUE, _has_multi_issue(text)),
            (MISSING_FACTS, _has_missing_facts(text)),
            (MULTI_STAGE, _has_multi_stage(text)),
            (MULTI_TURN_CONTEXT, _has_material_multi_turn(bootstrap, text)),
        )
        if present
    }
    return tuple(code for code in DECISION_REASON_CODE_ORDER if code in detected)


def decide_gate(bootstrap: RequestBootstrap) -> AgentGateDecision:
    """Classify one committed bootstrap without I/O or mutable state."""
    text = _text(bootstrap)

    if bootstrap.intent == "cheating_request":
        return AgentGateDecision(mode="refuse", complexity="policy", reason_codes=(POLICY_CHEATING_REQUEST,))

    if bootstrap.intent == "chitchat" or not text:
        return AgentGateDecision(mode="fast_path", complexity="simple", reason_codes=(NON_AGENT_INTENT,))

    complex_reasons = _complex_reason_codes(bootstrap, text)
    if bootstrap.intent == "study_aid" and not complex_reasons:
        return AgentGateDecision(mode="fast_path", complexity="simple", reason_codes=(NON_AGENT_INTENT,))

    if _is_document_comparison(bootstrap, text):
        return AgentGateDecision(mode="agent_path", complexity="complex", reason_codes=(DOCUMENT_COMPARISON,))

    if _is_document_review(bootstrap, text):
        return AgentGateDecision(mode="agent_path", complexity="complex", reason_codes=(DOCUMENT_REVIEW,))

    if _is_criminal_civil_boundary(text):
        return AgentGateDecision(mode="agent_path", complexity="complex", reason_codes=(CRIMINAL_CIVIL_BOUNDARY,))

    if complex_reasons:
        return AgentGateDecision(mode="agent_path", complexity="complex", reason_codes=complex_reasons)

    if _EXACT_ARTICLE_RE.search(text):
        return AgentGateDecision(mode="fast_path", complexity="simple", reason_codes=(EXACT_ARTICLE_LOOKUP,))

    return AgentGateDecision(mode="fast_path", complexity="simple", reason_codes=(SINGLE_ISSUE_QUERY,))
