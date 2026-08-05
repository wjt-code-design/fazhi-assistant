# 架构决策记录（ADR）

> 每条决策带「背景 → 决策 → 后果/代价」，不写「全对」。如实记录权衡与代价。

---

## ADR-001 单一 omni 模型，不用「分类模型 + 生成模型」双模型

- **背景**：法学生做题（study_aid）和咨询（legal_query）需要不同行为，早期考虑双模型。
- **决策**：统一用**一个 omni 模型**（qwen3.5-omni-plus，读图 + 文本 + 流式），靠**提示词分流**区分行为。
- **理由**：双模型增加配置/成本/接口分支；omni 已能覆盖多模态。模型信息仅管理员可见，不对普通用户展示 badge。
- **代价**：单模型能力上限就是系统上限；换模型需整体调提示词。
- **演进**：本决策已被 **ADR-010 多模型分级路由**取代——按复杂度/模态在「文本旗舰 / 全模态旗舰(兜底)」间路由，并加回答缓存与配额监控。模型信息仍仅管理员可见（本条该约束保留）。

## ADR-002 引用校验：以知识库存在性为准，而非检索作用域

- **背景**：早期校验只查「本轮检索召回」，导致「正确但没被检索到」的引用被误报。
- **决策**：`citation_verify` 用 `article_in_kb`（`(source, article)` 双重匹配 + `_source_key` 容忍源名差异）判「是否在库」。
- **理由**：以用户上传的库为唯一权威来源；跨法编造（把民法典条文挂到电商法名下）会被正确判不在库。
- **代价**：需对全库查（精确条号，无嵌入成本）；源名/条号归一规则需维护（宪法括注、〇/零、数字中英）。

## ADR-003 本地 BGE + 混合检索（向量 + BM25 RRF），而非仅向量

- **背景**：法律条文含大量条号/专有名词，纯向量检索对精确匹配是短板（「第87条」嵌入后语义漂移）。
- **决策**：向量召回 + BM25(jieba 分词) 双路，RRF 融合（K=60）；**条号直查路由在前**（精确命中零嵌入）。
- **理由**：中文法律场景，BM25 对条号/法名精确匹配可靠；条号直查是「零成本精确路由」。
- **代价**：BM25 索引需随知识增删重建（`invalidate()`）；两路召回有延迟叠加（本地可忽略）。

## ADR-004 意图分流短路：作弊/学习不做通用检索

- **背景**：考试题会被误检索成作弊罪条文堆砌，答非所问。
- **决策**：`classify_intent` 三分类——cheating 定向检索刑法284之一+治安法27 并拒答；study_aid 不检索只引导。
- **理由**：把「要不要检索」放在检索前决定，避免无关条文污染上下文。
- **代价**：意图误判会选错分支（靠关键词+双向搜索平衡，测试覆盖）。

## ADR-005 知识库以用户上传为权威来源；清洗绝不改写条文

- **背景**：法律文本改一个字符都是法律风险。
- **决策**：清洗只做格式层（空行/页码残留），`--dry-run` 审计后写盘；`file_hash` 幂等去重。
- **理由**：法律场景对内容真实性零容忍；可审计、可重跑。
- **代价**：docx 的修订标记（w:del/w:ins）需人工确认；页码残留正则理论上可能误删孤立数字行（dry-run 审计兜底）。

## ADR-006 受控沉淀（curation）：高置信进 QA 库，低置信留人工

- **背景**：想让优质回答沉淀复用，又不能把模型「自说自话」当真。
- **决策**：`grounded_top_score` 阈值 + `should_curate`；高置信自动进 QA 候选，管理员在后台确认。
- **理由**：自动沉淀有幻觉污染风险；人工确认兜底。
- **代价**：需要管理员定期处理候选（低维护成本）。

## ADR-007 并发模型：本地单 worker 是唯一安全配置

