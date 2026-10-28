"""Typed exact-article lookup adapter."""

from __future__ import annotations

from typing import Any

from .contracts import LookupArticleInput, LookupArticleOutput, ToolContext, map_document


def _exact_article_lookup(**kwargs: Any) -> list[Any]:
    from retrieval import exact_article_lookup

    return exact_article_lookup(**kwargs)


def lookup_article(context: ToolContext, tool_input: LookupArticleInput) -> LookupArticleOutput:
    docs = _exact_article_lookup(
        source=tool_input.source,
        article=tool_input.article,
        cutoff=context.law_as_of.isoformat(),
    )
    evidence = [map_document(doc, context.law_as_of) for doc in docs]
    statement = f"精确检索到 {len(evidence)} 条法律资料。" if evidence else "未检索到指定法条。"
    return LookupArticleOutput(statement=statement, evidence=evidence)
