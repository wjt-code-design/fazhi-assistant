"""Regression: Agent structured-output prompts must state the exact server schema.

Root cause (2026-09-05, isolated preflight): the planner and writer validators
fail closed on any deviation from their exact JSON schemas, but neither system
prompt ever documented those schemas. A live model therefore had to guess the
decision shape (it emitted ``name`` instead of ``tool_name`` and omitted
``issue_id``), the strict validator rejected it, and every Agent run ended in
``PLANNER_PARSE_ERROR`` fallback or a pre-run hard failure. The prompt is the
interface contract; these tests pin it.
"""

from __future__ import annotations

import json

from agent.planner import parse_plan_decision
from agent.runtime import _PLANNER_SYSTEM_PROMPT
from prompts import AGENT_WRITER_SYSTEM
from tools.gateway import ToolGateway

# Independent copy of the tool_call decision shape the planner prompt must
# document. Written here by hand so the test does not derive its expectation
# from the production functions it is guarding.
_TOOL_CALL_FIELDS = ("kind", "issue_id", "tool_name", "args")
_TOOL_ARGS_FIELDS = {
    "retrieve_laws": ("query",),
    "lookup_article": ("source", "article"),
    "analyze_contract": ("text",),
    "retrieve_memory": ("limit",),
}


def test_planner_prompt_states_exact_tool_call_fields() -> None:
    for field in _TOOL_CALL_FIELDS:
        assert field in _PLANNER_SYSTEM_PROMPT, (
            f"planner prompt must state the exact tool_call field name {field!r}; "
            "without it the model guesses a different shape and the strict "
            "validator fail-closes every tool_call decision"
        )


def test_planner_prompt_states_per_tool_args_fields() -> None:
    for tool_name, arg_fields in _TOOL_ARGS_FIELDS.items():
        assert tool_name in _PLANNER_SYSTEM_PROMPT
        for arg in arg_fields:
            assert arg in _PLANNER_SYSTEM_PROMPT, (
                f"planner prompt must state the args field {arg!r} for tool {tool_name!r}"
            )


def test_documented_tool_call_example_passes_strict_validator() -> None:
    """The shape the prompt documents must be exactly what the validator accepts."""

    documented = {
        "kind": "tool_call",
        "issue_id": "issue_a",
        "tool_name": "retrieve_laws",
        "args": {"query": "诉讼时效"},
    }
    decision = parse_plan_decision(
        documented,
        policies=ToolGateway().policies,
        issue_ids={"issue_a"},
    )
    assert decision.kind == "tool_call"
    assert decision.tool_name == "retrieve_laws"
    assert json.dumps(decision.args.model_dump(mode="json"), ensure_ascii=False)


def test_writer_prompt_states_claims_output_schema() -> None:
    for token in (
        "claims",
        "missing_information",
        "local_id",
        "issue_id",
        "evidence_ids",
        "fact_ids",
        "section",
        "conclusion",
        "issue_analysis",
        "risk",
    ):
        assert token in AGENT_WRITER_SYSTEM, (
            f"writer prompt must state the exact output field {token!r}; without it "
            "the model cannot produce a draft the strict validator accepts"
        )


def test_strict_json_tolerates_single_markdown_fence():
    """007 预注册修复（证据：diag/decomposer-sampling-20260906.json 24/24 复现）：
    LongCat 对部分查询会把合法 JSON 包进 ```json 围栏。剥离围栏后仍走严格解析；
    非围栏的 prose 包裹依旧拒绝（安全边界不变）。"""
    from agent.runtime import _strict_json

    fenced = '```json\n{"issues": []}\n```'
    assert _strict_json(fenced) == {"issues": []}
    assert _strict_json('{"issues": []}') == {"issues": []}
    import pytest

    with pytest.raises(ValueError):
        _strict_json('以下是结果：{"issues": []}')


def test_writer_prompt_requires_conditional_claim_when_cannot_conclude() -> None:
    """2026-09-15（C 方案 A）：无法给出确定结论时**不得留空**，须条件化论述。

    实测依据：C01 争点1（事实认定型，且绑定的证据是该争点的可得证据）——
    旧提示词（"证据不足时…应省略该 Claim"）下模型返回空 claims（2/2 采样，
    claims_proposed=0 → 整轮 ISSUE_CLAIMS_MISSING）；
    改为要求条件化论述后，同一 payload 产出 claim（2/2 采样，绑 4 条证据）。
    缺此约束时 run 会因单个争点零 claim 而整轮失败（见 writer.py ISSUE_CLAIMS_MISSING）。
    """
    for token in ("条件化论述", "不得留空", "待确认事实", "不得复述"):
        assert token in AGENT_WRITER_SYSTEM, (
            f"writer prompt must require conditional analysis ({token!r}); otherwise a "
            "fact-assertion issue yields zero claims and fails the whole run"
        )


def test_planner_prompt_pins_ask_user_shape_boundary() -> None:
    """2026-09-17 审计 S4 修复锁：ask_user 形态边界句必须保留（三段摇摆已统一）。

    校验器事实（planner.parse_plan_decision）：tool_name=="ask_user" 直接拒绝；
    AskUserDecision 才是合法独立 kind。提示词必须同时写明合法形态与禁止组合，
    防止后续编辑回退到"一刀切禁止 ask_user"或"暗示可用 ask_user 工具调用"的摇摆表述。
    """
    assert "ask_user 的形态边界" in _PLANNER_SYSTEM_PROMPT
    assert '{"kind":"ask_user"' in _PLANNER_SYSTEM_PROMPT
    assert '"question"' in _PLANNER_SYSTEM_PROMPT, (
        "planner ask_user 示例必须含完整 question 字段（省略号会被弱模型照抄进 JSON）"
    )
    assert "不得作为 tool_call 的 tool_name" in _PLANNER_SYSTEM_PROMPT
