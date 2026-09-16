# 工作进度文档（2026-09-12 · session 3）

> **自包含声明**：本文档不依赖任何对话记忆，读完即可理解当前状态并接手。
> 项目根：`C:\Users\33393\Desktop\ai-legal-helper`。任务书见 `docs/final-agent-handoff-20260912-session3.md`（已跟踪）。
> 前置：`docs/work-progress-20260912-session2.md`（session 2：T1a/T1b/T4{r1,r2}）。

---

## 1. 项目是什么（30 秒背景）

**法智 Agent**：法律问答 Agent，主链路 `争点分解 → 检索法条 → 澄清用户 → 逐争点起草 → verifier 校验 → 终稿`。
- 争点数 N 由模型决定，上限 8；单次运行最多处理 5 个（产品约束，多选需用户确定）。
- `max_steps=20`、`max_tool_calls=10`；付费模型 **qwen3.8-flash（DashScope）**。
- 纪律红线：不改冻结 judge/案例；每轮付费独立目录+账本+隔离库；连续 2 轮同类 writer 失败即停。

## 2. 本 session 任务（来自交接文档 Ticket 0–4）

session 2 结束时唯一卡点 = writer 多争点一次渲染的生成遵守度（跨争点引用/非规范引用）。
本 session 按已确认的最小方案落地：**每个争点独立、单次、串行起草**；6–8 争点先让用户选择 ≤5。

## 3. 已做了什么（均完成；代码提交 `e93df61`，文档 `01d9b1b`）

| # | Ticket | 内容 | 结果与证据 |
|---|---|---|---|
| 0 | T1b 局部修复接收 | 批内早退保全 observation/AgentEvidence 与真实失败码 | 3 项参数化 SQLite 测试复现通过（`ticket0-accept-20260912/`） |
| 1 | **争点范围选择** | `pending_scope_issue_ids` 有界字段；6–8 争点→WAITING_USER 持久化编号清单（`ISSUE_SCOPE_SELECTION_REQUIRED`）；resume 纯确定性解析（1–5 唯一编号、原顺序裁剪、不写 Fact、不耗澄清预算） | 14+1 passed；全量 **967 passed / 78.63%**（`ticket1-evidence-20260912/`） |
| 2 | **逐争点串行 writer** | `render`/`render_issue`/`merge_draft_answers`；单争点 payload；失败即停；零 claim→`ISSUE_CLAIMS_MISSING`；删除错误回喂重试与 service `_coverage_research_loop`（首次 verifier 非 PASS 即终态失败） | writer 41 passed；全量 **960 passed / 78.54%**（`ticket2-evidence-20260912/`） |
| 3 | 离线集成验收 | 新证据目录四 phase：targeted 27 / 静态三项 0 / smoke 24/24 / **960 passed**，候选 SHA-256 固化 | `ticket3-acceptance-20260912/` |
| 4 | **T4 真实模型验证** | C01 两轮（隔离库/账本/run 名/端口 18121/18122）：r1 `UNKNOWN_MISSING_INFORMATION`、r2 `ISSUE_CLAIMS_MISSING` → 双轮同类 writer 遵守度失败，**按止损即停** | 费用 0.0186 元；`t4-serial-writer-20260912*/` |
| 5 | 对抗审查与修复 | 对 `e93df61` 五维度对抗审查 → 无 P1；修复 P2-1（scope 防御边界）/P2-2（writer 死链）/P3（单一来源+死函数+注释）/fx4（resume 409），提交 `28c197e` | **959 passed / 78.56%**；`review-20260913/` |

## 4. 关键成果（有证据）

1. **session 2 选型 2 已落地并实证生效**：逐争点串行 writer 真实运行单争点 payload = **1639/1402 tok**（旧 6 争点全量 5514）；串行失败即停符合设计（r1 恰 2 次 writer、r2 恰 1 次）；DB 实测两轮均 4 争点、未触发 scope（≤5）。
2. **历史失败面 `CROSS_ISSUE_EVIDENCE`/`NON_CANONICAL_CITATION` 消失**（单争点结构确定性排除跨争点引用）。
3. 质量门禁：Ticket 3 验收 **960 passed / 78.54% / ruff·format·mypy 0 / smoke 24/24**；候选与付费运行服务加载 hash 逐字节一致。
4. 全程费用累计 ≈0.136 元（session3 T4 0.0186 元），20 元授权窗口内。

## 5. 遇到的问题

### 5.1 已解决
- 范围选择触发时未写 `pending_scope_issue_ids` 到 state（只写了 checkpoint）→ 补 state 写入；
- 单争点 payload 化后跨争点 Fact 全集判断仍引用 payload → 改基于 state（`derive_fact_id` 全集）；
- T1b 既有 8 争点测试与新约束冲突 → 适配为先选 5 再批量检索（已注明）。

### 5.2 未解决（结构性，卡点仍在 writer 生成遵守度）
- T4 双轮：r1 `UNKNOWN_MISSING_INFORMATION`（missing_information 未逐字命中 unknown_facts）、
  r2 `ISSUE_CLAIMS_MISSING`（某争点零被接受 claim，本候选新增显式失败码按设计触发）。
- 定性：上下文缩小解决了**跨争点引用**，但模型对"逐字约束/至少一条绑定生效成文法 claim"的遵守度
  仍不稳定（结构性问题，历史多轮同族）。确定性边界保证 fail-closed、无伪终稿。
- git 对象库损坏（预存，非本次引入）：`03a2f14` 缺失、geometric repack 失败；新提交不受影响；**push 前须修**。

## 6. 当前状态

