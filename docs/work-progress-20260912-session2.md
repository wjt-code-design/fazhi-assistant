# 工作进度文档（2026-09-12 晚 · session 2）

> **自包含声明**：本文档不依赖任何对话记忆，读完即可理解当前状态并接手。
> 项目根：`C:\Users\33393\Desktop\ai-legal-helper`。详细操作纪律见 `docs/final-agent-handoff-20260912-session2.md`（交接文档）。

---

## 1. 项目是什么（30 秒背景）

**法智 Agent**：一个法律问答 Agent。主链路是 LLM 驱动的循环：
`争点分解 → 检索法条 → 澄清用户 → 起草 → 验证器校验 → 出终稿`。

- 每个"争点"（issue）= 用户问题拆出的一个法律争议点；争点数 N 由模型自由决定。
- **步数（steps）**= 状态机转换次数，是每轮运行的硬预算（当前 `max_steps=20`）。
- 关键组件：`backend/agent/controller.py`（主控制器）、`backend/agent/writer.py`（起草，**fail-fast**：
  任意一条 claim 校验失败 → 整篇作废）、`backend/agent/verifier.py`（覆盖率门）、`backend/tools/gateway.py`（工具网关）。
- 付费验证用真实模型 **qwen3.8-flash（DashScope）**（宿主 `dispatch-output/agent-quality-20260911/serve.py`，断言此模型）。
- 纪律红线：不改冻结评测 judge/案例；每轮付费独立证据目录+账本+隔离库；连续 2 轮同类失败即停。

## 2. 正在做什么（当前任务）

**目标**：让主链路在步数预算内"走到起草"（出终稿，`agent_completed=True`）。

**为什么是它**：历轮付费运行显示——争点一多（实测 8 个）步数就在 20 内耗尽 → `budget_exceeded`
→ 技术失败回落 Fast Path → 用户拿到的是 RAG 快答而非 Agent 终稿。这是当时唯一未解决的阻塞点。

## 3. 已做了什么（按时间顺序，均已完成并提交）

| # | 阶段 | 内容 | 结果 | 提交 |
|---|---|---|---|---|
| 1 | 交接核对 | 交接文档 vs 代码库逐条核对 | 3 处口径出入已修正 | — |
| 2 | **T1a**（C-1b） | 检索扇出期间**暂缓澄清**：不中途问用户，先把全部争点检索完 | 8 争点检索 5→6，仍 19/20 停（半程） | `11b435c` |
| 3 | **T1b**（真·批量检索） | 把逐争点检索改为**一个周期连发全部检索**，步数与争点数解耦 | **8 争点 9/20 步 COMPLETED** | `c5236ef` |
| 4 | T2 门禁 | 全量回归 + lint | **950 passed / 78.52% / ruff·mypy 全 0** | — |
| 5 | **T4** 付费验证 | qwen3.8-flash 真实模型跑 C01，目标连续 3 轮全绿 | **2 轮同类失败 → 止损停止** | `c68dfda` |

前置轮次（交接文档 §3，早于本 session）：H1 检索超时修复（5 轮 0 超时）、三套归因埋点（覆盖率/writer/数字违规分桶）、`AGENT_MAX_STEPS` 16→20（用户批准）。

## 4. 关键成果（有证据）

- **步数阻塞点彻底解除**：8 争点从"18/20 停"→ 批量后 **9/20 步 COMPLETED**（离线）；真实付费 r1 也实测 `steps=9/20`、4 争点全检索、**证据绑定逐条核对正确**。
- 质量门禁全绿；候选哈希 ALL_MATCH。
- T4 成本 0.0463 元（累计 ≈0.1175 元，20 元授权窗口内）。

## 5. 遇到的问题

### 5.1 已解决（T1b 实现中实测踩到，均已修复+回归）

