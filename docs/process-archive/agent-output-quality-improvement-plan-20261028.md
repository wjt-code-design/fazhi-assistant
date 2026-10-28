# Agent 输出质量改造清单（2026-10-28）

> **写给正在改 `backend/agent/` 的会话。** 本文基于一次真实失败案例的逐层排查，
> 已完成的事实核验写在 §1，**请勿重复试错**。
>
> 写作时 HEAD = `5602d30`。你已经提交了 `1e7befa`（零引用草稿强制重试），
> 本文与你改动的是同一批文件 —— **动手前先 `git log` / `git diff` 确认重叠范围**。

---

## 0. 一句话结论

**架构不用换**。「分解争点 → 逐争点检索起草 → 确定性校验 → 合并」这个范式对法律场景是对的，
换成单次生成会丢掉引用可核验性（那是产品唯一的护城河）。
要改的是**编排（串行/整稿否决/零进度）+ 输出纪律（冗余复述）**。

---

## 1. 已核验的事实（别再重查）

失败案例：商铺先抵押后出租、抵押权实现被拍卖、承租人抗辩（完整 prompt 见 §7）。

| # | 事实 | 怎么验的 |
|---|---|---|
| 1 | **民法典 405 条在知识库里** | `col.get(where={'source':'民法典','article':'第四百零五条'})` → 1 条，原文「抵押权设立前，抵押财产已经出租并转移占有的，原租赁关系不受该抵押权的影响」 |
| 2 | **通用检索器能召回 405，且排第 1 位** | `retrieval.retrieve('商铺先抵押后出租，抵押权实现拍卖后，承租人能否以买卖不破租赁对抗新所有权人', k=12)` → 召回 16 条，第 1 条就是 405；另带出「城镇房屋租赁合同解释 14 条」「担保制度解释 54 条」「民法典 417/404 条」⚠️ 接手复核：云端未复现 417（短问句 405 第 2、404 第 12），见 §1b |
| 3 | **Agent 的检索用 `issue.question` 作 query** | `controller.py:1027` `retrieve_laws(query=issue.question)` |
| 4 | **Agent 的检索已经是并行连发的** | `controller.py:962` 注释：「在一个 EXECUTING 周期内全部连发、一次 EVALUATING」 |
| 5 | **慢的主因是 writer 串行** | `agent/service.py` 逐争点 `for issue in state.issues:` 串行调 `runtime.writer.render_issue(...)`，N 争点 = N 次串行 LLM 调用 |
| 6 | **答案非流式是架构必然** | `agent/writer.py:819` `render_issue()` **整体返回** WriterResult（非 yield）。必须拿完整文本才能做引用/数字校验，这本身合理 |
| 7 | **Agent 路径一条 `step` 事件都不推** | `main.py:2452` 的 `step` 推送**只在合同评估分支**（`_contract_messages` 那条路）。前端 `api.ts` 的 `onSteps` 已接好，Agent 侧没接 |
| 8 | **`partial_delivery` 已开启且生效** | 两端 `agent_partial_delivery_enabled=True`；本次实测确实降级为"部分交付"并列出未覆盖争点 |

**结论性推断（待你验证）**：既然 ①知识库有 405 ②通用检索排第 1，
那本次 `UNSUPPORTED_CITATION` **不是知识库缺失、也不是通用检索召回不足**，
而最可能是以下之一：
- **(a) `issue.question` 的文本与自然语言提问差异过大**（planner 生成的抽象表述召回不到 405）
- **(b) 405 被召回，但没进入该争点的证据池 / 未被 writer 引用**
- **(c) writer 引用了 405，但 verifier 的"已检索依据"集合不含它**

**第一步就该验 (a)**：把本次 run 的 `issue.question` 打出来，用它单独跑一次 `retrieval.retrieve()`，看 405 是否还在前 12 位。这一步能一刀切开三种可能。

---

## 1b. 接手复核（2026-10-28 22:5x，云端实测）

> 接手会话按 §1 第一步复跑，结论与 §1 的事实**部分不同**；后续以本节为准。

