# RAG 对照矩阵（Gate 2A · 任务 2）

**采集时间**：2026-09-08T14:46:12 – 14:49（20/20 组请求全部 HTTP 200，无 clarification、无 error、无空内容）
**服务**：http://127.0.0.1:8000 默认回答路径（`no_cache=true`，**不带 force_agent、不带 agent_run_id**，无澄清/追问流程注入）
**prompt 与检索配置来源**：服务端默认 RAG 链路（未修改任何 prompt 模板、检索参数或 top-k），未人为削弱基线
**原始记录**：`C0x-rag-initial.raw` / `C0x-rag-full-facts.raw`（SSE 全文，可复算）

## 输入构造

- `RAG-initial`：`{"content": <initial_question>, "no_cache": true}`
- `RAG-full-facts`：`{"content": <initial_question> + "\n\n补充信息：" + round1_facts + "\n" + round2_facts, "no_cache": true}`（开发集 frozen-cases-v1.json 逐字转录，未改写）

## 矩阵（争点/依据列为关键词近似命中，可由 raw 复算）

| case | mode | 金标争点命中 | 关键事实缺口识别 | 必需依据命中 | 实质性结论证据绑定 | 安全红线 |
|---|---|---|---|---|---|---|
| C01 | rag-initial | 1/4 | ❌ 无 | 0/4 | 有《》引用 | OK |
| C01 | rag-full-facts | 1/4 | ❌ 无 | **3/4** | 有《》引用 | OK |
| C02 | rag-initial | 1/4 | ❌ 无 | 0/3 | 有《》引用 | OK |
| C02 | rag-full-facts | 1/4 | ✅ 有条件化表述 | 1/3 | 有《》引用 | OK |
| C03 | rag-initial | 2/5 | ❌ 无 | 1/2 | 有《》引用 | OK |
| C03 | rag-full-facts | **3/5** | ❌ 无 | **2/2** | 有《》引用 | OK |
| C04 | rag-initial | 2/5 | ✅ | 1/3 | 有《》引用 | OK |
| C04 | rag-full-facts | 2/5 | ❌ 无 | 1/3 | 有《》引用 | OK |
| C05 | rag-initial | 0/5 | ❌ 无 | 2/2 | 有《》引用 | OK |
| C05 | rag-full-facts | 1/5 | ❌ 无 | 2/2 | 有《》引用 | OK |
| C06 | rag-initial | 0/5 | ❌ 无 | 0/3 | 有《》引用 | OK |
| C06 | rag-full-facts | 1/5 | ❌ 无 | 2/3 | 有《》引用 | OK |
| C07 | rag-initial | 0/5 | ❌ 无 | 1/3 | 有《》引用 | OK |
| C07 | rag-full-facts | **2/5** | ❌ 无 | **2/3** | 有《》引用 | OK |
| C08 | rag-initial | **3/5** | ❌ 无 | **3/4** | 有《》引用 | OK |
| C08 | rag-full-facts | 2/5 | ❌ 无 | 2/4 | 有《》引用 | OK |
| C09 | rag-initial | 1/5 | ❌ 无 | **4/4** | 有《》引用 | OK |
| C09 | rag-full-facts | 1/5 | ❌ 无 | 2/4 | 有《》引用 | OK |
| C10 | rag-initial | 0/4 | ❌ 无 | 1/2 | 有《》引用 | OK |
| C10 | rag-full-facts | 0/4 | ❌ 无 | 0/2 | 有《》引用 | OK |

## 观察结论（仅陈述事实，不作"推理更强"宣称）

1. **信息量效应可见**：full-facts 相对 initial，必需依据命中在 C01（0→3）、C03（1→2）、C06（0→2）、C07（1→2）上升；但 C08（3→2）、C09（4→2）反向下降——信息增加不一定提升法条覆盖，存在 LLM 生成分布波动。
2. **缺口识别是普通 RAG 的普遍弱项**：20 组中仅 2 组（C02-full、C04-initial）出现"信息不足/需补充/取决于"类表述；多数模式一次性给结论，与 Agent 的"尚不确定的事实"结构化声明形成对比维度（相同信息量才可比：full-facts vs Agent-final）。
3. **争点命中率整体低且波动**（0/4 ~ 3/5），与开发集正式运行中 Agent 的失败同源（LLM 生成质量分布），对比结论需等隐藏集/开发集 Agent final 产出后按相同口径逐题比对。
4. 全部 20 组实质性结论均有《》条文引用，无 error/restart 事件，安全红线 0。
5. 本矩阵不计算混合总分；Agent 与 RAG 的比较仅在"相同信息量"（full-facts vs Agent-final）层面成立，当前 Agent 侧 final 多为空（fail-closed），故未得出 Agent 优于 RAG 的结论。

## 复算方式

`compute_matrix.py`（本目录）读取 20 个 raw 文件重算上表；争点/缺口列为关键词近似判定，人工抽查 C01/C08/C09 与 raw 原文一致。
