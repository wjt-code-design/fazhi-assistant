# 法智 Agent 主链路交接文档（2026-09-12 晚 · session 2）

> 本文档**自包含**：不依赖任何对话记忆。读完即可接手。
> 它**取代** `docs/final-agent-handoff-20260912.md`（那份保留为历史记录，其第 10/11 节是本次新增的修正条款）。
> 写作时间：2026-09-12 16:5x。所有路径以项目根 `C:\Users\33393\Desktop\ai-legal-helper` 为准。

---

## 0. 一页速览（TL;DR）

| 事项 | 状态 |
|---|---|
| 检索超时（`TOOL_TIMEOUT`） | ✅ **已修复并经 5 轮真实运行验证**（20 次检索 0 超时，391–1663ms） |
| 三套归因埋点 | ✅ 已上线并离线验证（覆盖率 / writer / 数字违规分桶） |
| 主链路"能否走到起草" | ❌ **未解决（当前唯一阻塞点）**：步数成本随争点数 N 线性增长，N 由模型决定、无上界 |
| `AGENT_MAX_STEPS` 16→20 | 已改（用户批准），**只把可完成的争点数从 4 提到 5，不解决问题** |
| 待你拍板 | C-1 批量检索（推荐）/ C-2 约束争点数 / C-3 暂停交回 |
| 代码 | **全部未提交**；最后一次 git 提交是 2026-09-09 `ebe82e2` |
| 今日真实调用花费 | **0.0711986 元**（5 轮，全部 200，无未知服务端状态） |

**一句话**：检索链路已经修好、可观测性已经建好；现在卡住的是 **controller 的步数预算随争点数线性增长**，
而争点数是模型自由决定的 —— 这必须做一次主链路循环语义的改动（或约束争点数），需要用户拍板。

---

## 1. 你在哪、怎么跑

- 项目根：`C:\Users\33393\Desktop\ai-legal-helper`；后端：`backend/`；venv：`backend/venv/Scripts/python.exe`。
- 测试（**必须带 `--basetemp`，且每次用全新目录名**，见 §10）：
  ```
  cd backend
  ./venv/Scripts/python.exe -m pytest -m 'not slow' --cov=. --cov-fail-under=70 -q \
      --basetemp="<本轮证据目录>/pytest-full-1" --junitxml="<本轮证据目录>/full-junit.xml"
  ```
  当前基线：**949 passed / 0 failed / 覆盖率 78.50%**；ruff / format / mypy 全 0。
- **付费验收宿主**（已参数化，勿复制脚本）：
  `dispatch-output/agent-quality-20260911/serve.py`，环境变量
  `EVAL_EVIDENCE_DIR`（本轮证据目录）/ `EVAL_PORT`（18111）/ `EVAL_GUARD_LIMIT` / `EVAL_LEDGER`。
  启动后等日志出现 `EVALUATION_READY {...}`，其中记录实际加载的模型/预算/检索配置/知识库指纹。
- **付费跑案例**：`backend/scripts/gate2_runner.py --run <唯一run名> --case C01 --base-url http://127.0.0.1:18111 --out-dir <本轮证据目录>`
  （runner 会独占创建 `gate2-run-<run名>.claim.json`，重跑需 `--resume`）。
- 停机：**只 kill 日志里 `Started server process [<pid>]` 那个 PID**；确认 18111 无 LISTENING、账本 0 pending，
  写 `shutdown-check.json`。
- 本机坑：Bash 工具里 **`head/tail/ls/mkdir/cat/dirname` 全缺** → 统计/文件操作一律用 Python 绝对路径脚本。

## 2. 红线与纪律（继承 + 本次修订）

**不可违反**（来自交接文档第 1 节 + 预登记纪律）：
1. 不改冻结 judge（`gate5_judge` 的 `passed=False` 不当语义结论）；冻结案例/轮次协议/fact-ids 的哈希
   在 `dispatch-output/agent-quality-20260911/frozen-hashes.json`，动过必须能对出来。
2. 不为通过评测放宽**事实来源、证据、CAS、终稿验证、预算约束**；不删失败的测试或失败样本。
3. 付费运行：每轮**独立证据目录 + 独立 `cost-ledger.jsonl` + 独立业务库/quota 库**（账本 `exist_ok=False` 拒绝复用）；
   唯一 run 名；**服务端状态未知 → 保留完整预约、不重跑**；不放大样本。
4. guard 白名单外端点/模型一律不发（DashScope `qwen3.8-flash` 预约 2 元；SiliconFlow `BAAI/bge-reranker-v2-m3` 0 元）。
5. 记录真正送出的模型名与端点；**不打印任何密钥**。

**本次修订（均有据可查）**：
- `AGENT_MAX_STEPS` **16→20**（用户 2026-09-12 批准；`backend/.env` + `settings.py` 默认值 +
  `tests/test_agent_gate.py` 断言三处同步，注释记录两次批准历史 8→16→20）。
  交接文档第 11 节说明了为什么这不违反"不得借此提高硬上限"（是显式配置变更，非装配层自动提高；未放松任何校验）。