- 交接文档 Ticket 0–4 **全部完成**；代码已提交 `e93df61`（9 文件），交接文档 `01d9b1b`。
- 范围选择机制就绪但真实 C01 未触发（≤5 争点；离线 6–8 争点测试已覆盖）。
- **结构性决策已拍板：接受现状**（诊断结论与理由见第 7 节；决策记录在
  `dispatch-output/t4-serial-writer-20260912/conclusion-report.md`"决策"节）。

## 6.5 对抗审查与修复（2026-09-13）

对 `e93df61` 做对抗性审查（五维度：正确性/死代码/行数/安全/一致性），报告与证据在
`dispatch-output/review-20260913/`。结果：无 P1；2 项 P2 + 4 项 P3。经 grilling 对齐后
修复批次已提交 **`28c197e`**（9 文件 +47/−71）：

- **P2-1**：scope 触发改正向（多于 5 个即选择），去掉 `MAX_ISSUES` 上界——防 9+ 争点静默跳过范围选择；
- **P2-2**：清理 writer `feedback` 死链（`_render_once`/`has_feedback`/协议/`runtime.generate` 分支；
  **planner feedback 保留**，仍活）；
- **P3**：`MAX_ISSUES` 统一单一来源；删除无生产调用的 `register_verifier_research_return` 及单测；
  清理注释残留；
- **fx4**：resume 空输入改抛 `ResumeRunConflict`（409）而非 ValueError→500，新增测试断言状态不变。

门禁：**959 passed / 覆盖率 78.56% / ruff·format·mypy 0 / smoke 24/24**。

## 6.6 深度审查与冻结决策（2026-09-13，文档记录未提交）

对 `backend/agent/` 全模块（12 文件）做六维深度审查（质量/逻辑/可优化/矛盾/死代码/耦合），
报告与证据在 `dispatch-output/review-deep-20260913/`。结论：无 P1。
- 非冻结项自动修复已提交 **`707785a`**（5 文件 +11/−16）：删死函数 `has_unsupported_numeric_token`；
  提示词 `"1 到 8 个"` 改插值 `MAX_ISSUES`；过时注释/文档修正；service 类型收紧。门禁
  **959 passed / 78.57% / 静态 0 / smoke 24/24**。
- **冻结项决策（用户确认，零代码改动，仅记录）**：
  - **R1**：verifier `RESEARCH_MORE if 0 < max else FAIL_SAFE` 预算分支生产不可达（唯一增量器
    `register_verifier_research_return` 已删）→ 判定**保留**。理由：公开行为与 FAIL_SAFE 完全一致
    （service 均按非 PASS 终态失败）；verifier 为冻结发布门禁组件，解冻治理成本 > 清理收益；
    字段参与冻结 `_state_digest` 契约且具前向兼容性；连注释都不加（冻结文件零触碰）。
  - **R8**：`draft_digest` 生产不用（测试专用）→ 判定**保留**（冻结文件公开助手，无害）。
  - 连带字段（`verifier_research_returns`/`max_verifier_research_returns`/settings 项）一并保留，
    避免 verifier/settings 不一致。

## 7. 结构性决策（2026-09-12 已按推荐执行：接受现状）

**决策：接受现状**（fail-closed 保证无伪终稿）。依据（T4 结论报告"诊断闭环"节，证据链完整）：
- r1 失败争点 `proposed=0`（模型空 claims）；r2 失败争点 `proposed=1/dropped=1`（产出 claim 但
  evidence_ids 空），且该争点 state 实测有 4 条 succeeded 可绑证据 → **纯模型失语，非校验误杀、
  非证据缺失、非检索问题**；
- 工程边界修复（如 missing_information 归一化）对 r1 无恢复力（仍会因 0 claim 触发
  ISSUE_CLAIMS_MISSING）→ 不值得触碰 fail-fast/逐字约束语义；
- 不追加提示词重试（违反已确认决策"每争点一次有效生成"）；
- **排除换模型**：项目 2026-09-08 已做 qwen 换档实验——"失败分布迁移、与模型强弱关系不大"
  （`runtime.py` 注释，`docs/gate5-formal-dev-20260908.md` 附 C）；且 qwen3.7-plus/max 价格为
  0.8/2.7 的 5–15 倍、换模型需改 .env/宿主 assert/预算预约额，成本与改造无对应收益预期。
- 实质改善路径已穷尽评估（校验放宽无效 → 重构已做 → 换模型证伪），**接受现状为最终决策**。

## 8. 接手者快速上手

- 全量回归：`cd backend && ./venv/Scripts/python.exe -m pytest -m 'not slow' --cov=. --cov-fail-under=70 -q --basetemp="<新目录>/full-1"`（960 expected）
- 范围选择定向：`pytest tests/test_agent_controller.py -k scope`；writer 定向：`tests/test_agent_writer.py -k 'serial or merge_draft or render_issue or five_issues or dropped_for_zero'`
- 关键实现：`controller.py:_maybe_scope_selection / _parse_scope_selection / _resume_with_scope_selection`；
  `writer.py:render / render_issue / merge_draft_answers / ISSUE_CLAIMS_MISSING`；`service.py` drafting 串行段
- 付费运行宿主：`dispatch-output/agent-quality-20260911/serve.py`（env：EVAL_EVIDENCE_DIR/EVAL_PORT/EVAL_GUARD_LIMIT）
- 本 session 证据目录：`dispatch-output/ticket0-accept-20260912`、`ticket1-evidence-20260912`、`ticket2-evidence-20260912`、
  `ticket3-acceptance-20260912`、`t4-serial-writer-20260912*`（T4 r1/r2）