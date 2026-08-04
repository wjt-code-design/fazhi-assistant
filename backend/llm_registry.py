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
import quota_utils
from domain_rules import QUOTA_THRESHOLD
from settings import settings

DEFAULT_QUOTA = 1_000_000

# 默认代表模型表：key / model / modality / tier / capabilities / initial_used（截图已用量）
# base_url / api_key 复用 settings；可在 .env 用 LLM_MODELS_JSON 整体覆盖。
DEFAULT_ROLES: list[dict[str, Any]] = [
    # priority：同 (modality, tier) 内能力优先级，小=优先；配额只判可用与否，不参与排序。
    # 2026-08-05 因配额耗尽重引 thinking 兜底（ADR-010 反向决策）：受缓存写闸（引用⊆检索）
    # / citation_verify / self_check / refuse 四防线约束，仅作最后兜底；切换后须跑 eval_exam 验证。
    # 文本队列按**质量序**（用户确认，质量优先）：强模型优先，弱模型兜底。
    # priority 强弱依据用户给出的从弱到强排名反转而来；改 priority 一行即可换序。
    # quota_total 默认 100 万，initial_used 待管理员用 /api/admin/llm-quota 校准真实值。
    {"key": "text_flag", "model": "qwen3.7-plus", "modality": "text", "tier": "flag", "priority": 0, "capabilities": ["text"], "disable_thinking": True, "initial_used": 28580},  # 现役旗舰；关深度思考：法律引用无需长思考
    {"key": "text_ds_flash", "model": "deepseek-v4-flash", "modality": "text", "tier": "flag", "priority": 1, "capabilities": ["text"], "disable_thinking": True},  # 用户确认：最强非思考模型
    {"key": "text_max_37d", "model": "qwen3.7-max-2026-06-08", "modality": "text", "tier": "flag", "priority": 2, "capabilities": ["text"], "disable_thinking": True},
    {"key": "text_max_37", "model": "qwen3.7-max", "modality": "text", "tier": "flag", "priority": 3, "capabilities": ["text"], "disable_thinking": True},
    {"key": "text_max_37pv", "model": "qwen3.7-max-preview", "modality": "text", "tier": "flag", "priority": 4, "capabilities": ["text"], "disable_thinking": True},
    {"key": "text_max_36pv", "model": "qwen3.6-max-preview", "modality": "text", "tier": "flag", "priority": 5, "capabilities": ["text"], "disable_thinking": True},
    {"key": "text_ds_pro", "model": "deepseek-v4-pro", "modality": "text", "tier": "flag", "priority": 6, "capabilities": ["text"], "disable_thinking": True},
    {"key": "text_kimi", "model": "kimi-k2.6", "modality": "text", "tier": "flag", "priority": 7, "capabilities": ["text"], "disable_thinking": True},
    {"key": "text_glm52", "model": "glm-5.2", "modality": "text", "tier": "flag", "priority": 8, "capabilities": ["text"], "disable_thinking": True},
    {"key": "text_glm5", "model": "glm-5", "modality": "text", "tier": "flag", "priority": 9, "capabilities": ["text"], "disable_thinking": True},
    {"key": "text_plus_36", "model": "qwen3.6-plus", "modality": "text", "tier": "flag", "priority": 10, "capabilities": ["text"], "disable_thinking": True},
    {"key": "text_plus_35", "model": "qwen3.5-plus-2026-02-15", "modality": "text", "tier": "flag", "priority": 11, "capabilities": ["text"], "disable_thinking": True},
    {"key": "text_qwen_plus", "model": "qwen-plus-2025-07-28", "modality": "text", "tier": "flag", "priority": 12, "capabilities": ["text"], "disable_thinking": True},
    {"key": "text_ds_flash0731", "model": "deepseek-v4-flash-0731", "modality": "text", "tier": "flag", "priority": 13, "capabilities": ["text"], "disable_thinking": True},
    {"key": "text_flash_37", "model": "qwen3.7-flash-2026-07-15", "modality": "text", "tier": "flag", "priority": 14, "capabilities": ["text"], "disable_thinking": True},
    {"key": "text_flash_35", "model": "qwen3.5-flash-2026-02-23", "modality": "text", "tier": "flag", "priority": 15, "capabilities": ["text"], "disable_thinking": True},
    {"key": "text_thinking_32b", "model": "qwen3-vl-32b-thinking", "modality": "text", "tier": "flag", "priority": 16, "capabilities": ["text"], "disable_thinking": False},  # 思考专属版，仅最后兜底
    {"key": "text_thinking_235b", "model": "qwen3-vl-235b-a22b-thinking", "modality": "text", "tier": "flag", "priority": 17, "capabilities": ["text"], "disable_thinking": False},  # 思考专属版，仅最后兜底
    {"key": "vision_flag", "model": "qwen3.5-omni-plus-2026-03-15", "modality": "vision", "tier": "flag", "priority": 0, "capabilities": ["text", "vision"], "disable_thinking": True, "initial_used": 140644},  # 关深度思考，图片回答同样提速
    {"key": "vision_rt", "model": "qwen3.5-omni-plus-realtime", "modality": "vision", "tier": "flag", "priority": 1, "capabilities": ["text", "vision"], "disable_thinking": True},
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
    # thinking:disabled 是 DashScope qwen 专属参数；deepseek/glm/kimi 经兼容端点
    # 可能 400（审查 I6）——只对 qwen 系发，第三方模型默认无思考不改行为
    if cfg.get("disable_thinking") and str(cfg.get("model", "")).startswith("qwen"):
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
    """中文 token 近似估算（无真实 usage 时用）：约 1.5 字符 / token。

    ADR-011 code-review 收敛：唯一实现在 quota_utils，此处 re-export 保兼容
    （main.py / tests/test_routing.py 继续按 llm_registry.estimate_tokens 引用）。
    """
    return quota_utils.estimate_tokens(text)


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
                # 校准覆盖（块 3）：管理员从控制台读数后用 /api/admin/llm-quota 校准，
                # 覆盖默认 initial_used——看门狗 remaining 与真实值对齐
                ov = quota_store.initial_override(key)
                if ov is not None:
                    e.initial_used = ov
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

    def thinking_mult(self, key: str | None) -> int:
        """思考模型扣减系数（审查 K1：流式无真实 usage，thinking 的 reasoning_content 不进入
        本地估算——×3 近似，防看门狗失明导致"剩<5% 自动跳过"不按时触发）。"""
        with self._lock:
            e = self._entries.get(key) if key else None
            if e and not e.cfg.get("disable_thinking", True):
                return 3
            return 1

    def mark_depleted(self, key: str, reason: str) -> None:
        """配额耗尽即时失效（块 2.2：依据真实 API 错误，不靠估算）。置 remaining=0，
        该模型立即 unavailable；下一请求/同请求重试自动落后备。

        仅改内存 runtime_used（本进程立即生效）；持久化由 /api/admin/llm-quota 校准
        端点或重启后初始值负责——耗尽是运行期事实，内存标记足够（重启即恢复默认，
        需管理员按控制台校准真实剩余）。"""
        with self._lock:
            e = self._entries.get(key)
            if not e or e.depleted:
                return
            e.runtime_used += max(0, e.quota_left)

    def calibrate(self, key: str, remaining: int) -> dict[str, Any]:
        """配额校准（块 3）：按控制台真实剩余值回写 initial_used，看门狗对齐真实值。

        quota_left = quota_total - initial_used - runtime_used；设 remaining=R →
        initial_used = quota_total - R - runtime_used（下限 0）。持久化到 quota_store，
        重启后 _load 自动应用。"""
        with self._lock:
            e = self._entries.get(key)
            if not e:
                raise KeyError(f"未知模型 key: {key}")
            new_init = max(0, e.quota_total - int(remaining) - e.runtime_used)
            e.initial_used = new_init
        quota_store.set_initial(key, new_init)
        return {"key": key, "model": e.model, "quota_left": e.quota_left, "initial_used": e.initial_used}

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
        """工具类模型（embedding/rerank）配额（ADR-011 阶段E + code-review 收敛）。

        - embedding：**换班制**（grilling 决策）——耗尽不自动降级，后台标红提示手动换班重建库，
          真耗尽时检索返回 409 明确报错。fallback="manual_rebuild"。
        - rerank：**多模型自动轮换**——每模型独立配额，耗尽自动切队列下一个，全耗尽自动降级
          本地 cosine 精排（fallback="local_cosine"）。
        配额 0 表示未启用配额监控，跳过。
        """
        items = []
        # embedding（单条，per-model key：换班后新模型从 0 起算）
        et, ei = settings.embedding_quota_total, settings.embedding_quota_initial
        if et > 0:
            ek = quota_utils.embedding_model_key()
            used = ei + quota_store.get_used(ek)
            left = max(0, et - used)
            pct = left / et
            items.append(
                {
                    "key": ek,
                    "model": "BGE (local)" if settings.embedding_provider != "aliyun" else settings.embedding_model,
                    "modality": "embedding",
                    "tier": "utility",
                    "priority": 0,
                    "capabilities": ["embedding"],
                    "quota_total": et,
                    "quota_left": left,
                    "depleted": left <= 0,
                    "below_threshold": pct < settings.embedding_hard_threshold,
                    "warn_threshold": pct < settings.embedding_warn_threshold
                    and pct >= settings.embedding_hard_threshold,
                    "fallback": "manual_rebuild",
                }
            )
        # rerank（每模型一条，按轮换序列；B11：degraded=队列全部不可用=整体降级本地精排，
        # 区别于单模型耗尽但还有替代可轮换）
        rw, rh = settings.rerank_warn_threshold, settings.rerank_hard_threshold
        rerank_items: list[dict[str, Any]] = []
        for m in quota_utils.rerank_model_list():
            total = quota_utils.utility_quota_total_for(m)
            if total <= 0:
                continue
            used = settings.rerank_quota_initial + quota_store.get_used(m)
            left = max(0, total - used)
            pct = left / total
            rerank_items.append(
                {
                    "key": m,
                    "model": m,
                    "modality": "rerank",
                    "tier": "utility",
                    "priority": 0,
                    "capabilities": ["rerank"],
                    "quota_total": total,
                    "quota_left": left,
                    "depleted": left <= 0,
                    "below_threshold": pct < rh,
                    "warn_threshold": pct < rw and pct >= rh,
                    "fallback": "local_cosine",
                }
            )
        # 整体降级 = 有 rerank 配置但当前无可用模型（单一来源 quota_utils.rerank_active_model）
        degraded = bool(rerank_items) and quota_utils.rerank_active_model() is None
        for i in rerank_items:
            i["degraded"] = degraded
        items.extend(rerank_items)
        return items

registry = LLMRegistry()