- **预算窗口**：用户 2026-09-12 指示「9.15 之前放开跑 qwen3.8-flash」→ 该窗口内 `EVAL_GUARD_LIMIT`
  用每进程 20 元兜底、**不按累计扣减**；**2026-09-15 起恢复累计纪律**（截至 09-12 累计 0.0711986 元）。
- **写代码前先存字节快照**（本轮起执行；前两轮漏做导致没有纯差异 diff）。

## 3. 今天的时间线（每一步都有证据目录）

| # | 做了什么 | 证据目录（`dispatch-output/`） | 结果 |
|---|---|---|---|
| 1 | H0 起点核对 | `agent-quality-h3-20260912/`（`h0-baseline.txt`） | 冻结哈希 MATCH、旧账本 0 pending |
| 2 | **H1 修复**：检索超时 | `agent-timeout-h1-20260912/`（`h0-h1-findings.md`） | 内层 rerank 30→12s、外层 8→15s、预算闸门、deadline 透传 |
| 3 | H2 离线验收 | 同上 | 939 passed / 78.38% |
| 4 | **付费 run 1**（0.0107） | `agent-quality-h3-20260912/`（`h3-report.md`） | 终态 `VERIFIER:FAIL_SAFE`（覆盖率闸门） |
| 5 | 覆盖率归因埋点 | `agent-coverage-observability-20260912/`（`report.md`） | `agent_coverage_issues` 字段 |
| 6 | **付费 run 2**（0.0205） | `agent-coverage-attribution-20260912/`（`attribution-report.md`） | 终态 `WRITER:NON_CANONICAL_CITATION` |
| 7 | writer 归因埋点 | `agent-writer-observability-20260912/`（`report.md`） | `agent_writer_summary` 字段 |
| 8 | **付费 run 3**（0.0167） | `agent-writer-attribution-20260912/`（`attribution-report.md`） | 终态 `UNSUPPORTED_NUMERIC_TOKEN` |
| 9 | 数字分桶埋点 | `agent-numeric-bucket-20260912/` | `numeric_violation` 字段 |
| 10 | **付费 run 4**（0.0073） | `agent-numeric-attribution-20260912/`（`atttribution-report.md`） | 终态 `AGENT_BUDGET_EXCEEDED`（5 争点） |
| 11 | grilling 对齐 ×2 + 步数测算 | `alignment-20260912-writer-bottleneck.md`、`alignment-20260912-step-budget.md`、`step-budget-measurement.md` | 五支决策 + 测算 |
| 12 | `AGENT_MAX_STEPS` 16→20 + 5 争点离线反例 | `agent-step-budget-20260912/` | 949 passed；16 步下复现缺陷（watch-it-fail） |
| 13 | **付费 run 5**（0.0092） | `agent-budget20-verify-20260912/`（`round1-report.md`） | **8 争点**，仍 `AGENT_BUDGET_EXCEEDED` → 假设证伪 |
| 14 | 证据审计 | 同上（`evidence-audit.md`） | 3 处纠正 + 2 处补验成立 |

## 4. 当前代码状态（⚠️ 先读这段再动 git）

- **2026-09-12 17:02 已提交两笔**（用户指示"先提交未提交的改动"）：
  - `d802a8d` fix(agent)：主链路检索超时修复 + 三套归因埋点 + 步数预算参数调整（156 文件：代码/测试/文档）
  - `712ac27` chore(evidence)：归档 12 个证据目录（592 文件；`*.sqlite`/`*.log`/pytest 临时目录/
    `token.json`/`task1/` 隐藏评测集已被 `.gitignore` 排除）
  - 此前最后一次提交是 2026-09-09 `ebe82e2`；两者之间混合了**多个会话**的未提交改动，
    **`git diff` 无法区分出"本 session"的改动** —— 本 session 的改动清单见下。
- 本 session 实际改动的文件：
  - H1：`backend/tools/contracts.py`、`backend/tools/gateway.py`、`backend/tools/legal_retrieval.py`、
    `backend/retrieval.py`、`backend/tests/test_retrieval_rerank.py`、`backend/tests/test_tool_gateway.py`
  - 归因埋点：`backend/agent/service.py`、`backend/observability.py`、`backend/agent/writer.py`、
    `backend/tests/test_agent_chat_integration.py`、`backend/tests/test_agent_writer.py`
  - 预算：`backend/.env`（**gitignore 内，不入库**——但 `settings.py` 默认值已改为 20，
    故**新 clone 也能得到 20**，无需手工同步；详见 §13.7）、
    `backend/settings.py`、`backend/tests/test_agent_gate.py`
  - 文档：`docs/final-agent-handoff-20260912.md`（§10、§11）+ 本文档
- 每个改动文件都有 `.before`/`.after` 快照与 SHA-256，在 `agent-numeric-bucket-20260912/candidate-manifest.json`
  及更早各轮的 manifest 里。
