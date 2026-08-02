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
    zhipuai_api_key: str = ""  # 旧名兼容

    # ---- 鉴权 ----
    jwt_secret: str = ""
    admin_username: str = "admin"
    admin_password: str = "admin12345"

    # ---- 特性开关 ----
    feature_hybrid: bool = True  # 向量+BM25 RRF 混合检索
    feature_rerank: bool = False  # cross-encoder 重排（CPU 重，默认关）
    feature_router: bool = True  # 多模型分级路由总开关；False 时主回答退化为旧单模型（get()）

    # ---- 多模型配置（可选整体覆盖默认代表表；JSON 数组，元素见 llm_registry.DEFAULT_ROLES 字段） ----
    # 留空则用 llm_registry 内置的 8 代表模型默认表（base_url/api_key 复用上面的 LLM_*）
    llm_models_json: str = ""

    # ---- 图片限制 ----
    image_max_mb: int = 5
    image_max_px: int = 6000
    image_min_px: int = 10

    # ---- 日志 ----
    log_level: str = "INFO"

    @property
    def api_key(self) -> str:
        return self.llm_api_key or self.zhipuai_api_key


settings = Settings()
