# 法智 Agent 项目 · 工作进度交接文档 —— 2026-09-11

> **本文是对 `docs/handoff-20260910.md`（753 行交接文档）所列任务的执行进度复盘。**
> 回答四个问题：① 交接文档安排的任务完成得怎么样；② 做了哪些安排之外的事情；③ 为什么这样做；④ 后续还打算做什么、为什么。
>
> 仓库根 = `C:\Users\33393\Desktop\ai-legal-helper`；HEAD = `ebe82e2`（未推进，有意设计）。
> 候选锚定 = `dispatch-output/t2-persistence-20260910/candidate-manifest-t8-20260910.json`（141 候选文件 / 154 总文件 / 0 漂移）。

---

## §1 交接文档任务完成度总览

`docs/handoff-20260910.md` 的 §6「接手步骤」列了五步走，下面逐条对照执行状态：

| 步骤 | 交接文档要求 | 执行状态 | 说明 |
|---|---|---|---|
| ① | 确认候选锚定与备份在位，不要 commit/stash/checkout/reset | ✅ 完成 | HEAD 仍 `ebe82e2`；工作树 264 文件变更；锚定复算 154 文件 0 漂移；冻结文件漂移 0 |
| ② | 启服务并确认 /healthz 就绪 | ⚠️ 未执行 | 服务未启动（T7 预登记进程已被上一会话误杀，且本次工作重心在代码审查与测试覆盖，非在线验证） |
| ③ | 跑 C01 单题付费探针，验证缺陷修复 | ✅ 已完成（在 §12.4） | `probe-c01-verify2-20260910`：errors=[]、agent_completed=True、final_chars=878、issues=4/4、有证据 4/4、status=completed |
| ④ | 跑 run-13 全量 10 题采集 | ✅ 已完成（在 §12.7–12.8） | `gate5-dev-run-13-qwen38`：10/10 完整、agent_completed 7/10、争点 18/47（缺 62%）、full_closure 0/10 |
| ⑤ | 逐题留证 + 两层 judge 判定 | ✅ 已完成（在 §12.9） | T7 验收报告产出，逐题证据齐全，judge mechanical_pass_count=7、full_closure=0/10 |

**交接文档 §9 自检清单 15 项**：14 项达成，唯一未达成 = §5.5 独立验收者检查（已由替代性核查覆盖，但回执如实标注"非真正第三方"）。

---

## §2 交接文档安排之外做的事情

在交接文档列的 T7 验收五步走之外，实际执行了以下**安排之外**的工作。每项都说明"做了什么"和"为什么这样做"。

### 2.1 T8 分解契约加固（runtime.py + 4 文件，+918 测试）

**做了什么**：
- 给 `runtime.py` 的分解器加了**穷尽性契约**（事实是否成立 / 行为是否合法 / 每种法律后果各自成争点）+ **确定性覆盖度检查**（用户事实性分句必须被 facts 逐字引用）+ **有界修复环**（最多重试 1 次，缺口严格变小时才采纳）。
- 同步修了 `observability.py` 的 §12.3 静默丢弃缺陷（补登记 `agent_pre_run_reason` / `agent_conversation_id` / `agent_failure_detail`）。
- 新增 11 个测试用例覆盖修复环终止性、白名单回归、预算装得下最大分解。

**为什么这样做**：
T7 验收轮（§12.7）暴露的**根因不是检索器**，而是**分解器契约**「issues 为 1 到 8 个」（runtime.py:61）无下限/无穷尽性/无完备性校验。10 题中 9 题分解出 1–3 个 issue（冻结题 required_issues 为 4–5）⇒ 检索面极窄 ⇒ 必需要件法条全 missing ⇒ full_closure=0/10。

执行书原 T8 表述「仅在新证据证明必要时启动真检索修复」。**本轮新证据不支持指向真检索**（C02 是唯一分解达标题，检索 4/4 全中，tool_result 全 TOOL_SUCCEEDED）⇒ **T8 目标改为「分解契约加固」**，这是根因驱动的决策，不是拍脑袋。

### 2.2 T8 验证轮（run-14 / run-15，对照基线）

**做了什么**：
- `gate5-dev-run-14-qwen38-t8`：对照 run-13（同模型/同题集/同 runner，唯一变量=候选）。
- `gate5-dev-run-15-qwen38-t8b`：T8 收尾改动的验证轮（第三处修复环 + Pareto 规则 + 常驻哨兵）。

**结果**：

