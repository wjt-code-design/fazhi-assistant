# 问答证据与引用链专项审查

审查日期：2026-09-18。固定版本：`27d5363ace42d22678293c8878f1d72daa4e2f19`。

## 结论

确认三项工程缺陷（均 P2），另复现一项已知但未补齐的核心能力缺口（P1）：结构化绑定通过，不能证明结论与事实一致。现有190项相关测试通过，但本次反例仍能触发错误。

范围为 Agent 的“检索 → 证据物化及争点绑定 → writer → verifier → 最终闸门 → 引用展示/历史覆盖提示”。这是当前功能审查，不声称问题由最新提交引入；不重复上轮费用公式、时效函数和伪调用误报。后端动态检查使用本提交的隔离副本，全部未提交修改排除。未实施业务修复、未调用真实模型、未改写生产数据库或索引。

规范依据包括 Agent V1 设计中的不可变证据快照、事实编造检查、引用存在性不能替代语义核验，以及 2026-09-16 主线交接书的引用展示规则。结论分为“已知能力缺口”和“工程缺陷”，不将结构性局限包装成新发现回归。

## 已知能力缺口

### E1 [P1，高置信] 与已绑定事实相反的结论仍获得 supported=True，并通过最终输出闸门

位置：[verifier.py:362](C:/Users/33393/Desktop/ai-legal-helper/backend/agent/verifier.py:362)、[verifier.py:491](C:/Users/33393/Desktop/ai-legal-helper/backend/agent/verifier.py:491)。

最小反例：

- 已确认事实为“借款尚未清偿。”；claim 通过正确的 `fact_id` 绑定这条事实。
- 证据为有效成文法、正确关联本争点，内容说明应按约定期限还款。
- 生成 claim 写“根据《民法典》第六百七十五条，该借款已经全部清偿。”。
- 实际结果：writer `READY`，verifier `PASS`，该 claim 的 `supported=True`，`finalize_verified_agent_answer` 返回 `READY`。
- 最终答案同页出现“已确认事实：借款尚未清偿”和“可执行建议：借款已经全部清偿”。正向对照“尚未清偿”同样通过。

原因：绑定完整性、数字来源、引文存在性、争点覆盖及措辞检查都可通过；没有检查这个关键事实命题的正反方向。最终 citation/quality 闸门也不执行这类核验。`supported=is_pass` 将这些结构检查的通过提升成了每项结论受支持的标记。

独立要求：[V1设计:122](C:/Users/33393/Desktop/ai-legal-helper/docs/process-archive/superpowers/specs/2026-08-27-legal-agent-v1-design.md:122)要求检查事实编造和矛盾，`:134` 明确引用存在性不能代替 Claim-Evidence 语义校验。[后续执行计划:183](C:/Users/33393/Desktop/ai-legal-helper/docs/next-assistant-execution-plan-20260911.md:183)已将“证据绑定但语义不支持”列为独立任务，因此这属于已知未完成能力，而非新引入回归。

影响：错误事实可在默认开关配置下进入最终答复，并保留看似通过核验的记录。本次是假生成器提供固定反例，证明防线允许这种错误，不代表真实模型发生频率或线上事故。

最小建议：优先围绕已确认关键事实补内容一致性验收与有界矛盾检查；将“结构检查通过”和“事实/法律结论得到支持”的含义区分清楚。仅改标签不能修正错误答案。不要因为本例就引入通用多模型评审框架，也不要把同一个生成模型的自评视作独立证明。

## 工程缺陷

### E2 [P2，高置信] 精确查条工具漏做条号归一，已有条文被报为未找到

位置：[exact_article.py:19](C:/Users/33393/Desktop/ai-legal-helper/backend/tools/exact_article.py:19)、[retrieval.py:350](C:/Users/33393/Desktop/ai-legal-helper/backend/retrieval.py:350)。

