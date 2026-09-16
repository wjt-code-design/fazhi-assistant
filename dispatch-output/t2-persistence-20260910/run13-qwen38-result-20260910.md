# run-13 结果记录 —— `gate5-dev-run-13-qwen38`（qwen3.8-flash 域）— 2026-09-10

> **本轮目标已如实重定**：建立 qwen3.8-flash 域的失败分布基线。
> **本轮不构成 C01 修复的验证**（该验证已在 LongCat 域完成并存档，见 §6）。
> **本轮不得与 run-8/9/10/11 的 LongCat 基线并列对照。**

## 1. 运行参数

| 项 | 值 |
|---|---|
| run 名 | `gate5-dev-run-13-qwen38`（换模型后重登记；pre-registration 见 `t7-run13-manifest-v2-qwen38.json`） |
| 模型 | `qwen3.8-flash`（provider=dashscope / 阿里云百炼 compatible-mode），单 entry 全链 |
| 服务 | `main:app` @ `127.0.0.1:8001`，`AGENT_ENABLED=true`（非付费哨兵验证）、`AGENT_MAX_STEPS=16` |
| 环境 | `NO_PROXY=127.0.0.1,localhost`（绕沙箱代理，见 handoff §12.5） |
| 耗时 | **5m40s / 10 题**（对比 LongCat 单题 2m25s） |
| 产物 | `release-evidence/legal-agent-v1-complex-v1-20260907/gate2-run-gate5-dev-run-13-qwen38-sessions.json` |

## 2. 题级结果（sessions JSON，10/10 完整，无缺题）

| 题 | rounds | clar | error_codes | final_chars | agent_completed |
|---|---|---|---|---|---|
| C01 | 3 | 2 | — | 404 | ✅ |
| C02 | 3 | 2 | `EVIDENCE_COVERAGE_DEFICIENT` | 0 | ❌ |
| C03 | 3 | 2 | — | 790 | ✅ |
| C04 | 3 | 2 | `UNSUPPORTED_NUMERIC_TOKEN` | 0 | ❌ |
| C05 | 3 | 2 | — | 331 | ✅ |
| C06 | 3 | 2 | — | 667 | ✅ |
| C07 | 3 | 2 | — | 556 | ✅ |
| C08 | 3 | 2 | `UNSUPPORTED_NUMERIC_TOKEN` | 0 | ❌ |
| C09 | 3 | 2 | — | 529 | ✅ |
| C10 | 3 | 2 | — | 293 | ✅ |

- **10/10 题都走了 2 轮澄清**（`clar_rounds=2`）：澄清预算每轮都被用满。
- `has_final`（`final_chars>0`）= **7/10**；`agent_completed` = **7/10**。

## 3. 两层 judge（冻结判分器 `gate5_judge.py`）

```
mechanical_pass_count = 7
full_closure_pass_count = 0      full_closure_denominator = 10
formal_gate_passed = False
```

- 每题均 `missing=[必需要件法条...]`、`redline=NOT_PROVEN`、多数 `unbound=1`。
- 仅 C07 有 `R8hint=True`。
- **不得把原始 `full_closure` 改成新指标、把 REVIEW 自动置 PASS**（执行书 F2 红线）。

## 4. ⭐ 本轮最重要的发现：qwen 域下**分解塌缩**（分解质量主导）

逐题 issue 数（读 `app.db` 的 `agent_runs.state_json`）：

| 题 | issues（实测） | frozen `required_issues` | backfill 触发 | tool_calls |
|---|---|---|---|---|
| C01 | **1** | 4 | no | 1 |
| **C02** | **4** | 4 | **YES** | 4 |
| C03 | 3 | 5 | no | 3 |
| C04 | 1 | — | no | 1 |
| C05 | 1 | — | no | 2 |
| C06 | 3 | — | no | 3 |
| C07 | 1 | — | no | 2 |
| C08 | 1 | — | no | 1 |
| C09 | 2 | — | no | 2 |
| C10 | 1 | — | no | 1 |

