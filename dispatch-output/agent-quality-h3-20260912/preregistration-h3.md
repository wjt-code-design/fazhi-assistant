# H3 真实模型小样本验收预登记（2026-09-12）

承接 `docs/final-agent-handoff-20260912.md` 第 6 节 H3 与第 9.4 节。**本轮调用前登记**，事后不追改。

## 候选（H1 修复后，离线已验收）

`dispatch-output/agent-timeout-h1-20260912/candidate-manifest-h1.json` 记录的 6 个文件，
SHA-256 以该清单为准；启动时另由 serve.py 写入 `runtime-manifest.json` 记录实际加载文件哈希
（含 `tools/gateway.py`、`tools/legal_retrieval.py`、`tools/contracts.py`、`retrieval.py`、`settings.py`）
与知识库/索引轻量标识。**候选哈希必须以宿主实际写出的 manifest 为准**，本预登记不预先断言数值。

## 模型与端点

- 后端 `backend/.env` 选择的模型；宿主断言 `entry.cfg["model"] == "qwen3.8-flash"`，与根目录 `.env` 的
  LongCat 配置**不混用**。
- rerank：SiliconFlow `BAAI/bge-reranker-v2-m3`（官方免费型号）；embedding：本地。
- 只允许 guard 白名单内的两个端点/模型，其它端点或型号一律停止外呼。

## 费用与次数

- 新增账本 `cost-ledger.jsonl`（新目录、新文件，`exist_ok=False` 拒绝复用）。
- **guard 上限 = 20 − 0.0067501 = 19.9932499 元**（上一轮累计 `accounted_upper_cny`），
  使跨轮累计外呼金额不超过 20 元总授权。guard 是进程内计数，必须这样显式扣减。
- 每次 qwen 预约 2 元（覆盖最大输入 100 万 token、输出 131072、思考 262144，未折扣价合计 1.86 元 ≤ 2 元）；
  rerank 预约 0 元。usage 缺失或服务端状态未知时保留完整预约。
- 单进程最多 60 次外呼（guard 进程内计数；跨轮累计次数另行统计，不当作额度）。
- 估算不等于账单；实扣以供应商为准。

## 案例与顺序

1. 先只跑 **C01**（`--case C01`），唯一 run 名、独立会话，使用新业务库与 quota 库。
2. 结束并核对持久化与账本后，才按 H3 顺序决定是否继续 C07、C10。
3. 每题最多两轮补充，按 frozen-round-protocol 投放事实，不提前泄露补充事实。

## 停止规则

- 出现技术失败或未知服务端状态 → 暂停队列先诊断，不自动重跑、不自动扩大样本、不增加预算。
- 预算不足以覆盖下一次最坏调用 → 停止付费工作，完成已有证据整理。
- 不修改冻结 judge；`gate5_judge` 的 `passed=False` 不当作法律语义结论，须看具体失败项并保留 REVIEW。

## 已知限制（沿用上一轮，未消除）

验收宿主会缓冲响应体以取 usage，且 guard 把任意非成功 HTTP 状态视为停止条件，
因此**不能证明**生产重试/降级分支与首 token 延迟达标。