`LookupArticleInput` 接受一般字符串条号，工具直接传入 `exact_article_lookup`；后者只归一法名，然后按原条号等值查库。库内元数据若为“第五百七十七条”，输入“第577条”返回空。

本轮真实 `exact_article_lookup` 配合单条匹配的内存 collection：同一来源、同一基准日，阿拉伯条号结果为 `[]`，中文条号返回 `OLD_SNAPSHOT`。仅替换存储依赖，没有重写过滤函数。普通检索的 `parse_article_query` 和前端 `/api/law` 路径已经调用现有 `_normalize_article`，所以这是工具路径漏接，非库中缺文。

影响：Planner 使用合法的阿拉伯条号时可能收到空证据，消耗重试/工具预算，继而误报知识不足或漏掉争点。

最小建议：在共享的 `exact_article_lookup` 边界复用现有 `_normalize_article`；补中文、阿拉伯、全角及“之”条号等价命中的工具级用例，不新增解析器。

### E3 [P2，高置信] 引用原文卡按今天重新查询，未绑定答复采用的证据版本

位置：[useLawCards.ts:27](C:/Users/33393/Desktop/ai-legal-helper/frontend/lib/hooks/useLawCards.ts:27)、[main.py:1309](C:/Users/33393/Desktop/ai-legal-helper/backend/main.py:1309)、[retrieval.py:347](C:/Users/33393/Desktop/ai-legal-helper/backend/retrieval.py:347)。

Agent 查条工具传递 run 的 `law_as_of`；前端原文卡却只传书名和条号，接口未传 cutoff，检索默认今天。前端共享缓存键也只有书名和条号，不含 run、证据或版本。

动态反例使用**合成版本夹具**：同一来源及条号，旧快照有效至2024-12-31，新快照从2025-01-01生效。按 `2023-01-01` 查询得到 `OLD_SNAPSHOT`，省略 cutoff 得到 `NEW_SNAPSHOT`。这些日期和版本是测试数据，不是对某一真实条文修订历史的陈述。

结合已核对的调用链：旧版本答复点击原文会重新取现行内容；若今天已无有效版本，也可能返回404。即使当前答复默认当天，历史消息跨法规更新后仍有同样问题。不同消息的同条号缓存还会复用同一结果。

影响：用户看到的“原文”可能不是答案当时采用的证据，破坏复核来源的一致性。版本切换由真实检索函数复现；本轮未进行浏览器点击或真实历史库验收。

最小建议：聊天引用优先读取消息所属 run 的已绑定证据快照，并明确快照/原文的展示范围；需完整条文时按证据版本查询。缓存键包含相应证据或版本身份，卡片标注基准日。独立法条速查可继续默认今天。

### E4 [P2，高置信] verifier 接受的 snippet 引文在“法律依据”区被漏列

位置：[verifier.py:192](C:/Users/33393/Desktop/ai-legal-helper/backend/agent/verifier.py:192)、[verifier.py:400](C:/Users/33393/Desktop/ai-legal-helper/backend/agent/verifier.py:400)。

验证引用时使用绑定证据的 `source_ref + snippet`；渲染法律依据却只从 `source_ref` 提取。两处认可集合不同。

反例：唯一有效证据的 `source_ref` 为 `民法典#第五百七十七条`，snippet 提及《民法典》第五百八十四条；claim 绑定该证据且只引用584。writer `READY`、verifier `PASS`、最终闸门 `READY`，但最终“法律依据”显示“（无）”，正文仍有584。

独立要求：[主线交接书:221](C:/Users/33393/Desktop/ai-legal-helper/docs/final-agent-mainline-handoff-20260916.md:221)明确从绑定证据的 `source_ref` 和必要的 `snippet` 提取引用，再与 claim 正文取交集。

影响：已被当前引用规则认可的条文没有列入法律依据区，导致展示自相矛盾。本项不是“正文引用消失”，也不证明584具体结论在语义上得到支持；那是E1所述另一层检查。

