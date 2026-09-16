# 前端 Agent 体验适配设计（B 方向）— 2026-09-13

## 1. 目标与范围

后端 Agent 主链路已交付（争点范围选择 Ticket 1、逐争点澄清/失败 Ticket 2、fail-closed 失败），
但前端仍以"普通气泡追问"展示澄清/失败，零适配。本设计为**纯前端适配**（B 方向，全 4 子项）。

- **B1** 争点范围选择 UI（解析候选 → 点击多选 → 填入输入框）
- **B2** 澄清消息差异化（标签 / 序号 / 样式）
- **B3** 失败态结构化（reason_code → 人类可读文案）
- **B4** 澄清进度可视化（基础版）

**范围红线**：不改后端契约、不改 frozen release-evidence、不加前端依赖/测试基建、
不引入第二种发送路径（坚持"所有回复经输入框发送"）。

## 2. 现状与数据契约（已核实）

- 后端澄清 SSE 事件：`type=clarification`，字段 `prompt`（文本）、`run_id`、`state_version`、
  `conversation_id`；`api.ts` 现仅把 `prompt` 当普通 chunk 追加，记录 `pendingAgentRun`。
- **范围选择 prompt 格式**（controller.py 硬编码，稳定）：
  `"本次请求分解出 N 个法律争点，超过单次可处理上限 5 个。请从中选择最多 5 个争点（输入编号，用逗号分隔，例如：1,3,5）：\n1. 争点甲\n2. 争点乙\n…"`
- resume 接受：`最终答案` = 1–5 个唯一 ASCII 编号，`[\s,，、;；/]+` 分隔（后端确定性解析）。
- 失败事件：Agent error 事件 `{type:"error", code, message}`——**已核对后端契约带 `
  code`（reason_code）**（chat_integration.py，2026-09-13 审查修正原假设：并非"SSE 未带结构
  字段"）。B3 直接透传 code 做映射，**零后端改动**。

## 3. B1 争点范围选择 UI

### 3.1 解析（前端，含降级）
- 澄清消息若命中**范围选择特征**（`prompt` 以"本次请求分解出"开头 且 含 `\n1. ` ）→ 走卡片路径。
- 解析器 `parseScopeCandidates(prompt)`：提取 `N. 文本` 行（编号 1..N 单调递增）为
  `{number, text}[]`；解析失败 → **降级为现有纯文本追问**（行为不变，无卡片）。
- 纯函数模块级，供渲染与测试引用。

### 3.2 交互（方案 A：填输入框，不新增发送路径）
- 在澄清消息气泡内联渲染候选卡片网格（每张：编号徽标 + 争点文本）；点击**切换选中**，
  选中态高亮 + 顶部"已选 N/最多 5 个"即时计数（达 5 后再点未选项给出 toast/禁用抖动提示）。
- 点选即时把选中编号按升序拼成 `"1,3,5"` **填入输入框**（覆盖原输入框内容，可手改）；
  用户点发送即回给后端。撤销卡片 → 输入框同步重拼。
- 与输入框是**同一数据流**：卡片只是"帮填"，发送仍经 `doSend`，streaming 期间禁点。

### 3.3 视觉（主题色内）
- 卡片：`glass-card` 底 + `border-mist`，hover `border-sea`；选中：`bg-sea/10 border-sea` +
  `shadow-card`；编号徽标 `bg-sea text-white`（未选）→ `bg-ink`（已选）；计数行 `text-slate` + `accent-deep` 强调。

## 4. B2 澄清消息差异化

- `Msg` 增加 `agentNote?: { kind: "clarification"; index: number; total: number }`；
  渲染澄清气泡：左侧小标签 **"Agent 澄清"**（`text-sea` 描边徽章）+ 右上角小字
  **"第 {index}/{total} 次澄清"**（`text-slate`）；气泡 `border-sea/40`（区别于普通回答）。
- 澄清 bubble 顶部小字提示："请针对上面的问题补充事实，完成后发送；提交后继续"。
- 普通回答（final 前 content 流式 / 非澄清）保持现状；`final`/`error` 后下一轮不为澄清。

