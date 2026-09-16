# 付费运行预登记：C01 覆盖率失败归因（2026-09-12）

目的：**给上一次 C01 的覆盖率闸门失败定性** —— 用上一轮新加的 `agent_coverage_issues` 诊断，
区分「该争点完全没有 claim」与「有 claim 但未绑定生效成文法」。
**不是**法律质量验收，**不**声称 C01 通过。

## 候选（离线已验收）

`dispatch-output/agent-coverage-observability-20260912/candidate-manifest.json` 的 3 个文件，
启动前已核验字节对齐（ALL_MATCH=True）：
- `backend/agent/service.py`、`backend/observability.py`、`backend/tests/test_agent_chat_integration.py`

离线验收：全量 **941 passed / 0 failed**、覆盖率 78.42%、ruff/format/mypy 全部 exit 0。
此外 H1 轮的 6 个文件哈希未变（`tools/gateway.py`、`tools/legal_retrieval.py`、`tools/contracts.py`、
`retrieval.py` 及两个测试文件），故本轮同时携带 H1 的检索超时修复。

## 模型与端点

后端 `backend/.env` 选择；宿主断言 `entry.cfg["model"] == "qwen3.8-flash"`，与根目录 `.env` 的 LongCat 不混用。
rerank：SiliconFlow `BAAI/bge-reranker-v2-m3`（官方免费）。embedding 本地。
只允许 guard 白名单内端点/模型。

## 费用与次数

- 新账本 `cost-ledger.jsonl`（新目录、`exist_ok=False` 拒绝复用）。
- **guard 上限 = 20 − 0.0174420 = 19.9825580 元**（跨轮累计：第一轮 0.0067501 + H3 轮 0.0106919）。
  guard 是进程内计数，必须显式扣减，否则等于把总授权翻倍。
- 单次 qwen 预约 2 元；rerank 预约 0 元。usage 缺失或服务端状态未知时保留完整预约。
- 预估本轮 ≈0.011 元（3 次 qwen + 若干 rerank，按 H3 轮实测外推）。估算≠账单。

## 案例与顺序

- **只跑 C01**，唯一 run 名 `attr-q38-c01-20260912-01`，新业务库与新 quota 库。
- 不扩到 C07/C10。若出现技术失败或未知服务端状态 → 暂停并诊断，不自动重跑、不扩样本、不加预算。

## 本轮要回答的问题（判定标准）

从 `server.log` 取 `coverage_gate_terminal_failure` 记录，读 `agent_coverage_issues`：
- 若 deficient 争点 `claims == 0` → 缺口是「**无 claim**」；
- 若 `claims > 0` 且 `claims_bound_effective_statute == 0` → 缺口是「**有 claim 未绑定生效成文法**」。
两种结果都算**归因成功**（这正是本轮目的）；本轮不评价答案法律质量。

## 停止规则

沿用 `agent-quality-h3-20260912/preregistration-h3.md`：不改冻结 judge、不删失败样本、
`gate5_judge` 的 `passed=False` 不当语义结论、预算不足即停。
