"""多模型分级路由注册表 + token 配额监控（保留旧单模型兼容接口）。

代表模型 8 个（按 modality × tier 分层），配额一次性、用完即止、剩余 <5% 自动跳过：
- 纯文本旗舰 qwen3.7-plus / 轻量 deepseek-r1-distill-qwen-7b / 备用 qwen-plus
- 全模态旗舰 qwen3.5-omni-plus-2026-03-15 + qwen3-vl-235b / 中端 qwen3-vl-32b /
  轻量 qwen3.5-omni-flash + qwen2.5-omni-7b

兼容：`get()` 仍返回旧默认全模态旗舰（omni-plus），现有 6 个辅助调用点（描述/改写/
压缩/兜底/流式首配置）行为不变；主回答路由用 `pick(modality, tier)`。

配额运行态经 quota_store（独立 SQLite）持久化，重启不丢。
探针结论沿用：langchain 流式无 stream_options 400；接受 extra_body 关思考（variant）。
"""
import json
import threading
from dataclasses import dataclass, field
from typing import Any

from langchain_openai import ChatOpenAI

import quota_store
from domain_rules import QUOTA_THRESHOLD
from settings import settings

DEFAULT_QUOTA = 1_000_000

# 默认代表模型表：key / model / modality / tier / capabilities / initial_used（截图已用量）
# base_url / api_key 复用 settings；可在 .env 用 LLM_MODELS_JSON 整体覆盖。
DEFAULT_ROLES: list[dict[str, Any]] = [
    {"key": "text_flag", "model": "qwen3.7-plus", "modality": "text", "tier": "flag", "capabilities": ["text"], "initial_used": 28580},
    {"key": "text_light", "model": "deepseek-r1-distill-qwen-7b", "modality": "text", "tier": "light", "capabilities": ["text"], "initial_used": 177},
    {"key": "text_backup", "model": "qwen-plus-2025-07-28", "modality": "text", "tier": "flag", "capabilities": ["text"], "initial_used": 418},
    {"key": "vision_flag", "model": "qwen3.5-omni-plus-2026-03-15", "modality": "vision", "tier": "flag", "capabilities": ["text", "vision"], "initial_used": 140644},
    {"key": "vision_flag2", "model": "qwen3-vl-235b-a22b-thinking", "modality": "vision", "tier": "flag", "capabilities": ["text", "vision"], "initial_used": 0},
    {"key": "vision_mid", "model": "qwen3-vl-32b-thinking", "modality": "vision", "tier": "mid", "capabilities": ["text", "vision"], "initial_used": 0},
    {"key": "vision_light", "model": "qwen3.5-omni-flash", "modality": "vision", "tier": "light", "capabilities": ["text", "vision"], "initial_used": 0},
    {"key": "vision_7b", "model": "qwen2.5-omni-7b", "modality": "vision", "tier": "light", "capabilities": ["text", "vision"], "initial_used": 0},
]

# 各模态的 tier 回退链（请求某 tier 时，从该 tier 起沿链向上找未耗尽的）
TIER_CHAIN: dict[str, list[str]] = {
    "text": ["light", "flag"],
    "vision": ["light", "mid", "flag"],
}

# 旧单模型兼容：get() 指向的 key（全模态旗舰 omni-plus，等价旧行为）
DEFAULT_KEY = "vision_flag"


class QuotaExhausted(RuntimeError):
    """所有可用模型配额均已耗尽/低于阈值。"""


@dataclass
class ModelEntry:
    key: str
    model: str
    modality: str
    tier: str
    capabilities: set[str]
    cfg: dict[str, Any]
    quota_total: int
    initial_used: int
    runtime_used: int = 0
    llm: ChatOpenAI | None = field(default=None, repr=False)

    @property
    def quota_left(self) -> int:
        return max(0, self.quota_total - self.initial_used - self.runtime_used)

    @property
    def depleted(self) -> bool:
        return self.quota_left <= 0

    @property
    def below_threshold(self) -> bool:
        if self.quota_total <= 0:
            return True
        return self.quota_left / self.quota_total < QUOTA_THRESHOLD

    @property
    def unavailable(self) -> bool:
        return self.depleted or self.below_threshold


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


def estimate_tokens(text: str) -> int:
    """中文 token 近似估算（无真实 usage 时用）：约 1.5 字符 / token。"""
    return max(1, int(len(text or "") / 1.5))


