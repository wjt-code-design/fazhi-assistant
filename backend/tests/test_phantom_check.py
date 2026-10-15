"""R12 伪调用检测（phantom_check）测试。

对照 docs/external-harness-plan-gap-analysis-20260918.md P0-3 与
agent/phantom_check.py docstring。已知缺陷映射：deepseek-v4-flash"伪调用"
（工具调用被渲染为文本而非真实执行）。
"""

from datetime import datetime

import pytest

import settings as settings_module
from agent.phantom_check import IssueExecution, issue_executions, phantom_action_categories
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
from tools.contracts import RetrieveLawsOutput

# ---- 纯函数：争点执行事实取数 ----


def execution(*, tools: tuple[str, ...] = (), has_evidence: bool = False) -> IssueExecution:
    """按 (工具成功集, 该争点是否有证据) 构造判定入参。"""
    return IssueExecution(frozenset(tools), has_evidence)


def test_issue_executions_does_not_leak_across_issues():
    """issue-a 的工具成功与证据都不得计入 issue-b。"""
    observations = [
        Observation(
            issue_id="issue-a",
            statement="ok",
            tool_name="retrieve_laws",
            status="succeeded",
            output=RetrieveLawsOutput(statement="found"),
        ),
        Observation(issue_id="issue-a", statement="evidence", evidence_ids=["e"], confidence=0.9),
        Observation(
            issue_id="issue-b",
            statement="bad",
            tool_name="lookup_article",
            status="failed",
            error_code="TOOL_EXECUTION_ERROR",
        ),
    ]
    executions = issue_executions(observations)
    assert executions["issue-a"] == execution(tools=("retrieve_laws",), has_evidence=True)
    # failed 观察不留条目（既不算工具成功、也不算证据）；调用方对缺失争点取 NO_EXECUTION。
    assert "issue-b" not in executions


# ---- 纯函数：类别判定 ----


def test_retrieval_flagged_without_any_execution():
    flagged = phantom_action_categories(
        "经检索《民法典》第一百八十八条，诉讼时效期间为三年。",
        execution=execution(),
        clarifications=0,
    )
    assert flagged == ["retrieval"]


def test_retrieval_backed_by_tool_success():
    flagged = phantom_action_categories(
        "经检索《民法典》第一百八十八条，诉讼时效期间为三年。",
        execution=execution(tools=("retrieve_laws",)),
        clarifications=0,
    )
    assert flagged == []


def test_retrieval_backed_by_evidence_fallback():
    """**该争点**证据由检索工具物化（落库 Observation.tool_name 可为 None）⇒ 视为检索发生过。

    兜底只在争点内成立：另一争点的证据不豁免本争点的声称（见
    test_issue_executions_does_not_leak_across_issues 与 writer 侧跨争点用例）。
    """
    flagged = phantom_action_categories(
        "经检索《民法典》第一百八十八条。",
        execution=execution(has_evidence=True),
        clarifications=0,
    )
    assert flagged == []


def test_negated_phrases_not_flagged():
    """「未经检索」「未查询到」不构成"声称执行过"。"""
    for text in ("未经检索，无法给出结论。", "未查询到相关条文。", "没有检索到相关依据。"):
        assert phantom_action_categories(text, execution=execution(), clarifications=0) == []


def test_searched_but_found_nothing_still_flagged():
    """「经检索未发现」仍断言了检索发生过 → 无执行记录时必须标记。"""
    flagged = phantom_action_categories(
        "经检索未发现相关证据。",
        execution=execution(),
        clarifications=0,
    )
    assert flagged == ["retrieval"]


def test_contract_analysis_and_memory_flagged():
    text = "经审查合同文本第3条，历史会话显示您此前咨询过类似问题。"
    flagged = phantom_action_categories(text, execution=execution(), clarifications=0)
    assert flagged == ["contract_analysis", "memory"]


def test_user_confirmation_requires_clarification_budget():
    text = "根据您补充的信息，损失发生于2023年。"
    assert phantom_action_categories(text, execution=execution(), clarifications=0) == ["user_confirmation"]
    assert phantom_action_categories(text, execution=execution(), clarifications=1) == []


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


def two_issue_state() -> LegalAgentState:
    """issue-a 检索成功并物化证据；issue-b **完全无执行记录**（无工具成功、无证据）。

    多争点是伪调用的主要发生形态：模型对没查过的争点也写「经检索」。
    """

    def make_issue(issue_id: str, question: str) -> LegalIssue:
        return LegalIssue(
            issue_id=issue_id,
            question=question,
            facts=[
                Fact(
                    statement="2023年8月1日对方拖欠货款",
                    source=SourceType.USER,
                    source_ref="user:q",
                    confidence=1,
                )
            ],
        )

    return LegalAgentState(
        issues=[make_issue("issue-a", "诉讼时效多久？"), make_issue("issue-b", "违约金怎么算？")],
        observations=[
            Observation(
                issue_id="issue-a",
                statement="retrieved statute",
                evidence_ids=["ev-a"],
                confidence=0.9,
            )
        ],
        evidence=[evidence()],
    )


def test_writer_phantom_check_is_scoped_to_the_claims_issue(monkeypatch: pytest.MonkeyPatch):
    """另一争点的证据不得豁免本争点的伪检索声称（render_issue 是生产路径）。

    issue-a 检索成功并物化证据；issue-b 零执行记录。同一段「经检索」措辞在
    issue-b 上必须被拦，在 issue-a 上必须放行——两者同测，防修成一律拦或一律放。
    文本刻意不含数字：否则 issue-b 会先被数字白名单门拦下，测到的就不是伪调用门。
    """
    monkeypatch.setattr(settings_module.settings, "phantom_tool_check", True)
    text = "经检索发现相关依据，对方存在拖欠行为。"
    blocked = EvidenceBoundedWriter(SingleClaimGenerator(text)).render_issue(two_issue_state(), "issue-b")
    assert blocked.status is WriterStatus.FAIL_SAFE
    assert blocked.reason_code == "PHANTOM_TOOL_CLAIM"

    allowed = EvidenceBoundedWriter(SingleClaimGenerator(text)).render_issue(two_issue_state(), "issue-a")
    assert allowed.status is WriterStatus.READY


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
