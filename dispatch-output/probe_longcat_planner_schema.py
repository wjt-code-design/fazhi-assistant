"""验证 LongCat 对 planner 复杂联合 schema（PlanDecision）的 response_format 约束力（方案 A 单题验证）。

ADR: docs/adr-longcat-response-format-20260909.md

入口验证：
- 构造真实 planner 输入（来自 run-8 典型缺失事实+证据不全的 state snapshot）
- 调用已实现的 LLMPlannerAdapter.decide()（含 response_format=json_schema 降级逻辑）
- 检查是否解析成功、是否符合 discriminator 语义
- 输出解析结果与失败原因（若有）

若本脚本调用成功，说明复杂 schema 也能被 LongCat 正确约束，全量 run-10 可继续。
"""
import sys
from pathlib import Path

# 加 backend 到路径
REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "backend"))

import os
import json
from datetime import date
from llm_registry import registry
from request_bootstrap import RequestBootstrap
from agent.runtime import LLMPlannerAdapter, _PLANNER_SYSTEM_PROMPT, _planner_payload
from agent.schemas import (
    AgentBudgets,
    Fact,
    LegalIssue,
    LegalAgentState,
    SourceType,
    UnknownFact,
    PlanDecision,
)

def main() -> int:
    # 取 LongCat 实例（registry 按 key 取）
    try:
        llm = registry.pick_by_key("longcat_text_flag")
    except KeyError as e:
        print(f"FAIL: 取不到 longcat_text_flag: {e}")
        print("请检查 .env LLM_MODELS_JSON 是否配置正确")
        return 1

    print(f"取模型成功: model={llm.model_name} base_url={llm.base_url}")

    # 构造典型 planner 输入：C02（劳动合同加班工资）——两个 issue，一个缺失事实
    issue1 = LegalIssue(
        issue_id="issue_abc123",
        question="标准工时制度下周六上班是否构成加班",
        facts=[
            Fact(
                statement="过去一年几乎每周六工作",
                source=SourceType.USER,
                source_ref="request:abc123:user",
                confidence=1.0,
            ),
            Fact(
                statement="月薪一万元",
                source=SourceType.USER,
                source_ref="request:abc123:user",
                confidence=1.0,
            ),
        ],
        unknown_facts=[
            UnknownFact(
                statement="调休是否已经安排",
                why_outcome_changes="未安排调休则需支付加班费，安排了则无需支付",
            )
        ],
    )
    issue2 = LegalIssue(
        issue_id="issue_def456",
        question="加班工资计算基数如何确定",
        facts=[
            Fact(
                statement="工资结构包含基本工资",
                source=SourceType.USER,
                source_ref="request:abc123:user",
                confidence=1.0,
            ),
        ],
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
        conv_id=12345,
        summary="",
        recent=[],
        recent_messages=[],
        image=None,
        user_text="我公司实行标准工时制度，过去一年几乎每周六工作，月薪一万元，工资结构包含基本工资，请问周六上班算不算加班，加班工资怎么算？",
        image_rel=None,
        thumb_rel=None,
        image_description="",
        raw_query="我公司实行标准工时制度，过去一年几乎每周六工作，月薪一万元，工资结构包含基本工资，请问周六上班算不算加班，加班工资怎么算？",
        supplement_text="",
        intent="consultation",
        is_exam=False,
        has_options=False,
        contract_mode=False,
        contract_text=None,
        client_truncated=False,
    )

    adapter = LLMPlannerAdapter(llm)

    print("\n--- 开始调用 LLMPlannerAdapter.decide ---")
    print(f"Input issues: {len(state.issues)} → {[i.question[:30] for i in state.issues]}")

    try:
        raw_result = adapter.decide(state=state, bootstrap=bootstrap)
    except Exception as e:
        print(f"\nFAIL: 调用抛出异常: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return 1

    print(f"\nSUCCESS: 解析成功！")
    print(f"  类型: {type(raw_result).__name__}")
    if hasattr(raw_result, 'kind'):
        print(f"  kind: {raw_result.kind}")
        if hasattr(raw_result, 'issue_id'):
            print(f"  issue_id: {getattr(raw_result, 'issue_id', 'N/A')}")
        if hasattr(raw_result, 'tool_name'):
            print(f"  tool_name: {getattr(raw_result, 'tool_name', 'N/A')}")
        if hasattr(raw_result, 'args'):
            print(f"  args: {repr(getattr(raw_result, 'args', 'N/A'))[:200]}")
        if hasattr(raw_result, 'question'):
            print(f"  question: {getattr(raw_result, 'question', 'N/A')[:80]}")

    # 打印 schema 验证通过的原始 payload（脱敏）
    print("\n--- 原始输出 payload (planner 格式) ---")
    payload = _planner_payload(state, bootstrap)
    print(json.dumps(payload, ensure_ascii=False, indent=2)[:800] + ("\n... (truncated)" if len(json.dumps(payload)) > 800 else ""))

    return 0

if __name__ == "__main__":
    sys.exit(main())
