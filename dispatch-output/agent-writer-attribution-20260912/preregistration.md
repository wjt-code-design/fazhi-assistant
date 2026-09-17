# 付费运行预登记：C01 writer 侧归因（2026-09-12）

目的：用本轮新加的 `agent_writer_summary` 埋点，回答上一轮**未能回答**的二义性 ——
真实 C01 的 `claims == 0` 究竟是 **(a) 模型没产出 claim** 还是 **(b) 产出后因 `evidence_ids`
为空被 `writer.py` 静默丢弃**；以及 `WRITER:NON_CANONICAL_CITATION` 是**首稿**还是
**coverage 回喂那次**触发的。
**不是**法律质量验收，**不**声称 C01 通过。

## 候选（离线已验收）

`dispatch-output/agent-writer-observability-20260912/candidate-manifest.json` 的 3 个文件，
启动前已核验字节对齐（ALL_MATCH=True）：
`backend/agent/writer.py`、`backend/observability.py`、`backend/tests/test_agent_writer.py`。
离线：全量 **945 passed / 0 failed**、覆盖率 78.46%、ruff/format/mypy 全 exit 0；
watch-it-fail 已在**最终代码**上复验（抹掉发射则 3 项全红）。
同时携带此前各轮的检索超时修复（H1）与覆盖率诊断（`agent_coverage_issues`）。

## 模型与端点

后端 `backend/.env`；宿主断言 `entry.cfg["model"] == "qwen3.8-flash"`。
rerank SiliconFlow `BAAI/bge-reranker-v2-m3`（官方免费）；embedding 本地。

## 费用（按用户 2026-09-12 临时指令）

用户指示「9.15 之前可以放开跑 qwen3.8-flash」→ 本轮**不做累计扣减**，
`EVAL_GUARD_LIMIT` 用**每进程 20 元**作失控兜底（参考：跨轮累计 0.0379714 元，单轮实测 ≈0.02 元）。
仍保留：独立账本（`exist_ok=False`）、未知服务端状态保留预约且不重跑、不扩样本、不改冻结 judge。

## 案例与顺序

只跑 C01，唯一 run 名 `wattr-q38-c01-20260912-01`，新业务库与新 quota 库。不扩到 C07/C10。

## 判定标准

从 `server.log` 取 `writer_render_summary` 记录（预期 1–3 条：`render()` 首稿、可能的通用错误回喂、
以及 coverage 回喂那次），按下表定性；两种结果都算**归因成功**：

| 观察 | 结论 |
|---|---|
| `claims_proposed == 0` | (a) 模型没产出 claim |
| `claims_proposed > 0` 且 `claims_dropped > 0` 且 `accepted == 0` | (b) 产出后被静默丢弃 |
| `reason == "NON_CANONICAL_CITATION"` 且 `has_feedback` 为真/假 | 定位到是首稿还是回喂那次失败 |

本轮不评价答案法律质量。