## 5. B3 失败态结构化

- **错误事件带 `code`（reason_code）→ 前端映射为可读文案**（零后端改动，审查修正）：
  每条失败族映射一小段"原因提示"：
  | reason_code（前端 key 匹配） | 提示文案 |
  |---|---|
  | `ISSUE_CLAIMS_MISSING` | 模型未能生成可引用的法律依据，请换一种问法或简化问题 |
  | `UNKNOWN_MISSING_INFORMATION` / `MISSING_FACT` | 信息不足，建议补充时间/金额/主体等关键事实后重发 |
  | `UNSUPPORTED_CITATION` / `NON_CANONICAL_CITATION` | 未能从法律库引用到准确条文，建议换个表述重问 |
  | 其他 | 服务暂时未能完成本次分析（Agent 未能安全完成） |
- 展示：错误气泡 `border-error/40` + `text-ink` + 左上 `error` 小徽标"未能完成"；气泡内两行
  （主文案 + 原因提示 `text-slate`）；失败时**不清空** pendingAgentRun？→ **否决**：失败=本轮结束，
  保持现有行为（清空 pending，用户重新提问开新 run）。
- 不做"重新发送"按钮（防重复发送误操作）。

## 6. B4 澄清进度（基础版）

- 复用现有 step 胶囊区/流式三态：新增顶部细进度条仅当 `agentNote` 存在：
  `澄清 1/2`（`bg-sea/20` 底 + `bg-sea` 填充，宽 = index/total）；无额外控制元素。

## 7. 文件改动清单（全部前端）

- `frontend/lib/annotate.ts`（或新建 `frontend/lib/scope.ts`）：`parseScopeCandidates`、`buildScopeAnswer`
  （编号列表→输入框文本）、`ScopeCandidate` 类型。→ **选择新建 `frontend/lib/scope.ts`**（纯函数隔离，便于审阅）。
- `frontend/app/chat/page.tsx`：
  - `Msg` 扩展 `agentNote`；
  - clarification 处理：判断范围选择 → 解析 → 存候选；否则标 `agentNote`；
  - 渲染分支：候选卡片 / 澄清气泡 / 错误气泡 / 进度条；
  - `doSend`/`send`/`newChat`/`selectConv` 重置 `agentNote` 与候选状态。
- `frontend/app/globals.css`：新增少量样式（候选卡/进度条/澄清气泡描边，全用主题变量）。
- 无后端改动、无 package.json 变更。

## 8. 逻辑与异常处理

- 流式期间（streaming）候选卡片禁用；新会话/切换会话清空候选。
- 解析失败 → 降级纯文本（不渲染卡片，不清 pendingAgentRun）。
- 选满 5 个后多点 → 轻提示（输入框 placeholder 抖动或 text 提示），不阻断已选。
- 输入框被卡片重写前：若用户已手输内容 → **覆盖**（语义 = 用户此刻仍可撤回重填）；
  在卡片区加"清空选择"链接（重置输入框为该轮澄清前的空态）。
- 深度链接/刷新：候选状态仅内存，刷新后回落为普通消息（可接受，因会话恢复走 `convApi.detail`）。

## 9. 验收标准

1. `tsc --noEmit` 零错误；`npm run build`（next build）通过。
2. 代码自查回顾：范围选择解析/降级两路径、澄清标签不误伤普通回答（普通 content 仍走原渲染）、
   streaming 禁用、重置路径（新会话/切换）无残留。
3. 视觉符合主题色（sea/accent/ink/mist）——不引入新色板。
4. 后端契约未动（git diff 不含 backend/）、frozen 未动、无新依赖。

## 10. 不做（明确排除）

- 改后端 / 增加 reason_code 透传（留未来，需后端 batch 决策）
- 单测基建 / 端到端付费测试（验收仅类型+构建+审查，用户已确认）
- "确认提交"自动发送按钮（另一发送路径，已否）
- Agent 分析进度（非澄清）的深入可视化（现有 step 胶囊/流式三态已覆盖）