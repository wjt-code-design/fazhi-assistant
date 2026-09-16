"""方案 A 最终验证：修复后的 LLMPlannerAdapter._invoke_planner 经 LangChain ChatOpenAI bind 真实调用 LongCat。

验证点：
1. TypeAdapter(PlanDecision).json_schema() 不再抛错 → bind 真正启用 response_format
2. ChatOpenAI.bind(response_format=...) 请求被 LongCat 接受（未 400）
3. decide() 返回可被 parse_plan_decision 接收的 dict

运行：venv python dispatch-output/probe_longcat_planner_bind.py
"""
import json
import os
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO / "backend"))

# 先 load_dotenv，使 settings 能读到 .env（settings 只读 os.environ，不读文件）
from dotenv import load_dotenv

load_dotenv(Path(_REPO / "backend" / ".env"))

from langchain_openai import ChatOpenAI

from request_bootstrap import RequestBootstrap
from agent.runtime import LLMPlannerAdapter, _PLANNER_SYSTEM_PROMPT, _planner_payload
from agent.schemas import (
    AgentBudgets,
    Fact,
    LegalIssue,
    LegalAgentState,
    SourceType,
    UnknownFact,
)
from agent.planner import parse_plan_decision
from tools.gateway import ToolGateway

def build_transport() -> ChatOpenAI:
    from settings import settings
    assert settings.llm_api_key, "LLM_API_KEY not loaded"
    assert settings.llm_base_url, "LLM_BASE_URL not loaded"
    # 与 llm_registry._build 对齐的最简配置（用默认 key/base_url）
    return ChatOpenAI(
        model="LongCat-2.0",
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
        streaming=False,
        timeout=120,
        max_retries=2,
    )


def make_state_and_bootstrap():
    issue1 = LegalIssue(
        issue_id="issue_abc123",
        question="标准工时制度下周六上班是否构成加班",
        facts=[
            Fact(statement="过去一年几乎每周六工作", source=SourceType.USER,
                 source_ref="request:abc123:user", confidence=1.0),
            Fact(statement="月薪一万元", source=SourceType.USER,
                 source_ref="request:abc123:user", confidence=1.0),
        ],
        unknown_facts=[UnknownFact(
            statement="调休是否已经安排",
            why_outcome_changes="未安排调休则需支付加班费，安排了则无需支付",
        )],
    )
    issue2 = LegalIssue(
        issue_id="issue_def456",
        question="加班工资计算基数如何确定",
        facts=[Fact(statement="工资结构包含基本工资", source=SourceType.USER,
                    source_ref="request:abc123:user", confidence=1.0)],
        unknown_facts=[],
    )
    state = LegalAgentState(
        status="planning",
        budgets=AgentBudgets(max_steps=16, max_clarifications=2),
        issues=[issue1, issue2],
        observations=[],
        evidence=[],
    )
    bootstrap = RequestBootstrap(
        conv_id=12345, summary="", recent=[], recent_messages=[], image=None,
        user_text="我公司实行标准工时制度，过去一年几乎每周六工作，月薪一万元，工资结构包含基本工资，请问周六上班算不算加班，加班工资怎么算？",
        image_rel=None, thumb_rel=None, image_description="",
        raw_query="我公司实行标准工时制度，过去一年几乎每周六工作，月薪一万元，工资结构包含基本工资，请问周六上班算不算加班，加班工资怎么算？",
        supplement_text="", intent="consultation", is_exam=False, has_options=False,
        contract_mode=False, contract_text=None, client_truncated=False,
    )
    return state, bootstrap


def main() -> int:
    transport = build_transport()
    print(f"transport: ChatOpenAI model=LongCat-2.0 base_url={getattr(transport, 'openai_api_base', 'N/A')}")

    state, bootstrap = make_state_and_bootstrap()
    adapter = LLMPlannerAdapter(transport)

    # 1) 确认 _invoke_planner 内部 schema 能构建（不再走 except 回退）
    from pydantic import TypeAdapter
    from agent.schemas import PlanDecision
    schema = TypeAdapter(PlanDecision).json_schema()
    print(f"schema 构建 OK: $defs={list(schema.get('$defs', {}))}")

    print("\n--- 调用 decide()（修复后的 _invoke_planner → bind → LongCat）---")
    try:
        raw = adapter.decide(state=state, bootstrap=bootstrap)
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: decide() 抛 {type(exc).__name__}: {exc}")
        import traceback
        traceback.print_exc()
        return 1

    print(f"SUCCESS: decide() 返回 type={type(raw).__name__}")
    print(f"  raw={json.dumps(raw, ensure_ascii=False, default=str)[:300]}")

    # 2) parse_plan_decision 校验（与 controller 一致）
    try:
        decision = parse_plan_decision(
            raw,
            policies=ToolGateway().policies,
            issue_ids={"issue_abc123", "issue_def456"},
        )
        print(f"parse_plan_decision OK: kind={decision.kind}")
        if hasattr(decision, "tool_name"):
            print(f"  tool_name={decision.tool_name}")
        if hasattr(decision, "issue_id"):
            print(f"  issue_id={decision.issue_id}")
        print("\n✅ 结论：修复后方案 A 经 ChatOpenAI bind 链路真实生效，" +
              "LongCat 对复杂 PlannerDecision 联合 schema 有效，parse 死亡点有望下降。")
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: parse_plan_decision 抛 {type(exc).__name__}: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())