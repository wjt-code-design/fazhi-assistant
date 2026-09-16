# C01 覆盖率闸门失败：诊断（2026-09-12，零付费）

对象：H3 运行 `quality-q38-c01-20260912-h3-01` 的终态
`failed / state_version=14 / EVIDENCE_COVERAGE_DEFICIENT / VERIFIER:FAIL_SAFE`。
本轮诊断**未发起任何外部 HTTP**（rerank 关闭 + 本地 embedding + HF 离线）。

## 一、已证实的收窄（从归档可判定）

1. **失败点 = verifier 覆盖率闸门**，不是检索超时、不是存储/CAS 冲突。
   `agent_steps`: v13 `coverage_rewrite_attempt / EVIDENCE_COVERAGE_DEFICIENT / ATTEMPT_RESERVED`
   → v14 `failure / EVIDENCE_COVERAGE_DEFICIENT / VERIFIER:FAIL_SAFE`。
2. **缺口的性质 = 纯绑定缺口，不是冲突驱动**。
   回喂**确实被发起过**，而 `service.py:136 _rewrite_worth_attempting` 只有在下列条件全部满足时才返回 True：
   - 没有「未解决的关键冲突」（`state.conflicts` 实测为空 ✓）；
   - 至少一个 issue 判 deficient（`service.py:146-148`）；
   - **每个 deficient issue 都有「生效成文法」证据、且经成功 observation 链接**（`service.py:155-161`）。
   ⇒ 所以：存在 deficient issue，且该 issue **手上有可用的生效成文法证据**，
     只是草稿的 claim 没有绑上去（或该 issue 完全没有 claim）。二者都会让
     `verifier.py:289` 的 `not issue_claims or not has_effective_statute` 为真。
3. **重写预算被消耗且未能修复**：`verifier_research_returns = 1 = max_verifier_research_returns`，
   重写后仍 deficient → `verifier.py:298-304` 只能走 `FAIL_SAFE`。
4. **草稿未持久化**：`LegalAgentState` 无 `draft`/`claims` 键，DB 只留步骤元数据
   ⇒ 归档**无法**区分「无 claim」与「有 claim 未绑定」。这是当前证据的硬边界。

## 二、已证实：检索输入本身有问题（零外呼复现）

从 `state.observations[*].output.retrieval.query` 取到当时**实际发出的三条 query**，
用 `probe_retrieval_offline.py`（rerank 关闭）逐条复现：

| # | planner 发出的 query | 复现到的 top-8 | 必需法条命中 |
|---|---|---|---|
| 1 | 公司主张的连续两次绩效不合格事实是否成立？ | 公司法27、产品质量法58、安全生产法92、民法典793、政府采购法82、公司法257/250、产品质量法56 | **0** |
| 2 | 即使绩效不合格，公司直接解除合同而未进行培训或调岗是否合法？ | 劳动法99/25/97/98/32、劳动合同法22/39/89 | **0** |
| 3 | 公司未支付任何经济补偿即解除合同，劳动者能否要求赔偿金？ | 劳动法99/91/97、劳动争议调解仲裁法16、**劳动合同法87**、**劳动合同法47**、民法典579、社会保险法85 | 87、47（但排第 4/5 位） |

冻结案例要求《劳动合同法》40 / 43 / 47 / 87。结论：

- **问题在 rerank 之前**：关掉 rerank 后必需法条同样召不回（q1/q2 为 0，q3 仅 87/47 且靠后），
  所以不是排序把好结果弄坏了，而是**召回池里就没有目标条文**。
- **q1 是词面陷阱**：query 是事实性问题（"…事实是否成立"），检索器按词面匹配
  「成立/虚假/考核」→ 命中公司法「决议不成立」、产品质量法、安全生产法。
- **三条 query 全部无锚点**：`query_understand.decompose` 对三者都只返回一个
  `('…', 'original')` 单元。对照实验显示它**只在出现罪名时**才抽 `anchor`
  （"非法持有毒品罪如何量刑？" → 抽出 `('非法持有毒品罪','anchor')`），
  而"《劳动合同法》第四十条""劳动合同法第47条"这类条号也只给 `original`。
  ⇒ 「锚点保底」机制（`retrieval.py` 里保证核心条文必现的那段）在这三条上**完全没有启动**；
  `_rerank_query` 因无语义锚点也回落整句前 120 字。

## 三、结构性差异（已证实）

`_rewrite_for_retrieval`（检索用 query 改写）**只接在 Fast Path 上**
（`main.py:466` 定义、`main.py:663` 注入 `request_bootstrap`）；
**Agent 工具路径没有改写阶段** —— `tools/legal_retrieval.py` 把 planner 给的
`tool_input.query` 原样送进 `retrieval.retrieve()`。即：同一个用户问题走 Fast Path 会被改写，
走 Agent 主链路不会。

## 四、未证实（不得当作结论）

1. **覆盖率失败的近因**：是「writer 产出的 claim 没绑生效成文法」还是「该 issue 完全没 claim」。
   归档无法区分（草稿未持久化）。需要先能观测到草稿或 claim 绑定情况。
2. **检索质量差是否就是覆盖率失败的原因**：两者都在归档里被证实存在，但因果链未建立。
   反证思路：闸门只要求"绑一条生效成文法" —— 检索到的公司法/产品质量法条文**也是**生效成文法，
   只要 writer 引了它们就能过闸。若 writer 选择不引（因为它认为不相关），才会失败。
   因此更可能是「检索给了一堆无关但合法的条文 → writer 不引 → 闸门挂」，
   但这仍是**推测**，需要草稿证据。
3. 澄清协议 `no_rule_match` 对结果的影响未隔离。

## 五、建议的下一步（按性价比排序）

1. **先让失败可观测**（小改动、离线可验）：在起草/覆盖率判定处持久化
   「每个 issue 的 claim 数 + 是否绑定生效成文法」这类**判定摘要**（不是全文草稿），
   使下一次失败能直接归因到「无 claim」还是「未绑定」。否则再来一轮付费也解释不了。
2. **改善 Agent 路径的检索输入**（设计改动，需单独规划）：让 `retrieve_laws` 的 query 带锚点
   （法名+条号、罪名、法律概念），或给 Agent 路径补一个检索用改写阶段。这会改变
   「planner 直接写问句」的现状，属主链路行为变更，必须先离线反例 + 重记候选。
3. 两条各自离线验收通过并重记候选后，才申请下一轮付费验证（剩余 19.9825580 元）。

本轮未改任何生产代码，未消耗预算（0 元）。