最小建议：统一验证与展示的引用集合，并按实际引用生成正确标签；不能简单沿用父证据577的标签来展示584。

## 已核查但不新增问题的边界

- 争点隔离：成功 Observation 决定证据归属，writer/verifier 检查跨争点引用；已有对应测试，本轮未找到可报告的跨争点泄漏。
- 部分交付：service 追加未覆盖说明，SSE final 携带覆盖字段，历史记录可投影，前端有顶部警示。静态链路与集成测试未发现隐藏未覆盖争点的问题；不等于已做浏览器验收。
- 共享条文可能只保留一条 `AgentEvidence` 行，但 state 中多个争点仍能通过 Observation 绑定。目前未发现会因此错误回答的消费者，不升级为功能缺陷。
- 过度承诺检测中“术语优先可放过同句承诺”已有明确接受风险测试，本轮不重新计为新bug。
- 上次报告的6项未因本次190测试通过而消除。

## 验证证据与限制

隔离源码与JUnit位于：[审查目录](C:/Users/33393/Desktop/ai-legal-helper/dispatch-output/evidence-chain-review-27d5363-20260918)。

在其中 `committed/backend`，使用项目 venv，设置测试用 LLM/JWT 配置及 `HF_HUB_OFFLINE=1`、`TRANSFORMERS_OFFLINE=1` 后运行：

```powershell
& 'C:\Users\33393\Desktop\ai-legal-helper\backend\venv\Scripts\python.exe' -m pytest tests/test_agent_writer.py tests/test_agent_verifier.py tests/test_tool_gateway.py tests/test_agent_chat_integration.py -q -m 'not slow' --junitxml='../../evidence-chain-junit.xml'
```

结果：**190 passed / 5 warnings，54.80秒，exit 0**。警告包括依赖弃用及一次 `.pytest_cache` 写入受限，不影响测试执行结果。没有将全仓测试、真实知识库、生产配置或浏览器操作算入本次通过范围。

独立反例复用了固定提交中的 `make_state/render/one_claim` 和真实 writer/verifier，明确绑定事实ID；假生成器只提供候选文本，不代替被审查的校验逻辑。最终闸门使用真实 `finalize_verified_agent_answer`、`citation_verify`、`quality.self_check` 及输出归一，只把知识库存在性查询替换为精确的内存引用集合；不是把整个 citation/quality 检查替换成“总是通过”。

最小复现E1的核心代码（在隔离副本 `committed/backend`、测试环境下执行；不调用模型）：

```python
from tests.test_numeric_matching_v2 import make_state, render, one_claim
from agent.writer import derive_fact_id
from agent.verifier import DeterministicVerifier, render_verified

state = make_state(
    question="合同债务如何处理？",
    facts=["借款尚未清偿。"],
    evidence_specs=[("ev-1", "《民法典》第六百七十五条",
                     "借款人应当按照约定的期限返还借款。")],
)
claims = one_claim("ev-1", "根据《民法典》第六百七十五条，该借款已经全部清偿。")
claims[0]["fact_ids"] = [derive_fact_id("issue-x", state.issues[0].facts[0])]
draft = render(state, claims).draft
result = DeterministicVerifier().verify(state, draft)
print(result.verdict, result.claim_checks)
print(render_verified(state, draft, result))
```

该片段复现到 verified render；本轮还另外执行了上述真实 finalizer，结果为 `READY`。导入该层时，测试 conftest 预先设置私有数据库，隔离副本承接索引初始化；有 Chroma telemetry 调用签名警告，未影响反例。没有测量真实模型出错率，不给出准确率或上线就绪结论。

## 建议执行顺序

E2与E4都是局部口径不一致，适合先做小修复并锁定回归。E3单独处理消息与证据版本关联，不必重做整个法条卡。E1应作为独立的关键事实一致性任务：先固定清偿/未清偿这类可判定反例和验收边界，再实施最小防线；在此之前不能将结构PASS宣传为完整的事实或法律正确性证明。
