# C01 writer 侧归因报告（2026-09-12）

预登记：`preregistration.md`。**归因成功，且结论否证了上一轮的两个候选解释。**
未部署、未提交、未推送。

## 1. 结论（一句话）

真实 C01 的 `claims == 0` **既不是**「模型没产出 claim」，**也不是**「产出后因 `evidence_ids`
为空被丢弃」；真正的阻塞点是 **writer 的 `UNSUPPORTED_NUMERIC_TOKEN` 校验**，
且**两次尝试都卡在同一个争点**、回喂重试修不好。本轮**根本没走到 verifier**。

## 2. 原始证据

runner：`[C01] rounds=3 clar_rounds=2 answered=2 unmatched=1 final_chars=0 agent_completed=False
over2=False errors=['UNSUPPORTED_NUMERIC_TOKEN']`，exit 0（仅表示采集完成）。

`server.log` 里本轮新埋点记录 **2 条** `writer_render_summary`（`render()` 的两次尝试）：

| 尝试 | `has_feedback` | `reason` | 提出 | 接受 | 丢弃 | `failing_issue_id` |
|---|---|---:|---:|---:|---:|---|
| 首稿 | `false` | `UNSUPPORTED_NUMERIC_TOKEN` | **4** | 1 | 2 | `issue_27a7682dff95c73eb3728cda` |
| 通用错误回喂重试 | `true` | `UNSUPPORTED_NUMERIC_TOKEN` | **4** | 3 | 0 | **同一个 `issue_27a7…`** |

逐争点明细（首稿）：4 个争点**各提出 1 条 claim**；`issue_10ff…` 接受 1；`issue_27a7…` 提出 1 / 接受 0；
另两个争点各提出 1 / 被丢弃 1。

**关键否证**：
- 提出数为 **4**（不是 0）⇒ **(a)「模型没产出 claim」被否证**。
- 丢弃数只有 2（对应 `evidence_ids` 为空的那些），不是全部 ⇒ **(b)「产出后被静默丢弃」被否证**。
- 本轮**没有** `coverage_gate_terminal_failure` 记录 ⇒ **没到 verifier**：`render()` 两次都失败后
  直接在 `service.py:423` 的 writer 分支落败。

## 3. 三个 run、三种终态 —— writer 是当前瓶颈

| 轮次 | 终态 stage | 含义 |
|---|---|---|
| H3 轮 | `VERIFIER:FAIL_SAFE` | 走到 verifier，覆盖率闸门挂 |
| 归因轮（上一次） | `WRITER:NON_CANONICAL_CITATION` | writer 重渲染被引用格式校验拒 |
| **本轮** | `UNSUPPORTED_NUMERIC_TOKEN` | writer 首稿与回喂均被数字来源校验拒 |

`_render_once` 对 claim 是 **fail-fast、全有全无**：任何一条 claim 不通过，**整篇作废**；
且本轮显示通用错误回喂（带理由重试一次）**没能修好同一个争点**。
⇒ 与其继续在检索侧找原因，当前更该处理 **writer 校验/重试语义**。

## 4. 未证实（不要当成结论）

1. **具体是哪个数字 token 触发**：埋点只记计数与争点，未记 token 内容。
2. **为什么回喂修不好**：未记录反馈文本与该 claim 原文，无法区分"没看懂反馈"与"上游就没有可用数字来源"。
3. **是否与"该争点没绑定到含数字的事实"有关**：C01 的 round2 事实含「月平均工资 12,000 元」，
   本轮 `answered=2`（确实拿到了事实）。**若某争点的 claim 写了该数字却没绑定对应事实，就会被本校验拒** ——
   这是**与证据一致但未证实**的假设，需要用绑定视图验证。

## 5. 费用

| 项 | 值 |
|---|---|
| 本轮外呼 | 7 次（qwen + rerank），全部 200，无未知服务端状态 |
| 本轮估算 | **0.0167091 元** |
| 跨轮累计 | **0.0546805 元**（参考值；临时放宽期内不做累计扣减） |
| 剩余参考 | 19.9453195 元 |

口径：用户 2026-09-12 指令「9.15 之前放开跑」，本轮 `EVAL_GUARD_LIMIT=20`（每进程兜底）。
估算≠供应商账单。

## 6. 关闭状态

`shutdown-check.json`：serve PID 22160 已终止；18111 无监听；7/7 预约闭合、0 pending。

## 7. 下一步建议（零成本埋点，然后再跑一轮）

把 `UNSUPPORTED_NUMERIC_TOKEN` 的**触发细节**记进 `agent_writer_summary`：
- 触发的**数字 token 本身**（这是法条/事实里的数字，非用户全文）；
- 该 claim 绑定的 `evidence_ids` / `fact_ids`（标识）；
- 该争点可用事实里**是否含**这些数字（布尔），用来验证第 4.3 节的假设。

拿到这些后一次付费运行即可定位到"具体缺哪个数字来源"，再判断是**提示词/契约**问题
还是**上游事实-争点绑定**问题，然后才谈改代码（并先离线反例 + 重记候选）。
**在此之前不建议再跑**：现在的记录只能告诉我们"又一个争点被数字校验拒了"，无法更进一步。
