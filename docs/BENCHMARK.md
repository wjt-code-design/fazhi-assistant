# 法智 · 质量与性能基准

> 2026-08-03 基准，真实运行环境（单 worker、本地 BGE CPU、阿里云 qwen3.7-plus/omni）。
> 所有数字可复跑：脚本在 `backend/scripts/`，原始结果在 `docs/benchmark_results/*.json`。
> 诚实标注贯穿全文——每个数字都注明「怎么测的 + 已知限制」。

## 总览表

| 指标 | 数字 | 怎么测的 | 已知限制 |
|---|---|---|---|
| 幻觉率（引用合法率） | **1.0**（53/53 引用全在库） | eval_set 28 例真实答案 → `citation_verify` | 判"引在库"，不判"引对题"（ADR-010） |
| 答案级非法引用 | **0%**（28/28） | 同上，答案含非法引用即计 | — |
| 自检通过率 | **96.4%**（27/28） | `quality.self_check`（有据须引条） | 1 例"正当防卫"回答未引条被判失败 |
| 召回率 recall@1/2/4/6 | **0.82 / 0.93 / 1.00 / 1.00** | eval_set 28 例纯检索 | 合成标注，非真实问答 |
| MRR | **0.90** | 同上，期望条文 rank 倒数 | — |
| 答案相关性 | **100%**（10/10 完全相关） | LLM judge（qwen3.7-plus）打 0/1/2 | **单一 judge、无人工金标**——主观度量 |
| 首字时延 p50 / p90 | **1.3s / 2.1s** | 服务端 `first_ms` 埋点，65 个非缓存首问 | 含检索 pre（~1.2s）+ LLM TTFT |
| 端到端时延 p50 | **3.8s** | 服务端 `ms` 字段，同一批样本 | 生成长度决定（提示词限 ≤300 字） |
| 缓存命中 | ~0.2s/问 | answer_cache（进程内 LRU 512/TTL 6h） | 重启即清；key 含条文 ids（近似问题共享） |
| 限流 | **生效**（第 60 次 429） | node 连发 61 次（60s 窗口内） | 按 IP；chat 60/min、login 10/min |
| 检索时延 | ~1.2s（cosine 精排免重嵌后） | 阶段插桩（精排只嵌 BM25 独有条目） | 无独立运行时间隔统计脚本 |
| 吞吐量 / 并发 | **无压测数字** | — | 单 worker 架构约束（ADR-007/008），量化需多 worker 改造 |
| 长文本 | 99 部法 / 10236 条 / 最长 **7627 字** | `split_law_document` 句切（>800 字跨多条） | **无上下文预算管控**（提示词无 token 上限断言） |
| 重试与幂等 | 配置齐全 | stream_with_retry 3 配置 + max_retries=3；file_hash 幂等 | 幂等仅 upload 路径；删-写非原子 |
| 压力测试 | **降级为时延测量 + 限流冒烟** | 见上文 | 完整并发压测被砍（缓存/限流污染数字，见方法学） |
| chunking | 16 测试（含长条覆盖） | `tests/test_chunking.py` | MIN_ARTICLE=10 会吞过短真条文 |

## 方法学（每个数字的来路与边界）

### 质量类

- **幻觉率 / 引用合法率**：`scripts/eval_hallucination.py`。eval_set 28 例走真实 chat，答案抽取所有《法名》第X条，`citation_verify` 判定是否在库。**只证明"没编造不存在的条文"**，不证明"引对了题目要的条文"——那是语义层，靠 full 门禁 + 人工 QA 沉淀兜底（ADR-010 明示此边界）。
- **自检通过率**：同一批答案跑 `quality.self_check(context_present=True)`。1 例失败是"正当防卫过当"（模型答了但没引条号）——语义答对但形式未引条，诚实计入。
- **相关性**：`scripts/eval_relevance.py`。qwen3.7-plus 单 judge 对 10 例问答打 0/1/2。**主观 + 单 judge + 无金标**，数字仅供参考；修复"法定"误拒答后 10/10 完全相关。
- **准确性**：`scripts/smoke_citation_full.py` 12 场景（8 正向引条 + 2 负向诚实拒答 + 2 轻量）。**字符串包含断言偏弱**，且结果不落盘——理想是 LLM faithfulness（`EVAL_LLM_JUDGE=1` 可选开启）。

### 性能类

- **首字/端到端时延**：服务端 `first_ms`/`ms` 埋点（`observability.log_account`），日志统计**排除缓存命中**（`model != "cache"`）。65 个非缓存首问 p50/p90。首帧 = 检索 pre（~1.2s）+ LLM 首个 token（~0.6-1s）；总时延 = 首帧 + 流式生成（字数决定）。
- **缓存命中**：同题二次问 ~0.2s（进程内 LRU + SQLite 无持久，重启即清；key 含条文 ids → 近似问题共享缓存）。
- **限流**：node 脚本 61 次连发（12s 内，缓存命中零配额），第 60 次触发 429（60/min 生效）。**注意**：Python urllib 读 SSE 首帧有 ~2s 测量假象（http.client readline），客户端时延一律用 node（浏览器同源口径）。
- **吞吐/并发**：**故意不给数字**。单 worker（`uvicorn` 无 `--workers`）+ 60/min 限流 + 远端 LLM 生成 3-8s——压测会同时撞缓存（同题二次命中）与限流（429），数字无法反映真实容量。扩并发路径在 ADR-008（Qdrant/PG + PostgreSQL + 多 worker），当前规模不需要。
- **压测**：完整并发压测被 grilling 审查砍掉（缓存 + 限流双重污染），降级为「端到端时延测量 + 429 限流冒烟」两项真实有效的验证。

### 工程类

- **chunking**：按「第X条」行首锚定切分，章节前缀注入，目录页跳过（4 重退出条件）；>800 字条文按句切（500 字 + 60 重叠），16 测试含"长条跨句切后覆盖完整原文无遗漏"。
- **重试幂等**：流式空答按 3 配置重试 `[(禁思考,0),(开思考,0.5),(禁思考,0.5)]`；ChatOpenAI `max_retries=3`；知识导入 `file_hash`(sha256) 幂等（仅 upload 路径）；缓存 key 幂等（问题|意图|日期|排序去重条文）。
- **长文本**：语料最长条文 7627 字（≈16 chunk）；多轮记忆增量压缩（RECENT_K=6 / 6000 字阈值触发）。**无上下文预算管控**——提示词条文块不设 token 上限，超长场景未验证，列为已知限制。

## 基准发现的两个真实 bug（本次基准的副产品）

1. **「遗产的法定继承顺序」误拒答**：法名抽取黑名单漏「法」前一字"定/的/据"（法定/遗产的法/根据法定被当法名）→ 源名查库失败 → 误拒答。已修（排除集补 3 字 + 回归测试），复验正常引《民法典》1127 条。
2. **限流冒烟第一版失败是测量问题**：urllib 假象 + 缓存未命中导致 61 次跨 60s 窗口。修正后验证限流真实生效。

## 复跑方式

```bash
cd backend
python scripts/eval_hallucination.py   # 幻觉/自检（28 例真实 LLM）
python scripts/eval_retrieval.py       # 召回多 k + MRR（离线）
python scripts/eval_relevance.py       # 相关性（10 例 LLM judge）
node scripts/bench_latency.mjs         # 端到端时延（node 口径）
node scripts/bench_rate_429.mjs        # 限流冒烟（60s 窗口连发）
python scripts/eval_negative_run.py    # 弃答率（LawBench 范式）
```
全部输出落盘 `docs/benchmark_results/*.json`（不覆盖，时间戳追加）。
