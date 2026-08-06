"""集中配置（pydantic-settings）。从环境变量读取（main.py 已 load_dotenv 注入 os.environ）。

- 字段名小写；环境变量名大小写不敏感（case_sensitive=False）。
- 未知环境变量忽略（extra=ignore），避免 .env 里多余项报错。
- 兼容旧名 ZHIPUAI_API_KEY（见 api_key 属性）。
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(case_sensitive=False, extra="ignore")

    # ---- LLM ----
    llm_api_key: str = ""
    llm_base_url: str = ""
    llm_model: str = "qwen3.5-omni-plus-2026-03-15"
    zhipuai_api_key: str = ""  # 旧名兼容（智谱平台 key，8-23 到期免费 token）
    zhipu_base_url: str = "https://open.bigmodel.cn/api/paas/v4"  # 智谱 OpenAI 兼容端点

    # ---- 鉴权 ----
    jwt_secret: str = ""
    admin_username: str = "admin"
    admin_password: str = "admin12345"

    # ---- 特性开关 ----
    feature_hybrid: bool = True  # 向量+BM25 RRF 混合检索
    feature_router: bool = True  # 多模型分级路由总开关；False 时主回答退化为旧单模型（get()）
    feature_study_retrieval: bool = True  # ADR-012：study_aid 具体题分步检索（False 一键回滚"不检索"）
    feature_study_cache: bool = True  # 法考题(study_aid)进回答缓存白名单（False 回滚=仅 legal_query 可缓存）
    feature_similar_cache: bool = True  # BGE 近重复命中（结构护栏防错答；False 只精确 key 命中）

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

    # ---- 合同 / 文书风险评估（确定性骨架，2026-08-06）----
    feature_multi_analyze: bool = True  # 合同评估开关（一键回滚）
    contract_max_chars: int = 12000  # 合同文本上限（之上截取并在报告注明）

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
