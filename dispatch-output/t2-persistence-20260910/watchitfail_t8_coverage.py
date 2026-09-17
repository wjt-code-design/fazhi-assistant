"""watch-it-fail 证据：证明新增的覆盖度修复环测试确实能区分"旧行为 vs 新行为"。

方法：同一场景（用户明说两条事实，分解器只覆盖其中一条）跑两遍 ——
  A. fact_repair=False → 等价于加固前的行为（只调一次、缺陷保留）
  B. fact_repair=True （默认，生产行为）→ 回喂修复一次并采纳
若 A 与 B 的观测值相同，则新测试不具鉴别力（假绿）；两者不同才说明测试有效。

全程离线（RecordingTransport），不触发任何 LLM 外呼。
"""

from __future__ import annotations

import json
import os
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve()
BACKEND = HERE.parents[2] / "backend"
sys.path.insert(0, str(BACKEND))
os.chdir(BACKEND)

from agent.runtime import LLMIssueDecomposer, build_initial_agent_state  # noqa: E402
from request_bootstrap import RequestBootstrap  # noqa: E402

QUERY = "公司拖欠我两个月工资，并在昨天口头解除劳动合同"


class Response:
    def __init__(self, content: str) -> None:
        self.content = content


class RecordingTransport:
    def __init__(self, *responses: str) -> None:
        self.responses = list(responses)
        self.calls = 0

    def invoke(self, messages):
        self.calls += 1
        if not self.responses:
            raise IndexError("no canned response left")   # 等价于旧实现"没有第二次外呼预算"
        return Response(self.responses.pop(0))


def issue_json(*quotes: str) -> str:
    return json.dumps(
        {
            "issues": [
                {"question": f"争点{i}是否成立？", "facts": [{"quote": q}], "unknown_facts": []}
                for i, q in enumerate(quotes, start=1)
            ]
        },
        ensure_ascii=False,
    )


def bootstrap() -> RequestBootstrap:
    return RequestBootstrap(
        conv_id=1, summary="", recent=[], recent_messages=[], image=None,
        user_text=QUERY, image_rel=None, thumb_rel=None, image_description="",
        raw_query=QUERY, supplement_text="", intent="legal_query", is_exam=False,
        has_options=False, contract_mode=False, contract_text=None, client_truncated=False,
    )


lines: list[str] = []
for label, repair in (("A 旧行为 fact_repair=False", False), ("B 新行为 fact_repair=True", True)):
    transport = RecordingTransport(issue_json("公司拖欠我两个月工资"), issue_json("公司拖欠我两个月工资", "在昨天口头解除劳动合同"))
    state = build_initial_agent_state(bootstrap(), decomposer=LLMIssueDecomposer(transport, fact_repair=repair))
    lines.append(f"{label}: 外呼次数={transport.calls}  issues={len(state.issues)}")

lines.append("")
if lines[0].split("外呼次数=")[1].split("  ")[0] == lines[1].split("外呼次数=")[1].split("  ")[0]:
    lines.append("判定：A 与 B 相同 ⇒ 新测试**不具鉴别力**（假绿），加固无效——需重新设计。")
else:
    lines.append("判定：A 与 B 不同 ⇒ 新测试**具备鉴别力**（在旧行为下会为正确原因变红）。")

out = HERE.parent / "watchitfail_t8_coverage.txt"
out.write_text("\n".join(lines) + "\n", encoding="utf-8")
print("\n".join(lines), flush=True)
print(f"[log] {out}", flush=True)
