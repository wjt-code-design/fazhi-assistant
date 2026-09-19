"""伪调用检测（R12，2026-09-18）。外部 harness 方案差距分析 P0-3：方案 §3.1 要求
「工具入口计数 vs 模型声称的调用数比对，不等即告警」——对应本仓库**已知缺陷**：
deepseek-v4-flash 的"伪调用"（工具调用被渲染为 XML 文本而非真实执行，只能靠肉眼发现；
见项目记忆 known defects b）。当前 agent 链路已有"重复调用"检测（state_machine.
register_action 的 fingerprint 判重），但没有"**声称执行过而实际从未执行**"的检测。

检测对象：writer 产出的 claim 文本中**断言执行过某动作**的确定性短语
（"经检索""合同条款显示""您已确认"……），与 state 中的真实执行记录比对：
- 检索类短语 → 需要该争点有 retrieve_laws / lookup_article 的 succeeded 记录，**或**
  该争点物化过证据（证据由检索工具获取，落库的 Observation.tool_name 可为 None）；
- 合同分析类 → 需要该争点 analyze_contract succeeded；
- 历史会话类 → 需要该争点 retrieve_memory succeeded；
- 用户确认类 → 需要 state.clarifications > 0（真的追问过用户）。

**执行记录一律按争点取，不按 state 全局取**（`issue_executions`）：一个争点查过/分析过，
不构成另一个争点声称"经检索""经审查合同"的依据——按全局取会让检测在任意争点有过
一次执行后对该 claim 整体失效。clarifications 是 run 级计数（追问对象是用户，
不区分争点），保持全局。

设计边界（自审记录）：
1. **否定形态不误报**："未经检索""未查询到""没有检索到"不构成"声称执行过"——
   短语全部带否定前置 lookbehind（未/没/无/有，覆盖"没有/并无"形态；代价是
   "均有检索到"这类罕见肯定形态漏报，宁可漏报不误杀）。"经检索未发现"仍会被
   标记：它断言了"检索发生过"。
2. **evidence 兜底**：证据observations（tool_name=None）也意味着检索真实发生过，
   故检索类以「该争点工具 succeeded ∪ 该争点证据存在」为充分条件，避免把合法引用误杀。
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
from typing import NamedTuple

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
                r"(?:历史会话|此前(?:的)?咨询记录)(?:中)?(?:显示|表明|记载)",
                r"(?:根据|依据)(?:您|该用户)?(?:的)?(?:历史会话|此前(?:的)?咨询记录)",
                r"(?:已|曾|经)(?:经)?(?:读取|调取|查询)(?:了)?(?:您|该用户)?(?:的)?历史",
                r"调取了(?:您|该用户)?(?:的)?历史",
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


class IssueExecution(NamedTuple):
    """一个争点的真实执行事实（伪调用判定的唯一依据来源）。"""

    tool_success: frozenset[str]
    has_evidence: bool


NO_EXECUTION = IssueExecution(frozenset(), False)


def issue_executions(observations) -> dict[str, IssueExecution]:
    """state.observations → 争点 → 该争点的执行事实；failed 观察不计入任何字段。

    只按 succeeded 观察取数：证据观察（tool_name=None）带 evidence_ids 即说明检索
    真的发生过（controller 的 `_materialize_evidence` 只从 succeeded 的
    retrieve_laws / lookup_article 产出证据），因此 has_evidence 是 tool_success
    之外的第二条独立佐证，不是"state 里有没有证据"的全局探针。
    """
    executions: dict[str, IssueExecution] = {}
    for observation in observations or ():
        if observation.status != "succeeded":
            continue
        tools, has_evidence = executions.get(observation.issue_id, NO_EXECUTION)
        if observation.tool_name is not None:
            tools = tools | frozenset({observation.tool_name})
        executions[observation.issue_id] = IssueExecution(
            tools,
            has_evidence or bool(observation.evidence_ids),
        )
    return executions


def phantom_action_categories(
    claim_text: str,
    *,
    execution: IssueExecution,
    clarifications: int,
) -> list[str]:
    """claim 文本断言执行过、但**该争点**无真实执行记录的动作类别（升序）。

    全部真实执行过（或该争点有证据兜底/追问计数兜底）→ 空列表。
    `execution` 必须是 claim 所属争点的事实（由 `issue_executions` 取），传 state 级
    全局值会让跨争点的伪调用漏检。
    纯函数：不修改任何状态、不调用模型。
    """
    text = claim_text or ""
    flagged: list[str] = []
    for category in sorted(_ACTION_PATTERNS):
        patterns, required_tools = _ACTION_PATTERNS[category]
        matches = [match for pattern in patterns for match in pattern.finditer(text)]
        if category == "memory":
            # 只看命中前的当前分句，否定声明不能豁免后一句的肯定声称。
            matches = [match for match in matches if not re.search(
                r"(?:未|没有|无法|不能|并无)[^，。；！？\n]*$", text[:match.start()]
            )]
        if not matches:
            continue
        if category == "user_confirmation":
            if clarifications <= 0:
                flagged.append(category)
            continue
        assert required_tools is not None
        backed = bool(execution.tool_success & required_tools)
        if category == "retrieval":
            backed = backed or execution.has_evidence  # 该争点证据由检索工具物化 ⇒ 检索发生过
        if not backed:
            flagged.append(category)
    return flagged


__all__ = ["IssueExecution", "NO_EXECUTION", "issue_executions", "phantom_action_categories"]
