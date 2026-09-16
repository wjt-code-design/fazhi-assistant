# run-5 coverage 失败深挖（2026-09-08，只读分析）

> 数据源：`release-evidence/legal-agent-v1-complex-v1-20260907/gate2-run-gate5-dev-run-5-sessions.json`（只读，无修改）
> 目的：为"EVIDENCE_COVERAGE_DEFICIENT 的 feedback reason 码细化"提供输入（附 D 已知：reason 码仍太粗，未指明缺哪个 issue/为何缺）。

## run-5 失败分布（10 题）

| case | error_codes | answered_fact_ids | unknown | final_chars |
|---|---|---|---|---|
| C01 | EVIDENCE_COVERAGE_DEFICIENT | 1 | 1 | 0 |
| C02 | ISSUE_DECOMPOSITION_INVALID | 0 | 0 | 0 |
| C03 | CROSS_ISSUE_EVIDENCE | 0 | 2 | 0 |
| C04 | PLANNER_PARSE_ERROR | 0 | 2 | 905* |
| C05 | EVIDENCE_COVERAGE_DEFICIENT | 1 | 1 | 0 |
| C06 | EVIDENCE_COVERAGE_DEFICIENT | 5 | 0 | 0 |
| C07 | PLANNER_PARSE_ERROR | 1 | 1 | 743* |
| C08 | EVIDENCE_COVERAGE_DEFICIENT | 4 | 0 | 0 |
| C09 | EVIDENCE_COVERAGE_DEFICIENT | 2 | 0 | 0 |
| C10 | EVIDENCE_COVERAGE_DEFICIENT | 0 | 2 | 0 |

（*C04/C07 final_chars>0 为 fail-closed 前已流出的部分内容，error 仍判负。）

## 核心发现：coverage 失败可分为两类

**A 类 · 事实缺口型**（unknown>0 或未答全，缺口直观）：C01、C05、C10
- 追问方向本身合理（工龄/平均工资、租金宽限期、立案标准/履行地），但用户侧事实未提供或未投放 → coverage 落空。
- 这类是"预期可由用户补充解决"的缺口，机制上无需改模型，只需确认投放协议（审查侧 A1 已指出的协议错位同类）。

**B 类 · 事实补全仍失败型**（answered≥2 且 unknown=0，仍 EVIDENCE_COVERAGE_DEFICIENT）：C06、C08、C09
- 关键事实已全部/大部分由用户补充，仍判定证据覆盖不足 → 失败不在"缺失事实"，而在：
  1. **检索召回**：frozen required_laws 未被召回（session json 无检索命中明细，需服务端日志佐证），或
  2. **writer 生成**：draft claim 未逐 issue 绑定证据（观察/claim 覆盖不全），或
  3. **verifier 校验**：确定性判定判定某 issue 无足够证据（r-spam/绑定失败）。
- 该类是 run-5 中 6/10 coverage 的主要构成，与附 D 结论一致：`planner 稳定后更多题推进到 writer/verifier 层，coverage 突起为主失败面`。

## 对下一步（feedback reason 码细化）的输入

- 细化落点：EVIDENCE_COVERAGE_DEFICIENT 产生时，服务端需携带"缺哪个 issue 的什么证据 + 检索候选命中情况（哪些法条被召回/未召回）"，理由再回喂 writer，使回喂从"你错了"变成"你缺 issue-X 的《Y》法第 Z 条证据"。
- 实施前置：本结论基于 sessions json；检索命中/verifier 判定明细需服务端 ai_runs 记录/日志导出后核验（run-6 正在运行，服务日志占用中，**导出排期到 run-6 结束后**）。
- 不在 run-6 期间改码（run-6 = LongCat-2.0 + 错误回喂基线验证，需保证代码冻结）。

## 边界声明

- 本深挖仅基于 run-5 sessions json 的公开字段；"检索未召回/verifier 判定"为结构性推断（B 类逻辑排除法），**非现场取证**，待服务端日志导出后复核。