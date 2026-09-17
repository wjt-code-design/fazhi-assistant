# Gate 6：入口与路由验收报告（2026-09-08）

> 依据：任务书 `docs/agent-complex-consultation-v1-taskbook-20260907.md` §9 Gate 6 与 §3.6、§6.1；
> 评测器纠偏任务书 §7.1 第 4 点「Gate 6 未完成独立验收」之补验。
> 方式：静态代码审计 + 既有测试证据；**未调模型、未改代码、未发起真实请求**（运行时人工交互验证列在"未验证项"）。
> 判定口径（任务书要求）：① 手动"深入分析"稳定进入 Agent 并提示可能 1-2 轮追问；② 自动规则第一阶段只给"建议"，不得无提示直接切换；③ 拒绝→保持普通 RAG；接受→带当前问题进入同一 Agent 会话；④ 入口测试与回答质量测试分开报告。

## 逐项判定

| 验收项 | 判定 | 证据 |
|---|---|---|
| G1 手动"深入分析"入口稳定进入 Agent | ⚠️ **部分** | 服务端就绪：`ChatIn.force_agent`（`backend/schemas.py`），`main.py:1454` `forced_manual = force_agent and gate.mode != "refuse"` → 强制走 agent 路径；测试 `backend/tests/test_chat_force_agent.py`（3 条：默认 False 不静默切换 / True 解析 / resume 三件套强制校验仍生效）。**前端 UI 空缺**：`frontend/app/chat/page.tsx` 无"深入分析"按钮或相关文案（全文检索"深入/深度/智能体/建议深入"零命中），仅存在 Agent resume 处理（pendingAgentRun）。→ API 可测入口成立，用户可见按钮未接入 |
| G2 自动规则"只建议不无提示切换" | ❌ **不通过** | 自动路径实现为确定性流量分流：`routing_metrics.should_route_agent`（行 43-60）在 `gate.mode=="agent_path"` 且 `agent_traffic_percent>0` 时按 `stable_request_seed` 哈希分桶直接选中 agent；**无任何"建议/确认"交互**（无 suggest SSE 事件、前端无建议气泡，GateMode 仅 fast_path/agent_path/clarify/refuse 四种）。与任务书"不得在无提示情况下直接切换"语义不符。缓解事实：`settings.agent_traffic_percent` 默认 `0`（`backend/settings.py:49`），自动分流**当前未实际启用**，冲突未暴露给真实流量；但机制本身不满足要求 |
| G3 拒绝保持 RAG / 接受进同一会话 | ⚠️ **部分（仅服务端）** | 拒绝路径：无 force_agent 且自动未选中 → `fast_path`（普通 RAG 链路，`main.py:1426` `_pre` 分支）结构成立；接受路径：force_agent 单会话多轮通过 `conversation_id/agent_run_id/agent_state_version` resume（runner 协议同卷实测成立）。**UI 建议→接受/拒绝交互不存在**（因 G2 无建议机制） |
| G4 入口测试与质量测试分开报告 | ✅ 通过 | 本报告（路由/入口）与 gate5 判定（回答质量）为独立文档与独立测试；force_agent 测试不参与 9/10 回答门槛计算 |

## 结论

**Gate 6 不通过。** 关键缺口：
1. **前端"深入分析"入口未接入**（API 层 `force_agent` 已就绪并有单测，UI 无按钮、无"可能 1-2 轮追问"提示文案）；
2. **自动路由是静默流量分流而非"建议式"交互**，与任务书 §3.6 / Gate 6 语义冲突（当前因 `agent_traffic_percent=0` 未实际分流，但机制不满足要求）。

服务端能力（force_agent、fast_path 保持、单会话 resume）已具备且经测试，**缺口集中在交互层与策略语义**。

## 未验证项（需运行时人工操作）

- 前端按钮触达"深入分析"后的实际提问流程与 1-2 轮追问提示（UI 不存在，无法验证）；
- 真实用户"拒绝建议"后是否保持 RAG（无建议交互可拒绝）；
- 分流百分比若开启后的行为（当前 0，未做实流量验证）。

## 修复建议（归入后续 Agent 修复项，不在本任务范围）

1. 前端接入"深入分析"按钮 + "可能需 1-2 轮追问"提示（force_agent=true 触发）；
2. 新增"suggest"交互语义：gate 判定 agent_path 的高置信请求返回"建议"事件而非直接分流，用户确认后再以 force_agent 进入（或将任务书策略按产品决策调整为显式灰度分流并记录 ADR）；
3. 补充 UI 层入口自动化测试（entry + resume 提示）。

## 关闭条件

上述 1/2 项实现并验证后，重新按 G1-G4 验收；当前报告作为"Gate 6 粗粒度独立验收：不通过"的正式记录存证。