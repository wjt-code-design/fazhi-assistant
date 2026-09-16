# grilling 对齐结论：C01 writer 瓶颈（2026-09-12）

形式：grilling（逐支追问、每题先给推荐再由用户定）。以下为**已达成共识**，作为下一步实现的依据。
可查的事实我自查了（未占用用户决策）。

## 先把事实摆出来（自查结论）

- `has_unsupported_numeric_token(text, bound)` = `numeric_tokens(text) ⊄ numeric_tokens(bound)`：
  claim 文本里**每个**数字都必须出现在**它自己绑定的**事实+证据文本里。
- writer 只在 `evidence_ids` 为空时**丢弃** claim；**其它所有校验都 `_fail` 整篇作废**
  （`writer.py:569` 注释：「仍失败才 fail-safe 拦截（**不弱化任何校验**）」）。
- 「出终稿」= verifier PASS → `persist_agent_final_once` → DB `status='completed'` + assistant 消息
  → runner 的 `agent_completed=True`。**不代表答案对**（引错法条也可能 PASS）。
- 「结局 = 终稿」的精确含义里**不含**法律正确性。
- `prompts.AGENT_WRITER_SYSTEM` **已经**写明：不得新增数字/金额/日期；只能引用同 Issue 的 Fact ID；
  证据不足应省略该 Claim。**规则已在，模型两次都没遵守。**
- writer payload 的 per-issue `facts` 取自 `issue.facts`（排除 INFERENCE）；跨争点引用事实会 `CROSS_ISSUE_FACT` 整篇作废。
- 仓库有 AST 哨兵（`tests/test_log_field_whitelist.py`）：任何 `extra={...}` 字段不登记白名单即失败。

## 五支决策（已定）

**第 1 支 交付目标与红线**
- 目标 = **A：工程链路出终稿**（`agent_completed=True` + DB 有 assistant 消息）。
- **法律质量本轮不做、不混算**：不得把"跑通"写成"质量达标"。
- 红线 = **writer 校验强度一律不动**，只允许改**上游 / 提示词契约**。

**第 2 支 writer 瓶颈处理策略**
- 先**补零成本埋点定位**根因，不直接改。
- 预置决策树（定位后照此执行，避免事后挑改法）：
  - **① 编造数字** → 改 `AGENT_WRITER_SYSTEM`，把笼统的"不得新增数字"改成**可机械执行**的表述
    （写数字前必须确认它出现在所引用的 `fact_id`/`evidence` 文本中，否则删数字或省略该 claim）。
  - **② 漏绑来源** → 在 writer payload 里给每条 fact/evidence **标注它包含哪些数字**，把"可用数字清单"摆到模型面前。
  - **③ 事实挂错争点** → **超出本轮范围**，只记录 + 交回用户决策（涉及 planner 输出契约/争点-事实绑定）。
  - 混合 → 按占比最大那档处理，其余记录。
- 每档实现前都要 **离线反例 + 重记候选**。

**第 3 支 可观测性边界**
- 新增字段只记**分桶计数 + issue_id**，**不记任何数值、不记 claim 文本、不记事实原文**：
  `in_own_claim_sources`（非 0 ⇒ 校验 bug）/ `in_own_issue_facts`（⇒②）/ `in_other_issues`（⇒③）/ `nowhere`（⇒①）。
- 只在数字校验真的触发时带出；主摘要每轮一条。

**第 4 支 验收口径**
- **连续 3 轮全部 `agent_completed=True`** 才算达成目标 A；中间任一失败则重计。

**第 5 支 节奏与止损**
- 节奏：**改一次 → 先跑 1 轮 → 出终稿才续跑到连续 3；失败先停下读埋点再决定**。
- 止损：① 连续 2 轮**同类**失败（同一 reason）即停；② 出现未知服务端状态即停（保留完整预约、不重跑）；
  ③ 2026-09-15 窗口到期即停，恢复 20 元累计纪律并重算累计。
- 串行、单进程、单宿主；轮次间复用宿主但**每轮新 run 名 + 新会话**；同批次共用隔离业务库。

## 下一步（待用户点头即可开工）

实现第 3 支的埋点（零成本）：在 `_render_once` 的数字校验分支上，把四个桶的计数与 `issue_id`
并入已有的 `agent_writer_summary`；先写测试看它红 → 再实现 → 定向 + 全量 + lint/format/mypy →
按第 5 支节奏跑 1 轮付费 C01（≈0.017 元）。
