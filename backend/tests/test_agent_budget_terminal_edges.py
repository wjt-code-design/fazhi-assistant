"""DB-15（2026-10-09，审查报告 B-01 + B-47）：终稿边与恢复边不计步，预算防循环照旧。

改前的形状（四腿实测记录见 `docs/backend-readonly-audit-20260929.md` §12.1/§12.2）：
`transition()` 对**每一条**边都 +1 步，而工具路径的预检口径是 `steps + 3 > max_steps`
⇒ 预检挡不住"DRAFTING 只花 1 步"这种落点，状态可以合法地停在 `steps == max_steps`，
此后
  ① `DRAFTING→COMPLETED`：已 PASS 校验的终稿在落库瞬间被 `BudgetExceeded` 炸掉，
     并被 `service.py` 的 `except Exception` 折成 `AGENT_STORAGE_FAILURE`
     （该码**不在** `TECHNICAL_FALLBACK_REASON_CODES` ⇒ 用户拿到硬错误、run 永卡 drafting）；
  ② `WAITING_USER→PLANNING`：用户对追问的回答被 409 拒收，该 run **永久不可恢复**
     （真数据 47 只 waiting_user 里 16 只 steps==cap）。

本轮把这两条"不发起任何模型/工具调用"的记账边免计费，并留下四条反证：
免计费**不等于**不设界——越界仍 fail-closed、计费边一口没动、澄清轮数另有上界。
"""

from __future__ import annotations

import ast
import pathlib
from datetime import datetime

import pytest

from agent.chat_integration import persist_agent_final_once
from agent.repository import create_run
from agent.schemas import (
    AgentBudgets,
    AgentStatus,
    Evidence,
    Fact,
    LegalAgentState,
    LegalIssue,
    LegalValidity,
    Observation,
    SourceType,
)
from agent.state_machine import FREE_STEP_EDGES, BudgetExceeded, register_clarification, transition
from agent.verifier import DeterministicVerifier
from agent.writer import DraftAnswer, DraftClaim, derive_claim_id, derive_fact_id
from models import AgentRun, Conversation, Message, User
from routing_metrics import is_technical_fallback_reason

ANSWER = "借款本金为10000元，依据《民法典》第675条应按约返还。"


def _drafting_state(steps: int, *, status: AgentStatus = AgentStatus.DRAFTING) -> tuple[LegalAgentState, DraftAnswer]:
    fact = Fact(
        statement="借款本金为10000元",
        source=SourceType.DOCUMENT,
        source_ref="document:loan-1",
        confidence=1.0,
    )
    issue = LegalIssue(issue_id="issue-a", question="借款是否应返还", facts=[fact])
    evidence = Evidence(
        evidence_id="evidence-a",
        source_id="statute:civil-code:675",
        source_ref="《民法典》第675条",
        source_type=SourceType.STATUTE,
        snippet=ANSWER,
        legal_validity=LegalValidity.EFFECTIVE,
        acquired_at=datetime(2026, 8, 31),
    )
    state = LegalAgentState(
        status=status,
        steps=steps,
        issues=[issue],
        evidence=[evidence],
        observations=[
            Observation(
                issue_id="issue-a",
                statement="已取得借款返还规则",
                evidence_ids=["evidence-a"],
                confidence=1.0,
            )
        ],
    )
    fact_id = derive_fact_id("issue-a", fact)
    claim = DraftClaim(
        claim_id=derive_claim_id("issue-a", ANSWER, ["evidence-a"], [fact_id]),
        issue_id="issue-a",
        text=ANSWER,
        evidence_ids=("evidence-a",),
        fact_ids=(fact_id,),
        section="conclusion",
    )
    return state, DraftAnswer(conclusion=(claim,))


def _records(db, steps: int):
    user = User(username="budget-terminal-owner", password_hash="x")
    db.add(user)
    db.commit()
    conversation = Conversation(user_id=user.id, title="", summary="", message_count=1)
    db.add(conversation)
    db.commit()
    state, draft = _drafting_state(steps)
    run = create_run(db, user_id=user.id, conversation_id=conversation.id, state=state)
    return user, conversation, run, state, draft


def _finalize(db, user, conversation, run, state, draft):
    return persist_agent_final_once(
        db,
        user_id=user.id,
        conversation_id=conversation.id,
        run_id=run.id,
        expected_version=0,
        state=state,
        answer=ANSWER,
        verification=DeterministicVerifier().verify(state, draft),
    )


def test_free_edges_are_exactly_the_two_bookkeeping_edges():
    """免计费集合本身要钉住：**扩它是一次产品决定**，不许被无声加边。"""
    assert FREE_STEP_EDGES == frozenset(
        {
            (AgentStatus.DRAFTING, AgentStatus.COMPLETED),
            (AgentStatus.WAITING_USER, AgentStatus.PLANNING),
        }
    )