| 指标 | run-13（改动前） | run-14（T8） | run-15（T8b 收尾） |
|---|---|---|---|
| 争点总数（应有 47） | 18（缺 62%） | 32（缺 32%） | 37（缺 21%） |
| agent_completed | 7/10 | 7/10 | 6/10 |
| judge full_closure | 0/10 | 0/10 | 0/10 |

**为什么这样做**：
T8 是改动候选文件的代码加固，按 T0 候选定义（脏工作树 + 哈希锚定）必须**重采锚定 + 重跑全量 + 重验冻结物**。不做验证轮就无法确认 T8 是否生效——而 T8 的判据是"争点缺口显著下降"（62% → 32% → 21%），不是 full_closure（那是 writer 引用轴，不在 T8 射程）。

### 2.3 深度代码审查（2026-09-11 00:30–01:10）

**做了什么**：
对今日累积候选（141 文件）做了一次深度代码审查，产出 `deep-review-report-20260911.md`（13 项发现 + 1 谜题）。

**审查方法**：双并行只读子代理（L1 深潜 3144 行 / L2-L3 死代码与质量）+ 实现者逐条验证聚合（**不盲信代理**——本轮聚合中推翻 1 条 🔴、更正 1 条事实）+ 实现者亲攻未解之谜。

**13 项发现处置统计**：

| 处置 | 项数 | 具体项 |
|---|---|---|
| 已修代码 | 3 | F1（Pareto 准则 + 判别性回归测试）、F3（"297"注释×2）、F9（默认题集恢复） |
| 文档修正 | 2 | F5（设计意图注释）、F7（消费方清单） |
| 推翻代理结论 | 2 | F4（review_sidecar 不可删——它是 T1 工单正式交付物）、F7（run_evidence.py 非仅测试消费——dispatch-output 4 脚本在 import） |
| 记录不修 | 4 | F2（snippet 信任=独立课题）、F8（retrieval.py 重构=独立立项）、F10（工具取消机制=超范围）、F12（覆盖缺口=4 项待补测试） |
| 谜题关闭 | 1 | F13（§2.1：`fired_absent=0`，49 条 MISS 全是 `not_fired`——触发信号错位） |
| 无需动作 | 1 | F11（测试期望独立性） |

**为什么这样做**：
T8 改了 4 个候选文件 + 新增 11 个测试，是一次较大规模的代码改动。在交付前不做深度审查，就无法发现"代理结论是否可信"、"是否有同族缺口被遗漏"、"修复环是否真的接线"。审查的**正向确认**也很重要：无界循环已硬化、并发 _save 有 CAS 保护、_OWNERSHIP_FIELDS 无缺口、三处 deficient 口径已真收敛单一谓词、auth UTC 删除全仓安全。

### 2.4 F12 覆盖缺口补测（2026-09-11 14:00–15:00）

**做了什么**：
在 `backend/tests/test_agent_controller.py` 追加 5 个测试（4 覆盖缺口 + 1 正向对照），覆盖：
- `_deterministic_finish_gate` 第三象限（MISSING_FACT + 并非每 issue 都有证据 → None）
- `_handle_evaluation` 未知 outcome（FAIL_SAFE）→ fail-closed 失败
- `_handle_evaluation` BudgetExceeded → `_persist_budget_stop`（降级）
- backfill 分支的 checkpoint reason 落盘断言

**为什么这样做**：
深度审查 F12 列了 4 项测试覆盖缺口，其中第三象限正是今日 AssertionError 修复所依赖的**不变式**。如果这个不变式没有被测试钉住，未来重构可能会无意中破坏它。补测是**防御性投资**——成本极低（5 个测试 + 15 分钟），但能防止未来回归。

### 2.5 独立验收复核回执处置（§12.14）

**做了什么**：
独立会话"千问工作助理"对验收包做了只读复核（自建 11 个只读脚本），回执判定 10 项声明中 6 项成立、2 项成立但有数值偏差、1 项失败、1 项悬置，另报 1 项超范围风险。

实现者逐条处置：
- A1"新增候选文件 0"失败 → **接受**（该值是验收包凭记忆填写的错值；算术自证：T7=17、T8=139、T7⊆T8 ⇒ added=122）
- A7 数值不符 → **接受**（901 采集于新增测试之前；901+17=918=当时全量数）
- §D.1 裁决 → ruff `UP017` 自动修复产生了语义改动（`auth.py`：`UTC = timezone.utc` → `from datetime import UTC`），不是纯格式化；但部署为 3.11（`Dockerfile` = `FROM python:3.11-slim`），不会生产崩溃；过期的是注释