- **背景**：并发是单机部署的关键约束。uvicorn `--workers>1` 会撞本地 Chroma/SQLite 写锁，且多进程重复加载 BGE（内存 ×N）。
- **决策**：本地 **`--workers 1 --threads N`**（FastAPI 线程池内用 `run_in_threadpool` 跑同步重活）。
- **理由**：Chroma（本进程内嵌）、SQLite（单文件写锁）、BGE 模型单例都不支持多进程共享。
- **代价**：单进程吞吐受模型推理速度限制。**扩并发路径 = 托管向量库 + 托管 PostgreSQL + 多 worker 水平扩容**（ADR-008）。
- **注意**：这是「现在不做、路径在」的诚实标注，不是缺陷藏匿。
- **突增应对（2026-08-04 补充）**：吞吐数字被缓存/限流污染（见 BENCHMARK 方法学），
  故不做吞吐压测，但补了**并发门控**（`llm_guard.py`）：全局信号量（默认 4，
  env `LLM_MAX_CONCURRENCY`）限制同一时刻 LLM 调用数，超限排队 30s（`LLM_QUEUE_TIMEOUT`）
  仍无位则降级「服务繁忙」（503/流内提示）——突增时可预测降级而非无界并发打向供应商。
  并发冒烟（`bench_concurrency.mjs`）验证「并发下不崩/无死锁/健康检查仍绿」，非容量测量。

## ADR-008 扩展路径：托管向量库 + 托管 DB（暂不实施）

- **背景**：本地架构的并发天花板明确。
- **决策**：扩展顺序 = 换 Qdrant/PGVector（托管向量库）→ 换托管 PostgreSQL → 多 worker + 负载均衡。
- **理由**：把状态（向量/关系数据）从「进程内」移到「托管服务」，worker 才能无共享冲突。
- **代价**：成本上升、运维复杂度增加；当前规模（单机部署）不需要。

## ADR-009 study_aid 解析型回答（律师式分步分析）

- **背景**：用户愿景是 agent 像"高专业性的律师"——灵活分析题目、逐项解析案例（判断 + 条文依据 + 法理/易错点）、归纳知识点。旧管线 study_aid 只引导不检索（`docs=[]`）、300 字保守提示词，法考题无条文依据。
- **决策**（2026-08-04 重构）：把回答形态从"单轮静态 RAG"升级为**分步分析型**——`retrieval.retrieve_exam` 分步检索（题干主锚 + 每选项补漏）+ `prompts.SYSTEM_STUDY` 法律讲师/律师解析型（考点识别 → 逐项判断 + 条文依据 + 法理/易错点 → 结论）+ `query_understand.is_meta_study` 元问题短路。
- **理由**：RAG 底座/多模型路由/QA 沉淀是资产，差距在回答形态；真作弊已有 cheating 层拦截，解析型可放心给判断。
- **代价**：分步检索 + 长回答使单次成本约涨 2-3x；多条文题受 k 截断（见 ADR-012 遗留）。
- **演进**：评测闭环与防线见 ADR-012。

## ADR-010 多模型分级路由 + 回答缓存 + 配额监控（取代 ADR-001 的单模型）

- **背景**：用户提供一批一次性配额模型（用完不重置），希望简单问题用省配额的模型、复杂/图片用强模型，并监控配额自动切换、相同问题命中缓存零 token。
- **决策**：
  - **分级路由**（`llm_registry` + `complexity`）：`complexity.assess` 按模态/长度/高利害词/多轮定 tier；`registry.pick(modality, tier)` 同档按**能力优先级**选（配额只判可用，不参与排序，避免备用模型抢在旗舰前）；配额剩 <5% 自动跳过该模型。
  - **轻量准入闸**（`complexity.admit_light`）：仅「法律咨询 + 无图 + 单轮 + 检索命中 + 短文本 + 无高利害词」才走轻量路径，宁误伤不误放。
  - **轻量自检 + 升级**（`quality.self_check` + `_light_buffered`）：轻量回答先缓冲→自检（引用在库/无含糊/非空）→不过则升级旗舰重答一次；仍不过追加核对注，**不静默**。
  - **回答缓存**（`answer_cache`）：仅安全形态（单轮无图+命中+自检 PASS）写缓存，key 含 cutoff 日期；知识增删经 `retrieval.invalidate` 同清。
  - **配额监控**（`quota_store` SQLite 持久化 + `routing_metrics` 进程内指标 + `/api/admin/llm-status`）；模型信息仅管理员可见。
  - **模型精简**：最终只留 2 个强可控模型（文本旗舰 `qwen3.7-plus` + 全模态旗舰/兜底 `omni-plus`）。thinking/视觉推理模型与 `deepseek-r1` 在「库外问题被检索召回无关条文」时会据无关条文硬答、不可控，故剔除；text 轻量档空缺时 `_safe_pick` 回退全模态强模型兜底。
