"""集中配置（pydantic-settings）。从环境变量读取（main.py 已 load_dotenv 注入 os.environ）。

- 字段名小写；环境变量名大小写不敏感（case_sensitive=False）。
- 未知环境变量忽略（extra=ignore），避免 .env 里多余项报错。
- 兼容旧名 ZHIPUAI_API_KEY（见 api_key 属性）。
"""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(case_sensitive=False, extra="ignore")

    # 敏感字段名标记（大小写不敏感的子串匹配）：命中即打码。
    _SECRET_NAME_MARKERS = ("api_key", "password", "secret", "token")

    def __repr__(self) -> str:
        """掩盖敏感字段值（2026-09-22 安全修复）。

        为什么必须修：`AttributeError`/断言失败会把 **Settings 的 repr 整段打进日志**——
        实测在 pytest 失败输出里泄漏过明文 `dashscope_api_key`/`zhipuai_api_key`/
        `siliconflow_api_key` 与 `admin_password`。任何 CI 日志收集都会把它带走。
        注意：`model_dump()` **不在**本修复范围内（未观察到它进入日志路径）；
        若将来有接口输出配置，仍需另行脱敏。
        """
        parts: list[str] = []
        for name, value in self:
            if any(marker in name.lower() for marker in self._SECRET_NAME_MARKERS) and value:
                parts.append(f"{name}='<masked:len={len(str(value))}>'")
            else:
                parts.append(f"{name}={value!r}")
        return f"Settings({', '.join(parts)})"

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
    # 公开历史查询（Owner 2026-09-23 决定，取代 09-21 的"评测通道"定位）：默认可用；
    # 部署显式关闭时带日期的请求返回 503，不静默改用当日。`case_domain` 仍是评测专用控制量。
    # ⚠️ 09-21 裁定里的成本事实**没有被公开化消除**：显式基准日会退出零-token 直返与共享答案缓存
    #   （`prepare_fast_path` 置 `qa_hit=None`、`main._cacheable` 排除），分水岭前的值还触发版本
    #   绊线回落 LLM ⇒ 客户端可用一个日期把"命中"打成"未命中"。现状有界（单请求、60/分钟、
    #   最贵等于一次未命中），但调用者已从评测通道变成任意已认证用户，成本口径需按新前提复评。
    allow_client_law_as_of: bool = True

    # 同款的另一半（Owner 2026-09-21 裁定的 `case_domain` 侧，2026-09-22 落地）：
    # False（默认）⇒ 客户端传的 `case_domain` 被忽略（各消费方落 None，行为与"没传"一致）；
    # True ⇒ 评测/灰度放行。理由：该值决定 R1-OB 判域，属评测输入而非用户偏好；
    # 前端实测**从不传**该字段 ⇒ 默认关在生产**零行为变化**。
    allow_client_case_domain: bool = False

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
    # T-A3（2026-09-17）：数字匹配 v2——口语金额归一（N万块/N万 ≡ N万元）+ 全 state 事实
    # 数字白名单（含跨争点事实与脱敏前未决事实原值；池外新数字仍拦，防幻觉边界不变）。
    # 默认关 = writer/verifier 数字校验行为逐字不变。设计依据 T-A0
    # （dispatch-output/ta0-numeric-trace-20260917/report.md）。
    numeric_matching_v2: bool = False
    # R12 伪调用检测（2026-09-18，外部 harness 方案差距分析 P0-3）：writer/verifier 对
    # claim 文本做「声称执行过某动作（检索/合同分析/调取历史/用户确认）而 state 无真实
    # 执行记录」的确定性比对——对应已知缺陷 deepseek-v4-flash"伪调用"（工具调用被渲染
    # 为文本而非执行）。判定真源 agent/phantom_check.py；默认关 = writer/verifier 行为
    # 逐字不变（与 entity_precision_check / numeric_matching_v2 同一开关惯例）。
    phantom_tool_check: bool = False
    # R15 法律版本适用绊线（2026-09-18，外部 harness 方案差距分析 P0-2 的评测侧配套）：
    # claim 按 law_as_of 版本的法回答 2021-01-01（《民法典》1260 条）分水岭前的事实 →
    # verifier 终态拒答（LAW_VERSION_WATERSHED_MISMATCH）。判定真源
    # agent/limitation_calc.law_version_crosses_watershed；基准日由 service 从 AgentRun 透传，
    # 开关开而未透传 = 接线丢失，同样终态失败（LAW_TRIPWIRE_NOT_WIRED）。
    # 默认关 = verifier 行为逐字不变（与 phantom_tool_check / entity_precision_check 同一
    # 开关惯例；开启属评测批预登记事项，见 docs/handoff-external-harness-20260918.md §2.2）。
    law_version_tripwire_check: bool = False
    # S5（2026-09-19）：把上面那道绊线**扩展到快车道**。`agent_enabled=False` 时线上流量走快车道，
    # 而版本判定只挂在 agent 路径（verifier）上 ⇒ 快车道当时**没有任何版本判定**（R15 收口量出的缺口）。
    # 票 C/S6（2026-09-20）订正范围：**本开关覆盖快车道的两条「生成型」答复出口**——
    #   ① 缓冲轻量出口 `main._light_buffered_locked`（S5；⚠️ 当前部署配置下**零流量**，
    #      因为 `llm_registry` 没配 `('text','light')` 角色 ⇒ `use_light` 恒假）；
    #   ② 旗舰流式出口 `main.stream()` 分支2 的**两个**答案来源（流式 join 与 `_invoke_llm` 兜底，
    #      票 C；这条才是默认配置下真正承接流量的出口）。
    # **不覆盖**缓存复用型直返：登记表 E1（`answer_cache` 精确/近重复）与 E2（`_qa_direct_return`
    # QA 持久语料）在收口点之前就 return ⇒ 挂在收口的门永远走不到它们；那是票 I 的量级。
    # ⇒ 准确的句子是「快车道的生成型答复已受保护；缓存复用型答复未受保护」，
    #   "快车道已受保护"这句在票 I 落地前**不成立**。合同流式出口（E5/E6）按票 C §4-Q1 裁定不接
    #   （合同事实日期来自上传文本而非用户自述，`_fast_path_fact_texts` 那套取法在那分支不成立）。
    # 判定真源仍是 agent/limitation_calc.law_version_crosses_watershed（单一真源，快车道只消费）；
    # 开关开而未拿到 law_as_of = 接线丢失，同 agent 路径 verifier.py 口径 fail-closed（不当作不拦）——
    # 正常请求路径不会走到这一支：两个出口都传 `main._fast_path_law_as_of(body)`（缺省落当日）。
    # 默认关 = 快车道行为逐字不变；开启属评测批预登记事项。范围沿革见 docs/handoff-s6-stream-exit-version-gate-20260920.md §5-8。
    fast_path_law_version_check: bool = False

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

    # T-H（2026-09-18）：**修正性失败**的至多一次重试（仅在 agent_partial_delivery_enabled 下生效）。
    # P5 两轮独立盲评均点名 on 臂「过度排除/过度保守」：writer 一次生成引用了 payload 外的
    # fact_id（UNKNOWN_FACT_ID）或未检索到的法条（UNSUPPORTED_CITATION）→ 该**核心争点整体**
    # 落入 uncovered（案例1·乙「能否起诉」、案例5·乙「退一赔十」）。
    # 此前的注释主张「同输入同校验，重试无意义」——不成立：**校验确定性 ≠ 生成确定性**，
    # 生成是采样的（T3 的 1e9 实证：同分布输入两次结果不同），重试**可能**改变结果。
    # 边界：仅限 writer 自身可避免的失误（引用错 id / 引用未检索法条 / 数字无来源），
    # 至多一次；GENERATOR_FAILURE / MALFORMED_* 等技术失败与 ISSUE_CLAIMS_MISSING（已有 T3）不在此列。
    # 默认关 = 行为逐字不变。
    agent_writer_corrective_retry_enabled: bool = False

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
