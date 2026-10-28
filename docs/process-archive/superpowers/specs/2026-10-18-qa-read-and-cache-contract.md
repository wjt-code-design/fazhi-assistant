# QA候选选择、撤回与历史来源追踪：分阶段设计（2026-10-18）

状态：已确认产品原则与分阶段全范围要求的技术方案；未实现、未跑产品测试。H01历史/摘要已纳入第三阶段必做，不再是待决定是否做的缺口；具体旧未知来源输入策略在该阶段对齐，不能据文档宣称全部撤回路径闭合。

依据：[Owner五项决策](C:/Users/33393/Desktop/ai-legal-helper/docs/full-scope-decisions-20261018.md)、[完整执行书](C:/Users/33393/Desktop/ai-legal-helper/docs/process-archive/superpowers/plans/2026-10-15-full-scope-remediation-and-closeout-execution-plan.md)、[复核报告](C:/Users/33393/Desktop/ai-legal-helper/reports/reviews/handoff-work-report-20261018/review-results.md)。本设计只细化W06/C21及相关W12定向验证，不重开其他W票。

## 1. 对象与可查事实

候选根：`C:/Users/33393/Desktop/ai-legal-helper/.worktrees/nondeploy-closeout-20261010`；本次只读核对HEAD为`042f8090c4d76ed0289b26935b222259fa30292e`、工作树干净。主仓既有21项tracked修改仍须保护；执行前重新核定对象，不按旧SHA覆盖其他人的工作。

| 当前事实 | 源码位置 |
| --- | --- |
| C03=P的旧决策正文要求高分仅入pending；但当前create_candidate仍有高分approved并add_qa_pair的分支 | [当前写侧](C:/Users/33393/Desktop/ai-legal-helper/.worktrees/nondeploy-closeout-20261010/backend/knowledge_service.py:470)；旧RUN/task-status.json的c_gates.C03.shapes_20261017.P |
| 原始`search_qa`只取k=1；cosine与非cosine两条计分分支；公开score舍入4位 | [knowledge_service.py](C:/Users/33393/Desktop/ai-legal-helper/.worktrees/nondeploy-closeout-20261010/backend/knowledge_service.py:387) |
| 原始查询还用于种子/离线语料的去重，不能直接塞进产品读取策略 | [现有接缝说明](C:/Users/33393/Desktop/ai-legal-helper/.worktrees/nondeploy-closeout-20261010/backend/tests/test_request_bootstrap.py:708) |
| 产生处调用`deps.search_qa`，随后用统一资格函数判一次；显式历史日期绕过QA | [request_bootstrap.py](C:/Users/33393/Desktop/ai-legal-helper/.worktrees/nondeploy-closeout-20261010/backend/request_bootstrap.py:628) |
| 请求内QaHit记忆状态，当前无“发送前强制新读”入口 | [qa_eligibility.py](C:/Users/33393/Desktop/ai-legal-helper/.worktrees/nondeploy-closeout-20261010/backend/qa_eligibility.py:208) |
| 缓存保存答案/来源/护栏，尚不保存QA依赖；LRU已有本进程generation保护 | [answer_cache.py](C:/Users/33393/Desktop/ai-legal-helper/.worktrees/nondeploy-closeout-20261010/backend/answer_cache.py:53)、[LRU](C:/Users/33393/Desktop/ai-legal-helper/.worktrees/nondeploy-closeout-20261010/backend/retrieval_core.py:155) |
| main有1个精确缓存读取、相似兜底和3个缓存写入点；messages提前构造 | [main.py](C:/Users/33393/Desktop/ai-legal-helper/.worktrees/nondeploy-closeout-20261010/backend/main.py:2250) |
| SQL有eligibility_version与vector_doc_id；拒绝增加版本，重新批准会换doc id | [models.py](C:/Users/33393/Desktop/ai-legal-helper/.worktrees/nondeploy-closeout-20261010/backend/models.py:68)、[decide_candidate](C:/Users/33393/Desktop/ai-legal-helper/.worktrees/nondeploy-closeout-20261010/backend/knowledge_service.py:556) |
| 历史assistant及summary也进入prompt，而Message没有QA依赖字段 | [历史输入](C:/Users/33393/Desktop/ai-legal-helper/.worktrees/nondeploy-closeout-20261010/backend/main.py:484)、[Message](C:/Users/33393/Desktop/ai-legal-helper/.worktrees/nondeploy-closeout-20261010/backend/models.py:43) |

## 2. 三阶段与选择理由

**前置W06-P0：落实已裁暂停自动批准。** C03=P不是只增加approval_source标签。当前高分自动approved/写向量的分支必须先按已裁要求改为仅pending，保留明确人工采纳和旧记录的读资格处理；不重问是否暂停，也不直接改生产存量。这是前次方案缺少的明确前置修复，静态源码差异已证，运行反例须在Task 0隔离后取得。

