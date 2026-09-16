# 深度代码审查报告 —— 今日累积候选（2026-09-11 00:30–01:10）

> 方案：`deep-review-plan-20260911.md`（经 grill 对齐：parked 实验保留待谜题解；工具脚本"活跃深审 + 回执抽查"；🔴/🟡 即修、质量重构只评估）
> 方法：双并行只读子代理（L1 深潜 / L2-L3 死代码与质量）+ 实现者逐条验证聚合（**不盲信代理**——本轮聚合中推翻 1 条 🔴、更正 1 条事实）+ 实现者亲攻未解之谜
> 范围：今日候选 141 文件（L1 深潜 3,144 行 / L2 中度 / L3 广度），冻结物零接触，全程零付费

---

## §1 发现总表（12 项 + 1 谜题）

| # | 级别 | 来源 | 发现 | 处置 |
|---|---|---|---|---|
| F1 | 🟡 | L1 深潜（确证） | `runtime.decompose_with_fact_repair` 的 Pareto 采纳准则未排除 `non_verbatim`——残留非逐字引用的候选（下游必死）会被采纳并打误导性 `repaired` 日志 | **已修**：新准则"先可存活（nv 清零）再改进"；补判别性回归测试（判别点=日志 stage，见 §3.1） |
| F2 | 🟡 | L1 深潜（疑似） | writer 把证据 `snippet` 当数字/引文的可信源——投毒语料中的数字/法条可被洗白进终稿（内容完整性缺口；越权防御线完好） | **记录为信任假设**（RAG 固有；修复=数字白名单，属独立课题，写入 §4 遗留） |
| F3 | 💭 | L1 深潜 | controller 两处注释把 "297 次" 写成"边界实测"——实为当年 `if n>300` 阈值探针的**假象**（真实行为无界） | **已修**：两处注释据 handoff C01 节更正（探针不得自带阈值的教训即源于此） |
| F4 | 🔴→**不采纳** | L2/L3 | "review_sidecar.py + 测试可删（全仓无消费方）" | **推翻**：它是 **T1 工单的正式交付物**（R1–R12 复核 sidecar 校验器/聚合器，handoff ✅ VERIFIED、16 项测试）。引用搜索没错，但"无代码消费方"≠死代码——它是流程能力。**保留**；若 sidecar 流程永不落地，未来可降级为可删 |
| F5 | 🟡 | L2/L3 | `_STATUTE_SUPPLEMENT_TABLE` 跨块法条重复（劳动合同法46/47、民法典577 各出现两次） | **处置：有意设计**——各块需自洽（单关键词命中即得该场景完整要件），注入侧 `seen` 去重保证不重复；已加注释说明，避免后人"修复"它反而丢场景覆盖 |
| F6 | 💭 | L2/L3 | legal_retrieval 回退注释块证据齐全（三个证据文件均在） | 保留原样 |
| F7 | 🟡→**事实更正** | L2/L3 | "run_evidence.py 仅测试消费，与 docstring 不符" | **代理只搜了 backend/**——dispatch-output 的 4 个审计/对照脚本都在 import 它。docstring 已补真实消费方清单 |
| F8 | 🟡 | L2/L3 | retrieval.py（1065 行）三处 lazy-cache 模式重复；与 parked supplement 子系统形态重叠 | **只评估不动**（本轮未大改该文件；重构属独立立项，混入审查会不可归因） |
| F9 | 🟡 | L2/L3 | `gate2_runner --cases-file` 全局重绑后**不恢复默认**：同进程二次 run() 不带该参数会沿用陈旧题集 | **已修**：加载默认题集快照 `_DEFAULT_CASES/_DEFAULT_BY_ID`，不带参数时恢复 |
| F10 | 🟡 | L2/L3 | `BoundedExecutor` 超时 `future.cancel()` 无法中止运行中的同步工具——副作用在调用方收到 TOOL_TIMEOUT 后才完成 | **记录为已知限制**（真正的修复=全工具栈取消机制，超范围；现有工具副作用轻） |
| F11 | 🟢 | L2/L3 | 测试期望独立性：今日修过的两处无同类残留，四文件无"复算实现" | 无需动作 |
| F12 | 🟡 | L2/L3 | 覆盖缺口：`_handle_evaluation` 未知-outcome 分支与 `BudgetExceeded→_persist_budget_stop`、`_deterministic_finish_gate` 第三象限（MISSING_FACT+耗尽+某题无证据→None）、backfill 的 checkpoint reason | **记录为待补**（需 controller fixture 深入，列 §4；其中第三象限正是今日 AssertionError 修复所依赖的不变式，优先级最高） |
| **F13** | **🟡→谜题已破** | 实现者亲攻 | **§2.1**：首轮映射注入"触发了却没进证据"之谜 —— **真相：`fired_absent = 0`，管线无罪；49 条 EVIDENCE_MISS 全部是 `not_fired`（触发信号错位：挂在 LLM 的 issue 问句上，关键词却是用户口语）** | parked 实验的复活路径已明确：**case 级注入**（`bootstrap.user_text` 预计算 → `ToolContext` 下发）+ 每 issue 注入上限 + 存活探针。**是否重启实验：Owner 拍板**（`supplement-survival-probe.py` / `supplement-survival-probe.txt` 留痕） |

**L1 的正向确认（查过无发现）**：无界循环已硬化（seed 保证 attempted → backfill 不可自激）；并发 `_save` 有 CAS 保护；`_OWNERSHIP_FIELDS` 无缺口（所有工具输入 `extra="forbid"`）；三处 deficient 口径已真收敛单一谓词；`_handle_evaluation` 无 fall-through None；auth UTC 删除全仓安全。

## §2 处置统计

- **已修代码**：3 项（F1 准则 + 判别性测试；F3 注释×2；F9 默认题集恢复）
- **文档修正**：2 项（F7 消费方；F5 设计意图注释）
- **推翻代理结论**：2 项（F4 删除建议、F7 事实）—— 均经实现者独立查证
- **记录不修**：4 项（F2/F8/F10/F12，各有理由）
- **谜题关闭**：1 项（F13，含复活路径）

## §3 修复明细

### 3.1 F1 —— Pareto 采纳准则（runtime.py）
旧：`nv↓ and unc↓ and total 严格变小` ⇒ 可采纳 {nv:1,unc:1}→{nv:1,unc:0}（仍必死）。
新：`viable（nv 清零） and coverage_ok（unc 不变大） and strictly_better（unc 严格变少 或 修掉了致命 nv）`。
**判别点在日志 stage**：新旧准则下组装期都抛同样的 verbatim 错（表象相同），唯一可判别的是
`repaired`（旧，假象）vs `repair_ineffective`（新）——回归测试即断言于此。

### 3.2 F9 —— 题集全局重绑（gate2_runner.py）
`_DEFAULT_CASES/_DEFAULT_BY_ID` 快照 + 不带 `--cases-file` 时恢复，防同进程二次 run() 沿用陈旧题集。

### 3.3 F3 —— "297" 注释（controller.py ×2）
据 handoff C01 节更正为"阈值探针误报（`if n>300: raise` 的人为上限），真实行为无界"。

## §4 遗留清单（不修的理由）

1. **F2 snippet 信任**：修复 = 数字/引用白名单，牵动 RAG 信任模型 —— 独立课题。
2. **F8 retrieval.py 重构**：1,065 行、本轮未大改 —— 独立立项。
3. **F10 工具取消机制**：跨工具栈 —— 独立立项。
4. **F12 覆盖缺口**：4 项待补测试（优先：`_deterministic_finish_gate` 第三象限——今日 AssertionError 修复所依赖的不变式）。
5. **F13 rework**：case 级注入 + 上限 + 存活探针 + 重复轮次 —— Owner 拍板后按关卡 2 重验。

## §5 验证状态

- **终版全量：934 / 0 failed / 0 errors / 0 skipped**（`review-final-junit.xml`；含 1 项新增判别性回归测试）
- 门禁：ruff check / ruff format --check / mypy 对全部改动文件绿
- 锚定：重采 141 候选文件，复算 **154 文件 0 漂移**；冻结漂移 0；备份 `candidate-pre-waxis.patch`（9343 行）可整体回退

### §5.1 实现者自吞的教训（如实记）

F9 的修复**第一版自带 SyntaxError**（同一函数内对同名 `global` 声明了两次 ⇒
`name 'CASES' is used prior to global declaration`），导致 2 个测试文件收集失败、全量跑不起来。
**ruff 竟然全绿没报**——是 pytest 收集期抓到的。已改为单次 `global` 声明置于分支之前。
两条教训：① "linter 绿"不等于"语法正确"，**收集期/导入期错误要靠跑套件暴露**；
② 审查报告若在修复后不重跑全量，就会把带 SyntaxError 的"修复"当成交付。
