"""Thin typed adapter over the existing legal retrieval algorithm."""

from __future__ import annotations

from typing import Any

from .contracts import RetrievalMetadata, RetrieveLawsInput, RetrieveLawsOutput, ToolContext, map_document


def _retrieve(**kwargs: Any) -> list[Any]:
    from retrieval import retrieve

    return retrieve(**kwargs)


def retrieve_laws(context: ToolContext, tool_input: RetrieveLawsInput) -> RetrieveLawsOutput:
    kwargs: dict[str, Any] = {
        "query": tool_input.query,
        "k": tool_input.k,
        "category": tool_input.category,
        "cutoff": context.law_as_of.isoformat(),
    }
    # 仅在有预算时才透传：无 deadline 的调用方（历史调用、测试替身）收到的参数与历史完全一致。
    if context.tool_deadline_monotonic is not None:
        kwargs["deadline_monotonic"] = context.tool_deadline_monotonic
    docs = _retrieve(**kwargs)
    # R1（2026-09-14，预注册 dept-law-filter-r1）：判域后剔除「他域专属程序法」条文。
    # 判域用 issue query（Agent 逐争点检索的聚焦问句）。mixed/零指示 → 不过滤（保守，行为同现状）。
    # 开关 agent_dept_filter=False 时零行为变化；实体法永不过滤。
    from agent.dept_guard import domain_of_text, filter_docs_by_domain
    from settings import settings as _settings

    if _settings.agent_dept_filter:
        domain = domain_of_text(tool_input.query)
        if domain is not None:
            before = len(docs)
            docs = filter_docs_by_domain(docs, domain)
            if len(docs) < before:
                import logging

                logging.getLogger("legal.agent").info(
                    "dept_filter_removed",
                    extra={"query": tool_input.query, "domain": domain, "removed": before - len(docs)},
                )
    # ⚠️ 2026-09-10 首轮「要件法条确定性补充」接线已按预登记**回退**（判据文件：
    #    waxis-verification-preregistration.json；审计：writer-axis-verification.txt）。
    #   双集验收显示：①可靠性守卫恶化 —— 评测集 completed 6/10→5/10，出现 UNKNOWN_EVIDENCE_ID /
    #   UNKNOWN_MISSING_INFORMATION 两个新错误码，留出集仅 1/5 完成；②留出集 HIT 21% <
    #   评测集 37%−10pp ⇒ 按预登记判**过拟合**。首要嫌疑是证据池膨胀（每 issue 4→8–23 条，
    #   writer payload 拉长导致引用错 id / 漏绑定），但 n=1 无法归因定论。
    #   `domain_rules.statute_supplement_docs`（映射表 + 单测）**保留为暂存未接线状态**：
    #   重做前必须先解决 (a) 每 issue 注入上限 (b) 补充文档在 map_document 的存活问题，
    #   并以重复轮次排除随机性。
    evidence = [map_document(doc, context.law_as_of) for doc in docs]
    count = len(evidence)
    statement = f"检索到 {count} 条法律资料。" if count else "未检索到匹配的法律资料。"
    return RetrieveLawsOutput(
        statement=statement,
        evidence=evidence,
        retrieval=RetrievalMetadata(query=tool_input.query, requested_k=tool_input.k, returned_count=count),
    )