**C21-A：有界候选选择。** 保留原始查询语义，增加服务侧候选适配器；资格继续由`qa_eligibility`唯一裁决，新增纯选择函数仅处理顺序与明确重复。无新增库表、模型或依赖。

**W06-B：缓存依赖与输出前复核。** 在现有缓存条目中存不可变QA依赖快照；命中、生成前及首次正文输出前按阶段复核。保留本进程generation，跨进程撤回依靠新的SQL读取，不靠TTL或本地clear猜测。

**W06-C：历史回答、摘要及派生输入来源追踪。** 在新消息和摘要中持久化真实依赖，统一生成专用于模型的安全上下文，覆盖查询改写、普通回答和Agent记忆/恢复；隔离失效来源的派生QA再入库。原文和UI历史保留，旧不可追踪内容不补造可信身份。该阶段为最终计划必做项。

比较过的替代：直接改`search_qa`会改变去重/探针；同分固定取第一条会掩盖分歧；新增模型判等价增加不确定性；全局消息总线或新epoch表会扩大迁移与运维范围。当前已有SQL身份/版本及LRU，可先复用。纯选择逻辑单列一个标准库模块；不重构main整体、不扩展管理UI。

## 3. C21-A明确契约

### 3.1 窗口与分数

- 技术起点为K=8，另取1个边界哨兵，最多返回9条原始候选，只对前8条作可服务选择。8是工程初值，不是实测最优或行业标准；定向测试对照K=1/4/8，超过8或改变阈值需更新设计及对应证据。
- 每个请求最多1次向量候选查询，不递归补池。前8条均拒绝时返回空，不能拿第9条“顺手兜底”。哨兵只判断边界风险，不作为第9个服务项。
- cosine沿既有1-distance夹取[0,1]；非cosine沿既有embedding余弦口径，query只嵌入1次、候选最多1次批量嵌入9条。计分异常/NaN/Inf不放行，不偷换向量距离为余弦，不声称替身向量证明真实排序。
- 保留检索阈值0.7、QA直返阈值0.92及现有指纹、来源、时效/版本守卫。内部用未舍入有限分数，最高合格分与各候选之差≤1e-6视为本方案“同等匹配”；以最高分为固定锚，不能相邻链式扩组。公共score仍保持4位格式。
- 哨兵分数落入所选最高分的同分带，或其分数高于该带时，退出直返/QA注入，reason=window_boundary。窗口不足9条时不凭空制造耗尽。有限ANN窗口只证明窗内规则，不保证全库召回/全局确定性。

### 3.2 资格、重复与稳定选择

- 每条先复用现有`qa_read_eligible`完整判据；拒绝的高分项不挡住窗内下一条合格项。SQL/来源查询失败不得变成“没有链所以允许”。真实无链记录仍遵原来源/时效放行面，不把本票变成生产迁移。
- 在最高合格同分组内，比较完整五元组：`question, answer, evidence, law_as_of_basis, fingerprint`。正文/问题/依据只统一CRLF为LF，保留空格、标点、数字、否定词与引用顺序。前三者必须非空；基准日必须有效；fingerprint键必须存在，非选项题允许空值。
- 当前没有可证明“同一答案版本”的独立不可变标识，因此不以同一candidate id自动合并不同内容。仅采用上述严格字段一致分支；SQL资格版本也不是法律适用版本。
- 同分组有不同元组、必要字段缺失或无稳定身份，返回None，reason=ambiguous或unstable_id；不向prompt塞任选一条，不增加模型判等价。
- 确定重复且身份齐全时，按向量doc id的Unicode字典序、再按candidate id数值选最小项；无candidate id的真实种子可用doc id。只有一个最高合格项时沿既有守卫处理，不为去重额外删除单条旧语料。
- 返回原QaHit对象，保留doc_id及请求槽；禁止用dict复制把身份丢掉。选择reason通过独立结果/日志传递，不向公开hit字典塞测试/SQL字段。
- 相似且合格不保证结论支持性、法律正确性或对当前事实适用；本票不替代W03/W08独立质量验收。

## 4. W06-B明确契约

### 4.1 依赖与缓存