- **🚨 git 对象库存在预先存在的损坏**（非本次提交造成）：`git fsck` 报 22 处
  （missing blob/tree/commit，含历史提交 `03a2f14` —— 即 `test_agent_gate.py` 注释里引用的那个批准值提交；
  HEAD/master 的 reflog 也有坏条目）。**后果**：`git gc`/geometric repack 每次提交后都会报错
  （`Failed to traverse parents of commit 0c1eb0c4`），深层历史遍历会失败；**新提交本身不受影响**（HEAD 完好）。
  **修复建议（未执行）**：`git fetch origin` 尝试从远端补齐缺失对象 → 重跑 `git fsck`；
  若远端也没有，则考虑从远端重新 clone + 把未推送的本地提交 cherry-pick 过去。**不要跑 `git gc --prune`。**
- **尚未 push**（远端 `origin = https://github.com/wjt-code-design/fazhi-assistant.git`）；
  push 前建议先做上面的对象修复，否则远端/本地交互可能再次报 traverse 错误。

## 5. 已被证据确认的结论（可直接信任）

1. **H1 检索超时修复有效**：5 轮真实运行、20 次检索，**0 次 TOOL_TIMEOUT**，391–1663ms。
   机制：内层 rerank 单次尝试 12s + 每次尝试前查剩余预算（余量 0.3s）+ 外层 15s + deadline 透传。
2. **writer 是 fail-fast / 全有全无**（`writer.py:_render_once`）：除「`evidence_ids` 为空 → 丢弃该 claim」外，
   任何校验失败（未知 issue/evidence/fact id、跨争点引用、非规范引用、数字无来源…）都 `_fail` **整篇作废**；
   `render()` 会带 reason 回喂重试一次；coverage 回喂由 `service.py` 另行驱动（预算 1 次）。
3. **覆盖率闸门**（`verifier.py:289`）：每个争点必须有 claim 且至少一条绑定的证据是 `STATUTE + EFFECTIVE`；
   不足时若 `verifier_research_returns < max(=1)` 走 RESEARCH_MORE，否则 `FAIL_SAFE`。
4. **数字校验**（`writer.py`）：claim 文本里**每个**数字 token（date/percentage/amount/duration/number 五类，
   NFKC 归一）都必须出现在**该 claim 自己绑定的** fact+evidence 文本里。
5. **提示词已含约束**（`prompts.AGENT_WRITER_SYSTEM`）：「不得新增事实、数字、金额…」「只能引用同 Issue 的
   Fact ID」「证据不足应省略该 Claim」—— **规则已写明，模型仍会违反**（两次实测）。单靠重申提示词收益存疑。
6. **步数账**：`steps` = 状态转换次数（`state_machine.transition()` 每次 +1）；`register_action` 加的是
   `tool_calls`；发起工具调用前闸门 `steps + 3 > max_steps` → 停止（`controller.py:603`）。
7. **失败会回落 Fast Path**：`AGENT_BUDGET_EXCEEDED` 在 `routing_metrics.py:18` 的技术回落白名单里，
   `main.py:1403` 记录 `fast_path` 路由 → 用户拿到的是 **Fast Path 答案，不是 Agent 成果**
   （`runner.final_chars` 与 DB assistant 消息长度**口径不同**，勿混用）。
8. **历轮争点数 3 / 4 / 4 / 5 / 8**（近 5 轮；第 1 轮未测），澄清全部 2/2，backfill 0/1/1/2/3。

## 6. 被证伪 / 被纠正的结论（别重蹈）

| 曾以为 | 实际 |
|---|---|
| 「claims=0 ⇒ 模型没产出 claim」 | **✗**：真实运行 proposed=4（每争点 1 条），被丢的只是 `evidence_ids` 为空的 2 条 |
| 「步数需求 ≈ 3N+1，N=8 → 25」 | **不精确**：≈ **3N+2~3**（N=8 ≈ 24~27）；精确常数无法标定——5 轮里**没有一条完整成功的 run** 可作锚点 |
| 「历轮 state_version = 14/14/17/16」 | **转录错误**：正确是 steps=13/16/16/15/18、state_version=14/17/16/16/19 |
| 「1119 是 Fast Path 答案」（当时未验） | **已补验成立**：DB 消息 1126 字（口径不同于 runner 的 1119），内容为 ①② 结构 Fast Path 叙述 |
| 「必需法条召回 0/4」（探针自动计数） | **探针 bug**：期望集用了阿拉伯数字，而知识库 `article` 是**中文条号**（"第四十七条"） |
| 「state.claims == []」 | **查询错误**：`LegalAgentState` 根本没有 `claims` 键；`.get()` 返回 None ≠ 空集合 |
| 「 提高 max_steps 能解决」 | **✗ 已证伪**：争点数无上界（8 个），20 步仍耗尽 |
| A1（去 backfill 检查点）单独可行 | **余量为 0**：省 2 步后第 5 次检索可发起，但 tool_result→DRAFTING→COMPLETED 用满 16；任何回喂/replan 再撞 |

