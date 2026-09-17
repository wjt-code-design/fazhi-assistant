"""验证：增强后的 planner schema（args 注入具体工具输入字段）是否让 LongCat 填满 args。

不改模型语义（ToolCallDecision.args 仍是宽松 BaseModel，安全边界在 gateway），
只在请求层把 $defs/BaseModel 替换为具体工具输入联合——模型侧提示增强。
"""
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO / "backend"))

from dotenv import load_dotenv

load_dotenv(Path(_REPO / "backend" / ".env"))

from pydantic import BaseModel, TypeAdapter

from tools.contracts import (
    ContractInput,
    LookupArticleInput,
    RetrieveLawsInput,
    RetrieveMemoryInput,
)
from agent.schemas import PlanDecision

# ============ 构建增强 schema ============
_ARGS_UNION = TypeAdapter(RetrieveLawsInput | LookupArticleInput | ContractInput | RetrieveMemoryInput)
_args_schema = _ARGS_UNION.json_schema()
_args_models = ["RetrieveLawsInput", "LookupArticleInput", "ContractInput", "RetrieveMemoryInput"]


def _build_schema() -> dict:
    schema = TypeAdapter(PlanDecision).json_schema()
    schema["$defs"].update(_args_schema.get("$defs", {}))
    # 合并 name 映射（union 的 $defs 里 key 就是模型名）
    schema["$defs"]["ToolCallDecision"]["properties"]["args"] = {
        "anyOf": [{"$ref": f"#/$defs/{n}"} for n in _args_models]
    }
    return schema


schema = _build_schema()
print("增强后 args schema:")
print(json.dumps(schema["$defs"]["ToolCallDecision"]["properties"]["args"], ensure_ascii=False, indent=1)[:500])

# ============ 构造真实 messages ============
from request_bootstrap import RequestBootstrap
from agent.runtime import _PLANNER_SYSTEM_PROMPT, _planner_payload
from agent.schemas import AgentBudgets, Fact, LegalIssue, LegalAgentState, SourceType, UnknownFact

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

messages = [
    {"role": "system", "content": _PLANNER_SYSTEM_PROMPT},
    {"role": "user", "content": json.dumps(
        _planner_payload(state, bootstrap), ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )},
]

# ============ 请求 LongCat ============
from settings import settings

assert settings.llm_api_key and settings.llm_base_url
url = settings.llm_base_url.rstrip("/") + "/chat/completions"
payload_body = {
    "model": "LongCat-2.0",
    "messages": messages,
    "max_tokens": 512,
    "temperature": 0.0,
    "response_format": {
        "type": "json_schema",
        "json_schema": {"name": "plan_decision", "strict": False, "schema": schema},
    },
}
req = urllib.request.Request(
    url,
    data=json.dumps(payload_body).encode("utf-8"),
    headers={"Content-Type": "application/json", "Authorization": f"Bearer {settings.llm_api_key}"},
    method="POST",
)
try:
    with urllib.request.urlopen(req, timeout=120) as resp:
        body = json.loads(resp.read().decode("utf-8"))
        content = body["choices"][0]["message"]["content"]
        print(f"\n[HTTP {resp.status}] content={content}")
        parsed = json.loads(content)
        print(f"\n解析成功: keys={list(parsed.keys())}")
        pa = parsed.get("args")
        print(f"args = {json.dumps(pa, ensure_ascii=False)}")
        if isinstance(pa, dict) and pa.get("query"):
            print("\n✅ 结论：增强 schema 让 LongCat 填满 args（query 存在），方案 A 完整可用！")
        else:
            print("\n⚠️  args 仍未填满（可能 schema anyOf 无 discriminator 时平台退化为宽松）")
except urllib.error.HTTPError as exc:
    print(f"\n[HTTP {exc.code}] {exc.read().decode('utf-8', errors='replace')[:500]}")
    sys.exit(1)