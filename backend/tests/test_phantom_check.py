"""R12 伪调用检测（phantom_check）测试。

对照 docs/external-harness-plan-gap-analysis-20260918.md P0-3 与
agent/phantom_check.py docstring。已知缺陷映射：deepseek-v4-flash"伪调用"
（工具调用被渲染为文本而非真实执行）。
"""

from datetime import datetime

import pytest

import settings as settings_module
from agent.phantom_check import phantom_action_categories, succeeded_tools
from agent.schemas import (
    Evidence,
    Fact,
    LegalAgentState,
    LegalIssue,
    LegalValidity,
    Observation,
    SourceType,
)
from agent.verifier import DeterministicVerifier, VerificationVerdict
from agent.writer import EvidenceBoundedWriter, WriterStatus


def make_state(*, tool_success: set[str] = frozenset(), clarifications: int = 0) -> LegalAgentState:
    return LegalAgentState(
        issues=[
            LegalIssue(
                issue_id="issue-a",
                question="测试",
                facts=[
                    Fact(
                        statement="2023年8月1日对方拖欠货款",
                        source=SourceType.USER,
                        source_ref="user:q",
                        confidence=1,
                    )
                ],
            )
        ],
        observations=[
            Observation(
                issue_id="issue-a",
                statement="obs",
                tool_name=tool,
                status="succeeded",
            )
            for tool in tool_success
        ],
        clarifications=clarifications,
    )


# ---- 纯函数：类别判定 ----


def test_retrieval_flagged_without_any_execution():
    flagged = phantom_action_categories(
        "经检索《民法典》第一百八十八条，诉讼时效期间为三年。",
        tool_success=set(),
        has_evidence=False,
        clarifications=0,
    )
    assert flagged == ["retrieval"]


def test_retrieval_backed_by_tool_success():
    flagged = phantom_action_categories(
        "经检索《民法典》第一百八十八条，诉讼时效期间为三年。",
        tool_success={"retrieve_laws"},
        has_evidence=False,
        clarifications=0,
    )
    assert flagged == []


def test_retrieval_backed_by_evidence_fallback():
    """证据由工具获取（Observation.tool_name 可能为 None）⇒ 有证据即视为检索真实发生过。"""
    flagged = phantom_action_categories(
        "经检索《民法典》第一百八十八条。",
        tool_success=set(),
        has_evidence=True,
        clarifications=0,
    )
    assert flagged == []


def test_negated_phrases_not_flagged():
    """「未经检索」「未查询到」不构成"声称执行过"。"""
    for text in ("未经检索，无法给出结论。", "未查询到相关条文。", "没有检索到相关依据。"):
        assert phantom_action_categories(text, tool_success=set(), has_evidence=False, clarifications=0) == []


def test_searched_but_found_nothing_still_flagged():
    """「经检索未发现」仍断言了检索发生过 → 无执行记录时必须标记。"""
    flagged = phantom_action_categories(
        "经检索未发现相关证据。",
        tool_success=set(),
        has_evidence=False,
        clarifications=0,
    )
    assert flagged == ["retrieval"]


def test_contract_analysis_and_memory_flagged():
    text = "经审查合同文本第3条，历史会话显示您此前咨询过类似问题。"
    flagged = phantom_action_categories(text, tool_success=set(), has_evidence=False, clarifications=0)
    assert flagged == ["contract_analysis", "memory"]


def test_user_confirmation_requires_clarification_budget():
    text = "根据您补充的信息，损失发生于2023年。"
    assert phantom_action_categories(text, tool_success=set(), has_evidence=False, clarifications=0) == [
        "user_confirmation"
    ]
    assert phantom_action_categories(text, tool_success=set(), has_evidence=False, clarifications=1) == []


def test_succeeded_tools_ignores_failed_and_evidence_observations():
    from tools.contracts import RetrieveLawsOutput

    observations = [
        Observation(
            issue_id="i",
            statement="ok",
            tool_name="retrieve_laws",
            status="succeeded",
            output=RetrieveLawsOutput(statement="found"),
        ),
        Observation(
            issue_id="i",
            statement="bad",
            tool_name="lookup_article",
            status="failed",
            error_code="TOOL_EXECUTION_ERROR",
        ),
        Observation(issue_id="i", statement="evidence", evidence_ids=["e"], confidence=0.9),
    ]
    assert succeeded_tools(observations) == {"retrieve_laws"}


# ---- writer 集成（开关默认关 = 行为逐字不变）----