## 7. 核心未解决问题（当前唯一阻塞点）

**步数成本随争点数 N 线性增长，而 N 由模型决定、无上界。**

- 组成：`bootstrap 1 + 检索 2N + 澄清 2×2 + backfill (N−3) + 起草/落盘 2 ≈ 3N + 2~3`。
- 实测：N=3 → 13 步（含失败路径）、N=4 → 16、N=5 → 停在 15（差 1 步检索不到）、N=8 → 停在 18（差 3 个争点检索不到）。
- 后果：**争点数一多就永远到不了起草** → `stopped` → 技术失败回落 Fast Path → 用户拿到非 Agent 答案。
- 这**统一解释**了四轮四种终态：不是四个独立 bug，而是同一个预算约束在不同争点切法下的不同表现。
- **注意**：`backfill_retrieval`（2026-09-10 修复）本身是**正确**的语义（防止无证据起草），
  问题在于它每争点多花 1 步 + 检索 2 步，与步数上限相乘后无解。

## 8. 待决策 → ✅ 已拍板（用户 2026-09-12 17:1x）：**C-1 批量检索**

> 用户原话：「C-1 批量检索，写进交接文档，后续任务都交由助手来执行。」

| 选项 | 内容 | 状态 |
|---|---|---|
| **C-1 批量检索 ✅ 已选** | controller 的 planning/backfill 改为：**一轮内对所有未检索争点连续发起检索**，步数成本与 N 解耦 | **执行中**，见 §13 |
| C-2 约束/合并争点 | planner 侧限制争点数或合并相近争点 | 未选（保留为 C-1 失败后的备选） |
| C-3 暂停 | 把结论写成报告交回，停止投入 | 未选 |

执行纪律（沿用 §9）：离线反例（watch-it-fail 先红）→ 实现 → 全量回归 + lint/format/mypy
→ 预登记 → 付费 1 轮 → 出终稿再续跑到**连续 3 轮全绿**；**连续 2 轮同类失败即停**；
**不改任何校验**；**不再提高 max_steps**（20 保持，若 C-1 后仍不够，带数据回来）。

## 13. C-1 批量检索执行计划（**进行中：反例已立，实现待续**）

### 13.1 机制真相（读码后修正）

**批量检索的雏形已经在代码里**：`controller.py:764 _seed_issue_retrievals`（V2-G2 争点强制扇出）
会对每个"尚无成功证据"的争点构造 `ToolCallDecision(retrieve_laws, query=issue.question)` 走 `_execute_tool`，
状态回到 PLANNING 就 `continue` 下一个 —— **但有一个 break**（`controller.py:795-796`）：

```python
if run.state.status is not AgentStatus.PLANNING:
    break  # 评估推进出 PLANNING（如 WAITING_USER 澄清）→ 交调度器处理
```

**澄清（WAITING_USER）会打断扇出** → 控制权交回客户端（HTTP 轮次结束）→ 后续争点只能靠
`backfill_retrieval` 每争点多花 1 步补 → 这就是"每轮只检索 1 个 + 步数耗尽"的机制。

### 13.2 离线反例（已建，watch-it-fail ✅）

`tests/test_agent_chat_integration.py::test_eight_issue_decomposition_reaches_drafting_within_step_budget`
- 8 争点夹具（`_MULTI_ISSUE_QUOTES` 已扩到 8 条逐字片段）+ `agent_max_steps=20`
- **现状代码下实测红**：`terminal_decision = budget_exceeded:step_preflight, steps=18/20`
  —— 与真实付费运行 `budget20-q38-c01-20260912-01` **完全一致**（同 reason、同步数）✓

### 13.3 实现（C-1b：扇出期间暂缓澄清）—— ✅ 已实施（2026-09-12，见 §13.8）

**设计**：在 `_seed_issue_retrievals` 的扇出循环里，当评估结果为 `MISSING_FACT` 且澄清预算未用完、
**且其后仍有未检索争点**时，**暂缓该澄清**（不调 `_handle_evaluation`），转回 PLANNING 继续扇出；
扇出结束后状态在 PLANNING，由既有主循环（`_deterministic_finish_gate` → planner → 澄清）**照常**提出澄清
—— 澄清语义零改动（仍由 planner/评估器驱动、仍 ≤2 轮、每轮 1 问），只是**时序**推迟到扇出完成后。

**终止性三问**（loop-termination-preflight，已作答）：
1. 终止条件 = `_every_issue_retrieval_attempted`（"已尝试"，非"已拿到证据"）—— 检索器持续空命中时
   仍在有限步内变 True ✓（每争点至多尝试一次，fingerprint 去重）。
2. 空命中边界：既有 `test_backfill_retrieval_terminates_when_retriever_returns_no_evidence`
   （`_all_empty_gateway`）必须保持通过；`_MultiIssueTransport` 自带 `planner_call_limit=50` 护栏 ✓。
