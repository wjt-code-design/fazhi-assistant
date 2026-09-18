"""伪调用检测（R12，2026-09-18）。外部 harness 方案差距分析 P0-3：方案 §3.1 要求
「工具入口计数 vs 模型声称的调用数比对，不等即告警」——对应本仓库**已知缺陷**：
deepseek-v4-flash 的"伪调用"（工具调用被渲染为 XML 文本而非真实执行，只能靠肉眼发现；
见项目记忆 known defects b）。当前 agent 链路已有"重复调用"检测（state_machine.
register_action 的 fingerprint 判重），但没有"**声称执行过而实际从未执行**"的检测。

检测对象：writer 产出的 claim 文本中**断言执行过某动作**的确定性短语
（"经检索""合同条款显示""您已确认"……），与 state 中的真实执行记录比对：
- 检索类短语 → 需要 retrieve_laws / lookup_article 有 succeeded 记录，**或**
  state.evidence 非空（证据由工具获取， Observation.tool_name 可能为 None）；
- 合同分析类 → 需要 analyze_contract succeeded；
- 历史会话类 → 需要 retrieve_memory succeeded；
- 用户确认类 → 需要 state.clarifications > 0（真的追问过用户）。

设计边界（自审记录）：
1. **否定形态不误报**："未经检索""未查询到""没有检索到"不构成"声称执行过"——
   短语全部带否定前置 lookbehind（未/没/无/有，覆盖"没有/并无"形态；代价是
   "均有检索到"这类罕见肯定形态漏报，宁可漏报不误杀）。"经检索未发现"仍会被
   标记：它断言了"检索发生过"。
2. **evidence 兜底**：证据observations（tool_name=None）也意味着检索真实发生过，
   故检索类以「工具 succeeded ∪ 证据存在」为充分条件，避免把合法引用误杀。
3. **误伤面刻意收窄**：只收录"断言执行"的强短语；"根据您提供"映射的是 facts
   （SourceType.USER，首轮就有），不算"确认动作"，不收录。
4. 消费方：writer/verifier 在 `settings.phantom_tool_check` 开启时对每条 claim
   调用（默认关 = 行为逐字不变；与 entity_precision_check / numeric_matching_v2
   同一开关惯例）。判定结果走 writer 既有失败出口（PHANTOM_TOOL_CLAIM，
   fail-closed 方向：宁可拒绝也不交付"谎称查过"的答复）。
"""

from __future__ import annotations

import re
from collections.abc import Mapping

# 类别 → (触发短语 patterns, 兜底所需真实执行)。同一 claim 命中多类时全部返回。
_ACTION_PATTERNS: Mapping[str, tuple[tuple[re.Pattern[str], ...], frozenset[str] | None]] = {
    "retrieval": (
        tuple(
            re.compile(pattern)
            for pattern in (
                r"(?<![未没无有])经检索",
                r"(?<![未没无有])检索结果",
                r"(?<![未没无有])检索到",
                r"(?<![未没无有])经查询",
                r"(?<![未没无有])查询到",
            )
        ),
        frozenset({"retrieve_laws", "lookup_article"}),
    ),
    "contract_analysis": (
        tuple(
            re.compile(pattern)
            for pattern in (
                r"(?<![未没无有])经审查合同",
                r"(?<![未没无有])经对合同",
                r"(?<![未没无有])经分析(?:(?:该|本|这份)?合同|合同文本)",
                r"(?<![未没无有])合同条款显示",
            )
        ),
        frozenset({"analyze_contract"}),
    ),
    "memory": (
        tuple(
            re.compile(pattern)
            for pattern in (
                r"历史会话",
                r"此前(?:的)?咨询记录",
                r"调取(?:了)?(?:您|该用户)?(?:的)?历史",
                r"记忆中存有",
            )
        ),
        frozenset({"retrieve_memory"}),
    ),
    "user_confirmation": (
        tuple(
            re.compile(pattern)
            for pattern in (
                r"您已确认",
                r"经您确认",
                r"您确认过",
                r"根据您补充",
                r"您补充说明",
            )
        ),
        None,  # 兜底 = 追问计数（clarifications），由调用方显式传入
    ),
}


def succeeded_tools(observations) -> set[str]:
    """state.observations → 真实成功执行过的工具名集合（status == "succeeded"）。"""
    return {
        observation.tool_name
        for observation in observations or ()
        if observation.tool_name is not None and observation.status == "succeeded"
    }


def phantom_action_categories(
    claim_text: str,
    *,
    tool_success: set[str],
    has_evidence: bool,
    clarifications: int,
) -> list[str]:
    """claim 文本断言执行过、但 state 无真实执行记录的动作类别（升序）。

    全部真实执行过（或有 evidence 兜底/追问计数兜底）→ 空列表。
    纯函数：不修改任何状态、不调用模型。
    """
    text = claim_text or ""
    flagged: list[str] = []
    for category in sorted(_ACTION_PATTERNS):
        patterns, required_tools = _ACTION_PATTERNS[category]
        if not any(pattern.search(text) for pattern in patterns):
            continue
        if category == "user_confirmation":
            if clarifications <= 0:
                flagged.append(category)
            continue
        assert required_tools is not None
        backed = bool(tool_success & required_tools)
        if category == "retrieval":
            backed = backed or has_evidence  # 证据由工具获取 ⇒ 检索确实发生过
        if not backed:
            flagged.append(category)
    return flagged


__all__ = ["phantom_action_categories", "succeeded_tools"]