- **理由**：法律场景对引用准确零容忍，弱/不可控模型的风险 > 省下的配额；自检+升级+缓存三道闸在不牺牲质量的前提下省配额；优先级排序保证强模型答难题。
- **代价 / 诚实标注**：
  - text 无独立轻量档，简单文本经回退走全模态模型，「分级」主要靠缓存命中与不升级省配额，而非独立轻量模型。
  - 自检是**纯函数**，只能保证「引用在库」，不能保证「引对题」（引在库但不相干）——语义正确性靠 full 门禁 + 受控沉淀 QA 人工兜底，运行时无语义护栏。
  - 流式路径无真实 usage，按输出长度估算扣减（标注「近似」）。
  - `routing_metrics` 为进程内运行态，重启清零；跨重启审计看 `legal.chat` 日志。
  - LLM 有固有波动，full 门禁为 release 前抽查，允许偶发重跑，非 100% 稳定。
- **反向决策（2026-08-05，配额耗尽背景下重引 thinking 兜底）**：
  - 原因：qwen3.7-plus 配额将尽，需启用大后备队列保服务连续。用户提供同 API 内 17 后备
    文本 + 2 视觉模型（连同 qwen3.7-plus 共 18 文本）；按**质量序**注册（deepseek-v4-flash
    最强非思考 → max 系 → plus 系 → flash 系 → thinking 垫底），改 priority 一行可换序。
  - 风险收敛：thinking 模型（qwen3-vl-32b/235b-thinking）恢复 ADR-010 曾剔除的"库外据无关条文
    硬答"风险，仅作最后兜底；受缓存写闸（引用 ⊆ 检索条文）/citation_verify/self_check/refuse
    四防线约束，切换后须跑 eval_exam 验证（golden_hit 降 → 降 priority）。
  - **配额可信度整改**：本地估算（流式无真实 usage，按输出长度估）与阿里云控制台真实值偏差大
    （qwen3.7-plus 本地显示 585K，控制台接近耗尽）——后台**移除估算数字展示**（用户决策），
    改为只显示当前活跃模型 + 切换原因；新增 `/api/admin/llm-quota` 校准端点（管理员读控制台后
    回写 remaining），看门狗以校准值 + **真实 API 错误即时切换**（`mark_depleted`，不靠估算）双保险。
  - thinking 扣减 ×3 系数（reasoning_content 不计入本地估算，防看门狗失明）。
- **QA 持久语义缓存（2026-08-05，ADR-012 补充）**：
  - 背景：用户智谱平台 glm-4.5-air（文本）+ glm-4.1v-thinking-flashx（多模态）各 ~1000 万免费
    token，8-23 到期——需在到期前消耗 token 换取**持久价值**。
  - 决策：`scripts/gen_qa_corpus.py` 用 **glm-4.5-air 只烧智谱 token** 批量预生成 ~61 道
    法考高频/重点/难点解析（刑法/民法/刑诉/民诉/行政/商经知/宪法/劳动），验证（引用在库）
    后入 qa_pairs 持久库（含 options_fingerprint + evidence）；main.py 新增 **search_qa
    高阈值直返分支**（score≥0.92 + 选项指纹一致 + evidence 时效校验 → 零 LLM 直返）。
  - **质量责任**：生成后逐条人工验收 60 条（法律结论全部正确）；修复 18 条 evidence 错位
    （重derive为答案实际首引用）+ 1 条条号归一（第1254条→第一千二百五十四条）。
  - 智谱模型经 `provider="zhipu"` 注册（独立 base_url=open.bigmodel.cn/api/paas/v4 + key），
    glm-4.5-air 进文本队列、glm-4.1v-thinking-flashx 进视觉队列（thinking 仅最后兜底）。

---

## ADR-011 向量嵌入/重排序上云（本地 BGE + rerank → 阿里云 text-embedding-v4 + qwen3-rerank）

- **背景**：用户根本诉求是提升检索/回复准度与性能。原检索层全本地（BGE CPU 嵌入），
  rerank 接口占位未启用。用户有阿里云 embedding（text-embedding-v4）与
  qwen3-rerank/qwen3-vl-rerank 的云 token（各百万级）。