3. 同输入不重试：fingerprint 去重 + `duplicate_attempts_per_issue` 上限 ✓；让路目标是终态（DRAFTING）✓。

**步数测算（实现后实测，§13.8）**：~~N 争点 + 2 澄清 ≈ `2N + 6~8`~~ **不成立**——每争点检索固定
**3 步**（EXECUTING+EVALUATING+暂缓转回 PLANNING，状态机 `EVALUATING→仅PLANNING` 决定了省不掉这 1 步）。
实测 8 争点 = 19/20 步停、检索 6/8。**N=8 全扇出需 1+8×3 = 25 步 + 澄清/起草，总计 ~27~29，T5 估的 24~26 不够。**

### 13.4 ⚠️ 残余问题（C-1b 后仍在，实测数据见 §13.8，需用户再拍板）

- **提高 `max_steps`**：实测推算 N=8 需 ~27~29 步（全扇出 25 + 澄清/起草），**T5 原估 24~26 不够**；
- 或 **C-2 planner 争点合并**：8 个争点里明显可合并（预告期/代通知金、继续履行 vs 赔偿金、举证责任），
  法律上合并到 4~5 个更合理 —— 用户此前"不约束"的前提（降开销可行）已变；
- 或 **真·批量检索**（一个 EXECUTING 周期发完全部检索，步数与 N 解耦，N=8 ≈ 9~10 步）—— 见 §13.8 推荐。
- C-1b 已落地：修掉"澄清打断扇出"的病态（实测 clarifications=0），预算内检索数 5→6。

### 13.5 实现注意（给接手者）

1. 暂缓澄清**不要**预扣澄清预算（`register_clarification` 只在真正提问时调用）——评估器确定性，
   扇出结束后会再次给出同一澄清。
2. 暂缓**必须落检查点**（✅ 已定，2026-09-12，与本节原文"倾向不落"相反）：崩溃恢复时 `_drive`
   对 EVALUATING 检查点**直接走 `_handle_evaluation`**（无 C-1b 暂缓分支）——若不落盘，恢复后扇出会被
   澄清重新打断，C-1b 不变式失效；落盘为 PLANNING 后恢复走 `_seed_issue_retrievals` 继续扇出，语义一致。
3. 暂缓条件必须含"其后仍有未检索争点"，最后一个争点检索完后不要多绕一步。
4. 既有回归必须全绿：`test_clarify_budget_exhaustion_must_not_skip_unretrieved_issues`、
   `test_backfill_retrieval_terminates_when_retriever_returns_no_evidence`（空命中终止性；
   **预算 16→20**，C-1b 步数经济学变化所致，见 §13.8）、
   `test_finish_gate_quadrant_b_still_forces_conditional_analysis`。
5. ~~8 争点反例在实现后必须转绿~~ **修订（用户 2026-09-12 批准）**：8 争点 20 步内到不了起草是
   T1b 已知残余，测试改为**行为不变式锁**（扇出不被打断 + 预算停 + 实测步数留档），见 §13.8。

### 13.6 待办任务清单（按序执行，执行者 = 下一任助手；每步有验收）

> 用户 2026-09-12 指示：后续任务交由助手执行。以下按序做，**不要跳步**。

**T1 实现 C-1b** —— ✅ 已完成（2026-09-12，commit 见 §13.8；与下面伪码的差异仅两处：
暂缓**落检查点**（见 §13.5-2 修订）、8 争点测试改为行为不变式锁（见 §13.5-5 修订））：
- 在扇出循环内 `evaluation = self._evaluator.evaluate(run.state)` 之后、`handled = self._handle_evaluation(...)`
  **之前**插入暂缓判定（伪码，变量名以现场为准）：
  ```python
  pending_retrieval = [i for i in run.state.issues
                       if not any(obs.issue_id == i.issue_id and obs.status == "succeeded"
                                  and obs.evidence_ids for obs in run.state.observations)
                      and i.issue_id != issue.issue_id]          # 当前 issue 之外仍有未检索
  if (evaluation.outcome is EvaluationOutcome.MISSING_FACT
          and run.state.clarifications < run.state.budgets.max_clarifications
          and pending_retrieval):
      # C-1b：扇出未完成 → 暂缓澄清（不预扣预算；评估器确定性，扇出后会再次给出同一澄清）
      state = transition(run.state, AgentStatus.PLANNING)      # 已定：必须落检查点（§13.5-2）
      run = self._save(run, state, CheckpointMetadata(
          decision="fanout_defer_clarification", reason_code="C1_DEFERRED_CLARIFICATION"))
      continue
  ```
- ~~验收：8 争点反例转绿~~ **修订（用户 2026-09-12 批准）**：N=5 不回归 + 8 争点行为不变式 +
  §13.5-4 三个既有回归不回归 + 4/5 争点测试不回归（均 ✅）。

**T2 全量回归 + 静态检查**：`949+1 passed / 0 failed`、ruff/format/mypy 全 0
（命令见 §1；**basetemp 用全新目录名**）。

