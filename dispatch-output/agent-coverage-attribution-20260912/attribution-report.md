# C01 覆盖率失败归因报告（2026-09-12）

预登记：`preregistration.md`。本轮目的只有一个：**给覆盖率闸门失败定性**（无 claim / 有 claim 未绑定）。
**不是**法律质量验收，**不**声称 C01 通过。未部署、未提交、未推送。

## 1. 归因结论：目的是达成了，但答案指向了**另一个模块**

`agent_coverage_issues` 诊断（本轮新加的埋点，首次真实生效）：

```
verdict=RESEARCH_MORE  agent_issue_count=4  agent_coverage_gap_count=4  run=6b18d873-...
[{"issue_id":"issue_bfaaaf7e...","claims":0,"claims_bound_effective_statute":0,"deficient":true},
 {"issue_id":"issue_b64c3ffc...","claims":0,"claims_bound_effective_statute":0,"deficient":true},
 {"issue_id":"issue_19785971...","claims":0,"claims_bound_effective_statute":0,"deficient":true},
 {"issue_id":"issue_27ff9cb5...","claims":0,"claims_bound_effective_statute":0,"deficient":true}]
```

⇒ **缺口是「该争点完全没有 claim」**（4/4 全部 `claims == 0`），
**不是**「有 claim 但未绑定生效成文法」。这直接否证了「证据绑不上」的猜测。

**但更有价值的是失败阶段**：终态 step 17 的 `result_summary` 是
**`WRITER:NON_CANONICAL_CITATION`** —— 失败发生在 **writer**，不是 verifier。

完整链条（DB 步骤可逐条对上）：

| 步 | 事件 | 结果 |
|---|---|---|
| v2→v3 | `retrieve_laws` #1 | TOOL_SUCCEEDED，1460 ms |
| v4 / v8 | 两次 `clarification` | 等用户 |
| v6→v7 / v10→v11 | `retrieve_laws` #2 / #3 | TOOL_SUCCEEDED，1021 / 950 ms |
| **v12** | `backfill_retrieval` / `CLARIFY_BUDGET_EXHAUSTED_PENDING_RETRIEVAL` | 2026-09-10 那条修复路径生效（有争点从未检索） |
| v13→v14 | `retrieve_laws` #4 | TOOL_SUCCEEDED，675 ms |
| v15 | `conditional_analysis` / `CLARIFY_BUDGET_EXHAUSTED` | 澄清预算耗尽 → 强制条件化起草 |
| v16 | `coverage_rewrite_attempt` / `ATTEMPT_RESERVED` | 预留重写预算并落盘 |
| **v17** | `failure` / `WRITER:NON_CANONICAL_CITATION` | **writer 重渲染整次失败** → 终止 |

即：writer 首稿没产出可用 claim（4/4 争点 claims=0）→ verifier 覆盖率闸门判 deficient
→ `service.py:249 _rewrite_worth_attempting` 返回 True（说明各争点**都有**可用生效成文法证据）
→ 预留重写（v16）→ **重渲染被 `writer.py:616` 的 `has_noncanonical_citation` 拒绝，整次 `_fail`**
→ `service.py:286-289` 返回 `WRITER:{reason}` → 终态失败，公开原因透传为 `EVIDENCE_COVERAGE_DEFICIENT`。

另外：**本次 Agent 一条事实都没拿到** —— `answered_fact_ids: []`，
两个澄清问题**都** `no_rule_match`（问的是「劳动合同中是否约定了无需支付补偿的情形」
「解除是否符合《劳动合同法》第39条规定的即时解除条件」），冻结事实协议匹配不上。
⇒ 它是在**没有获得任何补充事实**的情况下起草的。

## 2. H1 修复继续有效（不受影响）

4 次 `retrieve_laws` **全部 `TOOL_SUCCEEDED`**（1460 / 1021 / 950 / 675 ms），**全程无 TOOL_TIMEOUT**。
本轮 stage_reason 是 `WRITER:…`（H3 那次是 `VERIFIER:FAIL_SAFE`），verdict 是 `RESEARCH_MORE`
（H3 是 `FAIL_SAFE`）—— 说明**失败形态在变**，检索已不是阻塞点。

## 3. 我的诊断还有一个盲区（必须说）

`claims == 0` **无法区分**这两种情况：
- (a) 模型压根没产出 claim；
- (b) 模型产出了 claim，但因 `evidence_ids` 为空被 `writer.py:620-621` **静默丢弃**（`dropped.append`）。

`_coverage_issue_facts` 读的是**校验之后**的草稿，所以看不到被丢弃的中间物。
⇒ 下一步的自然埋点是**记录 writer 的丢弃/拒绝原因**（`dropped` 与各 `_fail` reason），
同样零成本、离线可验。**在补这个之前，不要猜 (a) 还是 (b)。**

## 4. 费用（我的预估错了，如实记）

| 项 | 值 |
|---|---|
| 本轮外呼 | **8 次**（4 × qwen3.8-flash + 4 × BAAI rerank），全部 HTTP 200，无未知状态 |
| 本轮估算 | **0.0205294 元** |
| 预登记预估 | 0.011 元 → **低估约 1.9×**（外呼次数 4→8、提示更长；估算口径偏乐观，已如实记录） |
| 跨轮累计 | 0.0067501 + 0.0106919 + 0.0205294 = **0.0379714 元** |
| 剩余授权参考 | **19.9620286 元** |

按未折扣价与官方免费 rerank 估算，**不等于供应商账单**。

## 5. 关闭状态

`shutdown-check.json`：serve PID 19612 已终止；18111 无监听（仅 TIME_WAIT 残留）；
8/8 预约闭合、0 pending。runner 已结束、无活动请求。

## 6. 现在的判断与下一步

失败点已从「检索超时」→「覆盖率闸门」→ 现在明确落到 **writer**：
**首稿零 claim + 重渲染被 `NON_CANONICAL_CITATION` 拒绝**，且本次 Agent 未获得任何补充事实。

建议顺序（都不需要马上花钱）：
1. **补 writer 侧可观测**（`dropped` / `_fail` reason 逐 claim 记录）——零成本、离线可验，
   用来关掉第 3 节的 (a)/(b) 二义性。这是**继续归因的唯一必要前提**。
2. 归因清楚后再判断是「writer 契约/提示词」问题还是「无事实可绑」问题；若属主链路缺陷，
   按纪律先离线反例 + 重记候选。
3. 之后再申请付费验证。**不建议现在再花一次钱** —— 第 3 节的二义性不解决，再跑也只能看到同样的
   `claims=0`，无法进一步归因。
