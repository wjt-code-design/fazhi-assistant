# H3 真实模型 C01 验收报告（2026-09-12）

预登记：`preregistration-h3.md`。**本轮只跑 C01**，未扩到 C07/C10（预登记的停止规则）。
未部署、未 Git 提交、未推送。

## 结论（一句话）

**H1 修复在真实调用中生效：检索链路不再超时，Agent 首次推进到起草阶段。
新阻塞点换到了 verifier 的覆盖率闸门 —— 终态 `claims` 为空导致 `EVIDENCE_COVERAGE_DEFICIENT` → `VERIFIER:FAIL_SAFE`，无终稿。
按预登记停在此处诊断，不带病扩样本。**

## 前置核对（全部通过）

| 项 | 结果 |
|---|---|
| 3 个冻结哈希（cases / round-protocol / fact-ids） | 全部 MATCH |
| 18111 端口 / 遗留服务进程 | 空闲、无匹配实例 |
| 旧账本未决预约 | 4 reserved / 4 closed / **0 pending** |
| 新批次目录与库 | 新建，`cost-ledger.jsonl`、`evaluation.sqlite`、`quota.sqlite` 均不存在（拒绝覆盖） |
| 宿主改造 | `serve.py` / `budget_guard.py` / `test_budget_guard.py` 已快照为 `*.before-h3`；宿主参数化（见下） |

宿主参数化（默认值与历史完全一致，同一宿主可复用，不再每 run 复制脚本）：
`EVAL_EVIDENCE_DIR` / `EVAL_PORT` / `EVAL_GUARD_LIMIT` / `EVAL_LEDGER`。
**guard 上限设为 19.9932499 元**（= 20 − 上一轮累计 0.0067501），因为 guard 是进程内计数，
不显式扣减就等于把总授权翻倍。

宿主实际加载配置（`runtime-manifest.json` 的 EVALUATION_READY 行）：
`model=qwen3.8-flash, role=agent_text_q38f, rerank_enabled=true, rerank_model=BAAI/bge-reranker-v2-m3,
rerank_attempt_timeout_s=12.0, rerank_deadline_margin_s=0.3, gateway_retrieve_laws_timeout_s=15.0`
—— **H1 的三条常量在真实宿主中确认生效**。

## 运行结果

| 项 | 值 |
|---|---|
| run 名 | `quality-q38-c01-20260912-h3-01` |
| runner 退出码 | 0（只表示采集完成） |
| runner 汇总 | `rounds=3 clar_rounds=2 answered=1 unmatched=1 final_chars=0 agent_completed=False errors=['EVIDENCE_COVERAGE_DEFICIENT']` |
| Agent run_id | `013dd97e-ddc9-4c0d-94a7-49f95ea30983` |
| 数据库终态 | `status=failed`，`state_version=14`，`last_error_code=EVIDENCE_COVERAGE_DEFICIENT` |
| 终态计数器 | steps 13/16、tool_calls 3/10、replans 0/3、clarifications 2/2、verifier_research_returns **1/1** |
| assistant 消息 | 无（`messages` 仅有 1 条 user） |
| 墙钟 | 33.3s |

### 检索链路：已修好（这是本轮的正面结论）

| 步 | 事件 | 结果 |
|---|---|---|
| v2→v3 | `retrieve_laws`（issue_1928…） | **TOOL_SUCCEEDED，1304 ms** |
| v6→v7 | `retrieve_laws`（issue_33bf…） | **TOOL_SUCCEEDED，1464 ms** |
| v10→v11 | `retrieve_laws`（issue_afa0…） | **TOOL_SUCCEEDED，942 ms** |

三次全部成功、均远低于 15s 外层上限；**全程没有 TOOL_TIMEOUT**。对比第一轮（卡在第 2 步 8006ms 超时），
检索已不再是阻塞点。

## 新阻塞点：根因分析

### ⚠️ 更正（2026-09-12 后续核查）

**初版报告写的「终态 `state.claims == []`」是错的**：`LegalAgentState` 顶层**根本没有 `claims` 键**
（顶层键为 action_fingerprints / budgets / claim_checks / clarifications / conflicts /
duplicate_attempts_by_issue / evidence / issues / observations / replans / status / steps /
terminal_decision / tool_calls / verifier_research_returns）。当时的查询 `s.get('claims')` 返回 None，
被误读成「为空」。**草稿与 claim 均未持久化，因此单靠归档无法判定 claim 是有还是没有。**

### 已证实

1. 终态 `state.claim_checks == []`，且 state 中无 `claims`/`draft` 键 —— 草稿未持久化。
2. 覆盖率闸门 `backend/agent/verifier.py:289` 的判据是
   `if not issue_claims or not has_effective_statute: deficient = True`
   （两种情形都会 deficient：该争点没有 claim，或有 claim 但无「生效成文法」绑定）。
