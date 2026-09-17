# T8 改动集验证轮结果 —— `gate5-dev-run-14-qwen38-t8`

日期：2026-09-10 · 模型 `qwen3.8-flash` · 10 题 · 7m23s
对照基线：`gate5-dev-run-13-qwen38`（T7 轮，改动前；**同模型、同题集、同 runner，唯一变量 = 候选**）
预登记判据：`t8-validation-preregistration.json`（付费前冻结）

---

## 1. 主判据：争点覆盖 **18 → 32**（缺口 62% → 32%）

| case | 应有 | 改动前 issues | 改动后 issues | 改动前 steps | **改动后 steps** | 生效预算 |
|---|---|---|---|---|---|---|
| C01 | 4 | 1 | **4** | 9 | 16 | 16 → **26** |
| C02 | 4 | 4 | 3 | 16 | 13 | 16 → **26** |
| C03 | 5 | 3 | **4** | 13 | 16 | 16 → **26** |
| C04 | 5 | 1 | **4** | 9 | 16 | 16 → **26** |
| C05 | 5 | 1 | **4** | 11 | 16 | 16 → **26** |
| C06 | 5 | 3 | 无记录（预运行失败） | 13 | — | 16 → **26** |
| C07 | 5 | 1 | 1 | 11 | 11 | 16 → **26** |
| C08 | 5 | 1 | **5** | 9 | **19** | 16 → **26** |
| C09 | 5 | 2 | 3 | 11 | 13 | 16 → **26** |
| C10 | 4 | 1 | **4** | 9 | 16 | 16 → **26** |

**争点总数：18 → 32（应有 47）**；逐题缺口从"9/10 题欠分解"改善到 8/10 题 ≥3 个争点。

## 2. 预登记命题核验（逐条，含失败的那条）

| 命题 | 证伪条件 | 结果 |
|---|---|---|
| ① 契约加固提高争点覆盖 | 总数 ≤ 18 | ✅ **未被证伪**（32 > 18） |
| ② 预算修正使 5 争点题能跑完 | 无 `issues≥5` 且 completed | ✅ **未被证伪**：**C08 = 5 争点、19 步、completed** |
| ③ 覆盖度守卫生效 | 日志 `issue_decomposition_coverage` 触发 0 次 | ❌ **被证伪（但责任在我的判据设计）** —— 见 §4 |

## 3. 端到端结果：**未改善**（与预期一致）

| 指标 | 改动前 | 改动后 |
|---|---|---|
| `agent_completed` | 7/10 | **7/10** |
| judge `mechanical_pass_count` | 7 | **7** |
| judge `full_closure` | **0/10** | **0/10** |
| 错误码分布 | 无码7 / `UNSUPPORTED_NUMERIC_TOKEN`2 / `EVIDENCE_COVERAGE_DEFICIENT`1 | 无码7 / **`EVIDENCE_COVERAGE_DEFICIENT`2** / `ISSUE_DECOMPOSITION_INVALID`1 |

- **`UNSUPPORTED_NUMERIC_TOKEN` 2 → 0**（该类失败整类消失），但 `EVIDENCE_COVERAGE_DEFICIENT` 1 → 2。
- 终稿显著变长（C01 404 → **1303** 字符；C05 331 → 1051；C08 0 → 1112）⇒ 争点变多后答案确实更完整。
- **符合预登记的预期**：`full_closure` 被"终稿缺要件法条"（T7 中 10/10 全中）钉死，**属 writer 引用轴**，不在本轮射程。**本轮不由它判成败。**

## 4. ⚠️ 命题③：判据写坏了（我的责任），但接线已被独立验证

- **现象**：服务日志中 `issue_decomposition_coverage` **触发 0 次**。
- **判据缺陷**："0 触发"**同时兼容两种解释**——(a) 无缺口故未触发（**好结果**）；(b) 没接上（**坏结果**）。日志本身**无法区分** ⇒ 这条预登记判据**不具鉴别力**，属我设计失误。
  **教训**：预登记判据必须能**区分"好结果"与"没生效"**，否则它既不能证真也不能证伪。
- **改用离线接线验证闭合**（`t8-wiring-verification.txt`，走**生产装配路径** `build_agent_runtime → build_initial_state`，零 LLM 外呼）：

```
[场景1 覆盖缺口] 外呼=2（期望 2）  最终 issues=2（期望 2）  => 守卫已接线并生效 ✅
```

⇒ **接线正确**；③ 的真实状态是"**未触发是因为无缺口**"，即契约改动同时把缺口消掉了。

## 5. 🔍 本轮新暴露的第二个同族缺口：**非逐字引用无修复机会**

验证轮 C06 死于 `ISSUE_DECOMPOSITION_INVALID`，而**日志第一次给出了确切原因**（这正是 §12.3 白名单修复的成效）：

```
"msg": "agent_pre_run_failure",
"agent_pre_run_reason": "ISSUE_DECOMPOSITION_INVALID",
"agent_conversation_id": 2357,
"agent_failure_detail": "IssueDecompositionError: Issue fact is not a verbatim request fragment"
```

以前这三个字段**被静默丢弃**，7 种抛错文案坍缩为一个"未知"。

离线隔离验证（`t8-wiring-verification.txt` 场景 2）证明：**该错误的校验在 `build_initial_agent_state`（晚于 `decompose`）⇒ 不经过覆盖修复环**。

```
[场景2 非逐字引用·无覆盖缺口] 外呼=1（未触发覆盖修复）
  结果：IssueDecompositionError: Issue fact is not a verbatim request fragment
```

⇒ 与 planner（`71e5f23`）和覆盖度（本轮）不同，**"非逐字引用"这条确定性可判的失败仍然没有修复机会**。

## 6. 拟合被实测修正（闭合 skill 审计指出的缺口）

- skill 审计曾指出"**5 争点需 17 步**是我用 4 点拟合的估计"。**实测修正为 19 步**（C08）。
- 拟合式更接近 `steps ≈ 8 + 2N`（含重复调用余量），即**我原拟合低估约 2 步**；`+3` slack 正好吸收。
- ⚠️ **但由此暴露新风险**：契约允许最多 `_MAX_ISSUES = 8` ⇒ 实测趋势下 8 争点约需 **26 步 = 恰好等于当前上限，零余量**。
  **建议把 `_BUDGET_STEP_SLACK` 3 → 6**（上限 26 → 29，仍 ≤ settings 的 `le=32`）。

## 7. 不得声称

- **不声称**质量提升：`full_closure` 仍 **0/10**，`agent_completed` 仍 7/10。
- **不声称**"契约加固解决了 C01 缺陷"：C01 本轮 4 争点 + completed，但那是**题面变化**，本轮并非 C01 缺陷的验证（该验证在 LongCat 域 `probe-c01-verify2`）。
- **不声称**与 LongCat 基线可比。
- 未做：`full_closure` 的机制改进（writer 引用轴）；8 争点边界实测；§5.5 独立验收。