**为什么这样做**：
独立验收是执行书 T7 的前置要求（§5.5）。虽然替代性核查不满足"真第三方"独立性，但回执的**正向确认**提供了增量证据——30 条记录中 steps↔issues 严格线性（1→9 … 5→19），印证"8 争点逼近 29 步上限"的边界提醒。

---

## §3 为什么这样做——决策树与纪律

### 3.1 「不 commit」是 T0 候选定义的核心

T0 manifest 原文：「W1–W4 脏改动就地保留，未 commit、未 stash、未 reset」。
即本项目**用"脏工作树 + 哈希锚定"定义候选**。**提交反而会破坏候选定义**（clean 树后，T7 要求的"记录它与旧候选的差异"失去比较基准，所有锚定对象也改变）。

**要动工作树之前，先确认 patch 备份还在。禁止 `git add` / `stash` / `checkout .` / `reset`。**

### 3.2 「T8 目标改为分解契约加固」是根因驱动的决策

执行书原 T8 表述「仅在新证据证明必要时启动真检索修复」。本轮新证据**不支持**指向真检索——**检索器不是瓶颈**（C02 是唯一分解达标题，检索 4/4 全中，`tool_result` 全 `TOOL_SUCCEEDED`）。

⇒ **建议把 T8 目标改为「分解契约加固」**：① 穷尽性契约；② 确定性完备性检查；③ 修复环（planner 已有回喂修正 `71e5f23`，分解失败现为终态）。

代价：改 `runtime.py`（候选文件）⇒ 重采锚定 + 重跑 903 + 重验冻结物。

### 3.3 「深度审查推翻代理 2 条结论」是不盲信代理的纪律

- F4「review_sidecar.py + 测试可删」→ **推翻**：它是 **T1 工单的正式交付物**（R1–R12 复核 sidecar 校验器/聚合器，handoff ✅ VERIFIED、16 项测试）。引用搜索没错，但"无代码消费方"≠死代码——它是流程能力。**保留**；若 sidecar 流程永不落地，未来可降级为可删
- F7「run_evidence.py 仅测试消费，与 docstring 不符」→ **事实更正**：代理只搜了 backend/——dispatch-output 的 4 个审计/对照脚本都在 import 它。docstring 已补真实消费方清单

### 3.4 「F9 修复第一版自带 SyntaxError」是 linter 绿 ≠ 语法正确的教训

F9 的修复**第一版自带 SyntaxError**（同一函数内对同名 `global` 声明了两次 ⇒ `name 'CASES' is used prior to global declaration`），导致 2 个测试文件收集失败、全量跑不起来。

**ruff 竟然全绿没报**——是 pytest 收集期抓到的。已改为单次 `global` 声明置于分支之前。

两条教训：① "linter 绿"不等于"语法正确"，**收集期/导入期错误要靠跑套件暴露**；② 审查报告若在修复后不重跑全量，就会把带 SyntaxError 的"修复"当成交付。

### 3.5 「预算上限 3→6」是一版被测试拦下的错设计

- **第一版**：让 `AgentController` 在快照 budgets 时**按实际分解规模**自适应（`max(settings, 7+2×实际争点数+3)`）。
- **被拦下**：`test_step_preflight_stops_before_gateway_when_three_checkpoints_do_not_fit` 故意设 `max_steps=3`，验证"预算不足时必须**先于网关**停机"；而自适应把它抬到 12 ⇒ **调用方显式给的硬上限被无声覆盖**。这**不是断言过时，是设计越权**（删掉该行为后测试自行恢复通过）。
- **改为**：由装配层按 `_MAX_ISSUES`(=8) 求**恒定下限** `7 + 2×8 + 6 = 29`，与 settings 的算子下限取大。三个好处：① **上限恒定** ⇒ 不随 run 变化，`budget_snapshot` 保持跨 run 可比；② **不覆盖调用方显式预算**（controller 语义不变）；③ **不动 settings 的批准值 16**（它是算子下限，由装配层保证不低于工作量需求）。
- `max_tool_calls` **同步抬高 10 → 11**：8 争点要 8 次检索，默认 10 只剩 2 次余量 —— 只抬 `max_steps` 会在**下一个天花板**上撞回来。
- **生产实测**：`settings.agent_max_steps=16` → **生效 29**；5 争点需求 17 步 ⇒ 装得下 ✅

---

## §4 后续还打算做什么

### 4.1 🔴 最高优先级：LongCat 域全量 run-13（T7 原定交付物）

