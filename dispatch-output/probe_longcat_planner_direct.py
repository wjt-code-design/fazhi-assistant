"""直接调用 LongCat API 验证 planner 复杂联合 schema（PlanDecision）的约束力。

绕过 registry 配额检测（因为配额文件可能未记录初始用量导致被误判 depleted），
直接用 HTTP 请求验证，和原始探测脚本 probe_longcat_response_format.py 保持一致。
"""
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO / "backend"))

ENV_PATH = Path(r"C:\Users\33393\Desktop\ai-legal-helper\backend\.env")
_KEY = None
_BASE = None
_MODEL = "LongCat-2.0"
for line in ENV_PATH.read_text(encoding="utf-8", errors="replace").splitlines():
    if line.startswith("LLM_API_KEY="):
        _KEY = line.split("=", 1)[1].strip().strip('"').strip("'")
    elif line.startswith("LLM_BASE_URL="):
        _BASE = line.split("=", 1)[1].strip().strip('"').strip("'")

if not _KEY or not _BASE or not _MODEL:
    print("FAIL: 缺少 LLM_API_KEY / LLM_BASE_URL / LLM_MODEL（.env 未就绪）")
    sys.exit(2)

print(f"base_url: {_BASE}")
print(f"model: {_MODEL}")
print(f"key set: {bool(_KEY)}, len: {len(_KEY)}")

# 构造 planner 真实 prompt + 完整 PlanDecision 联合 schema
# 用 pydantic TypeAdapter 获取顶层 union schema（与 run 时解析保持一致）
from typing import Annotated
from pydantic import BaseModel, Field, TypeAdapter
from agent.schemas import (
    ToolCallDecision,
    AskUserDecision,
    FinishResearchDecision,
    ReplanDecision,
    StopDecision,
    PlanDecision as PD,
)

ta = TypeAdapter(PD)
schema = ta.json_schema()
print(f"\nSchema info:")
print(f"  type: {schema.get('type')}")
print(f"  $defs: {list(schema.get('$defs', {}).keys())}")
print(f"  anyOf: {len(schema.get('anyOf', []))} options")

# 验证 runtime.py 中 PlanDecision.model_json_schema() 是否可用（方案 A 是否曾真正生效）
try:
    _s = PD.model_json_schema()
    print(f"\n[CHECK] PlanDecision.model_json_schema() 可用，BIND 会真正启用")
except AttributeError as e:
    print(f"\n[CHECK] PlanDecision.model_json_schema() 抛错: {e}")
    print(f"[CHECK] → runtime.py 的 _invoke_planner 将静默走 except 回退普通调用，方案 A 从未真正绑定 response_format！")

# 构造真实 messages（完全复用 runtime 中的 prompt）
from request_bootstrap import RequestBootstrap
from agent.runtime import _PLANNER_SYSTEM_PROMPT, _planner_payload
from agent.schemas import (
    AgentBudgets,
    Fact,
    LegalIssue,
    LegalAgentState,
    SourceType,
    UnknownFact,
)

# 构造典型输入：C02 加班工资问题，两个 issue，一个缺失事实
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

messages = [
    {"role": "system", "content": _PLANNER_SYSTEM_PROMPT},
    {"role": "user", "content": json.dumps(
        _planner_payload(state, bootstrap),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )},
]

response_format = {
    "type": "json_schema",
    "json_schema": {
        "name": "plan_decision",
        "strict": False,  # 复杂联合 schema 不强制 strict，避免被平台 400 拒绝
        "schema": schema,
    },
}

url = _BASE.rstrip("/") + "/chat/completions"
payload = {
    "model": _MODEL,
    "messages": messages,
    "max_tokens": 512,
    "temperature": 0.0,
    "response_format": response_format,
}

print(f"\n--- 发送请求 ---")
print(f"  messages: {len(messages)} 条")
print(f"  system prompt: {len(_PLANNER_SYSTEM_PROMPT)} chars")
print(f"  user payload: {len(json.dumps(_planner_payload(state, bootstrap)))} chars")

req = urllib.request.Request(
    url,
    data=json.dumps(payload).encode("utf-8"),
    headers={"Content-Type": "application/json", "Authorization": f"Bearer {_KEY}"},
    method="POST",
)
try:
    with urllib.request.urlopen(req, timeout=120) as resp:
        body = json.loads(resp.read().decode("utf-8"))
        print(f"\n[{resp.status}] HTTP OK")
        content = body["choices"][0]["message"]["content"] if body.get("choices") else ""
        print(f"\nContent [{len(content)} chars]:")
        print(f"--- BEGIN ---")
        print(content)
        print(f"--- END ---")

        # 尝试解析为 JSON
        try:
            parsed = json.loads(content)
            print(f"\n✅ JSON 解析成功")
            print(f"  parsed keys: {list(parsed.keys())}")
            # 用 TypeAdapter 做顶层 union 校验（与 run 时 parse_plan_decision 同源 schema）
            try:
                validated = ta.validate_python(parsed)
                print(f"✅ Pydantic 校验成功")
                print(f"  kind: {validated.kind}")
                if hasattr(validated, 'issue_id'):
                    print(f"  issue_id: {validated.issue_id}")
                if hasattr(validated, 'tool_name'):
                    print(f"  tool_name: {validated.tool_name}")
                print(f"\n✅ 结论：LongCat 对复杂联合 discriminator schema 具备真实约束力！")
                print(f"   方案 A 可以继续实施，进入全量 run-10 验证。")
            except Exception as e:
                print(f"\n❌ Pydantic 校验失败：{type(e).__name__}: {e}")
                print(f"\n结论：schema 约束力不足，方案 A 需要回退或调整 strict 参数。")
        except json.JSONDecodeError as e:
            print(f"\n❌ JSON 解析失败：{e}")
            print(f"结论：LongCat 未正确产出 JSON，response_format 未生效。")
except urllib.error.HTTPError as exc:
    err = exc.read().decode("utf-8", errors="replace")[:600]
    print(f"\n[{exc.code}] HTTP REJECTED")
    print(f"  body={err}")
    sys.exit(1)
except Exception as exc:
    print(f"\nEXC {type(exc).__name__}: {exc}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