- **决策**：
  - **嵌入 provider 化**（`rag_chain._build_embeddings`）：`local`（默认，零配置回退，
    BGE CPU）↔ `aliyun`（`OpenAIEmbeddings` 调 text-embedding-v4，须
    `check_embedding_ctx_length=False` 防 400）。collection 名随 provider 派生
    （`legal_provisions_cos`/`legal_provisions_te4`），旧库保留可回退。
  - **rerank 接入**（`retrieval._rerank_docs`）：qwen3-rerank 经 OpenAI 兼容
    `/reranks` 端点，对**整个候选池**（实测 12-17 条）精排；**锚点保底条文不动**
    （防 rerank 挤出法考题核心定罪条款）；rerank 开时跳过 cosine 整池重嵌。
  - **配额监控**（`utility_quota_status` + `/api/admin/llm-status`）：embedding/rerank
    用量按 `estimate_tokens` 近似扣减，双阈值——<15% 标黄"快用完"、<5% 自动切回 local
    标红。LLM 走"同档多模型自动切换"，embedding/rerank 无平级切换故用双阈值。
- **理由**：本地 CPU 嵌入是首帧延迟大头且占 ~781MB 内存；rerank 是准度主菜（召回后
  精排，recall@1 提升显著）；云 token 便宜（embedding ¥0.43/全库、rerank 0.6元/百万
  token）且有配额可视化。
- **代价 / 诚实标注**：
  - 切云必须**重建向量库**（语义空间不同，即使维度同为 768）——`scripts/rebuild_embeddings.py`
    从旧库本身（含管理员上传）全量重嵌入，旧库保留可回退。
  - 云端单次嵌入比本地 CPU **慢**（+100-300ms RTT）——性能提升来自"免本地 CPU 瓶颈 +
    精排复用 chroma 距离分 + rerank 替代重嵌"，非嵌入本身变快。
  - embedding/rerank 用量**按输入文本估算**（无真实 usage 返回），非精确计费。
  - 失败降级：rerank 异常 → 回退原精排；embedding key 未配 → 启动报错（提示切回 local）。
  - **不做（层2 独立）**：托管向量库 + 托管 DB + 多 worker 全上云（ADR-008 路径），
    单独立项，运维彻底解放的后续工程。
- **落地修正（2026-08-04）**：text-embedding-v4 配额在阿里云真实耗尽（本地监控显示
  ~99.8% 不可信，**真实值以控制台为准**）→ 换班 qwen3.7-text-embedding 重建 10266 条后
  其配额仅剩 62K——**rebuild 一次 ≈ 86 万字符 ≈ ~60 万 token，一次换班烧掉百万配额的
  60%，云端 embedding 换班不可持续** → 最终切回**本地 BGE**（`EMBEDDING_PROVIDER=local`，
  cos 库无需重建，零 token）；rerank 仍走云端（换 rerank 模型不重建库，输出分数非向量）。
  换班脚本 `switch_embedding.py` 的 `_env_set` 曾把新键拼到无换行行尾损坏 .env（已修）。

---

## ADR-012 律师式分步分析 + 评测闭环（阶段 0-5）

- **背景**：ADR-009 落地后需可度量的专业度评测 + 防"引错条"（引在库但语义不对题，
  如 A 题该引刑法 20 却引了刑法 236）。
- **决策**：
  - **评测闭环**：`data/eval_exam.json`（20 法考题带 `expected_articles` 金标）+
    `scripts/eval_exam.py`（确定性指标 recall@6 / cite_ok / golden_hit / refuse_ok +
    可选 professional judge）+ 冻结 hash（阶段对比须同一题集，新题走 eval_exam_v2.json）。
  - **金标条号确定性判定**：条号对错由 `golden_hit`（归一化比对，中文/阿拉伯数字统一）判，
    不用 LLM judge——防"judge 和 LLM 一起错"同频失真；judge 只评结构/论证/法理主观维度。
  - **分步检索**：`retrieve_exam` 题干主锚 = **完整问题文本（含选项信号）**——实测剥离
    选项的裸题干丢关键条（高空抛物 1254 整题检索 rank1，裸题干 top3 全无关）；选项单元
    独立补漏（防死刑复核 252 漏）；ThreadPoolExecutor 并发（`_pre` 在 run_in_threadpool
    线程无 event loop，asyncio.gather 不可用）。
  - **场景定向补充**：`scenario_supplement_docs`（数据驱动 scenario_supplements.json：
    死刑复核/正当防卫/毒品），选项题与非选项题均前置（核心条防漏）。
  - **引用双校验**：citation_verify（在库存在性，防编造）+ golden_hit（金标条号，防引错条）。
- **关键指标（本地 BGE，2026-08-05）**：recall@6 0.9083 / golden_hit 0.95 / refuse_ok 1.0
  （详见 docs/benchmark_results/exam_*.json）。