**T3 提交**：消息格式沿用 `d802a8d`/`712ac27` 的风格；**只提交**本任务相关文件
（controller.py、test_agent_chat_integration.py、交接文档），不要把 `dispatch-output/` 全量带进去。

**T4 付费验证**（每轮独立目录/账本/隔离库，预登记先行）：
- 预登记要点：候选=本任务提交的哈希；`EVAL_GUARD_LIMIT=20`（9.15 前口径）；
  判定 = `agent_completed=True`；**法律质量不在判定范围**。
- 第 1 轮出终稿 → 续跑到**连续 3 轮全绿**；失败 → 读 `writer_render_summary` /
  `coverage_gate_terminal_failure` / `numeric_violation` 分桶，**连续 2 轮同类失败即停**。

**T5 升级路径**：8 争点已实测超 20 步（§13.8）→ **不要自行改上限**，
带实测数据向用户申请 `max_steps`（**实测推算 ~27~29，原估 24~26 不够**，需显式授权）、
提请 C-2（planner 争点合并）或**真·批量检索**（§13.8 推荐）。

**T6 时间窗**：2026-09-15 起恢复"20 元累计"纪律（以累计 0.0711986 元为基数重算）；
届时付费轮次停止，先对账再继续。

### 13.7 当前挂起状态（本文档写作时点）

- 8 争点反例测试与本文档 §8/§13 已于 `41cf4fa` 提交；**C-1b 实现见 §13.8 的 commit**（本任务 T3）。
- `backend/.env` 的 `AGENT_MAX_STEPS=20` 不入库（gitignore）；`settings.py` 默认值已是 20，
  故**新 clone 也能得到 20**，无需手工同步。
- 付费验证尚未开始（C-1b 的付费验证在 T4，**挂起等待 §13.8 的 T1b 决策**）。


### 13.8 ✅ T1a 完成记录（2026-09-12，C-1b 落地 + 实测数据）

**提交**：`11b435c`（本任务 T3：controller.py + test_agent_chat_integration.py + 本文档）。

**改动**：
1. `backend/agent/controller.py` `_seed_issue_retrievals`：扇出循环内插入 C-1b 暂缓判定
   （新增 `_has_pending_unretrieved_issue` 辅助方法 + `fanout_defer_clarification` 检查点）。
   **检查点必须落盘**（推翻 §13.5-2 原文"倾向不落"，理由见该节修订）。
2. `backend/tests/test_agent_chat_integration.py`：
   - 8 争点反例 → 改名 `test_eight_issue_decomposition_c1b_fanout_defers_clarification_and_measures`，
     改为行为不变式锁（见 §13.5-5 修订）。
   - `test_backfill_retrieval_terminates_when_retriever_returns_no_evidence` 预算 16→20
     （C-1b 步数经济学：空命中下 4 争点先全扇出再澄清，16 步不够；20 与产品默认一致）。

**实测（离线反例，`_MultiIssueTransport` 8 争点 + `agent_max_steps=20`）**：
- `[T1b-data] steps=19/20, retrieved=6/8, clarifications=0` —— C-1b 前基线 18/20 停、检索 5/8。
- 结论 1：C-1b 修复了"澄清打断扇出"（停止时 clarifications=0，澄清推迟到扇出后）。
- 结论 2：**每争点检索确证 3 步**（EXECUTING+EVALUATING+暂缓转回 PLANNING）——§13.3 原"2N"测算不成立。
- 结论 3：N=8 全扇出需 1+8×3 = 25 步 + 澄清(4)/起草(2) ≈ **27~29 步；T5 原估 24~26 不够**。
  N=7 ≈ 24~26；N=6 ≈ 21~23；20 步只覆盖 N≤5（与现状相同）。

**T2 结果**：950 passed / 0 failed（原 949+1 红测转绿）/ 覆盖率 78.57%；ruff / format / mypy 全 0。

**T4（付费验证）状态**：**挂起**——真实付费案例（budget20-q38）为 8 争点，C-1b + 20 步下必然
仍 `budget_exceeded`，烧钱无意义。**T1b 决策后再启动**。

**T1b 决策选项（需用户拍板）**：
| 选项 | 机制 | N=8 步数 | 对任意 N 鲁棒？ | 风险 |
|---|---|---|---|---|
| **A. 真·批量检索（推荐）** | 扇出改单 EXECUTING 周期连发全部检索、一次 EVALUATING 收齐 | ~9~10 步 | ✅ 是（步数与 N 解耦） | 改动面大：新状态机路径/批量检查点/逐工具 fail-closed 语义 |
| B. 提高 max_steps | 20→28+ | ~27~29（需 28~30） | ❌ 否（N 无上界，模型下次切 9 个又爆） | 击穿"硬上限"可信度；估算易再错 |
| C. C-2 争点合并 | planner 合并 8→4~5 | ~18~20 | ⚠️ 依赖 LLM 合并判断 | 合并错=丢争点=危险建议；新改动面 |

推荐 A：唯一步数与 N 解耦的方案，符合安全红线（不丢争点），且让预算讨论一次终结。

