"""Typed adapter for deterministic contract analysis."""

from __future__ import annotations

from typing import Any

from .contracts import ContractBlock, ContractInput, ContractOutput, ToolContext, map_document


def _build_contract_data(text: str, cutoff: str | None = None) -> dict[str, Any]:
    from domain_rules import build_contract_data

    return build_contract_data(text, cutoff=cutoff)


def analyze_contract(context: ToolContext, tool_input: ContractInput) -> ContractOutput:
    # 基准日必须在**取数时**带上（同 `lookup_article` 口径）：`blocks[*]["articles"]` 与 `docs`
    # 由 domain_rules 同源构建，事后按 `context.law_as_of` 只改得动 evidence 的 validity 标注，
    # 改不动已经按现行法取完的条号。
    data = _build_contract_data(tool_input.text, cutoff=context.law_as_of.isoformat())
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