- **405 不是问题**：用失败 run（`b88c83b0…`）的真实 `issue.question` 跑 `retrieval.retrieve(k=4)`，405 **第 1 位**；k=12 也第 1；且 405 已经在失败争点的绑定证据里（`民法典#第四百零五条`）。§1 的 (a)（issue.question 召回不到 405）**不成立**。
- **writer 是池外引用**：该 run 的 `writer_render_summary`：`reason=UNSUPPORTED_CITATION`、`citation_violation=cited_not_retrieved`、`failing_issue_id=issue_e1f8…`。即 writer 引用的条文**不在本争点池内**；verifier 根本没参与（(c) 也不成立）。
- **池里有本案更相关的条文**：失败争点绑定 8 条：405、担保制度解释 54、城镇房屋租赁合同解释 14、民法典 725/404/406、担保 53/55。本案是"抵押后出租"，405 是"抵押前出租"的规则；更相关的是担保 54 / 租赁解释 14 / 725。**不要为了让 writer 引 405 而改检索。**
- **§1 fact#2 的 417 未复现**：云端（rerank 开）用短问句跑 k=12 → 16 条：租赁解释 14 第 1、405 第 2、担保 54 第 3、404 第 12，**无 417**；完整案情/issue.question 也无 417。§1 fact#2 的"带出 417"在当前生产不可复现，不能作为后续依据。
- **结论**：失败根因是 **writer 引用了池外条文**（`cited_not_retrieved`），不是 405 召回、不是 query 差异、不是 verifier。下一步最小修复：对 `UNSUPPORTED_CITATION` 的 corrective retry 复用 `require_citation=True`（把精确池清单给 writer，仍走原校验，不放松）；不要改 finalizer/verifier。
- 证据：`dispatch-output/agent-partial-20261028/cloud_writer_summary_20261028.jsonl`、`cloud_issue_retrieval_probe.out`、`cloud_user_question_retrieval_probe.out`、`cloud_short_query_probe.out`。
- **§7 案例复核（2026-10-28 23:0x，精确清单 retry 部署后）**：最终 partial（3300 字，171s，4/5 争点）；未覆盖仍是第 1 问（`UNSUPPORTED_CITATION`）。writer 摘要：**第 3 问被 retry 救回**（`UNSUPPORTED_CITATION` → `DRAFT_VALIDATED`）；**第 1 问两次 `cited_not_retrieved` 均失败**。查 KB：**民法典 417 的原文是"建设用地使用权抵押后新增建筑物"规则，与本案租赁无关**——模型引 417 是法律错误，writer 拒绝正确；§1 fact#2 的 417 是假线索，**不要为召回 417 加 k**。下一步建议：引用类失败按 **claim-level drop**（丢掉池外/非规范 claim，保留同争点已通过 claim，仍走 verifier），让第 1 问用已通过的 claim 交付；备选第二次 retry（采样、不确定）。
- 证据（案例）：`cloud_case405_result.jsonl`、`cloud_case405_writer_summary.jsonl`、`cloud_417_k20_probe.out`。
- **§7 案例复核（2026-10-29 00:1x，claim-level drop 部署后）**：claim-level drop 已上线（partial 下丢池外 claim、保留同争点通过 claim；非 partial 仍 fail-closed；**255 个 Agent 测试通过**；corrective 开关已关，回滚 tag `fazhi-backend:pre-claimdrop-20261029`）。第一次案例在**争点分解**就失败：`ISSUE_DECOMPOSITION_INVALID`（`IssueDecompositionError: Issue fact is not a verbatim request fragment`；repair detected 5 issues/27 coverage gaps/1 non-verbatim → repair_ineffective 5/0/**3 non-verbatim**），33.8s，claim drop 未走到；**重跑仍 `ISSUE_DECOMPOSITION_INVALID`（27.2s）⇒ 连续 2/2 分解失败，claim drop 仍未走到**。
- **争点分解失败是新发现的独立失败模态**：案例 5 个子问题 + 长案情，模型 repair 后 facts 非逐字；与 writer/检索/claim drop 无关。已单列 P0 并由下条修复，未混进 claim drop 的验收。
- **§7 分解修复（2026-10-29）**：`runtime._snap_label_quote`——把“列表标签+原文子项”拼接的 quote（如 `丙提出三点抗辩：② …`）吸附到原文最长连续子串；仅当剩余部分只是标签/标点才吸附（“三个月≠两个月”这类实质偏差仍不吸附、继续 repair/拒绝）。`_fact_defects` 与 `_assemble_initial_state` 两处生效；新增 `test_label_concat_quote_is_snapped_to_verbatim_subitem`；后端 371 passed；云端已部署（回滚 `fazhi-backend:pre-decompose-20261029`）。
- **§7 案例重跑（2026-10-29 01:35 UTC+8，分解修复部署后云端容器）**：分解通过，正文 2224 字符、103.5s、0 轮澄清、无错误帧；`coverage_status=partial`，5 个争点里 **4 个 `DRAFT_VALIDATED`**（claims 2→1+1 dropped、2/2、3/3、2/2）。首个争点 `issue_e1f851…`（买卖不破租赁）由 claim-level drop 落地 1 条——分解失败遮蔽的 claim drop 本次实际生效。唯一未覆盖是租金/押金争点 `issue_47e7…`：`UNSUPPORTED_NUMERIC_TOKEN`（`unsupported_total=2`，`nowhere=1` + `in_own_issue_other_sources=1`）。剩余失败面已从“写不出任何草稿”收敛到数字 token 一类。
- **数字 token 失败根因（2026-10-29 02:0x，同 state 重放 8 次）**：同一份失败 state 重放并非稳定失败（6/8 直接 `DRAFT_VALIDATED`），属采样相关；抓到三类误报/真违规：
  1. **空格形态不归一**：事实原文“租期 5 年”，claim 写“5年” → `_DURATION_RE` 不容忍数字与单位间空格，同一数字被判无源；
  2. **日期形态不归一**：用户问题写“2025.01”，claim 写“2025年1月” → 前者 token 是 `number:2025.01`，后者是两个 duration token；用户自己给的日期被算成编造；
  3. **派生计算**：定金上限推导出 `4.8万`（20%×24万）、`9.6万`（双倍）、`41.6%`（10/24），不属于任何事实/证据原文（这类仍需拦住或按 claim 丢弃）。
- **数字修复（2026-10-29）**：① `_DATE_RE`/`_DURATION_RE` 容忍数字与单位间空白，并新增“2025.01 ⇄ 2025年1月”同 token；② **用户原话里的数字视为可信来源**（`state.user_question`，用户自己提供的不判编造）；③ partial 下把**数字违规也纳入 claim-level drop**（只丢该 claim、保留同争点通过 claim），非 partial 仍 fail-closed。测试：writer/verifier/集成/数字/时效共 **266 passed**；新增空格、点分日期、用户数字、数字 drop 四类用例。
- **§7 完整案例（2026-10-29 02:16 UTC+8，数字修复部署后）**：`coverage_status=full`、`uncovered_issues=[]`，正文 2719 字符、93.7s、0 轮澄清、无错误帧；5/5 争点 `DRAFT_VALIDATED`（claims 4→3+1 dropped、2/2、3→2+1 dropped、3/3、2/2）；`agent_claim_checks` **12/12 PASS**。定金争点 `issue_47e7…` 本次 3/3 claim 全部通过。
- **五连跑（2026-10-29 02:21，分解二次修复前）**：**2/5 正文**，3 次 `ISSUE_DECOMPOSITION_INVALID`（其中 1 次客户端 HTTPError）⇒ 分解仍是主失败源，且省略号缩写是主要非逐字形态。
- **分解稳定性二次修复（2026-10-29 02:3x）**：① 省略号缩写（`丁…竞得…并办理过户登记`、`丙提出三点抗辩：…② …`）吸附为原文首段→末段的**连续跨度**（仍逐字）；② 省略号前粘连的“标签：②”按 `_LABEL_SUBITEM_SPLIT_RE` 拆成标签与列表标记分别定位。新增两条测试；云端单独分解连跑 **10/10 成功**（`cloud_decompose_probe.out`）。
- **五连跑（修复后，2026-10-29 02:54 UTC+8）**：**4/5 正文，4 次 `full`（无 uncovered）**；唯一失败 run=4 为终稿 `OVERCONFIDENT_WORDING`（红色错误，不是 partial 横幅）。正文 2748–3219 字符，耗时 90.7/100.3/112.0/115.0/128.8s（中位 112.0s）；`agent_claim_checks` 10–13 条/次，**全部 supported**（13/13、13/13、10/10、11/11）。writer 摘要 25×`DRAFT_VALIDATED` + 1×`ISSUE_CLAIMS_MISSING`（后者为重试前抖动），共 8 条 claim 被 drop。达到 §2.4 第 1 条（≥4/5 正文）；残留失败面转为终稿 `OVERCONFIDENT_WORDING`。
- 证据：`dispatch-output/agent-partial-20261028/cloud_case405_5x_after_verifier.log`、`cloud_case405_5x_after_verifier.jsonl`、`cloud_case405_5x_writer_summary.jsonl`。
- 证据：`dispatch-output/agent-partial-20261028/cloud_numeric_probe_after.out`、`cloud_case405_numeric_result.jsonl`、`cloud_case405_numeric_writer_summary.jsonl`、`cloud_case405_numeric_body.txt`。

---

## 1.5 P0：`external` 引用的「适用性盲区」（2026-10-29 新增，实测 3 条错 2 条）

### 现象

快车道（**未开 agent**）一次真实输出中，前端「参考条文」分两组：
- 蓝色「**检索依据**」3 条：民法典 405、城镇房屋租赁合同解释 14、15 → **全部正确**
- 黄色「**补充依据（未在本次检索范围内，条文存在于法律库）**」3 条 → **2 条错误**

| 引用 | 库里原文 | 判定 |
|---|---|---|
| 民法典 538 | 「债务人以放弃其债权、放弃债权担保、**无偿**转让财产等方式无偿处分财产权益…」 | ❌ **应为 539 条**（「以**明显不合理的低价**转让财产」）。本案 600 万 vs 市场价 900 万属低价，答案却把 538/539 揉成一句「无偿**或**明显不合理低价」 |
| 民法典 587 | 定金罚则 | ✅ 正确 |
| 民事诉讼法 232 | 「**第十八章　公示催告程序**…利害关系人应当在公示催告期间向人民法院申报」 | ❌ **应为 236 条**（「第十九章　一般规定…认为**执行行为违反法律规定**的，可以…提出书面异议」）。232 条与执行异议毫无关系；答案自己都写了「注：具体条文号依现行民诉法为准」，系统仍标成「存在于法律库」 |

### 根因（代码位置明确）

| 位置 | 行为 |
|---|---|
| `retrieval.py:948` `citation_verify` | 判据是**知识库存在性**，不是本轮检索范围。docstring 明确写了理由：「后者会误伤正确但未检索到的引用（study_aid 不检索、legal_query 引用未进 top-k 的真实条文）」⇒ **这是有意设计，不要简单收紧** |
| `retrieval.py:970` `classify_citation` | 只做**三态存在性分级**：`ok`（法名+条号都在库）/ `article_missing` / `source_missing`。**完全没有「语境适用性」这一维** |
| `retrieval.py:992` `classify_answer_citations` | 对答案全部引用做上述分级，供前端渲染 |

⇒ **538 与 232 都被判为 `ok`**（条号确实存在），前端于是显示「条文存在于法律库」。
用户会把这句读成「系统认可这个引用」，实际它只意味着「这个条号不是编的」。

**关键对比**：agent 路径遇到「引用不在检索依据池」会直接 `UNSUPPORTED_CITATION` 拒写终稿
（fail-closed）。**快车道没有这道闸**，所以快车道在这个维度上比 agent 更不安全 ——
这与「agent 爱拒答、体验差」是同一问题的两面。

### 改法（成本递增，建议 ① + ②）

**① 只改文案（零风险，立即做）**
前端黄框副标题从「**条文存在于法律库**」改为
「**条号真实，未核验其是否适用于本案，请自行核对**」。
不改任何逻辑，只纠正用户预期 —— **性价比最高的一条**。

**② 章节一致性校验（真正能抓错，metadata 现成）**
条文的 `metadata` 里**已有 `chapter` 字段**：

```
民事诉讼法 第二百三十二条 → chapter = "第十八章　公示催告程序"
民事诉讼法 第二百三十六条 → chapter = "第十九章　一般规定"
```

实现思路：对 `external` 引用，取该条 `chapter`，与答案中该引用**周边上下文的主题词**做一致性判断；
不匹配则降级标注（如「⚠ 该条属『公示催告程序』章，与本文论述的『执行异议』不一致」）。
建议先做**确定性关键词表**（章节名关键词 vs 上下文关键词），覆盖高频误引场景，
不必上模型 —— 避免引入不确定性。

**③ 现行有效性校验（`status` 字段现成）**
`metadata.status`（如「现行」）、`effective_from`/`effective_to` 已在库里。
对 `external` 引用校验其现行性；已废止/被修正的条号应显式提示（民诉法 2021→2023 修正后条号整体位移，
这正是 232/236 这类错误的温床）。

### 验收标准

- 用本次案例（§7）跑一次快车道，538 与 232 必须**不再显示为无警示的「补充依据」**
- 「检索依据」组（蓝框）的 3 条**不得因本改动而被降级**（避免误伤 `in_context`）
- `classify_citation` 的既有三态语义不变（现有测试全绿），新维度为**附加标注**而非替换
- ⚠️ **不要**把判据收窄为「仅允许检索范围内的引用」—— 那会重现被用户批评的过度拒答，
  且 docstring 已说明会误伤 study_aid / 未进 top-k 的正确引用

### 1.5b 落地（2026-10-29）

- **① 文案**：`MessageBubble.tsx` external 副标题改为「补充依据（条号真实，未核验其是否适用于本案，请自行核对）」，tooltip 同步。
- **② 章节适用性**：`retrieval.article_chapter`（取 `metadata.chapter`）+ `_chapter_warning`（章节主题词表 vs 引用周边 ±120 字）；`citation_grounding_status(..., chapter_lookup=...)` 的 external item 新增 `chapter` / `applicability_warning`；`main.py` 快车道传入 `article_chapter`；前端 external 项显示章节，mismatch 时玫瑰色 ⚠ + tooltip。未知章节不告警；`classify_citation` 三态与 `in_context` 不变。
- **测试**：后端 57 passed（含新 `test_external_citation_chapter_applicability_warning`）；前端 `tsc --noEmit` + vitest 113 passed。
- **部署**：前端 `fe-artifacts-20261029`（sha256 `0abf89e3…`）→ prebuilt；回滚 `fazhi-frontend:pre-external-20261029`；后端 hot-copy/commit；回滚 `fazhi-backend:pre-external-20261029`。云端 `partial=True / corrective=False`。
- **验收**：§7 快车道探针（容器内 `fast405`）：external 3 条 = 587（违约责任章，无误报）/ 154（民事法律行为章，无误报）/ **232（公示催告程序章 → 已标警告）**；in_context 6 条全部不受影响；最终 **24/24 通过**。本次快车道模型引 154 而非 538；① 文案对任何 external 都生效，② 不覆盖**同章**的 538/539 混淆（两条都在“合同的保全”章）——538 类问题靠 ① 的“未核验适用性”提示，③（status/现行性）未做。

---

## 1.6 P1：受控沉淀的「近重复直返」在法律咨询场景护栏错配（2026-10-29 新增）

> ⚠️ 本节是**快车道**（非 agent）机制，但同属「复用可核验」问题域，故并入本文。

### 现有机制（已实现，设计正确）

```
高有据问答 → qa_candidates（待审队列）→ 管理员采纳 → qa_pairs（向量集合）→ 相似命中直返
```

**入队门槛**（`curation.py:21` `should_curate`）——三条同时满足：
```python
grounded >= 0.7          # 有据分门槛（DEFAULT_GROUNDED_THRESHOLD）
has_citation(answer)     # 必须带《法名》第X条 形式引用（CITATION_RE）
len(answer) > 20         # MIN_ANSWER_LEN
```
注释原文：「只有"高有据 + 带法条引用 + 非空答"的问答才进入待审，避免幻觉/低质答案污染知识库」。

### 两套直返路径（勿混为一谈）

| 路径 | 内容 | 阈值 | 护栏 | 位置 |
|---|---|---|---|---|
| **E2 `qa_pairs`** | 人工审核过的问答对 | `_QA_DIRECT_RETURN_THRESHOLD = 0.92` | 「低于则回落 LLM」 | `main.py:1471`、`knowledge_service.py:364 search_qa` |
| **E1 `answer_cache` 近重复** | 运行时缓存（进程内 LRU 512 / **TTL 6h**） | `NEAR_DUP_THRESHOLD = 0.95` | **结构护栏**：`polarity` / `option_count` / `label_system` / `options_fingerprint` | `answer_cache.py:22`、`main.py:1449` |
| E1 `answer_cache` 精确 | 字面 key | — | `scope` = 意图 + **cutoff 时效日** + 证据集合 | `answer_cache.py:29 make_scope` |

**已内建的正确设计**（勿推翻）：
- `key` 含 `cutoff_date` ⇒ 跨天自然不命中，避免引用昨日已失效条文
- 仅缓存「安全形态」：单轮无图 `legal_query`/`study_aid` + 检索命中 + 自检 PASS + 写闸
- `clear()` 由 `retrieval.invalidate()` 在知识增删时调用
- 缓存是「性能/省配额优化，非正确性依赖」（`answer_cache.py` docstring）

### ⚠️ 风险：结构护栏是为「选择题」设计的，对开放式咨询不生效

`answer_cache.py` 开头限定只缓存 `legal_query / study_aid`；而 `_cache_guards` 抽的四个维度是
**极性 / 选项数 / 标号体系 / 选项指纹** —— 这些全部来自**选择题**结构。

对**开放式法律咨询**（如「商铺先抵后租，承租人能否对抗」）：
- 没有选项 ⇒ `option_count` / `options_fingerprint` 恒为空
- 没有 A/B/C/D ⇒ `label_system` 恒为空
- 疑问/陈述极性无区分度

⇒ **护栏实际退化为「仅看余弦 ≥0.95」**。

而法律场景存在**向量极近、结论相反**的结构性难题：

```
「抵押在租前，承租人能否对抗」   vs   「租在抵押前，承租人能否对抗」
        相似度 > 0.95                       结论完全相反
```
（民法典 405 条：只有「抵押权设立**前**已出租并转移占有」才不受抵押权影响）

**后果**：若「先租后抵」版本曾被沉淀并审核通过，开放式问题「先抵后租」极易命中它，
**直接返回相反结论，且用户看不出任何异常**——这比 §1.5 的引用错误更危险，
因为引用错误至少还能看到条文原文对不上，而这里答案整体是「看起来专业且已审核过」的。

### 建议（按性价比）

**① 开放式咨询禁用 E1 近重复直返（P1，改动小）**
E1 保留**精确 key** 命中即可；近重复直返只留给结构化的 `study_aid`（法考题）。
`feature_similar_cache` 的开关已存在，按 `intent` 分流成本极低。

**② 给开放式问题加「关键事实要素指纹」（P1，治本）**
对标现有 `options_fingerprint`，但抽取维度改为法律相关的**事实要素**：
- **时间先后关系**（抵押先/租先、登记先/占有先）← 本案决定性要素
- **主体角色**（承租人/买受人/抵押权人/债权人）
- **标的类型**（住宅/商铺/动产/权利）
- **金额或期间区间**（是否超阈值、租期长短）

指纹不一致 ⇒ miss。这套指纹对「语序反转」敏感，而余弦不敏感。

**③ 直返时显式标注（P2，零风险）**
UI 标注：「本答复复用**已审核问答**，非针对本问题实时分析」。
让用户知道这不是为他算的 —— 与 §1.5 的文案修正同一思路：**信息披露优于静默降级**。

### 验收标准

- 构造一对「先租后抵 / 先抵后租」的问句，**必须不退化为同一条直返**（当前很可能会）
- `study_aid`（带选项的法考题）的 E1 近重复命中**不受影响**（现有测试全绿）
- 精确 key 命中与 `cutoff` 跨天不命中的既有语义**不变**
- ⚠️ 不要取消 `qa_pairs`（E2）直返 —— 那条有人工审核背书，是现有机制里最可靠的一环

---

## 2. P0：争点 writer 并行化（解决"等很久"）

**现状** `backend/agent/service.py`（`partial` 变量附近，约 416 行起）：

```python
for issue in state.issues:                      # ← 串行
    issue_result = runtime.writer.render_issue(state, issue.issue_id)
    ...
    drafts.append(issue_result.draft)
draft = merge_draft_answers(drafts)             # ← 全文合并
```

**目标**：把争点 writer 改成**有界并发**（如 `asyncio.gather` + `Semaphore(3)`）。

**必须保留的语义**（否则会破坏既有保证）：
1. **取消检查**：每个争点前检查 `cancelled()`（现在有，别丢）
2. **失败归因精确到争点**：`uncovered.append((issue.issue_id, reason_code))` 的语义不变
3. **"全部失败仍整轮失败"**（`if not drafts:` 分支）语义不变
4. **`partial_delivery` 开关关闭时行为逐字不变**（这是既有契约，见 §2 上方注释）
5. ⚠️ **`render_issue` 是否线程安全 / 是否依赖 `state` 的可变写入** —— 先确认再并发。
   若它内部会改 `state`，需要为每个并发任务传只读快照。

**验收**：
- 5 争点案例的端到端耗时较现在下降 ≥ 50%（用 §7 原 prompt 计时，前后各 3 次取中位数）
- `pytest -m 'not slow'` 全绿（当前基线 1650 passed / 10 skipped）
- 构造"某争点失败"用例，确认 `uncovered` 归因与串行版一致

---

### 2a 落地（2026-10-29）

- **实现**：`service.py` 的 partial 分支改为 `ThreadPoolExecutor(min(agent_writer_max_concurrency, len(issues)))`，默认 3（`settings.agent_writer_max_concurrency`）；非 partial 仍走原串行 fail-fast 路径。结果按 `state.issues` 原顺序归因/合并；取消检查、`ISSUE_CLAIMS_MISSING`/corrective 重试、全部失败仍整轮失败的语义不变。注入替身没有新字段时 service 按 1 兜底，既有测试逐字不变。
- **测试**：新增“两个争点必须同时进入 writer”的屏障用例（`max_active==2`）；相关 agent/集成/verifier/writer/runtime/stream 共 278 passed。
- **实测（同一 §7 五争点案例）**：串行基线 5 跑 90.7/100.3/112.0/115.0/128.8s（中位 **112.0s**，本次 4/5 正文）；并行 3 跑 73.9/52.5/69.5s（中位 **69.5s**，3/3 full）⇒ 对串行基线 **-38%**，对 10-28 原始 171s 案例 **-59%**。并行下 5 次 writer 摘要集中在约 23s（串行约 50s），writer 阶段本身接近减半。
- **结论**：对“当前串行基线”未达到 50% 的端到端目标——瓶颈已转移到争点分解/检索/终稿；继续加并发会引入 429/配额风险，不建议用 >3。下一步若还要提速，应针对分解/检索链路。
- 证据：`dispatch-output/agent-partial-20261028/cloud_case405_5x_after_parallel.log`。

---

## 3. P0：Agent 路径接 `step` 事件（解决"毫无反馈"）

**现状**：`main.py:2447` 的 `_steps` 只在合同分支构造。Agent 路径只推
`{"type":"agent_status","status":"processing"}` 和 `waiting_user`。

**现成机制可复用**（合同分支注释已写明设计原则）：

> SSE 分析进度（二期）：报告生成前回放**确定性骨架已完成的步骤**——真实数据，非虚假进度条

**目标**：Agent 路径推**真实步骤**，例如：

```json
{"type":"step","steps":[
  {"label":"拆解争点","detail":"识别 5 个争点"},
  {"label":"检索法条","detail":"争点① 命中 民法典405、406 条"},
  {"label":"起草","detail":"已完成 2/5 个争点"},
  {"label":"校验","detail":"待核验 3 个争点"}
]}
```

**硬约束**：**必须是真实数据**，禁止估算/伪造百分比（合同分支的注释就是这个原则）。

**验收**：
- 用 §7 prompt 跑一次，前端能连续看到 ≥3 次 `step` 更新
- 每一步的 `detail` 数字都能在日志/state 里找到对应真实值

---

## 4. P1：整稿否决 → 逐争点交付（让第一问先到用户手里）

**现状**：`service.py` 里 `verifier.verify(...)` 对合并后的整稿判定；非 PASS 则整轮失败
（`fail-closed`，是有意的）。

**目标**：争点答完一个就允许交付一个（渐进式），而不是等全部争点 + 整稿校验。

**⚠️ 风险提醒**：这与 `fail-closed` 的安全设计冲突。建议的最小改动是
**"已通过校验的争点先交付，未通过的标注未覆盖"**，而不是放宽校验本身。
即：**保持 verifier 严格性不变，只改变交付时序与粒度**。

**验收**：
- 构造"争点①过、争点②不过"的用例：用户能先收到争点①结论 + 未覆盖提示
- 不得出现"未通过校验的内容被当作结论交付"

---

## 5. P1：砍掉「已确认事实」复述（解决"太长"）

实测输出里有一整块「已确认事实」，把用户 prompt 里的事实逐条复述（20+ 行），纯冗余。

⚠️ **尚未定位这段文案的生成来源**（`grep 已确认事实` 在 `backend/**.py` 无命中
⇒ 可能在提示词文件 / `domain_rules.py` / writer 的模板里，也可能由模型自行组织）。
**先定位来源，再决定是改提示词还是改渲染。**

**验收**：同一 prompt 的输出长度下降 ≥ 30%，且结论部分信息量不减少。

---

## 6. P2：澄清去重 + 输出纪律

| 问题 | 现象 | 方向 |
|---|---|---|
| 澄清重复 | 第 1 轮问"送达时间方式"，第 2 轮问"是否依法通知"，实质同一件事 | 澄清问题生成时做**语义去重**；或让 planner 输出"该争点是否真的需要澄清"的判断 |
| 结论自相矛盾 | 「建议」段说"丙可依 539 条请求撤销"，「风险提示」段又说"难以直接适用 154 条" | 终稿增加**跨段落一致性检查**（现有 `detect_conclusion_contradiction` 已有雏形，可扩展） |
| 引用全集偏窄 | 五问只挂 539/154，缺 405/725/716 | 与 §1 的检索问题同源，先定位 (a)(b)(c) |

---

## 7. 失败案例原文（复现用）

> 甲将其名下一处商铺于 2023年3月抵押给乙银行，办理了抵押登记，担保 500 万元借款。
> 2024年1月，甲将该商铺出租给丙，租期 5 年，月租金 2 万元；丙当日预付了一年租金 24 万元并实际搬入占有。
> 租赁合同未提及抵押事宜，甲未告知丙抵押事实，丙亦不知情。
> 2025年6月，甲无力偿债，乙银行起诉并获生效判决后申请强制执行，法院裁定拍卖该商铺。
> 拍卖公告中未列明承租人信息。丁（甲之侄）以 600 万元竞得（同期市场价约 900 万元），并办理过户登记。
> 丁取得产权后要求丙限期搬离，主张"租赁成立于抵押之后，买卖不破租赁不适用"。
> 丙提出三点抗辩：① 自己签约时不知抵押、已付租并占有，租赁应受保护；② 作为承租人享有优先购买权，
> 丁与甲系亲属且明显低价，应撤销该交易；③ 此前于 2025年3月另向甲支付"续租定金"10 万元（收据注明"定金"），
> 甲尚未退还。另查明：丙的 24 万元预付租金对应的租期（2024.01–2025.01）已届满，
> 2025.01 之后的租金丙未再支付；丁要求搬离时，丙尚在占有使用。
> （随后 5 个子问题，见会话原文）

**澄清应答**（复现时用）：
- 第 1 轮「法院送达拍卖通知书的具体时间及方式」→ `不知道`
- 第 2 轮「法院是否依法通知承租人参加拍卖/行使优先购买权」→ `没有依法通知`

**本次实际结果**：`coverage_status=partial`，未覆盖争点 = 第 1 问（买卖不破租赁），
原因码 `UNSUPPORTED_CITATION`。

---

## 8. 不要做的事

1. ❌ **不要为了"答得更快"放宽 verifier** —— 引用/数字校验是产品护城河，宁可慢
2. ❌ **不要伪造进度** —— `step` 必须来自真实 state，合同分支的注释就是这个原则
3. ❌ **不要在 Agent 路径暴露自然语言思维链** —— 未验证的中间推理会被当结论读，
   且与终稿矛盾时（本次已出现）信任损失大于等待焦虑。用结构化进度替代
4. ❌ **不要动 `state_machine.py` / `prompts.py` / `gate5_judge.py`** —— 冻结中，需走解冻流程
5. ⚠️ **不要改 `docker-compose.override.yml`** —— 它是另一个会话的本机实验文件
   （我曾在其中加 `RERANK_ENABLED=false`，该文件随后被删）。本机 rerank 已按 Owner
   决定关闭（走本地精排，云端才有 rerank）

---

## 9. 建议顺序

0. **§1.5 的 ①（改文案）** —— 零风险、10 分钟，立刻纠正用户对「补充依据」的误解
1. **验 §1 的 (a)(b)(c)** —— 定位 405 为什么没进结论【半天，最高价值】
2. **P0-2 争点并行化** —— 解决"等很久"
3. **P0-3 Agent 接 step 事件** —— 解决"无反馈"，成本最低
4. **P1-5 砍冗余复述** —— 解决"太长"
5. **P1-4 渐进式交付** —— 与 fail-closed 有张力，放后面
6. **P2 澄清去重 / 跨段一致性**
