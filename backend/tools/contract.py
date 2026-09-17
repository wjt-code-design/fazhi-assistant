"""Typed adapter for deterministic contract analysis."""

from __future__ import annotations

from typing import Any

from .contracts import ContractBlock, ContractInput, ContractOutput, ToolContext, map_document


def _build_contract_data(text: str) -> dict[str, Any]:
    from domain_rules import build_contract_data

    return build_contract_data(text)


def analyze_contract(context: ToolContext, tool_input: ContractInput) -> ContractOutput:
    data = _build_contract_data(tool_input.text)
    evidence = [map_document(doc, context.law_as_of) for doc in data.get("docs", [])]
    blocks = [ContractBlock.model_validate(block) for block in data.get("blocks", [])]
    need_clarify = bool(data.get("need_clarify", False))
    statement = "需要补充合同全文后才能分析。" if need_clarify else f"已分析 {len(blocks)} 个合同条款。"
    return ContractOutput(
        statement=statement,
        truncated=bool(data.get("truncated", False)),
        need_clarify=need_clarify,
        blocks=blocks,
        evidence=evidence,
        risk_level=str(data["level"]) if data.get("level") not in (None, "") else None,
        basis=[str(item) for item in data.get("basis", [])],
    )