**issue 数分布 = `[1,1,1,1,1,1,2,3,3,4]`（中位数 1）**

三条推论：

1. **修复的触发条件（issue ≥4）在 qwen 域只出现 1/10 次**（仅 C02）⇒ 本轮**不能**作为 C01 修复的验证载体。
2. **分解塌缩本身成为 qwen 域的主导失败面**：issue=1 时检索面极窄 → 必需要件法条全部 `missing` → `full_closure=0/10`。
   这为 `docs/gate5-formal-dev-20260908.md` 的定性结论「qwen 替换只是把 LLM 质量失败**换了分布**」
   提供了**定量的机制解释**（旧证据只有 2 批×5 题的失败码表）。
3. **反直觉陷阱（必须写进报告）**：C01 在 qwen 域是 `completed` + `errors=[]` + 有终稿，**看似比 LongCat 域更好**，
   实际是题目被拆成 1 个 issue 导致失败面消失（`required_issues=4`）。**若只看 `errors` 与 `agent_completed`，会把退化读成改进。**

对照：同题在 LongCat 域分解出 3–4 个 issue（`probe-c01-verify2` = 4）。
`disable_thinking` 不是原因：qwen3.8-flash 关思维链 = 1 个 issue、开思维链 = 2 个。

**历史先例**：`docs/gate5-formal-dev-20260908.md:144` —— 「角色分流：**decomposer 保留 LongCat-2.0**；
planner 与 writer 按实验分档切换」。上一次切 qwen 时**特意未换 decomposer**；本轮观察与之吻合。

## 5. C02 的细节（唯一有效样本）

C02：`issues=4`、**4/4 全部有证据**、`backfill_retrieval` 已触发、`tool_calls=4`，
但**仍然 failed**（`EVIDENCE_COVERAGE_DEFICIENT`）。
⇒ 修复把"尾部 issue 未检索"这条链路切断了（4/4 覆盖），失败原因**迁移到 writer 引用不足**——
即 §7 定义的「`EVIDENCE_COVERAGE_DEFICIENT` = writer 没引用」，属执行书 **F5/T8** 的射程，**不是本修复的回归**。

## 6. C01 修复的验证状态（与本轮的边界）

| 模型域 | 载体 | 结论 |
|---|---|---|
| **LongCat-2.0** | `probe-c01-verify2-20260910` | ✅ **通过**：issues=4、4/4 覆盖、`backfill_retrieval` 指纹在案（见 `probe-c01-verify2-evidence-20260910.md`） |
| qwen3.8-flash | `probe-c01-qwen38-20260910` | ⚠️ **判为空过**：issues=**1**（<4）、backfill 未出现 ⇒ 触发条件未出现，不构成验证 |
| qwen3.8-flash | 本轮 run-13 的 C02 | 修复在该域**被执行且生效**（4/4 覆盖），但该题失败于另一条线路 |

## 7. 不得声称 / 未完成项

- **不声称**质量提升、不声称 `full_closure` 改善（实为 0/10）、不与 LongCat 基线并列对照。
- 未做：LongCat 域的全量 run-13（T7 原定交付物）——**本轮换模型后该产物仍缺**，需 Owner 决定是否用 LongCat 补齐。
- 未做：§5.5 第三方独立验收（仍缺，本轮只有替代性核查单）。
- 未做：现有待办共 6 项（handoff §12.3 诊断白名单 / F1 注释失真 / 谓词重复 / service.py catch-all / §5.5 / master 历史缺失对象），**均未修**（修则须重采锚定）。

## 8. 待 Owner 决定的分支

1. **是否用 LongCat 补跑 run-13**（T7 原定的可归因 LongCat 矩阵；C01 修复验证已单独取得）。
2. **是否把 qwen 的分解塌缩立项**（可能方向：decomposer 保持 LongCat 的角色分流——与历史先例一致；
   或调整 decomposer 提示词/结构化输出绑定以适配 qwen——后者改 `runtime.py`，**属候选改动，须重采锚定**）。
