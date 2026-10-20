"""R02（2026-10-20）：用户显式表示"不知道"的未决事实必须**保留**，且不得被再次追问。

原缺陷（两处叠加）：
1. `resume_with_user_fact` 的显式未知分支把该事实从 `issue.unknown_facts` 中 pop 掉——
   于是它既不再出现在终稿「尚不确定的事实」（`verifier._render_draft_text` 只渲染
   `state.issues[].unknown_facts`），也无法参与分情形分析。
2. 冻结的评估器（`evaluator.py`）见 `unknown_facts` 非空即判 MISSING_FACT、并按
   (statement, why) 取最小项作下一问，**不认"已答过"**；若澄清预算未耗尽，用户已明确
   无法提供的事实会被**重复追问**。

修复落在 controller 侧（evaluator/verifier 为冻结件）：
- resume 分支保留事实并标记 `UnknownFact.user_declined=True`；
- MISSING_FACT 统一门由「预算耗尽」扩展为「预算耗尽 或 无可问的未决事实」
  （`_clarification_blocked`），并就"再问哪一条"侧向重挑未答项（`_pending_clarification`）。
"""

from __future__ import annotations

from agent.controller import ControllerResult
from agent.evaluator import EvaluationDecision, EvaluationOutcome, EvidenceEvaluator
from agent.schemas import AgentBudgets, AgentStatus, UnknownFact
from agent.verifier import _render_draft_text
from agent.writer import DraftAnswer
from tests.test_agent_controller import FakeRepository, RecordingGateway, SequencePlanner, controller, sufficient_state

# 冻结评估器按 (statement, why_outcome_changes) 取最小项：履（U+5C65）< 违（U+8FDD），
# 故下列最小项为 DECLINED —— 正是"已答过"的那条，用来复现重复追问。
DECLINED = "是否约定履行期限"
OTHER = "是否约定违约金"


def _declined_fact() -> UnknownFact:
    return UnknownFact(statement=DECLINED, why_outcome_changes="影响起算时间", user_declined=True)


def _state_with_unknowns(*, declined: bool, other: bool, clarifications: int, max_clarifications: int):
    """单争点 + 每争点已有有效成文法证据的 state（满足 `_every_issue_retrieval_attempted`）。"""
    state = sufficient_state(budgets=AgentBudgets(max_clarifications=max_clarifications))
    unknown_facts: list[UnknownFact] = []
    if declined:
        unknown_facts.append(_declined_fact())
    if other:
        unknown_facts.append(UnknownFact(statement=OTHER, why_outcome_changes="影响责任范围"))
    state.issues[0].unknown_facts = unknown_facts
    state.clarifications = clarifications
    return state


def _decision() -> EvaluationDecision:
    """模拟冻结评估器的 MISSING_FACT 决策：issue 内最小未决项 = 已答过的那条。"""
    return EvaluationDecision(
        outcome=EvaluationOutcome.MISSING_FACT,
        reason_code="OUTCOME_CHANGING_FACT_UNKNOWN",
        issue_id="issue-a",
        clarification=UnknownFact(statement=DECLINED, why_outcome_changes="影响起算时间"),
    )


def test_frozen_evaluator_still_flags_missing_fact_for_declined_unknown():
    """前提（复现根因）：保留标记后评估器仍判 MISSING_FACT 并选中已答项 ⇒ 侧向阻断是必需的。"""
    state = _state_with_unknowns(declined=True, other=False, clarifications=1, max_clarifications=2)

    decision = EvidenceEvaluator().evaluate(state)

    assert decision.outcome is EvaluationOutcome.MISSING_FACT
    assert decision.issue_id == "issue-a"
    assert decision.clarification is not None and decision.clarification.statement == DECLINED


def test_all_unknowns_declined_forces_conditional_analysis_and_keeps_fact():
    """预算未耗尽但已无可问事实 ⇒ 不得重复追问，转确定性条件化，且事实保留进终稿。"""
    state = _state_with_unknowns(declined=True, other=False, clarifications=1, max_clarifications=2)
    repository = FakeRepository(state)
    agent = controller(repository, SequencePlanner([]), RecordingGateway())

    result = agent._handle_evaluation(repository.current, _decision())

    assert isinstance(result, ControllerResult)
    assert result.state.status is AgentStatus.DRAFTING
    assert result.state.clarifications == 1, "不得为已答事实重复注册澄清"
    last = repository.checkpoints[-1][1]
    assert (last.decision, last.reason_code) == ("conditional_analysis", "CLARIFY_ALL_UNKNOWNS_DECLINED")
    # 事实被保留（而非删除）→ 终稿「尚不确定的事实」仍能列出它并参与分情形分析
    assert [item.statement for item in result.state.issues[0].unknown_facts] == [DECLINED]
    assert DECLINED in _render_draft_text(result.state, DraftAnswer())


def test_declined_fact_is_skipped_while_another_unknown_still_askable():
    """仍有未答事实时，不得因评估器选中已答项而对同一事实重复追问——改问未答那条。"""
    state = _state_with_unknowns(declined=True, other=True, clarifications=1, max_clarifications=2)
    repository = FakeRepository(state)
    agent = controller(repository, SequencePlanner([]), RecordingGateway())

    result = agent._handle_evaluation(repository.current, _decision())

    assert isinstance(result, ControllerResult)
    assert result.state.status is AgentStatus.WAITING_USER
    assert result.pending_question == OTHER
    assert result.state.clarifications == 2
    last = repository.checkpoints[-1][1]
    assert (last.decision, last.reason_code) == ("clarification", "OUTCOME_CHANGING_FACT_UNKNOWN")
    assert last.pending_question == OTHER
