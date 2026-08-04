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