def _load_roles() -> list[dict[str, Any]]:
    raw = (settings.llm_models_json or "").strip()
    if not raw:
        return [dict(r) for r in DEFAULT_ROLES]
    return json.loads(raw)


class LLMRegistry:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._entries: dict[str, ModelEntry] = {}
        self._load()

    def _load(self) -> None:
        with self._lock:
            self._entries = {}
            for r in _load_roles():
                key = r["key"]
                cfg = {
                    "model": r["model"],
                    "base_url": r.get("base_url") or settings.llm_base_url,
                    "api_key": r.get("api_key") or settings.api_key,
                    "capabilities": list(r.get("capabilities", ["text"])),
                    "disable_thinking": bool(r.get("disable_thinking", False)),
                    "timeout": int(r.get("timeout", 120)),
                }
                e = ModelEntry(
                    key=key,
                    model=r["model"],
                    modality=r.get("modality", "text"),
                    tier=r.get("tier", "flag"),
                    capabilities=set(cfg["capabilities"]),
                    cfg=cfg,
                    quota_total=int(r.get("quota_total", DEFAULT_QUOTA)),
                    initial_used=int(r.get("initial_used", 0)),
                    runtime_used=quota_store.get_used(key),
                )
                e.llm = _build(cfg)
                self._entries[key] = e

    # ---------- 兼容接口（旧调用点不改） ----------
    def get(self) -> ChatOpenAI:
        with self._lock:
            e = self._entries.get(DEFAULT_KEY) or next(iter(self._entries.values()))
            assert e.llm is not None, "LLM 未初始化"
            return e.llm

    def variant(self, disable_thinking: bool) -> ChatOpenAI:
        with self._lock:
            e = self._entries.get(DEFAULT_KEY) or next(iter(self._entries.values()))
            cfg = dict(e.cfg)
            cfg["disable_thinking"] = disable_thinking
            return _build(cfg)

    def config(self) -> dict[str, Any]:
        with self._lock:
            e = self._entries.get(DEFAULT_KEY) or next(iter(self._entries.values()))
            return {"model": e.model, "capabilities": sorted(e.capabilities)}

    def reload(self, model: str | None = None) -> dict[str, Any]:
        """兼容：仅重建默认 entry（旧单模型热切换语义）。多模型整体重载用 _load。"""
        with self._lock:
            e = self._entries.get(DEFAULT_KEY)
            if e and model:
                e.cfg["model"] = model
                e.model = model
                e.llm = _build(e.cfg)
            return self.config()

    # ---------- 路由接口（主回答用） ----------
    def pick(self, modality: str, tier: str) -> tuple[str, ChatOpenAI]:
        """按 (modality, tier) 选模型：从请求 tier 沿回退链找首个可用；全不可用抛 QuotaExhausted。"""
        with self._lock:
            chain = TIER_CHAIN.get(modality, ["flag"])
            try:
                start = chain.index(tier)
            except ValueError:
                start = 0
            for t in chain[start:]:
                candidates = [e for e in self._entries.values() if e.modality == modality and e.tier == t]
                candidates.sort(key=lambda e: e.quota_left, reverse=True)
                for e in candidates:
                    if not e.unavailable:
                        assert e.llm is not None
                        return e.key, e.llm
            raise QuotaExhausted(f"模态 {modality} 无可用模型（全耗尽或低于阈值 {QUOTA_THRESHOLD:.0%}）")

    def pick_any_text(self) -> tuple[str, ChatOpenAI]:
        """辅助：纯文本调用（改写/压缩）也走配额感知选择，从轻量起。"""
        return self.pick("text", "light")

    def deduct(self, key: str, tokens: int) -> None:
        """扣减某模型用量（内存 + 持久化）。tokens<=0 忽略。"""
        if tokens <= 0:
            return
        with self._lock:
            e = self._entries.get(key)
            if not e:
                return
            e.runtime_used += int(tokens)
        quota_store.record_delta(key, int(tokens))

    def status(self) -> list[dict[str, Any]]:
        """管理员用：各模型配额与可用状态。"""
        with self._lock:
            return [
                {
                    "key": e.key,
                    "model": e.model,
                    "modality": e.modality,
                    "tier": e.tier,
                    "capabilities": sorted(e.capabilities),
                    "quota_total": e.quota_total,
                    "quota_left": e.quota_left,
                    "depleted": e.depleted,
                    "below_threshold": e.below_threshold,
                }
                for e in self._entries.values()
            ]


registry = LLMRegistry()
