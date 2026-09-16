# 付费运行预登记：max_steps 16→20 验证（2026-09-12，第 1/最多 3 轮）

依据：`alignment-20260912-step-budget.md`（grilling 对齐）+ `step-budget-measurement.md`（测算）。
用户 2026-09-12 批准 `AGENT_MAX_STEPS` 16→20。**目标 = 工程链路出终稿**（`agent_completed=True`）；
**不是**法律质量验收，**不**声称答案法律正确。

## 候选（离线已验收）

相对上一候选的新增改动：
- `backend/.env` `AGENT_MAX_STEPS=16→20`（含注释，记录批准依据）
- `backend/settings.py` 默认值 16→20（含注释）
- `backend/tests/test_agent_gate.py` 预算断言 16→20 + 注释记录两次批准历史
- `backend/tests/test_agent_chat_integration.py` 新增
  `test_five_issue_decomposition_reaches_drafting_within_step_budget`
  （**watch-it-fail 已做**：16 下复现 `budget_exceeded:step_preflight`，与真实付费运行一致；20 下通过）
- `docs/final-agent-handoff-20260912.md` 第 11 节：登记本次配置变更并修订"硬上限"条款的适用范围

离线：全量 **949 passed / 0 failed / 覆盖率 78.50%**；ruff/format/mypy 全 0。
同时携带：H1 检索超时修复、覆盖率归因诊断（`agent_coverage_issues`）、writer 归因诊断（`agent_writer_summary`）、
数字违规分桶（`numeric_violation`）。

## 口径

用户 2026-09-12 临时指令：9.15 前放开跑 qwen3.8-flash → `EVAL_GUARD_LIMIT=20`（每进程兜底，不按累计扣减）。
仍保留独立目录/账本/隔离库、唯一 run 名、未知服务端状态不重跑、不扩样本、不改冻结 judge。

## 节奏（对齐第 5 支）

- 本轮 = 改一次后的**第 1 轮**；宿主应打印 `max_steps: 20`（配置生效的硬证据）。
- **出终稿（agent_completed=True）→ 续跑到连续 3 轮全绿**；失败 → 停下读埋点，**连续 2 轮同类失败即停**。

## 判定标准

- 优先读 runner 汇总的 `agent_completed` / `final_chars` / `errors`；
- `writer_render_summary` 若出现，用 `numeric_violation` 分桶判断是否仍卡数字校验；
- `coverage_gate_terminal_failure` 若出现，说明到了 verifier 且覆盖率不足。
- **本轮通过 = `agent_completed=True`**；法律质量不在本轮判定范围。