| # | 问题 | 根因 | 修复 |
|---|---|---|---|
| 1 | 批量检索反复整批重跑 → 最终 `duplicate_attempts` 预算停 | 状态回 PLANNING 时重入扇出，而"待检索"条件用的是"无证据"而非"已尝试" | 待检索清单排除**已尝试**的争点（口径与 `_every_issue_retrieval_attempted` 一致） |
| 2 | `INTEGRITY_DIVERGENT_EVIDENCE_ID` 完整性失败 | 批内多个争点检索到同一法条时重复物化，同 ID 不同时间戳 | 批内物化基于"已累积"的线程化状态去重 |
| 3 | 第 7 次检索被网关拒绝（`TOOL_CALL_LIMIT_EXCEEDED`）→ 整轮失败 | 网关单工具上限 `max_calls_per_run=6`，8 争点需 8 次 | 6→10（与状态层总闸 `max_tool_calls=10` 对齐） |
| 4 | 离线起草测试"假绿"（实际一直失败） | 测试夹具输出缺 writer 严格 schema 要求的字段 | 补齐 `missing_information`/`section` 字段 |

### 5.2 未解决（结构性，当前卡点）

1. **writer 模型遵守度（当前唯一阻塞点）**
   - 现象：真实模型多争点起草时**跨争点引用证据** / **非规范引用** / **省略部分争点的 claim** →
     writer 校验失败 → 整篇作废 → `agent_completed=False`。
   - T4 两轮实测：r1 `CROSS_ISSUE_EVIDENCE`（生成 4 条 claim 只接受 1 条）；r2 `NON_CANONICAL_CITATION`+`CROSS_ISSUE_EVIDENCE`（生成 6 条接受 2 条）。
   - 定性：提示词约束（"只能引用同争点的 Evidence ID"等）**已写明、模型仍违反**（此前两次实测同样现象）；
     属于 LLM 生成遵守度问题，**不是批量检索/证据/预算的 bug**。
2. **争点数无上界（根因仍在）**：批量检索让步数成本不再随 N 涨，但模型仍可能切 9+ 个争点。
3. **git 对象库损坏**（预存，非本次引入）：22 处 missing（如 `03a2f14`），geometric repack 报错；
   HEAD 完好、新提交不受影响；**push 到远端前需先修复**（交接文档 §4 有建议：`git fetch origin` 补齐或重 clone）。

## 6. 当前状态

- **步数预算不再是阻塞点**（已实证）。
- **T4 已按止损规则停止**（连续 2 轮同类 writer 失败），结论报告在
  `dispatch-output/t4-batch-retrieval-20260912-r2/t4-conclusion-report.md`。
- **等待用户拍板 writer 遵守度的处理方向**（见第 7 节）。

## 7. 待决策（下一步）

writer 遵守度是模型生成层的结构性概率问题，工程手段有限，三条路：

1. **writer 侧确定性后处理**：证据-争点归属硬校验后自动修正引用（改动 writer 校验逻辑，触碰 fail-fast 语义，需谨慎）。
2. **分争点独立渲染**：每个争点单独调 writer 起草，消除跨争点上下文（直击根因，改动面大：渲染/回喂/合并）。
3. **接受现状**：付费验证口径改为"到起草即算绿"（不解决引用质量问题，但承认模型能力边界）。

## 8. 接手者快速上手

- 跑测试（必须带全新目录名 basetemp，见交接文档 §1/§10.1）：
  `cd backend && ./venv/Scripts/python.exe -m pytest -m 'not slow' --cov=. --cov-fail-under=70 -q --basetemp="<新目录>/pytest-full-1"`
- 8 争点离线反例（批量检索的目标测试）：`tests/test_agent_chat_integration.py::test_eight_issue_decomposition_batch_reaches_drafting_within_20`
- 批量检索实现位置：`backend/agent/controller.py` `_seed_issue_retrievals`
- writer 校验失败面：`backend/agent/writer.py` `_render_once`（fail-fast，各 reason_code 见 `_fail_here`）
- 本 session 提交链：`11b435c`（C-1b）→ `c5236ef`（批量）→ `c68dfda`/`49a94f3`（文档）
- 所有证据目录：`dispatch-output/t4-batch-retrieval-20260912*`（付费 r1/r2）、`t1a-c1b-20260912`（离线）