3. `verifier.py:298-304`：deficient 时若 `verifier_research_returns < max_verifier_research_returns`
   走 `RESEARCH_MORE`，否则 `FAIL_SAFE`。本轮 `1 < 1` 为假 → **FAIL_SAFE**。
4. `state.conflicts` 为空，所以冲突分支没有触发；12 条 evidence 全是 `statute` + `effective`，
   所以「无有效成文法」也不是触发原因 —— **触发项就是 claim 为空**。
5. 步骤序列：v12 `conditional_analysis / CLARIFY_BUDGET_EXHAUSTED`（2 次澄清用尽后条件化起草）
   → v13 `coverage_rewrite_attempt / EVIDENCE_COVERAGE_DEFICIENT / ATTEMPT_RESERVED`
   → v14 `failure / EVIDENCE_COVERAGE_DEFICIENT / VERIFIER:FAIL_SAFE`。

### 未证实（不得当成结论）

- **claim 为什么为空**：正文草稿未持久化到数据库，DB 只留步骤元数据，因此无法区分
  「writer 产出了候选 claim 但抽取/绑定失败」与「writer 在条件化路径下根本没产出 claim」。
  已证实的是终态为空，机制未建立。
- 「澄清额度耗尽 + 条件化起草」这条路径是否是诱因：与数据一致，但未隔离验证。
- **检索质量差是否与本次失败有关**：已证实检索内容偏（见下），但闸门在 claim 为空时
  无论证据相关与否都会判 deficient，所以**检索质量不是本次失败的已证成因**，是并列的独立质量问题。

### 并列发现（本轮观察到，未处理）

- **检索内容偏**（12 条全部 statute+effective，但匹配度低）：
  - issue_1928（绩效不合格事实是否成立）→ 公司法清算、公司法决议不成立、仲裁法仲裁协议独立、公司法吊销营业执照（**全部无关**）
  - issue_33bf（未经培训/调岗是否合法）→ 劳动法第二十五条、第九十八条、**民法典租赁合同第七百三十一条**、劳动法第九十九条
  - issue_afa0（能否要求赔偿金）→ **劳动合同法第八十七条** ✓、劳动法第九十一条、第八十五条、第十六条
  - 冻结案例要求：《劳动合同法》40 / 43 / 47 / 87 —— **只有 87 命中，40、43、47 全部缺失**。
- **澄清协议未对上**：Agent 问了 2 个问题（连续两次绩效不合格的事实与证据 / 考核制度是否经民主程序并公示），
  协议对第 1 个问题判 `no_rule_match`（`unmatched_questions`），`answered_fact_ids` 只有 `C01-r1-f1`；
  冻结的 round2 事实「公司没有培训或调岗」从未被索问，而「未询问培训/调岗」恰是案例列出的关键失败项。

## 费用

| 调用 | 模型 | 输入/输出 tokens | 估算人民币 |
|---|---|---|---|
| 1 | qwen3.8-flash | 792 / 393 | 0.0016947 |
| 2–4 | BAAI/bge-reranker-v2-m3 ×3 | 未提供 usage | 0（官方免费型号） |
| 5 | qwen3.8-flash | 3355 / 647 | 0.0044309 |
| 6 | qwen3.8-flash | 3801 / 565 | 0.0045663 |
| **本轮合计** | | | **0.0106919** |

- 外呼 6 次，全部 HTTP 200，**无未知服务端状态**。
- 跨轮累计：0.0067501 + 0.0106919 = **0.0174420 元**；剩余授权参考 **19.9825580 元**。
- 按未折扣价与官方免费 rerank 估算，**不等于供应商账单**。

## 关闭状态

`shutdown-check.json`：serve.py PID 12812 已终止；18111 无监听；6/6 预约闭合、0 pending。
runner 已结束、无活动请求，故未触发「未知状态保留预约」规则。

## 建议的下一步（不建议直接跑 C07/C10）

优先级从高到低：

1. **定位 claim 为空**（本次失败的已证触发项）。先读 `writer.py` 的 claim 产出/回喂与
   `verifier.py` 的 claim 抽取，用已有的 `test_agent_chat_integration.py::test_coverage_rewrite_*`
   夹具做离线反例；重点怀疑 `CLARIFY_BUDGET_EXHAUSTED → conditional_analysis` 这条少走的分支。
2. **单独评估检索质量**（并列问题）：为何 issue_1928 的查询召回公司法/仲裁法内容、
   为何《劳动合同法》40/43/47 召不回。这是独立于本轮失败的另一个问题，先别和 1 混在一起改。
3. 1、2 各自离线验收通过并重新记录候选后，再为新批次申请付费验证。

本轮按预登记停止：不修改生产代码、不自动重跑、不扩大样本、不增加预算。