- **代价 / 诚实标注**：
  - 多条文题（如保证担保需 4 条）受 k=6 截断，recall 上限受限——下迭代考虑动态 k 或案情拆解。
  - recall 0.9083 vs 基线 0.925（v4）的差距主要来自本地 BGE vs 云端 v4 的嵌入差异，
    非管线退化（golden_hit 0.95 已超基线 0.8）。
- **运维警示**：8000 端口曾出现系统 Python 幽灵 uvicorn 反复抢端口——评测/换班前必须
  确认端口归属并杀干净；embedding 配额以阿里云控制台为准。

---

## ADR-013 Query Rewrite 重构 + 题型感知作答 + 沉淀收窄（2026-08-05）

- **背景**：① 改写先于意图分流（chitchat/cheating/元问题白烧 LLM 改写）；② `SYSTEM_STUDY`
  不告诉模型单选/多选，多选题干无"多选"字眼时模型给一个坚定答案 → 漏答；③ 沉淀对所有
  intent 开放，法考题错答可被采纳污染 qa_pairs。经 grilling 对抗审查（5 角度 + 汇总）修订。
- **决策**：
  1. **分层职责**：词面桥接 `_bridge_query` 只归检索层（`hybrid_retrieve`，缓存 key 前），
     **不进 search_qa**；话语改写 `rewrite_query` 只做多轮指代消解。
  2. **意图后置改写**（main.py `_pre` 重排）：意图先判（raw）→ 非检索分支（chitchat/
     cheating/meta）`rewritten=raw_query` 零改写；检索分支走 `_rewrite_for_retrieval`
     （有历史 + 非完整法考题才调 LLM）。
  3. **完整法考题短路**：`has_exam_options`（带真实选项标号 `_OPTION_FMTS`）→ 自带题干
     跳过改写——完整考题改写冗余（长输入烧 token）+ 有风险（改写可能动选项/极性）。
  4. **题型感知作答**（决策 6）：`question_type`（多选/单选/不定项/unknown）→ `_build_messages`
     对法考题动态追加 `_EXAM_TYPE_SUFFIX`。unknown 兜底 =「列出所有正确项 + 注明推断，
     切勿默认单选」——单选误判 unknown 不漏答。多选误判 single 仅当题干真有"单选"字样且
     实为多选（出题不会这样写）。
  5. **沉淀收窄到 legal_query**（决策 7）：`_post` 闸 `curate and intent=="legal_query"`——
     一次解决 cheating 翻转、study_aid 法考题错答污染、chitchat/meta 无引用不沉淀。
     `/api/feedback` 的 `create_candidate`（main.py:1258）独立路径不受影响。
  6. **桥接扩充流程**（证据门槛）：用户词在库法条无 → 替换映射唯一 → 复现
     `hybrid_retrieve(k=6)` 漏目标条而桥接句召回 top-6 → 才加 pattern + 回归测试。不投机加。
- **0.6 阈值评估（用户疑问澄清）**：代码无 8.4/0.84 自动收录。机制 = 0.6 入待审队列
  （`DEFAULT_GROUNDED_THRESHOLD`）+ 管理员人工 approved 才写 qa_pairs。**不建议加
  "有据分 > X 自动收录"**——`grounded_top_score` 区分不了库内外（标定：库外工伤保险条例
  0.677 也高分），固定余弦分不能保证答对，自动收录会放污染。
- **明确不做（grilling 依据）**：
  - **正则自包含 gate**：缓存确定性论据是死路径（`_cacheable` 要求首轮，多轮从不算 key）；
    `以下|如下` 命中法考题题干 `_JUDGE_MARKS` 系统性误烧完整法考题；MIN=4 漏省略追问
    （"赔偿标准是多少"）致召回回退。多轮非考题保持改写现状。
  - **search_qa 双通桥接**：桥接目标词在 ~204 条 qa_pairs 零命中、方向与语料错配
    （库存口语措辞，桥接拉向法言）、raw miss 是常态致成本算反。
  - **不改 `rewrite_query` 提示词**、**不改 0.6 阈值**（入队过滤器够用，人工审是质量闸）。
- **代价 / 诚实标注**：study_aid 优质答案不再自动进待审——法考题持久复用由 gen_qa_corpus
  脚本（204 条已人工验收）承担；沉淀收窄的污染防护收益 > 丢失的 study_aid 复用价值。
  改动影响面：`query_understand.py`（+2 纯函数）、`prompts.py`（+1 常量表）、`main.py`
  （重排 + 接线 + 闸）；`memory.py`/`retrieval.py`/`knowledge_service.py` 零改动。
  测试：260 passed（含新增 test_pre_rewrite_order.py 集成 + test_query_understand 单测）。

