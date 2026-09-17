# C01 数字分桶归因轮（第 1 轮）：形态又变了 —— 但换来一个**确定性**发现（2026-09-12）

预登记：`preregistration.md`。按对齐第 5 支「改一次 → 先跑 1 轮 → 再决定」执行。
**本轮未触发数字校验**，按预登记写明的规则**如实记录并停下分析，不强行套用决策树**。
未部署、未提交、未推送。

## 1. 本轮结果：第 4 种失败形态

```
[C01] rounds=3 clar_rounds=2 answered=2 unmatched=1 final_chars=1087
      agent_completed=False errors=['AGENT_BUDGET_EXCEEDED']
DB: status='stopped'  state_version=16  last_error_code='AGENT_BUDGET_EXCEEDED'
step16: decision=stop  reason_code=AGENT_BUDGET_EXCEEDED
        tool_name=retrieve_laws  result_summary='budget_exceeded:step_preflight'
```

- **`writer_render_summary` 记录数 = 0** ⇒ writer 根本没跑到，本轮新增的数字分桶埋点**未被真实执行到**
  （仍只有离线验证；这点必须如实记，不能当成"埋点已生效"）。
- `final_chars=1087` 且 `messages` 有一条 1087 字符 assistant 消息 —— 这是 **Fast Path 降级答案**
  （技术失败回落），**不是 Agent 成果**；`agent_completed=False`。
- 本轮澄清协议**匹配上了 2 条事实**（`answered_fact_ids=['C01-r1-f1','C01-r2-f1']`），
  说明上一轮"拿不到事实"不是复发。

## 2. 机制：确定性的步骤预算交互（不是模型随机）

DB 逐步可复原：

| 争点 | 检索情况 |
|---|---|
| ① 绩效不合格事实是否成立 | v2→v3 ✅ 1663ms |
| ② 单方解除是否符合法定程序 | v6→v7 ✅ 1076ms |
| ③ 未付补偿是否导致赔偿请求权 | v10→v11 ✅ 1074ms |
| ④ 能否选择继续履行而非赔偿 | v12 `backfill_retrieval` → v13→v14 ✅ 802ms |
| ⑤ **诉讼时效是否届满** | v15 `backfill_retrieval` → **v16 stop（预算不足，未检索）** |

- 本次规划出 **5 个争点**；正常规划流只检索了 ①②③，④⑤ 靠 `backfill_retrieval` 补
  （即 2026-09-10 那条「澄清预算耗尽且仍有 issue 从未检索 → 回 PLANNING 补齐」的修复路径，本轮触发 2 次）。
- 每补一个争点要 **backfill 检查 1 步 + 检索 2 步（tool_call/tool_result）= 3 步**；
  两次澄清又占 4 步；bootstrap 1 步。
- 结果：**正好在第 5 个争点的检索前，`steps=15 / max_steps=16` 用尽** → preflight 拒绝 → `stopped`。
- ⇒ **这是确定性的**：只要争点数是 5、澄清用满 2 次，就必然到不了起草。

**系统级观察**：把历轮 run 的 state_version 摆一起看 —— 14 / 14 / 17 / 16，而 `max_steps=16`。
**整条主链路长期在预算边缘运行**，最终落到哪个失败点取决于"争点几个 + 澄清几次"这类小变化。
这解释了为什么四轮出了四种终态：不是四个独立 bug，而是**同一个预算约束在不同切法下的不同表现**。

| 轮次 | 争点数 | 终态 |
|---|---|---|
| H3 | 4 | `VERIFIER:FAIL_SAFE` |
| 归因轮 | 4 | `WRITER:NON_CANONICAL_CITATION` |
| writer 归因轮 | 4 | `UNSUPPORTED_NUMERIC_TOKEN` |
| **本轮** | **5** | **`AGENT_BUDGET_EXCEEDED`（连起草都没到）** |

## 3. 费用与状态

| 项 | 值 |
|---|---|
| 本轮外呼 | 7 次，全部 200，无未知服务端状态 |
| 本轮 | **0.0072769 元**（比前两轮便宜 —— 因为提前 stopped，模型调用少） |
| 跨轮累计 | **0.0619574 元**（参考值；临时放宽期内不扣减） |
| 剩余参考 | 19.9380426 元 |

`shutdown-check.json`：serve PID 22492 已终止；18111 无监听；0 pending。

## 4. 对既定对齐的影响

- 对齐第 2 支的预置决策树**暂不适用**：① ② ③ 都没被验证（writer 没跑）。
- 数字分桶埋点**保留**（离线已验、代码已合入 948 全绿），等下一次真跑到 writer 时自动生效。
- 对齐第 5 支的止损线（"连续 2 轮同类失败"）**未触发** —— 本轮与上轮**不同类**；
  但预登记的"形态变了就停下分析"已生效，故就此停下。

## 5. 建议下一步（未执行，等你定）

发现的是**确定性**问题 ⇒ 可以离线复现、不需要靠付费试探。三个方向：

**(A) 降低补齐的步骤开销（推荐）** —— 同等工作、更少步骤，不触碰任何红线。
例如让 `backfill_retrieval` 不单独占一步（把补齐判定并入下一次 planning），
或一次 planning 内批量补齐多个未检索争点。需先离线反例（构造 5 争点场景断言步数）。

**(B) 提高 `agent_max_steps`** —— 交接文档明写「**不得借此提高 steps/tool_calls 硬上限**」，
所以这需要你**显式授权**（像 9.15 预算那样）。它会改变成本边界，我不会自行做。

**(C) 先记录为已知缺陷、不动代码** —— 代价是目标 A（出终稿）会被这条卡死：
只要规划出 5 个争点，就永远到不了起草。

我倾向 **(A)**：它同时是"让目标 A 可达"的唯一不触线路径。
