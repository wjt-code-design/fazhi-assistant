# 评测器纠偏任务执行结果报告（2026-09-08）

> 任务书：`docs/evaluation-harness-correction-taskbook-20260908.md`
> 执行者：主会话助手（实施侧）｜ 验收：独立审核助手 / Owner
> 基线：git HEAD `d1215ac`（任务启动时工作树状态已记录，见 §7）
> 性质：验收基础设施纠偏，**不代表 Agent Gate 5 或第一阶段完成**（见 §9）。

## 1. 修改文件清单（相对 `<repo>`）

| 文件 | 类型 | 改动 |
|---|---|---|
| `backend/scripts/harness_fact_reveal.py` | **新增** | 单一事实投放入口（§4.1）：轮次隔离、去重、schema、未命中记录、协议违例 |
| `backend/scripts/gate2_runner.py` | 修改 | `_match_facts` 委托共享模块；新增 `_match_facts_tracked`；主循环轮次感知投放 + 已答去重；结果 schema 分列 `unmatched_questions`，`unknown_fact_ids` 置 deprecated |
| `dispatch-output/task1/hidden_runner.py` | 修改 | 同 gate2_runner 改造，接入同一共享模块 |
| `backend/scripts/gate5_judge.py` | 修改 | 删除手写 `REQUIRED_STATUTES`；两评分层（mechanical/full_case_verdict）；安全分层（NOT_PROVEN）；单一真源读 frozen-cases `required_laws` |
| `backend/tests/test_harness_fact_reveal.py` | **新增** | T1/T2/T3/T8 |
| `backend/tests/test_gate5_judge_layers.py` | **新增** | T4/T5/T6/T7 |
| `docs/task-execution-report-20260908.md` | 追加 | 仅末尾追加「独立复验更正」（§7.1），未改写原文 |
| 本文件 | **新增** | 任务执行结果报告（§7.2） |

未修改：`backend/agent/**`、`backend/main.py`、`backend/prompts.py`、全部 frozen/rubric/fact-ids、
hidden-cases/commitment/salt、run-a/b 及全部历史 sessions。

## 2. 问题 → 修复 对照

| 问题 | 修复 | 验证 |
|---|---|---|
| P0-1 事实投放无轮次隔离 | 共享模块 `match_revealable_facts` 只投放 `round <= current_round` | T1 red（旧实现实测返回 `C05-r2-f1/f3`）→ green |
| P0-2 事实重复投放 | 排除 `answered_fact_ids`（一个事实最多投放一次） | T2 red（接口缺失）→ green |
| P0-3 记录 schema 名实不符 | `unknown_fact_ids` deprecated（不再混存对象）；新增 `unmatched_questions:{round,prompt,reason}`、`manual_review_required`、`protocol_violations` | T3 red → green |
| P0-4 机械分误作完整闭环分 | 两层评分分离；`passed` 不再存在，改用 `mechanical_pass_count` / `full_closure_pass_count`；必需要（单一真源）与证据绑定纳入 complete | T4/T5/T7 red → green；run-6 重判 1 mechanical / 0 full |
| P0-5 安全结论超出扫描能力 | 安全分层：`scanner_detected_redline_count`、`scanner_coverage`、`unexercised_redline_scenarios`、`formal_redline_verdict=NOT_PROVEN`（未演练场景存在时） | T6 red → green；run-6 全部题 NOT_PROVEN |
| P1-1 隐藏集失去正式隐藏属性 | 不改题不改历史（hash 复算一致）；文档声明降级为公开回归集 | 更正文档 §6 |
| P1-2 法条口径不一致 | 统一口径：lawcheck 当前 27 行唯一 ID、全 found；报告不再使用 26/26、30/30 | 更正文档 §5 |

## 3. red / green 测试证据

命令、退出码与摘要（原始输出存档）：

- **red（旧实现）**：
  `venv\Scripts\python.exe -m pytest test_harness_fact_reveal.py test_gate5_judge_layers.py -q`
  → exit 1：`5 failed, 3 errors`（保存于 `dispatch-output/harness-red-green/red-phase.log`）。
  失败归因：T1 第一轮泄露第二轮事实（`C05-r2-f1`、`C05-r2-f3`）；T4-T7 旧 judge 无 `required_laws` 参数/双层输出；T2/T3/T8 共享模块缺失。
- **green（新实现）**：
  同一命令 → exit 0：`8 passed`（保存于 `dispatch-output/harness-red-green/green-phase.log`）。
- **回归**：原有 5 个 agent 测试文件 → `129 passed`（与本任务前基线一致，无回归）。

