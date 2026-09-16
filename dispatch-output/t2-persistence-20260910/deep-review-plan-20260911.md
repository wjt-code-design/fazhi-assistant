# 深度代码审查执行方案书 —— 今日累积候选全量审查（2026-09-10/11）

> 对象：本会话自 T0 起累积的全部候选改动（锚定 141 文件；实质逻辑 ~6,200 行 + 测试）
> 原则：冻结物零接触 · 离线零付费（除非深潜发现必须实测的边界，预登记后单独请示）· 每个发现带复算命令

---

## §1 分层与深度分配（按"变更风险 × 逻辑密度"分四层）

| 层 | 文件（行数） | 深度 | 理由 |
|---|---|---|---|
| **L1 深潜**（逐行 + 定向探针） | controller.py(1002) runtime.py(920) service.py(573) writer.py(649) | 逐行读 + 状态机/预算/修复环边界推演 | T8 核心，全部是本轮语义改动；已知出过 1 个真 bug（fall-through）与 1 个未解之谜（§2.1） |
| **L2 中度** | domain_rules.py(578) legal_retrieval.py(39) gateway.py(269) gate2_runner.py(460) run_evidence.py(111) observability.py(174) | 结构审查 + 关键分支 | 今日新增/修改；映射表刚回退、状态微妙 |
| **L3 广度**（机械 + 模式） | retrieval.py(1065，T8 未大改) tests/（933 项） dispatch-output 审计脚本 | AST/模式扫描 + 抽样 | 大文件但变更少；测试审查聚焦"期望独立性/覆盖缺口"而非逐行 |
| **L0 冻结物** | verifier/chat_integration/state_machine/repository/prompts/gate5_judge + frozen-*/hidden-* | 只核对哈希，**不审内容不改一字** | 红线 |

## §2 五条审查轴

### 轴 1 · 正确性深潜（含 1 个未解之谜，systematic-debugging 全流程）
- **§2.1 未解之谜 —— ✅ 已破（2026-09-11 00:45，探针 `supplement_survival_probe.py` / `supplement-survival-probe.txt`）**：
  - **`fired_absent = 0`**：凡按映射表触发的法条，全部活着进入 state.evidence（`map_document` 存活 4/4；管线无罪）。
  - 49 条 EVIDENCE_MISS **全部 = `not_fired`**：注入的触发信号挂在 **LLM 生成的 issue 问句**上，而问句是法律抽象改写（"未签订书面劳动合同"≠ 触发词"未签合同"），关键词表却是按**用户口语**调的 ⇒ 信号错位。
  - **结论**：不是 map_document 的坑，是**触发层设计错误**。修复方向 = 场景补充改为 **case 级**（从 `bootstrap.user_text` 预计算，经 `ToolContext` 下发到 retrieve_laws），并保留首轮的 payload 膨胀守卫（每 issue 注入上限 + 重复轮次）。**这是架构性 rework，不是小补丁——是否重启该实验，待审查结果后由 Owner 拍板。**
- controller 状态机边界：`_drive`/`_handle_evaluation` 的每个分支终态、C01 强制扇出与 `_persist_budget_stop` 的交互、resume 路径的 `pending_target`。
- runtime 修复环与预算边界：`_fit_budgets_to_max_decomposition` 与 `_messages(repair=...)` 的组合行为、schema-fallback 与修复环的交互次序。
- writer：`build_writer_payload` 的完整性校验（STATE_INTEGRITY_FAILURE 抛错面）、`_render_once` 失败路径、`coverage_feedback_payload` 与 verifier 口径一致性（今日已抽 `issue_is_deficient`，复核三处口径是否真同源）。

### 轴 2 · 死代码 / 冗余（已侦察到的候选）
- **`scripts/review_sidecar.py` + `tests/test_review_sidecar.py`**：全仓无消费方（grep 证实）——T6 遗留？确认后删。
- **`domain_rules._STATUTE_SUPPLEMENT_TABLE` + `statute_supplement_docs`（暂存未接线）**：按我方标准属"未接线死代码"，但它是带完整失败记录的 parked 实验 —— **处置需拍板**（删 / 留待重做），见 grill Q1。
- `legal_retrieval.py` 的 17 行回退历史注释：代码里不该背历史——移入 handoff/审计文档。
- 跨文件重复模式扫描（AST 级）+ 未使用导出。

### 轴 3 · 质量优化
- 复杂度热点：controller 1002 行 / writer 649 行是否该拆（**本轮只评估不动**——拆分是独立立项，混进审查会造成不可归因）。
- 命名/语义误导、异常吞噬（`except Exception` 面扫描——今日 C01 教训：裸 except 会把无界伪装成有界）。
- 日志可诊断性：新增失败路径是否都带归因字段（B5 哨兵已管白名单，这里查"该记没记"）。

### 轴 4 · 安全
- `auth.py`：今日改过（UTC 注释 + 删别名）——JWT 过期/算法/时序比较复核。
- **prompt 注入面**：writer/planner 声称"输入仅是数据"——检索证据里若含指令性文本（KB 被污染/用户上传），防线在哪？
- tool gateway：`_OWNERSHIP_FIELDS` 所有权校验的覆盖面（resume/注入路径）。

### 轴 5 · 测试质量抽查（L3）
- 期望独立性（CONTRIBUTING 红线：不复算实现）——AST 抽查今日新增测试。
- 覆盖缺口：今日改动的分支哪些没有测试（对照 diff）。

## §3 方法

1. **双并行子代理**（复用已验证的 code-review 双轴模式）：A = L1 深潜 + 轴1/轴4；B = L2/L3 + 轴2/轴3/轴5。我聚合去重、定级、逐条验证（不盲信子代理——今日教训：审查报告也会有错条目）。
2. **定向探针**：离线（本地 KB / 内存 DB），零 LLM 付费。
3. 每个发现：🔴/🟡/💭 分级 + 文件:行 + 复算命令 + 修复带 watch-it-fail。

## §4 修复策略（待 grill 对齐）

- 🔴 正确性/安全：即修 + 测试
- 🟡 死代码：**已确认无消费方即删**（git patch 可回退）；**parked 实验除外**（Q1 拍板）
- 🟡 质量重构（如拆 controller）：**只评估出清单，不动**（独立立项）
- 💭：批量
- 收尾：全量 ≥933 全绿 + 三道门禁 + 冻结漂移 0 + 重锚定

## §5 产出物

审计报告（发现清单 × 分级 × 处置状态 × 复算命令）、修复 diff、重锚定 manifest、未解之谜根因报告（若 §2.1 有结论）。

## §6 明确不做

- 不做付费验证轮（深潜全部离线）
- 不拆 controller/writer（只出评估清单）
- 不碰冻结物、不动评测口径、不把 parked 实验悄悄接线
