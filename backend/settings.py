"""集中配置（pydantic-settings）。从环境变量读取（main.py 已 load_dotenv 注入 os.environ）。

- 字段名小写；环境变量名大小写不敏感（case_sensitive=False）。
- 未知环境变量忽略（extra=ignore），避免 .env 里多余项报错。
- 兼容旧名 ZHIPUAI_API_KEY（见 api_key 属性）。
"""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(case_sensitive=False, extra="ignore")

    # ---- LLM ----
    llm_api_key: str = ""
    llm_base_url: str = ""
    # 对抗审计 v2 #12：删除死配置 llm_model（无任何代码读取，真正入口是 llm_registry 的
    # DEFAULT_ROLES / LLM_MODELS_JSON）。移除字段避免 .env/docker-compose 误以为 LLM_MODEL 生效。
    zhipuai_api_key: str = ""  # 旧名兼容（智谱平台 key，8-23 到期免费 token）
    zhipu_base_url: str = "https://open.bigmodel.cn/api/paas/v4"  # 智谱 OpenAI 兼容端点
    # 阿里云百炼（DashScope）OpenAI 兼容端点：全模态角色（vision/voice）专用 provider。
    # 2026-09-05 用户授权启用 qwen3.5-omni-flash（非 realtime 变体——实测其拒绝 HTTP 调用），
    # 复用既有账号 key；配额上限 100 万 tokens，单价见 docs/capability-matrix.md。
    dashscope_api_key: str = ""
    dashscope_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    # 硅基流动（SiliconFlow）provider key：rerank 切换 BAAI/bge-reranker-v2-m3 时使用
    # （2026-09-06 用户指定；rerank 调用方按 rerank_api_key or siliconflow_api_key 取 Bearer）。
    siliconflow_api_key: str = ""

    # ---- 鉴权 ----
    jwt_secret: str = ""
    admin_username: str = "admin"
    # 已由 seed_admin.py 从 ADMIN_PASSWORD 环境变量读取（此字段为死代码）；留空，
    # 避免"看似已配置密码"的假象与公知默认口令（对抗审计 2026-08-07）
    admin_password: str = ""

    # ---- 特性开关 ----
    feature_hybrid: bool = True  # 向量+BM25 RRF 混合检索
    feature_self_register: bool = (
        False  # 方案C（2026-08-08）：默认关闭公开注册，仅管理员开户；.env FEATURE_SELF_REGISTER=true 重开
    )
    feature_router: bool = True  # 多模型分级路由总开关；False 时主回答退化为旧单模型（get()）
    feature_study_retrieval: bool = True  # ADR-012：study_aid 具体题分步检索（False 一键回滚"不检索"）
    feature_study_cache: bool = True  # 法考题(study_aid)进回答缓存白名单（False 回滚=仅 legal_query 可缓存）
    feature_similar_cache: bool = True  # BGE 近重复命中（结构护栏防错答；False 只精确 key 命中）

    # ---- Legal Agent V1 rollout（安全关闭；仅显式 enabled + 流量命中才启动 Agent Path）----
    agent_enabled: bool = False
    agent_shadow_enabled: bool = False
    agent_traffic_percent: int = Field(default=0, ge=0, le=100)
    # Task 7 必须把这些部署期值快照进 AgentBudgets；不得静默使用旧 schema 默认值。
    # max_steps 默认 16：产品承诺"最多两轮追问"，两轮会话实测（第二轮澄清 checkpoint 时
    # steps 已达 8，resume + 检索 + 定稿仍需 ≥3 步）在 8 时会令第二轮用户回答触发
    # BudgetExceeded→409；16 在 le=32 防失控上限内留足两轮会话余量。
    # 2026-09-12 用户批准 16→20（8→16 先例的同类上调）：5 争点分解下
    # bootstrap 1 + 检索 5×2 + 澄清 2×2 + backfill 2 = 17 > 16，必然
    # `budget_exceeded:step_preflight`（确定性，与模型无关）；实测复现见
    # tests/test_agent_chat_integration.py::test_five_issue_decomposition_reaches_drafting_within_step_budget。
    agent_max_steps: int = Field(default=20, ge=1, le=32)
    agent_max_tool_calls: int = Field(default=10, ge=1, le=32)
    agent_max_replans: int = Field(default=3, ge=0, le=32)
    agent_max_clarifications: int = Field(default=2, ge=0, le=32)
    agent_max_verifier_research_returns: int = Field(default=1, ge=0, le=32)
    # T-A2（2026-09-17，执行书 entity-precision）：实体法适用精度校验（verifier 层，
    # SUBJECT_TYPE_MISMATCH / CLAIM_DIRECTION_REVERSED）。**默认关 = verifier 行为逐字不变**；
    # 数据源 backend/knowledge_base/law_annotations.json；判据与残余清单见
    # dispatch-output/ta2-design-20260917/design-prereg.md（D1 选项一）。
    entity_precision_check: bool = False

    # ---- 部门法守卫（R1/R1b，预注册 docs/preregistration-dept-law-filter-r1-20260913.md）----
    # R1：Agent 检索后剔除「他域专属程序法」条文（证据池防跨部门法混入；实体法永不过滤）。
    agent_dept_filter: bool = False
    # R1b：终稿引用清单程序法串台校验（防生成期注入；检测到即记红线，不阻断 agent_completed）。
    agent_proc_misroute_check: bool = False
    # R1-OB（2026-09-16 预注册 docs/preregistration-dept-guard-r1-optionB-20260916.md）：
    # 判域**输入**扩展——关（默认）= 两处判域点退回 issue 问句（R1/R1b 现状，行为逐字不变）；
    # 开 = 三级构造（tier-1 案例域码 > tier-2 用户原始问题+issue 问句拼接 > None）。
    # 独立开关、独立可回滚；dept_guard 指示词表与过滤规则零改动。
    agent_dept_filter_r1ob: bool = False

    # ---- writer 未决事实脱敏（2026-09-15，代码审查 B）----
    # 动机：同协议 12 次采样里 numeric 失败的**唯一形态**是 `from_unknown_facts`
    # —— 模型在条件化论述中复述未决事实里的数字（实测："三十日"/"一个月"/"十二个月"），
    # 而按纪律未决事实的数字**不可**作为依据（不能绑 fact_id）⇒ 被正确拒绝、整轮失败。
    # 做法：在 **payload 层**把未决事实的数字型 token 替换为中性表述（"一定期限"等），
    # 使模型**无从复述**；missing_information 的逐字来源校验用的是同一 payload ⇒ 自洽。
    # 只动 unknown_facts，**不碰 facts/evidence**（已确认事实允许引用，不得脱敏）。
    # 默认关（属行为变更）：先离线 A/B 对照验证有效且不损质量，再由用户决定开启。
    agent_writer_desensitize_unknown_facts: bool = False

    # ---- 争点级部分交付（2026-09-15，代码审查后的结构化分析）----
    # 动机：writer 逐争点串行、**首个失败即停** ⇒ 5 争点下单点 90% 的端到端成功率仅 ≈59%，
    # 且一次低频拦截（编造 fact_id / 引用池外法条）就让用户**拿零输出**。
    # 而 §4.2 明文要求「相关事实不足时**说明条件，不跳过问题**」——整轮零输出恰恰是**跳过了**
    # 其余能回答的争点（grounded-ai 的口径里，"拒答"应是有信息量的显式说明，不是沉默）。
    # 做法：某争点校验不过 → 该争点记 `uncovered`（含原因码），其余争点照常交付；
    # 终稿**显式列出未覆盖争点及原因**（防静默降级）；`verifier` 对未覆盖争点豁免覆盖判定。
    # **全部争点都失败时仍整轮失败**（无内容可交付，不得伪造"部分交付"）。
    # ⚠️ 边界（§4.2）：本开关**不改变验收标准** —— 未覆盖争点在评测中**仍记 FAIL/REVIEW**，
    # 只是把交付形态从"空"改为"部分内容 + 显式说明"。默认关 = 行为逐字不变。
    agent_partial_delivery_enabled: bool = False

    # ---- 多模型配置（可选整体覆盖默认代表表；JSON 数组，元素见 llm_registry.DEFAULT_ROLES 字段） ----
    # 留空则用 llm_registry 内置的 8 代表模型默认表（base_url/api_key 复用上面的 LLM_*）
    llm_models_json: str = ""

    # ---- 向量嵌入（local=本地 BGE CPU；aliyun=阿里云 text-embedding-v4，需配 key）----
    embedding_provider: str = "local"  # local / aliyun
    embedding_api_key: str = ""
    embedding_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    embedding_model: str = "text-embedding-v4"
    embedding_dimensions: int = 768  # text-embedding-v4 支持 768/1024 等；必须与重建库一致
    embedding_quota_total: int = 0  # 0=不启用配额监控
    embedding_quota_initial: int = 0  # 开通时已用 token（截图余量用）
    embedding_warn_threshold: float = 0.15  # 剩余 <15% → 后台标黄"快用完"
    embedding_hard_threshold: float = 0.05  # 剩余 <5% → 自动切回 local + 标红

    # ---- 重排序（rerank，准度主菜；多模型按配额自动轮换，全耗尽回落 cosine 精排）----
    rerank_enabled: bool = False  # 是否启用 rerank（开则跳过 cosine 精排，见 retrieval）
    rerank_api_key: str = ""
    rerank_base_url: str = "https://dashscope.aliyuncs.com/compatible-api/v1"
    rerank_model: str = "qwen3-rerank"  # 兼容：当前模型（body.model 由 _active_rerank_model 定）
    rerank_models: str = "qwen3-rerank,gte-rerank-v2,qwen3-vl-rerank"  # 轮换序列（逗号分隔，顺序即优先级）
    # gte-rerank-v2 / qwen3-vl-rerank 原生端点（OpenAI 兼容 /reranks 不支持这两个模型，2026-08-07 实测）
    rerank_native_url: str = "https://dashscope.aliyuncs.com/api/v1/services/rerank/text-rerank/text-rerank"
    rerank_quota_total: int = 0  # 0=不启用配额监控（单模型默认配额）
    rerank_quota_totals: str = ""  # 逗号分隔，与 rerank_models 对齐（每模型配额）；空则各模型用 rerank_quota_total
    rerank_quota_initial: int = 0
    rerank_warn_threshold: float = 0.15
    rerank_hard_threshold: float = 0.05

    # ---- 检索候选池深度（2026-09-14：与「返回条数 k」解耦）----
    # 背景（实测，报告 dispatch-output/quality-retrieval-20260914/REPORT.md §2c）：
    # 原实现把候选池上限绑在 k 上（v[:k] ∪ b[:k] ∪ RRF[:2k] = 4k），k=4 时池仅 16 条；
    # 而金标条文常落 9–20 名 → 进不了池 → 连 rerank 也无从发挥（rerank 只能重排池内条文）。
    # 该值 >0 时候选池深度独立于 k，**docs[:k] 返回条数不变**（writer payload 不膨胀）。
    # 0 = 兼容旧行为（池深 = k，与历史逐字一致）。
    retrieval_pool_k: int = 0
    # ---- LLM 查询改写（1d 第三候选，2026-09-15；离线验证见 quality-1d-20260914）----
    # 争点问句是"事实语言"，法条是"法条语言"——机制诊断（recall_generation_diag.py）实测：
    # 16 条硬缺口对问句的 bigram-Jaccard 仅 0.0086（比问句到其实际 top-1 还低），两路 @40
    # 命中向量 3/78、BM25 0/78 ⇒ 缺口在 query 侧。改写 = 让 LLM 把问句映射为法条语言检索句，
    # 作为**附加 slice 单元**进候选池（不吃锚点保底位、docs[:k] 返回条数不变）。
    # 离线（冻结词表 + 结果并集口径）救回 5/16 硬缺口对、零回归；但**真实路径口径重测救回仅 2~3 对
    # < DoD 4 → 已否证**（2026-09-15 §10：含聚焦词并入实验 aug 臂 3/16 亦不达标）⇒ 开关长期默认关，
    # 实现与 14 条契约测试保留为「已验证否证的分支」（同 retrieval_pool_k 先例）。
    query_rewrite_enabled: bool = False
    query_rewrite_max_units: int = 3  # 每问句最多几条改写句进池（控制 embedding 成本上界）
    query_rewrite_timeout_s: float = 6.0  # 单次改写的硬超时（超时/失败 → 静默回落原问句路径）

    # ---- 合同 / 文书风险评估（确定性骨架，2026-08-06）----
    feature_multi_analyze: bool = True  # 合同评估开关（一键回滚）
    contract_max_chars: int = 12000  # 合同文本上限（之上截取并在报告注明）

    # ---- 文件上传（chat_file / admin_upload 文本文件）----
    upload_max_mb: int = 10  # 单个文本/文档上传大小上限

    # ---- 图片限制 ----
    image_max_mb: int = 5
    image_max_px: int = 6000
    image_min_px: int = 10

    # ---- 语音转写（M2，Qwen livetranslate 语音模型）----
    audio_max_mb: int = 10  # 上传音频大小上限
    feature_transcribe: bool = True  # 语音转写开关（False → 端点 501，前端回退 Web Speech）

    # ---- 日志 ----
    log_level: str = "INFO"

    @property
    def api_key(self) -> str:
        return self.llm_api_key or self.zhipuai_api_key


settings = Settings()
