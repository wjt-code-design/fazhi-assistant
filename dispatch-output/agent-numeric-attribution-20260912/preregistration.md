# 付费运行预登记：C01 数字违规分桶归因（2026-09-12）

依据 `dispatch-output/alignment-20260912-writer-bottleneck.md`（grilling 对齐结论）。
目的：把 `UNSUPPORTED_NUMERIC_TOKEN` 的根因定位到 **②漏绑 / ③跨争点无权引用 / ①编造**，
以便按预置决策树选择改法。**不是**法律质量验收，**不**声称 C01 通过。

## 候选（离线已验收）

`dispatch-output/agent-numeric-bucket-20260912/candidate-manifest.json`：
`backend/agent/writer.py`(729→786)、`backend/tests/test_agent_writer.py`(537→600)、
`backend/observability.py`(183→183，未变——新数据嵌在已有 `agent_writer_summary` 内，无需新白名单字段)。
启动前字节对齐已核验 `ALL_MATCH=True`。
离线：全量 **948 passed / 0 failed / 覆盖率 78.50%**、ruff/format/mypy 全 0；
watch-it-fail 已对最终代码复验（把分桶函数打桩成全 0 → 3 项全红）。

## 口径（用户 2026-09-12 临时指令）

9.15 前「放开跑」→ 不按剩余额度收缩，`EVAL_GUARD_LIMIT=20`（每进程兜底）。
仍保留独立目录/账本/隔离库、唯一 run 名、未知服务端状态不重跑、不扩样本、不改冻结 judge。

## 案例与节奏

只跑 C01，唯一 run 名 `numattr-q38-c01-20260912-01`。
按对齐第 5 支：**先跑 1 轮**；出终稿才续跑到「连续 3 轮全绿」；
**连续 2 轮同类失败即停**并先分析。

## 判定标准

读 `server.log` 的 `writer_render_summary` → `agent_writer_summary.numeric_violation`：

| 观察 | 结论 | 对应改法（预置） |
|---|---|---|
| `in_own_issue_other_sources > 0` | ② 漏绑 | payload 标注每条 fact/evidence 含哪些数字 + 提示词要求同步绑定 |
| `in_other_issues > 0` 且前者为 0 | ③ 跨争点无权引用 | **超出本轮范围**，只记录 + 交回用户 |
| `from_unknown_facts > 0` | 数字来自未决事实（不可绑定） | 属上游事实确认问题，记录后判断 |
| `nowhere > 0` 且其余为 0 | ① 编造 | 提示词改为可机械执行的表述 |

若本轮**未**触发数字校验（换成别的 reason）→ 说明失败形态又变，如实记录并停下分析，不强行套用。