- 缓存依赖是生成实际使用的QA记录，不是“当前请求恰好命中的QA”。每项包含candidate id、vector doc id、eligibility_version，以及SQL的question/answer/evidence确定性摘要；摘要只在进程内部核对，不写日志/报告。不从答案引用反推依赖，不缓存可变QaHit/state_slot。
- 收集依赖时核SQL记录内容与选中hit一致、链映射一致，再保存冻结值。SQL没有law_as_of_basis，不能把created_at或eligibility_version冒充法律版本；保留原hit的已验基准日及既有来源/版本检查。
- 三态：`None`表示依赖未知；空tuple表示该次完整构造输入已确认没有使用QA；非空tuple表示完整QA依赖。旧缓存、缺追踪身份的QA参与生成、覆盖不全的路径均为None，不读/不写可复用缓存。只有本次输入生产者能签发“已知空”，不能在put默认空值蒙混。第三阶段完成前，存在未追踪summary/assistant历史的输入也不能签已知空；有无当前qa_hit不能替代整份输入的依赖判定。
  **2026-10-19 Owner 口径补裁（与上句冲突时以本句为准）**：W06-C 三态投影上线后，“输入”以**投影后**的实际生成输入为准——未知来源 assistant/摘要已被 `load_model_context` 剔除、不再属于模型输入，故对此类会话签已知空 `()` 是**事实真话**而非洗白（`main._input_qa_dependencies` 现状即此语义）；仅当投影后输入**仍含**未追踪内容时才必须 `None`。验收用例 B07b 的“未追踪历史”按**手工构造输入**口径理解（真实链路的输入由投影保证已消毒，见 `tests/test_qa_cache_read_guard.py` B07b 注释）。
- 缓存命中后、首次content前，使用新的SQL会话复核全部依赖的状态、身份、版本及记录摘要；任一撤回/隔离/丢行/映射变化/版本变化/内容变化/读取异常均miss。旧缓存不能因为TTL没到而放行；当前qa_hit=None也不能清空旧答案自身依赖。
- 3个put生产点都显式传入该份实际生成输入的快照，put前再次复核；无QA的合法路径显式传空tuple。旧generation仍阻止本进程失效前启动的写入，跨进程旧写入即使进入缓存也必须在下一读时被SQL核验拒绝。
- 无可靠SQL身份的QA仍可按既有守卫服务，但其派生答案不进答案缓存。这是牺牲缓存命中保正确性，不改变其直接读取资格。
- 暂不增加全局epoch表/消息队列/新依赖，不依靠管理动作通知每个进程才能生效。普通已缓存法条的任意外部修改不在本票新增承诺中，既有知识失效守卫保留。

### 4.2 阶段与在途请求

- tR：撤回SQL提交对新会话可见且撤回接口成功。其后开始的新请求的资格/依赖核对必须新读，不复用其他请求快照。
- 阶段P：构造生成输入前复核选中QA；阶段O：第一条**非空正文content**交给SSE生成器前新读；阶段W：写答案缓存前复核实际生成依赖。status/restart/sources/[DONE]都不算正文已经开始。
- 阶段内可复用，同一请求跨P/O/W必须fresh；不得沿用“所有出口永远只读1次SQL”的旧假设。新预算是每阶段每个依赖最多一次装载，另加C21最多8条候选检查；记录各阶段计数，不声称新增查询免费。
- 若QA直返或缓存尚未输出，在O发现失效，放弃该答案，落到不含失效QA的正常检索生成。仅清pre而继续使用旧messages不合格。
- 若轻量已缓冲整答、或旗舰已取得首块但尚未发正文，在O发现其输入QA失效，关闭/丢弃旧产物，清理失效QA并重建messages；最多重新进入生成1次。重建仍不能核验或执行失败，则走现有明确错误/无法完成路径，不无限重试，不把旧产物改标签后发送。
- 若O允许后已输出非空正文，Owner允许该流继续到结束，本轮不主动跨请求打断；后续不得把已失效依赖的结果重新写成可用缓存。历史显示/持久化按现有行为保留，取消/断连资源清理不能被回退分支破坏。
- 测试明确撤回发生在P前、P与O间、O后；通过Event/Barrier控制时序，禁止sleep碰运气。O检查的SQL读取是可见性观察点，不宣称与网络发送原子线性化；如果要保证O读取后任意瞬间撤回都阻止首字节，需要另行设计跨进程发送协调，不能拿本地RLock或status帧伪证。

## 5. W06-C：历史、摘要、改写及派生内容（必做）

已保留历史不代表历史不会被模型再次使用。当前`_build_messages`直接追加assistant历史及summary，`Message`没有QA依赖字段，无法仅凭现有记录精确追踪哪些历史结论来自被撤回QA；语义相似度或答案字符串匹配不能补造来源。

Owner已确认允许分阶段、最终执行书全部纳入。阶段一/二可独立验收，阶段三未完成或阻塞时，完整撤回门继续Partial/BLOCKED；不能把分阶段解释成历史/摘要可不做。计划包含合成schema迁移和历史输入处理，不因此取得真实库/会话的访问与迁移授权。