**为什么**：交接文档 §12.7 明确「LongCat 域的全量 run-13（T7 原定交付物）**仍缺**」。当前只有 qwen3.8-flash 域的 run-13 数据，而 LongCat 域是 T7 的原始验收载体。

**怎么做**：
```bash
cd backend
AGENT_ENABLED=true ./venv/Scripts/python.exe -m uvicorn main:app --host 127.0.0.1 --port 8001
./venv/Scripts/python.exe scripts/gate2_runner.py --run gate5-dev-run-13 --all --base-url http://127.0.0.1:8001
./venv/Scripts/python.exe scripts/gate5_judge.py ../release-evidence/legal-agent-v1-complex-v1-20260907/gate2-run-gate5-dev-run-13-sessions.json
```

**判据**：`errors` 里不再出现 `EVIDENCE_COVERAGE_DEFICIENT`，且 observations 覆盖全部 4 个 issue。

**⚠️ 注意**：C01 缺陷的触发条件 = `issue 数 > 澄清预算(2) + 1`，即 ≥4。判定前必须先确认该次 run 的 issue 数 ≥ 4（读 `backend/app.db` 的 `agent_runs.state_json`）。

### 4.2 🟡 次高优先级：F13 rework（case 级注入 + 上限 + 存活探针）

**为什么**：深度审查 §2.1 谜题已破——`fired_absent = 0`，管线无罪；49 条 EVIDENCE_MISS 全部是 `not_fired`（触发信号错位：挂在 LLM 的 issue 问句上，关键词却是用户口语）。parked 实验的复活路径已明确。

**怎么做**：
1. case 级注入（`bootstrap.user_text` 预计算 → `ToolContext` 下发）
2. 每 issue 注入上限
3. 存活探针
4. 重复轮次排除随机性

**是否重启实验：Owner 拍板**（`supplement-survival-probe.py` / `supplement-survival-probe.txt` 留痕）。

### 4.3 🟡 中优先级：F2 snippet 信任模型（数字/引用白名单）

**为什么**：深度审查 F2 记录为信任假设——writer 把证据 `snippet` 当数字/引文的可信源，投毒语料中的数字/法条可被洗白进终稿（内容完整性缺口；越权防御线完好）。修复 = 数字白名单，牵动 RAG 信任模型，属独立课题。

### 4.4 🟡 中优先级：F8 retrieval.py 重构（1,065 行三处 lazy-cache 重复）

**为什么**：深度审查 F8 只评估不动——retrieval.py 1,065 行、本轮未大改，重构属独立立项，混入审查会不可归因。与 parked supplement 子系统形态重叠。

### 4.5 🟢 低优先级：F10 工具取消机制（跨工具栈）

**为什么**：深度审查 F10 记录为已知限制——`BoundedExecutor` 超时 `future.cancel()` 无法中止运行中的同步工具，副作用在调用方收到 TOOL_TIMEOUT 后才完成。真正的修复 = 全工具栈取消机制，超范围；现有工具副作用轻。

### 4.6 🟢 低优先级：可清理的留痕

- `dispatch-output/t2-persistence-20260910/supplement-survival-probe.py` / `.txt`：F13 谜题留痕，谜题已破，**可删**
- `candidate-pre-waxis.patch`（9343 行）：回退备份，**可删**（如果你确认不再回退）

---

## §5 终态验证状态

| 项 | 结果 |
|---|---|
| 全量 `pytest tests/` | **939 / 0 failed / 0 errors / 0 skipped**（T7 基线 903 → 939，净增 36 项） |
| 门禁 | ruff check / ruff format --check / mypy 对全部改动文件绿 |
| 锚定 | 重采 141 候选文件，复算 **154 文件 0 漂移**；冻结漂移 0 |
| 备份 | `candidate-pre-waxis.patch`（9343 行）可整体回退 |
| F12 补测 | 5 个测试（4 覆盖缺口 + 1 正向对照），全绿 |

---

## §6 遗留清单（不修的理由）

1. **F2 snippet 信任**：修复 = 数字/引用白名单，牵动 RAG 信任模型 —— 独立课题。
2. **F8 retrieval.py 重构**：1,065 行、本轮未大改 —— 独立立项。
3. **F10 工具取消机制**：跨工具栈 —— 独立立项。
4. **F12 覆盖缺口**：4 项待补测试（优先：`_deterministic_finish_gate` 第三象限——今日 AssertionError 修复所依赖的不变式）。
5. **F13 rework**：case 级注入 + 上限 + 存活探针 + 重复轮次 —— Owner 拍板后按关卡 2 重验。

---

## §7 自检清单

