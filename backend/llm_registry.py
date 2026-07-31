"""模型注册表：文本/视觉分槽 + 线程安全在线热切换 + 关闭思考 + 重试。

探针结论（已实测，勿改回猜测）：
- 关思考参数写法：model_kwargs={"extra_body": {"thinking": {"type": "disabled"}}}；
  但该参数在 glm-4.7-flash 上**不可靠**：实测间歇性返回空 content（答案进了 reasoning_content），
  空答率约 50%，故默认 disable_thinking=False（让模型思考，管道只读 content，答案稳定）；
  确需提速可在已验证的模型上把配置改回 True。enable_thinking=False 无效，勿用。
- 视觉(glm-4.6v-flash)+流式 可用；图片须为合规尺寸（太小会被智谱 1210 拒绝）。
- 会偶发 429(1305)，故用 openai 客户端内置 max_retries 重试 429/5xx/连接错误。
- glm 系列偶发"空生成"（content/reasoning 皆空，间歇/突发，免费额度/限流下更易发生）；
  已由 rag_chain.stream_with_retry 做多配置轮换重试缓解，仍空则返回友好错误。生产建议换更稳定模型档位。
"""
import os
import threading
from typing import Any, Dict, Optional

from langchain_openai import ChatOpenAI

BASE_URL = os.getenv("ZHIPUAI_BASE_URL", "https://open.bigmodel.cn/api/paas/v4/")
API_KEY = os.getenv("ZHIPUAI_API_KEY", "")

# 槽位默认配置；reload 可覆盖 model
DEFAULT_SLOTS: Dict[str, Dict[str, Any]] = {
    "text": {
        "model": os.getenv("LLM_MODEL", "glm-4.7-flash"),
        "capabilities": ["text"],
        "disable_thinking": False,  # 关思考在 glm-4.7-flash 上不可靠（间歇空答），默认让模型思考
        "timeout": 120,
    },
    "vision": {
        "model": os.getenv("VISION_MODEL", "glm-4.6v-flash"),
        "capabilities": ["text", "vision"],
        "disable_thinking": False,  # 同上：追求可靠而非极限速度
        "timeout": 120,
        "max_image_mb": 5,
        "max_px": 6000,
        "min_px": 10,
        "formats": ["image/jpeg", "image/png"],
    },
}


def _build(slot_cfg: Dict[str, Any]) -> ChatOpenAI:
    model_kwargs: Dict[str, Any] = {}
    if slot_cfg.get("disable_thinking"):
        model_kwargs["extra_body"] = {"thinking": {"type": "disabled"}}
    return ChatOpenAI(
        model=slot_cfg["model"],
        api_key=API_KEY,
        base_url=BASE_URL,
        streaming=True,
        model_kwargs=model_kwargs,
        timeout=slot_cfg.get("timeout", 120),
        max_retries=3,  # openai 客户端内置：重试 429/5xx/连接/超时
    )


class LLMRegistry:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._slots: Dict[str, Dict[str, Any]] = {k: dict(v) for k, v in DEFAULT_SLOTS.items()}
        self._llms: Dict[str, ChatOpenAI] = {}
        self._build_all()

    def _build_all(self) -> None:
        for name, cfg in self._slots.items():
            self._llms[name] = _build(cfg)

    def get(self, kind: str = "text") -> ChatOpenAI:
        with self._lock:
            return self._llms.get(kind) or self._llms["text"]

    def choose(self, has_image: bool) -> ChatOpenAI:
        """能力路由：带图走 vision，否则 text。"""
        return self.get("vision" if has_image else "text")

    def variant(self, kind: str, disable_thinking: bool) -> ChatOpenAI:
        """按给定"是否关思考"构建该槽位的临时实例（用于空答重试的配置轮换）。"""
        with self._lock:
            cfg = dict(self._slots.get(kind, self._slots["text"]))
            cfg["disable_thinking"] = disable_thinking
            return _build(cfg)

    def vision_cfg(self) -> Dict[str, Any]:
        with self._lock:
            return dict(self._slots["vision"])

    def config(self) -> Dict[str, Dict[str, Any]]:
        """对外展示用：仅返回 model + capabilities（不含密钥/内部参数）。"""
        with self._lock:
            return {
                k: {"model": v["model"], "capabilities": list(v["capabilities"])}
                for k, v in self._slots.items()
            }

    def reload(self, text_model: Optional[str] = None, vision_model: Optional[str] = None) -> Dict[str, Dict[str, Any]]:
        """在线热切换：加锁重建缓存实例。进行中的流式仍持有旧实例引用，不受影响。"""
        with self._lock:
            if text_model:
                self._slots["text"]["model"] = text_model
            if vision_model:
                self._slots["vision"]["model"] = vision_model
            self._build_all()
            return self.config()


registry = LLMRegistry()