### 13.9 ✅ T1b 完成记录（2026-09-12，真·批量检索落地）

**提交**：`c5236ef`。用户此前批准"按推荐执行"（A：真·批量检索）。

**改动**：
1. `backend/agent/controller.py` `_seed_issue_retrievals` **重写为批量检索**：一个 EXECUTING 周期内
   连发全部未检索争点的 retrieve_laws、一次 EVALUATING 收齐；批起 `batch_tool_call` / 批止
   `batch_tool_result` 两个检查点。删除 C-1b 的逐争点暂缓逻辑与 `_has_pending_unretrieved_issue`。
   - **幂等性**：pending 排除"已尝试"（k=4 指纹）的 issue——否则空命中时 `_drive` replan→PLANNING
     重入整批 → 每轮仅递增 duplicate_attempts → `budget_exceeded:duplicate_attempts` 停止（实测踩到）。
   - **物化去重**：批内证据物化基于线程化 `current` 状态——否则同一 evidence_id 重复物化、
     同 id 不同 payload（acquired_at）触发 `INTEGRITY_DIVERGENT_EVIDENCE_ID`（实测踩到）。
   - fail-closed：任一工具失败 → 停批，由 `_drive` 的 EVALUATING 失败分支整轮失败（语义不变）。
2. `backend/tools/gateway.py`：`retrieve_laws` `max_calls_per_run` **6→10**（产品硬约束，见 §13.9 下方
   注释）：V2-G2 要求每争点至少一次定向检索，争点数模型自由（实测 8）——6 次上限在批量下拒第 7 次
   （TOOL_CALL_LIMIT_EXCEEDED→fail-closed）。10 与状态层总闸 `agent_max_tool_calls=10` 对齐；
   状态层 register_action 的 tool_calls 预算仍是真正的总量防御，本字段是单工具防御性冗余（read_only）。
3. `backend/tests/`：
   - 8 争点测试 → `test_eight_issue_decomposition_batch_reaches_drafting_within_20`（断言抵达起草/
     完成 + 全检索，**转绿**）；删除 C-1b 行为锁测试（被取代）。
   - 夹具 `_MultiIssueTransport` 补 `missing_information: []` 与 `section`（原输出不合 writer
     `_GeneratedDraft` strict schema → 所有走起草的离线测试实际都在 MALFORMED 假失败；5 争点测试
     断言未查起草状态故一直假绿）。
   - `test_agent_controller.py` 检查点顺序断言更新为 `batch_tool_call` / `batch_tool_result`。
   - 空命中 backfill 终止性测试（预算 20）在批量下通过（幂等性保证不重入）。

**实测（离线反例，8 争点 + 20 步 + 产品网关）**：`outcome=completed, status=COMPLETED,
steps=9/20, retrieved=8/8` —— 对比：C-1b 逐争点 19/20 停、6/8；批量前 18/20 停、5/8。

**T2 结果**：950 passed / 0 failed / 覆盖率 78.52%；ruff / format / mypy 全 0。

**T4（付费验证）结果（2026-09-12 执行）**：**2 轮同类失败 → 按止损规则停止**（详见
`dispatch-output/t4-batch-retrieval-20260912-r2/t4-conclusion-report.md`）：
- **批量检索真实生效**：r1 `steps=9/20`、4 争点全检索、证据绑定逐条核对正确；澄清 2 轮正常；步数预算不再是阻塞点。
- **剩余失败面 = writer 生成遵守度**（§5-2/§5-5 已记录的 fail-fast 家族）：r1 `CROSS_ISSUE_EVIDENCE`
  （4 争点、claims 4→1）；r2 `NON_CANONICAL_CITATION`+`CROSS_ISSUE_EVIDENCE`（6 争点、claims 6→2）。
  均为模型违反 AGENT_WRITER_SYSTEM 约束（跨争点引用/非规范引用），**非批量/证据/预算 bug**。
- 两轮成本 0.0463 元（账本见各轮 `cost-ledger.jsonl`）；全部 HTTP 200，无未知服务端状态。
- 后续方向需用户拍板：writer 侧确定性后处理 / 分争点独立渲染 / 接受现状。

## 9. 若继续执行：操作细节

1. **每轮付费运行前**：建新目录 `dispatch-output/<主题>-<日期>/`（`exist_ok=False`）；写**预登记**
   （目的、候选+哈希对齐核验、模型/端点、费用口径、判定标准、止损规则）；核对
   `candidate-manifest.json` 的哈希与当前字节 `ALL_MATCH`。
2. **启动宿主**：`cd dispatch-output/agent-quality-20260911 && EVAL_EVIDENCE_DIR=... EVAL_PORT=18111
   EVAL_GUARD_LIMIT=20 <venv python> -u serve.py > <新目录>/server.log 2>&1`；
   等 `EVALUATION_READY` 并核对其中 `max_steps` / `budget_cny` / `retrieval_config`。