## 4. 未运行项目及原因

- 未调用 LongCat / qwen / 任何在线模型或付费 API（任务书 §2.2 禁止；全部判定为离线确定性计算）。
- 未发起任何新的 Gate5/隐藏集正式运行（任务书明确：本任务不代表验收，正式验收待后续实施助手修复 Agent 后另行执行）。
- 推理/结构层（R1/R4/R6内容/R7/R9实质/R10/R11）为 `REVIEW_PENDING` 人工判定项——新 judge 以"未验证不得通过"保守处理，未伪造人工结论。

## 5. 历史结果重新判读（离线，无模型）

| 指标 | 原报告（旧 judge） | 重判（新 judge） |
|---|---|---|
| run-6 mechanical | 1/10（C05） | 1/10（C05）——机械口径不变 |
| run-6 full_closure | 未区分 | **0/10**（C05 缺《民法典》577、无证据绑定、多余引用待复核） |
| 安全红线 | "0" | **NOT_PROVEN**（全部场景未演练） |
| 数据有效性 | 视为正式 | 开发集与隐藏集均受投放协议缺陷影响，**不作为正式通过证据** |

命令（可复算）：
`venv\Scripts\python.exe scripts\gate5_judge.py ..\release-evidence\legal-agent-v1-complex-v1-20260907\gate2-run-gate5-dev-run-6-sessions.json`

## 6. `git diff --check` 结果

`git diff --check` → exit 0（无空白错误；仅有 CRLF 规范化 warning，非错误）。

## 7. 基线快照与完整性

- 启动基线：HEAD=`d1215ac`；工作树除既有历史 M（prompts/retrieval/tests 等，本任务范围外）外，本任务仅改动/新增上述允许范围文件。
- 禁改文件 hash 复核（任务前后一致，DoD #11）：frozen-cases `be281ab2…`、frozen-round-protocol `89d8d916…`、rubric `790fa407…`、frozen-fact-ids `262456b6…`、hidden-cases `d1f0b1f0…`、hidden-round-protocol `e4de149b…`、hidden-commitment `1ae1488c…`、salt `51157d68…`、run-a `097d5324…`、run-b `72a13d07…`。

## 8. DoD 15/16 达成情况

| DoD | 达成 |
|---|---|
| T1-T8 均有正确原因 red + green | ✅（§3） |
| 第一轮不得第二轮专属事实 | ✅（共享模块 round <= current_round；T1） |
| 已答事实不重复投放 | ✅（answered 去重；T2） |
| `*_ids` 只存 ID，未命中用独立字段 | ✅（T3；`unknown_fact_ids` deprecated） |
| 两 runner 同一投放语义 | ✅（单一模块；T8） |
| 机械分与完整闭环分分离，无歧义 `passed` | ✅（§4.3；T4/T5/T7） |
| 缺必需依据 → full 必败 | ✅（T4；C05 实证） |
| 未绑定证据的实质结论 → full 必败 | ✅（T5；`unbound` 机制） |
| 未演练安全场景 → 仅 NOT_PROVEN | ✅（T6） |
| 必需依据来自冻结单一真源 | ✅（judge 读 frozen-cases `required_laws`，删除手写表） |
| 冻结/隐藏/盐/承诺/历史结果 hash 未变 | ✅（§7） |
| 原报告只追加未改写 | ✅（§1） |
| 新报告含可复现命令/退出码/限制 | ✅（§3/§4/§5） |
| 未改 Agent 业务文件 | ✅（§1） |
| 未调 LongCat/在线模型 | ✅（§4） |
| `git diff --check` 通过 | ✅（§6） |

16 项 DoD 全部满足。**剩余风险**见下。

## 9. 声明与剩余风险

**声明**：本任务完成只代表"评测尺子得到纠偏"，**不代表** Agent 复杂咨询能力达 9/10、隐藏集达 4/5、
安全红线已证明为零、Gate 6 已完成或第一阶段完成。后续需按任务书 §10 执行正式验收。

**剩余风险**：
1. 语义等价未命中仅登记 `manual_review_required`（人工填），当前运行器不自动判定语义等价；
2. `claim_evidence_bindings` 需运行期证据清单输入（`--evidence-file`/服务端 agent_evidence 导出），本次离线重判未提供 → 该子项保守判 fail；
3. `formal_redline_verdict` 的 CLEAN_0 仅在全部安全场景演练后才能给出，正式验收需设计注入/更正/跨会话/伪造引用演练题；
4. 条号匹配对《法名》简称归一依赖别名表（已含 4 部常用法），超纲写法会落入 extra_citation 人工复核，不会误判通过。