---

## ADR-014 回答质量提升：动态 k + 多选完整性 + judge 趋势 + rerank 降级根治（2026-08-05）

- **背景**：回答质量三短板——① 多条文题受 k=6 截断 recall 0.9083；② SYSTEM_STUDY 多选漏答
  （用户实测"多选只给一个坚定答案"）；③ 论证深度无持续量化。另有 **Windows 偶发 segfault**
  阻塞 eval（diagnosing-bugs 根治）。
- **决策**：
  1. **动态 k**（retrieve_exam，测量驱动，**2026-08-05 已逆向回退**）：曾用 h10/o4/c12 深池
     把 recall@6 提到 0.9625（恢复 id9/13 满、id14 0.75；根因=题干主锚随 k 膨胀挤占截断位、
     选项专属金标条被 out[:k] 截掉）。**但深池拉长每次检索持有 BGE/Chroma 的时间，显著加大
     Windows onnxruntime 偶发原生 segfault 窗口**（恢复 rerank/降并发/串行/嵌入锁均压不住，
     诊断见第 4 点）→ **生产稳定优先，回退 k=6**（recall 维持 0.9083）。多条文题 recall 上限
     为已知局限。
  2. **多选完整性**：`quality._answer_declared_correct`（兼容 "X项判断：正确" / "【判断】正确"
     两格式）+ `multi_incomplete`（多选题型 + 回答只声明 1 项 → 症状标记）。main.py 流式路径
     追加确定性核对注 + 拦缓存写（防错答传播）。eval 加 `multi_ok` 指标（用已有
     options_verdict 金标，无需改冻结题集）。
  3. **professional judge 趋势**：eval_exam `EVAL_LLM_JUDGE=1` 追加 professional_avg 到
     exam_professional_trend.json，跨跑对比论证深度。
  4. **rerank 降级根治（诊断结论）**：本地配额库误标 3 个 rerank 模型全耗尽（used=1M×3，
     实际 gte/vl 满 1M）→ `rerank_active_model()`=None → 即使 rerank_enabled=true 也掉进
     `_cosine_rank` 整池重嵌（retrieval.py:428 每次 embed_documents 10-17 条）→ 持续真实
     检索（缓存 miss）→ BGE 嵌入量暴涨 → onnxruntime Windows 偶发原生 segfault。**修复**：
     `/api/admin/llm-quota` 校准回写（gte/vl used=0）→ rerank 恢复 → cosine 路径被跳过 →
     15/15 稳定压测无崩溃。**教训**：本地配额是估算扣减（ADR-011），不可信——rerank/embedding
     降级会静默改变检索路径（本地重嵌）引发隐藏崩溃，以控制台校准为准。
- **明确不做**：不回退动态 k（recall 收益真实且 rerank 恢复后稳定）；不重构 `_cosine_rank`
  复用 Chroma 距离（降级路径为稀有回退，估值不值改动风险）。
- **代价 / 诚实标注**：动态 k 已回退（见决策 1）——多条文题 recall 上限（id14 剩 691、
  id18 剩 1175 两条金标与选项语义不映射，金标数据边界）为已知局限。完整 eval 在 rerank
  激活下烧 ~40万 gte-rerank-v2 token，留待配额充裕时跑。测试 268 passed。
