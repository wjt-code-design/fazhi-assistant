# Gate 2 基线报告 + Gate 3 失败归因（Agent 复杂咨询 V1 第一阶段）

> 日期：2026-09-07 · 基线 commit：`ee7ab8d`（行为=4e6950a + force_agent 入口 12d1f2b）
> 模型 LongCat-2.0（.env LLM_MODELS_JSON 覆盖）、force_agent=true（手动深入单测通道）、no_cache=true
> 原始会话：`release-evidence/legal-agent-v1-complex-v1-20260907/gate2-run-gate2-baseline-1-sessions.json`

## 1. 入口基线（修复后）

- 自然路由（force=false）：仅 C07/C10 routed（8/10 RAG 快答）→ 验证"手动深入分析入口"必需性。
- force_agent=true：**10/10 进入 Agent**（C01-C10 均可测完整会话）✅（提交 `12d1f2b`，先红后绿：C01 fix 前 RAG→fix 后 agent+澄清）。

## 2. 多轮基线形态（10 题，每轮 ≤2 追问）

| 题 | rounds | 澄清轮 | answered fact | unknown | final_chars | 结果 |
|---|---|---|---|---|---|---|
| C01 | 1 | 0 | 0 | 0 | 0 | 首轮 error（另测） |
| C02 | 1 | 0 | 0 | 0 | 0 | 首轮 error（另测） |
| C03 | 3 | 2 | 1 | 1 | 0 | 第二轮 409→无 final |
| C04 | 3 | 2 | 1 | 1 | 0 | 第二轮 409→无 final |
| C05 | 3 | 2 | 1 | 1 | 0 | 第二轮 409→无 final |
| C06 | 2 | 1 | 0 | 1 | 1387 | 一轮后条件化（成功样） |
| C07 | 3 | 2 | 1 | 1 | 0 | 第二轮 409→无 final |
| C08 | 3 | 2 | 1 | 1 | 0 | 第二轮 409→无 final |
| C09 | 3 | 2 | 2 | 0 | 0 | 第二轮 409→无 final |
| C10 | 3 | 2 | 3 | 0 | 0 | 第二轮 409→无 final |

**开发集基线通过率：1/10（C06 有 final；C01/C02 首轮 error 除外）——远未达 9/10，如实记录。**

## 3. Gate 3 失败归因（逐题主失败面）

### 主失败面 F1：第二轮 resume 一律 409（会话/状态面）——8/10 题
- 证据链：round2 resume expected_version=8、run DB status=waiting_user/state_version=8 **完全一致**，
  仍 409 `AGENT_STATE_INTEGRITY/任务已变化`。
- 根因：`resume_with_user_fact` 要求评估器将本次作答判定为 **MISSING_FACT**（防"答非所问强行推进"）；
  当第二轮澄清指向**补充事实库外/已答事实**（问"书面合同是否明确定金/订金"等库外事项，
  或第一轮已答项），用户如实答"无此信息"→ 评估 outcome≠MISSING_FACT → 409。
- **机制事实**：系统在"用户无可用事实可给"的场景无法走条件化，只能拒绝恢复——Agent 自身又不具备
  "两轮后强制条件化"（prompt 无上限约束），形成对话死锁 → 无 final。

### 主失败面 F2：Agent 首轮追问偏向"决定性事实"而非"补充库事实"（planner 面）——大面积
- Agent 首轮多问"绩效评定标准/书面合同性质/停工原因"等决定性事实（deciding_facts），
  而这些多不在两轮用户补充库（只有任务书指定子集）→ answered 偏低、unknown 偏高。
- 判定：非模型能力问题，而是**追问事实集与用户可答集错位**（数据集设计特性 + Agent 问法选择）——
  §6.1 语义下正确行为是"不问到不提示"，但 Agent 问到的（库内无）也让会话推进困难。

### 主失败面 F3：首轮直接 error（C01/C02，generation/运行面）
- C01/C02 initial events=[agent_status,error]，无澄清无内容。
- 需补 error message 复测（诊断会话后处理），候选：分解/资源/预算异常。

### 次失败面汇总
- 六段式结构：无一题产出（final 缺失由 F1 阻断）；C06 final 起步即六段标题结构（说明 writer 具备能力，被 F1 阻断）。
- 依据命中：因无 final，R8（依据绑定）无法判定 → 挂 F1 修复后复评。
- 安全红线：0 触发（无越界/伪造/泄密迹象）。

## 4. 归因结论（供 Gate 4 最小修复）

1. **F1 是主 blocker**：多轮会话在"用户无法提供关键事实"的正确输入下无法推进到条件化。
   - 修复位（最小）：(a) Agent prompt/planner 引入「最多两轮追问，达到后必须条件化分析」，杜绝第三轮追问
     （Ask 角色不应在无新信息时继续追问）；(b) resume 语义：用户明确表示无此信息时，把该事实标记为
     "用户确认未知"，允许 planner 转入条件化（**需谨慎：不弱化 409 的防绕过保护**——仅对"显式未知"答复放行，
     而非任意非事实文本）。候选(a)先做（纯 prompt 层，风险低）。
2. **F2**：不视为需修项——数据集限制已由任务书定义；但若 (a) 后第二轮追问仍大量扑空补库，
   需在 Gate 4 补"追问事实选择"约束（planner 优先追问决定结论的缺失事实）。