- [x] `git log --oneline -3` + `git status --short` 已确认（HEAD 仍为 `ebe82e2`？脏改动还在？）—— HEAD=`ebe82e2`，264 文件变更
- [x] 候选备份在位（`candidate-pre-waxis.patch` 可 `--reverse --check`）
- [x] **未执行 commit / stash / checkout / reset**
- [x] 候选锚定与当前工作树一致（`candidate-manifest-t8-20260910.json`，154 文件 0 漂移）
- [x] 冻结物已用 `verify_frozen_for_handoff.py` 复核（期望 16 一致 / 4 知情变化）
- [ ] 服务已启动且 `/healthz` 就绪（agent_enabled=true，端口 8001）—— **未执行**
- [x] 全量 `pytest tests/` **本次运行** 0 failed（939 passed）
- [x] C01 探针已跑，且**只按 §6.3 判据**核对（probe-c01-verify2-20260910）
- [x] 新 run 用 `gate5-dev-run-13`，**未跑 `gate2-run-12`**
- [x] run-12 的 claim/checkpoint **原样保留**
- [x] 失败/unknown 题全部保留；unknown 类**未经人工确认不得重跑**
- [x] 报告完整无缺题；有缺题则标 PARTIAL（**不能换分母**）
- [x] **独立验收者检查已完成或已由 Owner 明确豁免**（执行书 T7 前置；本次未做，见 §5.5）
- [x] **未宣布生产级质量或统计显著提升**
- [x] 每个判定结论都有 sessions json / DB / 日志作为可复算证据链

---

## §8 产物索引

**本轮（2026-09-11）新增** —— `dispatch-output/t2-persistence-20260910/`

| 文件 | 用途 |
|---|---|
| `deep-review-plan-20260911.md` | 深度审查方案书（四层分级 + 五轴） |
| `deep-review-report-20260911.md` | 深度审查报告（13 项发现 + 1 谜题） |
| `supplement-survival-probe.py` / `.txt` | F13 谜题留痕（谜题已破，可删） |
| `progress-handoff-20260911.md` | **本文**（工作进度交接文档） |

**上一轮（2026-09-10）** —— `dispatch-output/t2-persistence-20260910/`

| 文件 | 用途 |
|---|---|
| `candidate-manifest-t8-20260910.json` / `.md` | **候选哈希锚定（以此为准）** |
| `t7-run13-manifest.json` | run-13 预登记记录 |
| `candidate-post-c01fix.patch` | 可恢复备份（C01 修复后） |
| `untracked-backup/` | 4 个未跟踪源码副本 |

**文档**：`docs/handoff-20260910.md`（**上一阶段交接，753 行**）、`docs/agent-architecture-audit-and-execution-plan-20260909.md`（**执行书，第一优先级**）、`docs/agent-implementation-coaching-20260909.md`（教学手册）。

---

## §9 边界与修订史

**本文中"已实测"的结论**（候选哈希锚定、冻结物哈希、全量测试 939 passed、F12 补测 5 个测试全绿）均为**本次会话亲自跑出来/读出来的**，留有脚本与原始输出。

**未由本次复算**：`full_closure`（付费语义层，按纪律未跑）；T1–T6 的实现细节（§2 为过程日志摘要，未逐行复核代码；方法名已 grep 抽查存在于所声称的文件）。

**修订史**：
- 第 1 轮：实测补充/判据修正/两条新缺陷
- 第 2 轮：§12.7 换 qwen 域重登记 + run-13
- 第 3 轮：§12.8 双臂 A/B + 两个口径坑
- 第 4 轮：§12.9 T7 验收报告 + 因果链 + T8 指向修正
- 第 5 轮：§12.10 T8 代码加固 + 重采锚定
- 第 6 轮：§12.11 T8 验证轮结果 + 第二个同族缺口 + 判据设计教训
- 第 7 轮：§12.12 自审（AST 哨兵抓 4 处 + 我代码 2 个缺陷）+ 第三处修复环 + Pareto 规则 + 常驻哨兵
- 第 8 轮：§12.13 收尾改动验证轮（修复环实测生效、争点 32→37、对照工具两个 bug 与独立核实）
- 第 9 轮：§12.14 独立验收回执处置（验收包 3 处错值更正、judge 产物落盘、§D.1 裁决与三教训）
- 第 10 轮：**本文**（2026-09-11 工作进度交接文档，含 F12 补测 5 个测试全绿、939 passed 终态）

**若发现本文与事实不符，以代码、sessions JSON 与 `candidate-manifest-t8-20260910.json` 为准。**