- **补记（2026-08-05 晚，multi_ok 深修 + 缓存污染发现）**：
  - **病灶分类**（8 失败案例逐一读答案）：抽取盲区 2（id8/10 答案判对正则漏）+ 检索缺口 2 可修
    （id5 胎儿 1155、id16 终局裁决 47/仲裁费 53）+ 真实错判 3（id14/18/20）+ 金标版本冲突 1
    （id13 新公司法 49(3) 无旧法 28(2) 违约责任表述）。
  - **Step 1 抽取层**：`_answer_declared_correct` 结论正则加"正确答案："变体 + "四个选项的说法均正确"
    中间件；`multi_ok` 加全选信号（双守卫）。multi_ok 0.43→0.57（id8/10 转正，通过案例零回归）。
  - **Step 2 检索**：scenario_supplements.json 加 statutory_inheritance（1155）/labor_dispute（47/53）。
    DEBUG 证实 1155 进上下文（docs_n=9 第 3 位），但 qa_cache 直返导致模型"引用条文却断言未包含"。
  - **关键发现——judge 基线被 qa_cache 污染**：后端日志 `tier=qa_cache cache=hit`——20 题答案大部分
    来自 search_qa 高阈值直返（智谱免费 token 预生成 204 条语料），从未走实时 LLM。所有早期 judge
    multi_ok 数字（0.43/0.57/0.64）均失真。修复：`/api/chat` 加 `no_cache` 参数（schemas.ChatIn +
    _qa_direct_return + answer_cache 绕过），eval 脚本传 no_cache=True 测真实 LLM。
  - **Step 3 决策（用户拍板）**：id20 定金金标 C/D→False（民法典 587 定金罚则需"致使不能实现合同目的"
    要件，题面锚点 [586,587] 自洽；模型 declared={A,B} 通过）；id13 版本冲突仅标注不自动改。
  - **Phase 1（workflow 综合审查 → 归因修复 + prompt B′）**：context_block 显式声明"本题相关法律条文
    （以下均为本题判断依据，含场景补充条文）"——修模型"清单重建遗漏"（引用 1155 却报未包含）；
    `_EXAM_VERDICT_RULE` 重写为真伪判定五条（子集省略→对 / 超集扩大→错 / 明文冲突→错 / 严禁声称
    未包含）并位置前移到 OUTPUT_FORMAT 之前（原尾部追加被 SYSTEM_BASE 压制无效）。
  - **真实基线（绕缓存 no_cache=True）**：multi_ok 0.5714（8/14）。id5 转正（归因修复，D 判正确）、
    id16 D 转正（仲裁免费）、id20 通过（金标配合）；id9/20 在 judge 与重跑间翻转 = **LLM 非确定性，
    单次 judge 有噪声**。剩余真实失败：id13（版本冲突）、id14 B（prompt a 条未转正）、id16 C
    （超集扩大，待 Phase 2 改金标）、id18（真实模型能力短板，A/C/D 全判错，待深查）。
  - 测试 283 passed（含新增 test_multi_extract 8 例 + test_scenario_supplement 4 例 slow）。
  - **Phase 2 金标再版（收尾）**：id16 C→False（终局裁决超集扩大，与 id20 同口径）、id13 B→False
    （2023 新公司法 49 条删除"对股东违约责任"表述，旧法口径校准）。快速验证（no_cache）：id16
    {A,D}==金标、id13 {A,C}==金标 均转正。multi_ok 真实基线 0.64→0.71（预期）。
  - **口径边界（不修，文档化）**：id14 B / id18 C——模型"法理严谨"（选项缺法条要件）vs 金标
    "法考简化口径"。改金标 = metric-gaming、调 prompt = 让模型不严谨，均不做；模型判错为已知特性。
  - **金标再版治理**：freeze_hash 因 id20/16/13 修改而变化（75bfbd80724e → 再版），旧基线
    376ee0b3a865 不再跨阶段可比，阶段对比须注明口径变化。**LLM 非确定性**：单次 judge 有 ±1 噪声
    （id9/20 翻转），multi_ok 数字 = 真实基线 + 波动，多次跑取中位数更稳。

## ADR-015 合同评估 eval 基线（2026-08-06，ADR-014 二期门控）

**决策**：合同评估一期交付后，先建 eval 基线量真实缺口，再决定二期投入（反脆弱顺序，不盲上多步成本）。

**新增**：
- `data/eval_contract.json`：6 份合成合同基线题集（租赁/劳动/借款/买卖/健身霸王条款/长商铺），遵循真实合同模板含典型陷阱。
  **金标不手写**，由确定性骨架（contract_split + rubric + 命中条文）即时生成，防 metric-gaming。
- `backend/contract_verify.py`：确定性 verifier（零 LLM）——coverage（漏条款）/ fabricated_fragments（编造）/
  structure_score（R_n 五要素）/ level_match（报告等级 vs rubric）/ cited_articles（条文提取）。16 例单测。
- `backend/scripts/eval_contract.py`：**两步运行**（Windows 单 BGE 进程纪律）——`--golden`（停后端，确定性骨架
  含 BGE 检索 → 条款/命中集/rubric 落盘）+ `--report`（起后端，真实 chat API no_cache + 纯函数 verifier，
  **严禁 import retrieval**——模块级加载 BGE，双进程冲突）。