3. **F3**：补 error message 后单独归因（下一轮诊断）。

## 5. 下一步

- Gate 4：(a) prompt 追问上限约束 + 测试（目标：第二轮后不再 clar，产出条件化六段式）
- 重跑 Gate 2 基线复测（第二轮不再 409 死锁）
- 若 (a) 不足以解 F1，提交 (b) 架构级评估（不盲目打第三轮补丁）

---

# 附：Gate 4 修复命中验证与归因修正（2026-09-08，baseline-2→6 四轮重跑）

> 会话原始：`release-evidence/legal-agent-v1-complex-v1-20260907/gate2-run-baseline-6-sessions.json`（及其余 baseline-N-sessions.json）

## A. F1 根因修正（重要）

`baseline-1` 曾把 F1（第二轮全部 409）归因为"评估器 MISSING_FACT 收紧校验"。多轮重跑 + DB counter 取证后**修正**：

- **真实根因 = steps 预算耗尽**：第二轮澄清 checkpoint 时 `steps=8` 已等于 `budgets.max_steps=8`，
  用户第二轮回答的 `transition(PLANNING)` 使 steps→9 触发 `BudgetExceeded` → `ResumeRunConflict`(409)。
  所有需两轮澄清的题全部中招（一轮内完成的不受影响）——与现象完全吻合，版本/状态字段其实全部匹配。
- 秘密：单测未暴露是因为 `LegalAgentState` 默认 `max_steps=24`，而运行环境 `settings.agent_max_steps=8` 才触发。

## B. Gate 4 修复（两处）

1. **`agent_max_steps` 默认 8→16**（`settings.py`，`.env` 显式 `AGENT_MAX_STEPS=16`）
   —— 产品承诺"最多两轮追问"，8 装不下两轮完整会话；16 在 le=32 防失控上限内留余量。
2. **确定性强制条件化门**（`controller._handle_evaluation` MISSING_FACT 分支）：
   `clarifications >= budgets.max_clarifications` 时仍判定 MISSING_FACT → 不再 `register_clarification`
   （原行为：预算 STOP→静默降级，用户最后回答被丢弃），而是 `transition(DRAFTING)`，
   审计记录 `conditional_analysis / CLARIFY_BUDGET_EXHAUSTED`。
   - 覆盖实测路径：第三次"澄清"可由 **finish_research 决策 + 评估器 MISSING_FACT** 注册（C10），
     仅拦 ask_user 不足，统一门放在评估器分支。
   - fail-closed 保留：预算到顶（steps 耗尽）时 resume 仍 409（`test_resume_when_steps_budget_exhausted_still_conflicts`）。

回归测试：`test_agent_resume.py` + `test_agent_controller.py` 合计 66 passed（含新增：
动作悬链第二次 resume、预算耗尽仍 409、ask_user/finish_research 强迫条件化、预存图片门禁 501 漂移修正）。

## C. 修复后基线形态（baseline-4/5/6 三次全量重跑，10 题）

| 维度 | baseline-1（修复前） | baseline-4/5/6（修复后） |
|---|---|---|
| 第二轮 resume 409 | 8/10 | **0/30 轮**（三轮无一次 409） |
| 第 3 轮追问（红线候选 over2） | 常发 | **0/30** |
| 两轮澄清完整走通 | 无 | 30/30 会话全部完成两轮（除 C04/C09 无澄清） |
| 最终六段式内容（成就感） | 1/10 | 4~7/10（波动，见 D 归因） |

## D. Gate 3 归因修正（baseline-6 带 reason 码，主失败面=LLM 生成层）

| 失败码 | 归属组件 | 频次（baseline-6） | 归类 |
|---|---|---|---|
| `UNSUPPORTED_CITATION` | writer（引用不在绑定证据） | C01 | 主失败面：LLM 生成引用未对齐证据 → fail-safe |
| `EVIDENCE_COVERAGE_DEFICIENT` | verifier（检索证据覆盖不足） | C02/C03/C07 | 主失败面：检索层 |
| `PLANNER_PARSE_ERROR` | planner（JSON 结构化输出坏） | C05/C06/C10（重启后成功或降级 RAG） | 主失败面：LLM 结构化输出不稳定 |
| `ISSUE_DECOMPOSITION_INVALID` | service（问题分解 R11） | C04/C09 | 次失败面：分解失败 |
| `AGENT_BUDGET_EXCEEDED` | budgets（长链路预算） | C08 | 次失败面：预算边界 |

- **结论**：工程性拦截项（409 死锁、第三轮追问红线）已全部清零；剩余失败为 LLM 生成/检索质量层，
  与历史 010/011 结论一致（结构性差距，非工程修复可治）。按任务书 §Gate 5 前，先做失败重试观测
  与分轮多次运行统计（开发集 2× 独立运行、隐藏集 1×），以 9/10、4/5、红线 0 作为验收闸。
- 安全红线：全程 0 触发（无越界/伪造/泄密）。

## E. 未决观测点

- baseline-4（成功 7/10）与 baseline-6（成功 4/10）波动：同一代码同时段，差异在 LLM 生成质量分布，
  需在 Gate 5 双运行统计中量化「每轮成功率」而非单次成败。
- runner 单请求超时已 300→600s（C10 长链路首请求曾超时被误杀）。