### 5.1 持久依赖与最小数据变化

- 拟新增nullable Text列：Message.qa_provenance、Conversation.summary_provenance、QaCandidate.qa_provenance，沿现有幂等migrations和schema parity测试。旧行NULL表示未知，不默认空依赖；不重写原content/summary，不从日期、引用或相似字符串推断旧来源。
- 依赖格式复用阶段二的QaDependency，序列化/校验只有一处。外层带schema_version、complete标志、依赖集合及输入来源标识；complete=false/格式坏/祖先未知均传播未知。新答案继承当前QA、实际使用的历史回答、摘要及工具结果的依赖并去重，不能只追最后一跳。
- Message内容与依赖同事务写入，缓存回放也传原生成依赖，不因curate=False丢来源；Agent终稿、占位和失败路径分别声明真实覆盖，未经证明不能签已知空。摘要内容、summary_upto与其依赖同事务更新。
- 依赖集合需有容量保护；不能截断后继续称完整。容量耗尽时保守不复用/不缓存并归因，不在本阶段引入无限历史图数据库。
- 派生依赖核验须拒绝循环、自引用和超限链；第三阶段record_digest还需覆盖来源包与其schema版本，不能在祖先来源变化后复用旧摘要。格式升级前的缓存保守miss，旧进程是否退出仍由W14核实际部署对象，不在文档中宣称已生效。

### 5.2 原文保留与模型输入分离

- 历史API/UI保留原文。新增模型上下文投影，不在原记录上删除、替换、伪造审批；用户自述与助手结论区分，用户输入不能因包含失效答案相同文字而被硬删或当已核法律依据。
- 同一投影同时供request_bootstrap、main的消息构造与改写、tools.memory及Agent后续生成使用；权限/会话归属先于内容读取。不只在最终_build_messages过滤，避免先由rewrite_query或工具Observation洗成新事实。
- 已知依赖撤回/隔离/版本或身份变化、读取失败时，不把对应assistant片段或摘要作为可信上下文复用。依赖在模型调用前及首正文前按阶段重新核；已开始流式完成边界沿Owner原决定。
- 旧未知来源assistant/摘要的输入规则是Task 6的具体产品决策，不再问是否纳入范围。推荐原文显示保留、模型侧不作为可信结论复用，优先从用户事实与已验证材料重建，信息不足则澄清；须先给合成对照和对多轮指代的影响，再确认该行为。未确认不暗中批量屏蔽，也不将未知标为安全。
- 已持久化Agent观察/恢复状态不能绕过新投影；对旧不可追踪状态套用同一已裁规则，不因有agent_run_id就认定来源完整。具体运行路径先做源码覆盖清单。

### 5.3 摘要与再次沉淀

- 新摘要继承旧摘要和实际压缩消息的完整依赖；旧摘要失效后不能作为“已有摘要”再次喂入压缩器。安全重建失败则不使用失效摘要，不推进summary_upto，不覆盖原文凑绿。
- 压缩提交以输入摘要/游标/来源快照作并发校验；生成期间撤回或其他压缩抢先提交时，拒绝过时结果，重建最多一次。不是仅在load_context时检查一遍就信任异步压缩产物。
- 派生答案继续进入受控沉淀时继承祖先依赖。已撤回来源参与的在途旧流即使允许完成，也不能自动再沉淀成新的可服务QA，或借新candidate id洗掉撤回；读侧复核传递依赖，旧未知候选沿原C03及具体迁移规则处理。
- 最终联合测试覆盖历史→改写→检索→回答→新历史/摘要/QA这一链，保留正常用户事实、多轮指代和已知无QA依赖的阳性控制。

## 6. 验收与停止条件

具体反例、阳性、性能计数及状态均在[验收用例表](C:/Users/33393/Desktop/ai-legal-helper/reports/planning/qa-read-contract-20261018/acceptance-cases.md)，三阶段及最终联合验收顺序在[分阶段执行方案](C:/Users/33393/Desktop/ai-legal-helper/docs/process-archive/superpowers/plans/2026-10-18-qa-selection-and-revocation-execution-plan.md)。未跑用例均记NOT_RUN，不用文档校验替代产品门。

不读.env、真实库或未授权数据副本/向量/会话，不调用模型/HTTP，不装依赖，不迁移实库，不部署或公开Git；合成对象与已授权评测副本沿原范围。本方案不授权先执行真实门再补安全审计。旧RUN与review快照只读。

停止条件：实际数据路径/fixture无法证明隔离；新行为需要读取现役秘密/数据；候选或并发边界与本设计不符；同bug三次修复不过；同命令失败未经诊断；任何必须靠删测试、改gold、改阈值或降低原门才能通过的修法。只停受影响工作，保留独立安全产物。