- `_build_contract_data`/`_contract_supplement_docs` 从 main.py 迁入 domain_rules.py（单一来源，eval 可干净复用）。

**基线结果（6 份合同，真实 LLM no_cache）**：
| 指标 | 值 | 解读 |
|---|---|---|
| trigger_ok | 1.0 | 触发判定全对 |
| structure_avg | 1.0 | R_n 五要素模板 100% 遵守（一期模板约束强） |
| coverage | 0.90 | 漏条款少；漏的 C6 转租/不可抗力为低风险条款（打标过宽所致） |
| fab_total | 44 | **人工复核全部为改写/修改建议文本，非虚构条款**——一期无编造 |
| cite_supported | 0.5 | 报告条文一半不在骨架命中集（**骨架映射弱，报告引用多为合理**） |
| level_match | 3 match / 3 diff_adj / 0 far | 无风险等级夸大；报告系统性偏低半级（rubric 偏严） |

**真实缺口（按价值排序）**：
1. **骨架条款→法条映射覆盖不全**（cite_supported 0.5 主因）：试用期→劳动法19、借款利息→民法典677/679/680、
   格式条款/最终解释权→497/498、免责→506、转租→715 等常见风险点未映射或未命中，报告被迫靠 LLM 内部知识
   补条文（有"建议核对"诚实标注，仍有错条风险）。补 `contract_clause_supplements.json` 一行 json 成本最低收益最大。
2. **coverage 风险打标过宽**：风险关键词把"解除/赔偿"等中性词当风险点，低风险条款计入"应覆盖"，coverage 虚低。
   需区分"真实风险条款"与"含风险词条款"。
3. **rubric 偏严**：报告等级系统性低半级（极高→高/高→中），无夸大但基准需校准。

**补映射执行（同日，eval 闭环）**：补 `contract_clause_supplements.json`（新增键：试用期→劳动19/20/21、
最终解释权→民496-498+消保26、概不→民506/497+消保26、转租→民715/716、瑕疵→民612/613/617、没收→民585、
经济补偿→劳动46/47/87；扩充：借款+677/679、劳动合同+36/39/46/47/87）+ `_CIVIL_GENERIC` 加"解除"（防劳动条款
错绑民法典563）+ 移除"解除/赔偿"中性风险词（rubric/coverage 虚高虚低）。重跑基线：
| 指标 | 修复前 | 修复后 |
|---|---|---|
| coverage | 0.90 | **1.0**（漏条款清零） |
| cite_supported | 0.5 | **1.0**（报告条文全在命中集） |
| level_match | 3/3/0 | **4 match / 1 diff_adj / 0 far** |
| structure | 1.0 | 0.93（LLM 单次输出波动，长报告尾条目五要素整体完整） |
| fab_total | 44 | 30（人工复核全为改写/修改建议，非虚构条款） |
一期骨架缺口基本补齐。剩余已知：C1/C3 报告等级差半级（rubric 对"没收押金/高利"敏感度不足，diff_adj 可接受）、
report_level 曾被 markdown 加粗干扰（已修 `_LEVEL_RE`）。

**验收（同日，扩展 11 份考卷）**：边界触发 11 断言全过（真实合同 100% 触发、法条/叙事/咨询 0 误触）；
追加 5 份新场景考卷（二手房定金/品牌加盟/装修/劳务/直播带货）重跑：coverage 0.97、cite_supported 0.857
（unsup 多为报告合理补充引用——506 弃权条款/543 单方变更/509 诚信原则，骨架未供给）、level 6 match / 5 adj / 0 far、
无编造（fab 抽样全为改写/修改建议）。**发现并修复会话连续性 bug**：合同续聊第二轮正常、第三轮短句
（"那利息按24%算合法吗"）被分支0.5 通用 clarify 判"信息不足"拦截（通用反问、绕开合同路径）——通用闸在
合同分支之前。修复：`pre["contract_data"]` 存在时 strategy 强制 direct（信息闸由分支0.3 need_clarify 负责）。
端到端验证三轮续聊贯通。骨架盲区记二期：C7 违约金条款方向性（保护乙方非风险，打标无法区分对谁不利）、
C9 保修条款回落检索错配担保条文（686-693，报告自行指出并纠正）、新映射缺原则性条文（506/543/509 等）。

**二期决策**：先 commit 基线 + 映射（eval 门控达标），再上文件上传/图片/SSE 进度功能。功能通道只是换输入，
骨架质量已达标。
