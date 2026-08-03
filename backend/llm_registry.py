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
    # priority：同 (modality, tier) 内能力优先级，小=优先；配额只判可用与否，不参与排序。
    # 精简为 2 个强可控模型：thinking/视觉推理模型与 deepseek-r1 在边缘 case（库外问题被检索召回
    # 无关条文时）会据无关条文硬答、不可控，故剔除。text 轻量档空缺时 _safe_pick 回退默认全模态
    # 强模型兜底（历史对边缘 case 诚实拒答/答对），消除轻量硬答风险；省配额靠缓存命中 + 不升级。
    {"key": "text_flag", "model": "qwen3.7-plus", "modality": "text", "tier": "flag", "priority": 0, "capabilities": ["text"], "disable_thinking": True, "initial_used": 28580},  # 关深度思考：法律引用无需长思考，关后 24s→3s 且引用更直接
    {"key": "vision_flag", "model": "qwen3.5-omni-plus-2026-03-15", "modality": "vision", "tier": "flag", "priority": 0, "capabilities": ["text", "vision"], "disable_thinking": True, "initial_used": 140644},  # 关深度思考，图片回答同样提速
]

# 各模态的 tier 回退链（请求某 tier 时，从该 tier 起沿链向上找未耗尽的）
TIER_CHAIN: dict[str, list[str]] = {
    "text": ["light", "flag"],
    "vision": ["flag"],  # 视觉单旗舰（可控）；图片描述也走默认全模态模型
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
    priority: int
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
                    priority=int(r.get("priority", 0)),
                    capabilities=set(cfg["capabilities"]),
                    cfg=cfg,
                    quota_total=int(r.get("quota_total", DEFAULT_QUOTA)),
                    initial_used=int(r.get("initial_used", 0)),
                    runtime_used=quota_store.get_used(key),
                )
                e.llm = _build(cfg)
                self._entries[key] = e

    # ---------- 兼容接口（旧调用点不改） ----------
    def _default_entry(self) -> ModelEntry | None:
        """默认/兜底 entry（调用方须持锁）。消除五处重复的默认查找。"""
        return self._entries.get(DEFAULT_KEY) or next(iter(self._entries.values()), None)

    def get(self) -> ChatOpenAI:
        with self._lock:
            e = self._default_entry()
            assert e is not None and e.llm is not None, "LLM 未初始化"
            return e.llm

    def variant(self, disable_thinking: bool) -> ChatOpenAI:
        with self._lock:
            e = self._default_entry()
            assert e is not None, "LLM 未初始化"
            cfg = dict(e.cfg)
            cfg["disable_thinking"] = disable_thinking
            return _build(cfg)

    def variant_of(self, key: str, disable_thinking: bool) -> ChatOpenAI:
        """按指定 entry 的 cfg 临时构建关/开思考实例（旗舰流式重试用）。"""
        with self._lock:
            e = self._entries.get(key) or self._default_entry()
            assert e is not None, "LLM 未初始化"
            cfg = dict(e.cfg)
            cfg["disable_thinking"] = disable_thinking
            return _build(cfg)

    def config(self) -> dict[str, Any]:
        with self._lock:
            e = self._default_entry()
            return {"model": e.model if e else "", "capabilities": sorted(e.capabilities) if e else []}

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
                # 同档按能力优先级（priority 升序）选，配额只判可用；同优先级再比剩余配额
                candidates.sort(key=lambda e: (e.priority, -e.quota_left))
                for e in candidates:
                    if not e.unavailable:
                        assert e.llm is not None
                        return e.key, e.llm
            raise QuotaExhausted(f"模态 {modality} 无可用模型（全耗尽或低于阈值 {QUOTA_THRESHOLD:.0%}）")

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

    def has_role(self, modality: str, tier: str) -> bool:
        """是否存在该 (modality, tier) 的模型——决定轻量路径是否可用。"""
        with self._lock:
            return any(e.modality == modality and e.tier == tier for e in self._entries.values())

    def is_unavailable(self, key: str) -> bool:
        """该 key 模型是否不可用（耗尽/低于阈值/不存在）——供回退降级判断。"""
        with self._lock:
            e = self._entries.get(key)
            return e.unavailable if e else True

    def default_key(self) -> str:
        """默认/兜底模型 key（_safe_pick 回退用，使回退路径也能扣配额）。"""
        with self._lock:
            e = self._default_entry()
            return e.key if e else ""

    def model_of(self, key: str | None) -> str:
        """key → 模型 id；None/未知返回默认模型名（供日志）。"""
        with self._lock:
            e = self._entries.get(key) if key else None
            if e:
                return e.model
            d = self._default_entry()
            return d.model if d else ""

    def status(self) -> list[dict[str, Any]]:
        """管理员用：各模型配额与可用状态。"""
        with self._lock:
            return [
                {
                    "key": e.key,
                    "model": e.model,
                    "modality": e.modality,
                    "tier": e.tier,
                    "priority": e.priority,
                    "capabilities": sorted(e.capabilities),
                    "quota_total": e.quota_total,
                    "quota_left": e.quota_left,
                    "depleted": e.depleted,
                    "below_threshold": e.below_threshold,
                }
                for e in self._entries.values()
            ]

    def utility_quota_status(self) -> list[dict[str, Any]]:
        """工具类模型（embedding/rerank）配额（ADR-011 阶段E）。

        LLM 走"同档多模型自动切换"；embedding/rerank 只有云端+local，无平级切换，
        故用双阈值：warn（<warn_threshold 标黄"快用完"）/ hard（<hard_threshold 自动
        切回 local 标红）。配额 0 表示未启用配额监控，跳过。
        """
        items = []
        for name, total, initial, warn, hard in (
            ("embedding", settings.embedding_quota_total, settings.embedding_quota_initial,
             settings.embedding_warn_threshold, settings.embedding_hard_threshold),
            ("rerank", settings.rerank_quota_total, settings.rerank_quota_initial,
             settings.rerank_warn_threshold, settings.rerank_hard_threshold),
        ):
            if total <= 0:
                continue
            used = initial + quota_store.get_used(name)
            left = max(0, total - used)
            pct = left / total if total > 0 else 0.0
            items.append(
                {
                    "key": name,
                    "model": settings.embedding_model if name == "embedding" else settings.rerank_model,
                    "modality": name,
                    "tier": "utility",
                    "priority": 0,
                    "capabilities": [name],
                    "quota_total": total,
                    "quota_left": left,
                    "depleted": left <= 0,
                    "below_threshold": pct < hard,  # 前端语义复用：已达降级阈值
                    "warn_threshold": pct < warn and pct >= hard,  # 标黄：快用完
                }
            )
        return items

    def deduct_utility(self, name: str, tokens: int) -> None:
        """扣减工具类模型用量（embedding/rerank），持久化。tokens<=0 或未启用配额 → 忽略。"""
        if tokens <= 0 or name not in ("embedding", "rerank"):
            return
        total = settings.embedding_quota_total if name == "embedding" else settings.rerank_quota_total
        if total <= 0:
            return  # 未启用配额监控，不积累
        quota_store.record_delta(name, int(tokens))


registry = LLMRegistry()