3. **跑案例**：`--run <唯一名> --case C01`；结束后读 `server.log` 的
   `writer_render_summary`（含 `numeric_violation` 分桶）与 `coverage_gate_terminal_failure`，
   以及 DB `agent_runs` / `agent_steps` / `state_json`。
4. **停机**：kill 日志里的 serve PID → 确认 18111 无监听 → 账本 0 pending → 写 `shutdown-check.json`（含费用）。
5. **埋点字段说明**（都在 `observability._ACCOUNT_FIELDS` 白名单内；新增字段必须登记，否则被
   `_JsonFormatter` **静默丢弃**，且有 AST 哨兵测试 `tests/test_log_field_whitelist.py` 会抓）：
   - `agent_coverage_issues`：覆盖率终态失败的逐争点 `{issue_id, claims, claims_bound_effective_statute, deficient}`。
   - `agent_writer_summary`：每次渲染的 `{reason, has_feedback, claims_proposed, claims_accepted,
     claims_dropped, per_issue[], failing_issue_id, numeric_violation?}`。
   - `numeric_violation`：`{issue_id, unsupported_total, in_own_issue_other_sources, in_other_issues,
     from_unknown_facts, nowhere}` —— **只记计数**（对齐决定：不记数值/文本）。
     `in_own_issue_other_sources>0` ⇒ ②漏绑；`in_other_issues>0` ⇒ ③跨争点无权引用；
     `nowhere>0` ⇒ ①编造。**注意：这组结论只有当运行真的走到 writer 时才有效。**
6. **验收口径**（对齐已定）：离线反例（watch-it-fail 先红）+ 全量回归 + lint/format/mypy
   → 付费 1 轮 → 出终稿再续跑到**连续 3 轮全绿**；**连续 2 轮同类失败即停**；未知服务端状态即停。

## 10. 环境坑（每一条都真实踩过）

1. **safe-delete 沙箱 + pytest basetemp**：pytest 会**在会话开始时删除** `--basetemp` 目录；
   复用已累积 >50 文件的旧目录 → `SAFE_DELETE_BULK_CONFIRM_REQUIRED` → `SystemExit(1)` →
   **所有用 `tmp_path` 的测试在 setup 阶段集体报错**（见过 183 errors / 762 passed，极易误判成实现问题）。
   ⇒ **每次用全新目录名**；旧目录改名留证，**不要手工删**（删也会触发守卫）。
2. **Bash 工具缺 coreutils**：`head/tail/ls/mkdir/cat/dirname` 全缺 → 一律用 Python 绝对路径脚本；
   含中文/空格路径加引号；`bash script.sh` 形式可能零输出，**内联命令可靠**。
3. **PowerShell 在本机拿不到 stdout** → 用 Python。
4. **Python 内联 `-c` 里 `$Recycle.Bin` 会被展开** → 涉及该路径写成 `.py` 文件。
5. **脱离沙箱跑含中文输出的 Python 要加 `-u`**，脚本内自建日志文件并 flush。
6. `os.walk` 对文件路径统计大小恒为 0 → 统计前先 `isfile` 分支。
7. **`replace_all` 改名后必须逐处核对作用域**（本轮把 `_render_once` 外两处和它自己内部一行都改了 →
   NameError + RecursionError，30+ 用例失败）。改名类重构：改名后 grep 全名核对。
8. **断言"为空/为 0"前先确认键是否存在**；**期望集合格式必须与数据实际格式对齐**
   （知识库 `article` 是中文条号）。

## 11. 账目（估算，非供应商账单）

| 轮 | 目录 | 元 |
|---|---|---:|
| 第一轮（H0 前） | `agent-quality-20260911/` | 0.0067501 |
| H3（run1） | `agent-quality-h3-20260912/` | 0.0106919 |
| 归因轮（run2） | `agent-coverage-attribution-20260912/` | 0.0205294 |
| writer 归因（run3） | `agent-writer-attribution-20260912/` | 0.0167091 |
| 数字归因（run4） | `agent-numeric-attribution-20260912/` | 0.0072769 |
| budget20（run5） | `agent-budget20-verify-20260912/` | 0.0092412 |
| **累计** | | **0.0711986** |

剩余授权参考 **19.9288014 元**（按 20 元总授权减累计；**9.15 后恢复累计纪律**时以此为基础重算）。
外呼合计 36 次，全部 HTTP 200，**无未知服务端状态**。

## 12. 交接清单（接手后第一小时该做的事）

1. 读本文档 §0–§8；读 `docs/final-agent-handoff-20260912.md` 第 1、10、11 节。
2. `git status` 确认工作区状态（**不要**试图用 git diff 理清本次改动，见 §4）。
3. 跑一次全量测试确认 949 passed（命令在 §1），确认环境没变。
4. 向用户确认第 8 节的 C-1 / C-2 / C-3 选择。
5. 若选 C-1：按 §9 的纪律做离线反例 → 实现 → 全量回归 → 预登记 → 付费验证（连续 3 轮全绿为达标）。