def test_finalize_at_exact_step_cap_now_succeeds(db):
    """B-01 正身（改前三条腿红：抛 BudgetExceeded + 0 条消息 + run 永卡 drafting）。"""
    cap = LegalAgentState().budgets.max_steps
    user, conversation, run, state, draft = _records(db, cap)
    assert _finalize(db, user, conversation, run, state, draft) is True
    assert db.query(Message).filter_by(conversation_id=conversation.id, role="assistant").count() == 1
    saved = db.get(AgentRun, run.id)
    assert saved.status == "completed"
    db.refresh(saved)
    assert LegalAgentState.model_validate_json(saved.state_json).steps == cap  # 不计步 ⇒ 落点仍是 cap


def test_finalize_one_below_cap_still_works(db):
    """对照腿：改前就能成功的那一格，改后必须继续成功（否则说明我把写路径改坏了）。"""
    cap = LegalAgentState().budgets.max_steps
    user, conversation, run, state, draft = _records(db, cap - 1)
    assert _finalize(db, user, conversation, run, state, draft) is True


def test_over_cap_state_is_still_rejected(db):
    """免计费 ≠ 不设界：越界（坏状态）仍 fail-closed，且抛的仍是 BudgetExceeded。"""
    cap = LegalAgentState().budgets.max_steps
    user, conversation, run, state, draft = _records(db, cap + 1)
    with pytest.raises(BudgetExceeded) as exc:
        _finalize(db, user, conversation, run, state, draft)
    assert exc.value.decision.reason == "budget_exceeded:steps"
    assert db.query(Message).filter_by(conversation_id=conversation.id, role="assistant").count() == 0


@pytest.mark.parametrize(
    ("status", "target"),
    [
        (AgentStatus.BOOTSTRAPPING, AgentStatus.PLANNING),
        (AgentStatus.PLANNING, AgentStatus.EXECUTING),
        (AgentStatus.EVALUATING, AgentStatus.DRAFTING),
        (AgentStatus.DRAFTING, AgentStatus.FAILED),
    ],
)
def test_charging_edges_are_untouched(status, target):
    """计费边界一口没动：到 cap 时这些边仍抛 ⇒ 防循环上界没被削弱。

    注意 cap 取自 `state.budgets.max_steps` 而不是写死数字——`LegalAgentState` 的兜底默认
    与生产注入值（`settings.agent_max_steps`）本来就不同，写死会把这条腿变成空腿
    （第一版我就这么写错了一次：steps=8 对 cap=24，永远不抛，"DID NOT RAISE"）。
    """
    cap = LegalAgentState().budgets.max_steps
    at_cap, _draft = _drafting_state(cap, status=status)
    with pytest.raises(BudgetExceeded):
        transition(at_cap, target)
    below, _d = _drafting_state(cap - 1, status=status)
    moved = transition(below, target)
    assert moved.steps == cap


def test_clarification_budget_still_bounds_resume_loop():
    """恢复边免计费后，"无限追问"仍被 `max_clarifications` 钉住（本票的替代上界确实存在）。"""
    state, _draft = _drafting_state(0, status=AgentStatus.EVALUATING)
    state = state.model_copy(update={"budgets": AgentBudgets(max_clarifications=2), "clarifications": 2})
    with pytest.raises(BudgetExceeded) as exc:
        register_clarification(state)
    assert exc.value.decision.reason == "budget_exceeded:clarifications"


def test_service_maps_residual_budget_to_the_whitelisted_reason():
    """归因链：坏形状下的 `BudgetExceeded` 必须落成 `AGENT_BUDGET_EXCEEDED`（在白名单里）。

    改前它被 `except Exception` 折成 `AGENT_STORAGE_FAILURE`——下面两条 `is_technical_fallback_reason`
    断言钉住"为什么这两个码对用户完全不同"，ast 段钉住 service.py 里那个 except 真的存在、
    且真的排在 `except Exception` 之前（顺序错了就等于没接住）。
    """
    assert is_technical_fallback_reason("AGENT_BUDGET_EXCEEDED") is True
    assert is_technical_fallback_reason("AGENT_STORAGE_FAILURE") is False

    # 按**文件自身位置**定位，不靠 cwd（换目录跑就会读错文件甚至恒真）
    src = open(
        pathlib.Path(__file__).resolve().parents[1] / "agent" / "service.py", encoding="utf-8", newline=""
    ).read()
    tree = ast.parse(src)

    def _call_name(call: ast.Call) -> str:
        return getattr(call.func, "id", "") or getattr(call.func, "attr", "")

    finalize_try = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Try)
        and any(isinstance(st, ast.Call) and _call_name(st) == "persist_agent_final_once" for st in ast.walk(node))
    )
    handlers = [ast.unparse(h.type) for h in finalize_try.handlers]
    assert "BudgetExceeded" in handlers, f"finalize 的 try 没接 BudgetExceeded：{handlers}"
    assert handlers.index("BudgetExceeded") < handlers.index("Exception"), (
        f"顺序错了（会被 Exception 先吃掉）：{handlers}"
    )
    budget_handler = finalize_try.handlers[handlers.index("BudgetExceeded")]
    assert "AGENT_BUDGET_EXCEEDED" in ast.unparse(budget_handler), "映射的码不对"
