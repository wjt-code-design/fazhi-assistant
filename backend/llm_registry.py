"""模型注册表：单一全模态模型（文字+图片由同一模型处理）+ 线程安全在线热切换。

探针结论（阿里云百炼 compatible-mode，qwen3.5-omni-plus-2026-03-15，已实测勿改回猜测）：
- 纯文本 / 流式 / 带图（OpenAI 兼容 content 数组）均可用；langchain 流式正常（无 stream_options 400）。
- 接受 extra_body={"thinking": {"type": "disabled"}}（不 400）；但 disable_thinking 默认 False（不传），
  仅在空答重试的 variant 中会用到。
- 会偶发限流/空答，故保留 max_retries=3 与空答重试。
"""

import threading
from typing import Any

from langchain_openai import ChatOpenAI

from settings import settings

DEFAULT_CFG: dict[str, Any] = {
    "model": settings.llm_model,
    "base_url": settings.llm_base_url,
    "api_key": settings.api_key,
    "capabilities": ["text", "vision"],  # 全模态
    "disable_thinking": False,  # 默认不传额外参数
    "timeout": 120,
}


def _build(cfg: dict[str, Any]) -> ChatOpenAI:
    if not cfg.get("api_key") or not cfg.get("base_url"):
        raise RuntimeError("缺少 LLM_API_KEY / LLM_BASE_URL，请在 backend/.env 配置")
    model_kwargs: dict[str, Any] = {}
    if cfg.get("disable_thinking"):
        model_kwargs["extra_body"] = {"thinking": {"type": "disabled"}}
    return ChatOpenAI(
        model=cfg["model"],
        api_key=cfg["api_key"],
        base_url=cfg["base_url"],
        streaming=True,
        model_kwargs=model_kwargs,
        timeout=cfg.get("timeout", 120),
        max_retries=3,
    )


class LLMRegistry:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._cfg: dict[str, Any] = dict(DEFAULT_CFG)
        self._llm: ChatOpenAI | None = None
        self._build()

    def _build(self) -> None:
        with self._lock:
            self._llm = _build(self._cfg)

    def get(self) -> ChatOpenAI:
        with self._lock:
            llm = self._llm
            assert llm is not None, "LLM 未初始化（_build 失败）"
            return llm

    def variant(self, disable_thinking: bool) -> ChatOpenAI:
        """按给定"是否关思考"构建临时实例（用于空答重试；阿里云接受该参数）。"""
        with self._lock:
            cfg = dict(self._cfg)
            cfg["disable_thinking"] = disable_thinking
            return _build(cfg)

    def config(self) -> dict[str, Any]:
        with self._lock:
            return {"model": self._cfg["model"], "capabilities": list(self._cfg["capabilities"])}

    def reload(self, model: str | None = None) -> dict[str, Any]:
        """在线热切换（单模型）。进行中流式仍持有旧实例引用，不受影响。"""
        with self._lock:
            if model:
                self._cfg["model"] = model
            self._build()
            return self.config()


registry = LLMRegistry()
