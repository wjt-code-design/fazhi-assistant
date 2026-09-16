# T2 红测试证据（修复前基线采集）

日期：2026-09-09。

## 采集说明（诚实标注）

红测试运行时 `service.py` 为 W1–W4 基线（`_coverage_research_loop` 原地自增、不落盘版本），
`test_agent_chat_integration.py` 已含 T2 新增测试。控制台输出经 `| tail` 管道截取展示，
pytest 原始退出码未直接捕获（pytest 报告 1 failed ⇒ 退出码为 1）。以下为实际捕获的原文。

## 中间失败（fixture 未构造到目标路径，按教学手册先修 fixture）

第一轮红测试死于 `ISSUE_DECOMPOSITION_INVALID`——根因：`build_initial_agent_state`
要求 issue fact quote 必须是用户请求原文逐字片段，共享 `_bootstrap` 的固定 query
"公司拖欠工资，应当如何主张权利？"不含"借款"片段。修复：新增
`_two_issue_bootstrap`，raw_query 同时包含两个争点的事实片段。

## 正式红（目标路径命中）

命令：

```bash
cd backend && export LLM_API_KEY=audit-offline LLM_BASE_URL=http://127.0.0.1:9/v1 \
  EMBEDDING_PROVIDER=local RERANK_ENABLED=false EMBEDDING_QUOTA_TOTAL=0 \
  RERANK_QUOTA_TOTAL=0 DATABASE_URL=sqlite:///:memory: \
  && ./venv/Scripts/python.exe -m pytest \
  tests/test_agent_chat_integration.py::test_coverage_rewrite_attempt_is_persisted_before_recall_and_completes \
  -q --tb=long
```

实际输出（截取）：

```text
>       assert result.outcome == "completed", f"unexpected failure: {result.reason_code}"
E       AssertionError: unexpected failure: AGENT_FINALIZATION_CONFLICT
E       assert 'failed' == 'completed'
E         - completed
E         + failed

tests\test_agent_chat_integration.py:890: AssertionError
=========================== short test summary info ===========================
FAILED tests/test_agent_chat_integration.py::test_coverage_rewrite_attempt_is_persisted_before_recall_and_completes
1 failed, 1 warning in 19.42s
```

## 结论

失败原因正是 `AGENT_FINALIZATION_CONFLICT`：回喂计数仅在内存自增（数据库计数仍 0），
终稿保存被 `persist_agent_final_once` 的 durable equality guard 正确拒绝。
与隔离复现（docs/agent-audit-state-repro-20260909.md，AST 提取 + 替身依赖）结论一致；
本红为真实 service → repository → final storage 全链路集成复现。
