"""T8 接线与修复环验证（离线，零 LLM 外呼）。

三个场景，全部走**生产装配路径**（build_agent_runtime → runtime.build_initial_state）：

  1. 覆盖缺口 → 守卫已接线并生效（闭合"日志 0 触发是在好结果还是没接上"的歧义）
  2. 非逐字引用（= 验证轮 C06 真实死因）→ 加固**前**不经过修复环、直接抛错；加固**后**可修复
  3. Pareto 采纳规则 → "补上覆盖缺口但新增非逐字引用"的结果**不得采纳**
     （旧实现只比覆盖缺口，会采纳它 ⇒ 把成功改成失败）

说明：`fact_repair=False` 是"加固前行为"的**代理**（真回退需 `git checkout`，属项目红线）。
场景 3 的"旧规则"用两行等价比较式复算，同样标注为代理，不是运行旧代码。
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

from agent.runtime import (  # noqa: E402
    IssueDecompositionError,
    LLMIssueDecomposer,
    _defect_total,
    _fact_defects,
    build_agent_runtime,
    build_initial_agent_state,
)
from request_bootstrap import RequestBootstrap  # noqa: E402
from settings import settings  # noqa: E402

QUERY = "公司拖欠我两个月工资，并在昨天口头解除劳动合同"   # 两个事实性分句


class Response:
    def __init__(self, content: str) -> None:
        self.content = content


class ScriptedTransport:
    def __init__(self, *responses: str) -> None:
        self.responses = list(responses)
        self.calls = 0

    def invoke(self, messages):
        self.calls += 1
        if not self.responses:
            raise IndexError("no canned response left")
        return Response(self.responses.pop(0))


def issue(question: str, *quotes: str) -> dict:
    return {"question": question, "facts": [{"quote": q} for q in quotes], "unknown_facts": []}


def payload(*issues: dict) -> str:
    return json.dumps({"issues": list(issues)}, ensure_ascii=False)


def bootstrap() -> RequestBootstrap:
    return RequestBootstrap(
        conv_id=1, summary="", recent=[], recent_messages=[], image=None,
        user_text=QUERY, image_rel=None, thumb_rel=None, image_description="",
        raw_query=QUERY, supplement_text="", intent="legal_query", is_exam=False,
        has_options=False, contract_mode=False, contract_text=None, client_truncated=False,
    )


def state_of(*responses: str, fact_repair: bool = True, via_runtime: bool = True):
    """via_runtime=True 走**生产装配**（build_agent_runtime，修复环按生产默认开启）；
    via_runtime=False 为"加固前行为"的**代理**（显式 fact_repair=False，直连 build_initial_agent_state）。"""
    t = ScriptedTransport(*responses)
    try:
        if via_runtime:
            r = build_agent_runtime(db=object(), user_id=1, settings=settings, llm=t)
            st = r.build_initial_state(bootstrap())
        else:
            st = build_initial_agent_state(
                bootstrap(), decomposer=LLMIssueDecomposer(t, fact_repair=fact_repair)
            )
        return t.calls, len(st.issues), None
    except IssueDecompositionError as exc:
        return t.calls, None, str(exc)


lines: list[str] = []

# ---- 场景 1：覆盖缺口 → 接线生效 ----
c, n, err = state_of(payload(issue("争点1是否成立？", "公司拖欠我两个月工资")),
                     payload(issue("争点1是否成立？", "公司拖欠我两个月工资"),
                             issue("争点2是否成立？", "在昨天口头解除劳动合同")))
lines.append(f"[场景1 覆盖缺口] 外呼={c}（期望 2）  issues={n}（期望 2）  err={err}")
lines.append(f"  => 守卫在生产装配路径上已接线并生效：{'✅' if (c == 2 and n == 2) else '❌'}")

# ---- 场景 2：非逐字引用（C06 真实死因）----
bad = payload(issue("争点1是否成立？", "公司拖欠我三个月工资"))          # 非逐字
good = payload(issue("争点1是否成立？", "公司拖欠我两个月工资"),
               issue("争点2是否成立？", "在昨天口头解除劳动合同"))
c_off, n_off, err_off = state_of(bad, good, fact_repair=False, via_runtime=False)
c_on, n_on, err_on = state_of(bad, good)
lines.append("")
lines.append(f"[场景2 非逐字引用] 加固前(代理 fact_repair=False)：外呼={c_off} issues={n_off} err={err_off}")
lines.append(f"                    加固后(生产装配)        ：外呼={c_on} issues={n_on} err={err_on}")
ok2 = err_off is not None and err_on is None and c_on == 2 and n_on == 2
lines.append(f"  => 第三处修复环补齐有效（加固前必失败、加固后可修复）：{'✅' if ok2 else '❌'}")

# ---- 场景 3：Pareto 采纳规则 ----
first = payload(issue("争点1是否成立？", "公司拖欠我两个月工资"))          # 缺口 1、非逐字 0
traded = payload(issue("争点1是否成立？", "公司拖欠我两个月工资"),
                 issue("争点2是否成立？", "在昨天口头解除劳动合同", "在昨天解除劳动合同"))  # 缺口 0、非逐字 1
c3, n3, err3 = state_of(first, traded)
env_first = json.loads(first)
env_traded = json.loads(traded)
from agent.runtime import _IssueEnvelope  # noqa: E402

d_first = _fact_defects(QUERY, _IssueEnvelope.model_validate(env_first))
d_traded = _fact_defects(QUERY, _IssueEnvelope.model_validate(env_traded))
old_rule_adopts = len(d_traded["uncovered"]) < len(d_first["uncovered"])   # 旧实现只比覆盖缺口
new_rule_adopts = (
    len(d_traded["non_verbatim"]) <= len(d_first["non_verbatim"])
    and len(d_traded["uncovered"]) <= len(d_first["uncovered"])
    and _defect_total(d_traded) < _defect_total(d_first)
)
lines.append("")
lines.append(f"[场景3 Pareto 采纳] 首轮缺陷={d_first}（总 {_defect_total(d_first)}）")
lines.append(f"                    候选缺陷={d_traded}（总 {_defect_total(d_traded)}）")
lines.append(f"  旧规则(只比覆盖缺口)会采纳={old_rule_adopts}  ← 会把成功改成失败")
lines.append(f"  新规则(Pareto)会采纳   ={new_rule_adopts}")
lines.append(f"  实测：外呼={c3} 最终 issues={n3}（期望 1 = 保留原结果）err={err3}")
ok3 = old_rule_adopts and not new_rule_adopts and n3 == 1
lines.append(f"  => Pareto 规则按预期拒绝劣化型修复：{'✅' if ok3 else '❌'}")

out = HERE.parent / "t8-wiring-verification.txt"
out.write_text("\n".join(lines) + "\n", encoding="utf-8")
print("\n".join(lines), flush=True)
print(f"[log] {out}", flush=True)