def evidence() -> Evidence:
    return Evidence(
        evidence_id="ev-a",
        source_id="source-ev-a",
        source_ref="《民法典》第一百八十八条",
        source_type=SourceType.STATUTE,
        snippet="《民法典》第一百八十八条规定诉讼时效期间为三年。",
        legal_validity=LegalValidity.EFFECTIVE,
        acquired_at=datetime(2026, 8, 30),
    )


def writer_state(*, include_evidence: bool = True, clarifications: int = 0) -> LegalAgentState:
    return LegalAgentState(
        issues=[
            LegalIssue(
                issue_id="issue-a",
                question="诉讼时效多久？",
                facts=[
                    Fact(
                        statement="2023年8月1日对方拖欠货款",
                        source=SourceType.USER,
                        source_ref="user:q",
                        confidence=1,
                    )
                ],
            )
        ],
        # build_writer_payload 只收「经 observation 关联到本争点」的证据（参照
        # test_agent_writer 的 fixture）——include_evidence=False 时彻底无执行记录。
        observations=(
            [
                Observation(
                    issue_id="issue-a",
                    statement="retrieved statute",
                    evidence_ids=["ev-a"],
                    confidence=0.9,
                )
            ]
            if include_evidence
            else []
        ),
        evidence=[evidence()] if include_evidence else [],
        clarifications=clarifications,
    )


class SingleClaimGenerator:
    def __init__(self, text: str):
        self.text = text

    def generate(self, *, payload, system_prompt, feedback=None):
        issue = payload.issues[0]
        return {
            "claims": [
                {
                    "local_id": "local-1",
                    "issue_id": issue.issue_id,
                    "text": self.text,
                    # 伪调用检测在证据校验之前执行：空证据时 claim 照常构造，
                    # 让检测（而非证据绑定）成为首个失败点。
                    "evidence_ids": [issue.evidence[0].evidence_id] if issue.evidence else [],
                    "fact_ids": [],
                    "section": "conclusion",
                }
            ],
            "missing_information": [],
        }


PHANTOM_TEXT = "经检索《民法典》第一百八十八条，诉讼时效期间为三年。"


def test_writer_default_off_phantom_text_passes():
    """默认关：同一段伪调用文本照常通过（行为逐字不变，基线安全）。"""
    result = EvidenceBoundedWriter(SingleClaimGenerator(PHANTOM_TEXT)).render(writer_state())
    assert result.status is WriterStatus.READY


def test_writer_flag_on_blocks_phantom_claim(monkeypatch: pytest.MonkeyPatch):
    """无任何执行记录（无工具成功、无证据）+ claim 声称"经检索" → fail-closed。"""
    monkeypatch.setattr(settings_module.settings, "phantom_tool_check", True)
    generator = SingleClaimGenerator("经检索发现相关依据，对方存在拖欠行为。")
    result = EvidenceBoundedWriter(generator).render(writer_state(include_evidence=False))
    assert result.status is WriterStatus.FAIL_SAFE
    assert result.reason_code == "PHANTOM_TOOL_CLAIM"


def test_writer_flag_on_allows_backed_claim(monkeypatch: pytest.MonkeyPatch):
    """真实执行过检索（有证据兜底）→ 同样的措辞合法。"""
    monkeypatch.setattr(settings_module.settings, "phantom_tool_check", True)
    result = EvidenceBoundedWriter(SingleClaimGenerator(PHANTOM_TEXT)).render(writer_state())
    assert result.status is WriterStatus.READY


# ---- verifier 第二道防线 ----


def test_verifier_flag_on_blocks_phantom_draft(monkeypatch: pytest.MonkeyPatch):
    """绕过 writer 直接构造 draft 的路径由 verifier 兜底（单一真源拆两防线）。

    用「用户确认」类短语构造：writer 侧无证据状态下的 retrieval 会被 writer 先拦，
    这里让 draft 合法生成（默认关），再单独开 verifier 侧开关验证兜底。
    """
    monkeypatch.setattr(settings_module.settings, "phantom_tool_check", False)
    writer_result = EvidenceBoundedWriter(SingleClaimGenerator("根据您补充的信息，对方存在拖欠行为。")).render(
        writer_state()
    )
    assert writer_result.status is WriterStatus.READY and writer_result.draft is not None

    monkeypatch.setattr(settings_module.settings, "phantom_tool_check", True)
    verdict = DeterministicVerifier().verify(writer_state(), writer_result.draft)
    assert verdict.verdict is VerificationVerdict.FAIL_SAFE
    assert verdict.reason_code == "PHANTOM_TOOL_CLAIM"
