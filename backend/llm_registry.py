"""多模型分级路由注册表 + token 配额监控（保留旧单模型兼容接口）。

代表模型按 modality × tier 分层，条目见 `DEFAULT_ROLES`（单一真源；这里不抄条数也不举模型名——
DB-24 的成因就是注释抄过"8 个"和一批模型名，而表已换成 27 条、举的名字大半不在表里）。
配额一次性、用完即止、剩余 <5% 自动跳过。

兼容：`get()` 仍返回旧默认全模态旗舰（omni-plus），现有辅助调用点（描述/改写/
压缩/兜底/流式首配置）行为不变；主回答路由用 `pick(modality, tier)`。

配额运行态经 quota_store（独立 SQLite）持久化，重启不丢。
探针结论沿用：langchain 流式无 stream_options 400；接受 extra_body 关思考（variant）。
"""

import inspect
import json
import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any

from langchain_openai import ChatOpenAI

import quota_store
import quota_utils
from domain_rules import QUOTA_THRESHOLD
from settings import settings

DEFAULT_QUOTA = 1_000_000

# 票 W07 §1 ①②：语音/视觉的**传输标记**从 entry 一路走到调用处，中间不许被无声丢掉。
# - `TRANSPORTS` 是值的闭集；`DEFAULT_TRANSPORT`＝chat ⇒ 没写这个键的既有条目行为逐字不变；
# - `CFG_KEYS` 是 cfg 的**键**闭集：`_build` 对白名单外的键显式报错（改前是「不报错也不生效」，
#   判据见 `tests/test_multimodal_transport_contract.py` 第 2、3 条，本轮改写成新闭集）。
#   注意 `capabilities` 在集合内但不被 `_build` 读（它归 ModelEntry 用），AST 闭集钉的是「读了哪些键」，
#   两者相差这一个键是设计而不是漏项。
TRANSPORTS: tuple[str, ...] = ("chat", "audio_transcriptions", "none")
DEFAULT_TRANSPORT = "chat"
CFG_KEYS = frozenset(
    {
        "api_key",
        "base_url",
        "model",
        "capabilities",
        "disable_thinking",
        "timeout",
        "translation_options",
        "transport",
    }
)
# entry（DEFAULT_ROLES／LLM_MODELS_JSON）里 `_load` 会读的键闭集；集合外的键**落日志**而不是无声消失——
# 刻意不在这里 raise：现役 `.env` 的条目内容本轮不可读也不可变，启动期炸整只 registry 超出本票授权。
ROLE_KEYS = frozenset(
    {
        "key",
        "model",
        "modality",
        "tier",
        "priority",
        "capabilities",
        "disable_thinking",
        "initial_used",
        "quota_total",
        "provider",
        "base_url",
        "api_key",
        "timeout",
        "translation_options",
        "transport",
    }
)

# DB-17（2026-10-09，审查报告 B-48）：**请求形状类 4xx** 的冷却时长（秒）。
# 判据来自 `llm_errors.is_request_shape_rejection`——400/401/403/404/422 是「这一发请求本身不被接受」
# （超长上下文、内容审核、模型名写错、key 失效、端点点错），**不是**「这个模型的积分用完了」。
# 改前两证已钉：分类口径由 `tests/test_llm_failover.py::test_permanent_status_is_not_transient_in_both_sdk_shapes`
# 钉成 permanent（本轮不动它；按名字引，行号会随该文件加腿而漂），
# 但 permanent 的处理通道只有一条 `mark_depleted`，其实现是 `runtime_used += quota_left`，
# 且 `reason` 参数被**整个丢弃** ⇒ 一次 400 在管理台/配额库里的读数是"该模型配额耗尽"，
# 运维据此去加积分、调 calibrate，而真病因（payload/配置）永远不出现在任何一张表里。
REJECT_COOLDOWN_S = 300

# D-9（Owner 2026-10-11 裁「分两档」）：401/403/404 是**配置性拒绝**——不改配置就不会好，
# 300 秒后重试等于反复打同一个坏端点；400/422 才是请求形状问题，短冷却合理。
# 两档在管理台也必须分得开，故 `rejected_kind` 进 `status()` 每一行。
REJECT_COOLDOWN_BY_STATUS = {401: 3600, 403: 3600, 404: 3600}
REJECT_CONFIG_STATUSES = frozenset(REJECT_COOLDOWN_BY_STATUS)


def reject_cooldown_s(status: int | None) -> int:
    """按状态码取冷却秒数；未知或无状态 ⇒ 短档（保守，不误升级成长冷却）。"""
    return REJECT_COOLDOWN_BY_STATUS.get(status if isinstance(status, int) else -1, REJECT_COOLDOWN_S)


def reject_kind(status: int | None) -> str:
    return "config" if isinstance(status, int) and status in REJECT_CONFIG_STATUSES else "shape"


def _unknown_keys(container: dict[str, Any], allowed: frozenset[str]) -> list[str]:
    """白名单外的键名（排序后的列表）。票 W7-B2：cfg 面（`_build`）与 entry 原始 dict 面
    （`LLMRegistry._load`）**共用这一把尺**——两处各写一遍 `set(x) - KEYS` 的话，
    entry 面那份会跟着 cfg 面一起漂，而「拼错的键无声消失」正是本票要钉死的失效。
    """
    return sorted(set(container) - allowed)


# 默认代表模型表：key / model / modality / tier / capabilities / initial_used（截图已用量）
# base_url / api_key 复用 settings；可在 .env 用 LLM_MODELS_JSON 整体覆盖。
DEFAULT_ROLES: list[dict[str, Any]] = [
    # priority：同 (modality, tier) 内能力优先级，小=优先；配额只判可用与否，不参与排序。
    # 2026-08-05 因配额耗尽重引 thinking 兜底（ADR-010 反向决策）：受缓存写闸（引用⊆检索）
    # / citation_verify / self_check / refuse 四防线约束，仅作最后兜底；切换后须跑 eval_exam 验证。
    # 文本队列按**质量序**（强模型优先，弱模型兜底；配额耗尽或质量不达标时自动切换）。
    # priority 强弱依据用户给出的从弱到强排名反转而来；改 priority 一行即可换序。
    # quota_total 默认 100 万，initial_used 待管理员用 /api/admin/llm-quota 校准真实值。
    {
        "key": "text_flag",
        "model": "qwen3.7-plus",
        "modality": "text",
        "tier": "flag",
        "priority": 0,
        "capabilities": ["text"],
        "disable_thinking": True,
        "initial_used": 28580,
    },  # 现役旗舰；关深度思考：法律引用无需长思考
    {
        "key": "text_ds_flash",
        "model": "deepseek-v4-flash",
        "modality": "text",
        "tier": "flag",
        "priority": 1,
        "capabilities": ["text"],
        "disable_thinking": True,
    },  # 用户确认：最强非思考模型
    {
        "key": "text_max_37d",
        "model": "qwen3.7-max-2026-06-08",
        "modality": "text",
        "tier": "flag",
        "priority": 2,
        "capabilities": ["text"],
        "disable_thinking": True,
    },
    {
        "key": "text_max_37",
        "model": "qwen3.7-max",
        "modality": "text",
        "tier": "flag",
        "priority": 3,
        "capabilities": ["text"],
        "disable_thinking": True,
    },
    {
        "key": "text_max_37pv",
        "model": "qwen3.7-max-preview",
        "modality": "text",
        "tier": "flag",
        "priority": 4,
        "capabilities": ["text"],
        "disable_thinking": True,
    },
    {
        "key": "text_max_36pv",
        "model": "qwen3.6-max-preview",
        "modality": "text",
        "tier": "flag",
        "priority": 5,
        "capabilities": ["text"],
        "disable_thinking": True,
    },
    {
        "key": "text_ds_pro",
        "model": "deepseek-v4-pro",
        "modality": "text",
        "tier": "flag",
        "priority": 6,
        "capabilities": ["text"],
        "disable_thinking": True,
    },
    {
        "key": "text_kimi",
        "model": "kimi-k2.6",
        "modality": "text",
        "tier": "flag",
        "priority": 7,
        "capabilities": ["text"],
        "disable_thinking": True,
    },
    {
        "key": "text_glm52",
        "model": "glm-5.2",
        "modality": "text",
        "tier": "flag",
        "priority": 8,
        "capabilities": ["text"],
        "disable_thinking": True,
    },
    {
        "key": "text_glm5",
        "model": "glm-5",
        "modality": "text",
        "tier": "flag",
        "priority": 9,
        "capabilities": ["text"],
        "disable_thinking": True,
    },
    {
        "key": "text_plus_36",
        "model": "qwen3.6-plus",
        "modality": "text",
        "tier": "flag",
        "priority": 10,
        "capabilities": ["text"],
        "disable_thinking": True,
    },
    {
        "key": "text_plus_35",
        "model": "qwen3.5-plus-2026-02-15",
        "modality": "text",
        "tier": "flag",
        "priority": 11,
        "capabilities": ["text"],
        "disable_thinking": True,
    },
    {
        "key": "text_qwen_plus",
        "model": "qwen-plus-2025-07-28",
        "modality": "text",
        "tier": "flag",
        "priority": 12,
        "capabilities": ["text"],
        "disable_thinking": True,
    },
    {
        "key": "text_ds_flash0731",
        "model": "deepseek-v4-flash-0731",
        "modality": "text",
        "tier": "flag",
        "priority": 13,
        "capabilities": ["text"],
        "disable_thinking": True,
    },
    {
        "key": "text_flash_37",
        "model": "qwen3.7-flash-2026-07-15",
        "modality": "text",
        "tier": "flag",
        "priority": 14,
        "capabilities": ["text"],
        "disable_thinking": True,
    },
    {
        "key": "text_flash_35",
        "model": "qwen3.5-flash-2026-02-23",
        "modality": "text",
        "tier": "flag",
        "priority": 15,
        "capabilities": ["text"],
        "disable_thinking": True,
    },
    {
        "key": "text_thinking_32b",
        "model": "qwen3-vl-32b-thinking",
        "modality": "text",
        "tier": "flag",
        "priority": 16,
        "capabilities": ["text"],
        "disable_thinking": False,
    },  # 思考专属版，仅最后兜底
    {
        "key": "text_thinking_235b",
        "model": "qwen3-vl-235b-a22b-thinking",
        "modality": "text",
        "tier": "flag",
        "priority": 17,
        "capabilities": ["text"],
        "disable_thinking": False,
    },  # 思考专属版，仅最后兜底
    {
        "key": "text_glm45air",
        "model": "glm-4.5-air",
        "provider": "zhipu",
        "modality": "text",
        "tier": "flag",
        "priority": 18,
        "capabilities": ["text"],
        "disable_thinking": True,
    },  # 智谱免费（8-23 到期）：强文本后备
    {
        "key": "vision_flag",
        "model": "qwen3.5-omni-plus-2026-03-15",
        "modality": "vision",
        "tier": "flag",
        "priority": 0,
        "capabilities": ["text", "vision"],
        "disable_thinking": True,
        "initial_used": 140644,
    },  # 关深度思考，图片回答同样提速
    {
        "key": "vision_rt",
        "model": "qwen3.5-omni-plus-realtime",
        "modality": "vision",
        "tier": "flag",
        "priority": 1,
        "capabilities": ["text", "vision"],
        "disable_thinking": True,
    },
    {
        "key": "vision_glm41v",
        "model": "glm-4.1v-thinking-flashx",
        "provider": "zhipu",
        "modality": "vision",
        "tier": "flag",
        "priority": 2,
        "capabilities": ["text", "vision"],
        "disable_thinking": False,
    },  # 智谱多模态思考版，视觉最后兜底
    # voice 语音档（M2，2026-08-06 门禁实测）：livetranslate 做语音→文字（ASR），qwen-tts 是文本→语音（备用）。
    # 转写调用链：OpenAI 兼容 /chat/completions + input_audio（data:;base64, 前缀 + wav/mp3/m4a/flac/ogg）
    # + stream=true + top-level translation_options（source/target 均 zh=转写）。disable_thinking 留 False：
    # 语音模型不吃 thinking 参数（门禁 ChatOpenAI 未带 extra_body 才成功）。
    {
        "key": "voice_lt",
        "model": "qwen3-livetranslate-flash-2025-12-01",
        "modality": "voice",
        "tier": "flag",
        "priority": 0,
        "capabilities": ["speech", "asr"],
        "translation_options": {"source_lang": "zh", "target_lang": "zh"},
    },  # 现役转写
    {
        "key": "voice_lt_rt",
        "model": "qwen3-livetranslate-flash-realtime-2025-09-22",
        "modality": "voice",
        "tier": "flag",
        "priority": 1,
        "capabilities": ["speech", "asr"],
    },  # realtime（websocket，备用）
    {
        "key": "voice_tts",
        "model": "qwen-tts-2025-05-22",
        "modality": "voice",
        "tier": "flag",
        "priority": 2,
        "capabilities": ["speech", "tts"],
    },  # TTS 备用（朗读回答未来用）
    {
        "key": "voice_tts_rt_latest",
        "model": "qwen-tts-realtime-latest",
        "modality": "voice",
        "tier": "flag",
        "priority": 3,
        "capabilities": ["speech", "tts"],
    },
    {
        "key": "voice_tts_rt",
        "model": "qwen-tts-realtime-2025-07-15",
        "modality": "voice",
        "tier": "flag",
        "priority": 4,
        "capabilities": ["speech", "tts"],
    },
]

# 各模态的 tier 回退链（请求某 tier 时，从该 tier 起沿链向上找未耗尽的）
TIER_CHAIN: dict[str, list[str]] = {
    "text": ["light", "flag"],
    "vision": ["flag"],  # 视觉单旗舰（可控）；图片描述也走默认全模态模型
    "voice": ["flag"],  # 语音转写（livetranslate 优先，tts 为输出侧不参与转写）
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
    # DB-17：请求形状类 4xx 的**冷却到期时刻**（`time.monotonic()` 基准，0 = 未处于冷却）。
    # 刻意不写进配额账（`runtime_used`/`initial_used` 一字不动），也刻意不落库：
    # 耗尽是运行期事实可持久校准，拒绝是**瞬时事实**，过期即自愈（重启自然清零）。
    rejected_until: float = 0.0
    rejected_kind: str | None = None  # D-9：config（改配置才好）与 shape（本次请求的问题）分档
    # 票 W07 §1 ③＋W7-FIX F11：transport 的**唯一存放处**就是 entry 上这一位（由 `_load` 从 entry
    # 原始 dict 派生一次，**不再**同时写进 cfg——两份同源的那些测试判据永远是绿的，量不到漂移）。
    # 调用方经 `LLMRegistry.transport_of(key)` 读它——不改 `pick()` 的公共返回形状，
    # 也不在 ChatOpenAI 上再存一份（那会变成两处各存一份，本票判据直接红）。
    transport: str = DEFAULT_TRANSPORT
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
    def rejected_now(self) -> bool:
        """是否处于 4xx 冷却中（DB-17）。与配额语义**无关**。"""
        return self.rejected_until > time.monotonic()

    @property
    def unavailable(self) -> bool:
        # DB-17：`unavailable` 的**配额语义**（depleted/below_threshold）保持不变——它被管理台、
        # `pick_by_key`（judge 等显式指定）与配额快照消费，把冷却混进去会让"显式指定被拒的模型"
        # 变成 KeyError，那超出本票范围。冷却只作用于**自动路由**（见 `pick` 的过滤式）。
        return self.depleted or self.below_threshold


def _build(
    cfg: dict[str, Any],
    share_llm: "ChatOpenAI | None" = None,
    share_cfg: dict[str, Any] | None = None,
) -> ChatOpenAI:
    # 票 W07 §1 ②：cfg 白名单——白名单外的键（如把 transport 拼成 transpor）**显式失败**，
    # 不再像改前那样「不报错也不生效」。这是全链路上唯一一处按字面读 `transport` 的地方：
    # 调用方读的是 ModelEntry.transport（同一个派生值），不是第二份 cfg 读取（判据见
    # tests/test_multimodal_transport_impl.py::test_transport_is_read_from_cfg_in_exactly_one_place）。
    # ⚠️ W7-FIX §2 的这条腿要说实话：`_load` 用固定键重建 cfg，所以真实配置路径**走不到**这里，
    # entry 面的等价检查在 `_load` 里（同一把尺 `_unknown_keys`），落日志而不是 raise。
    unknown = _unknown_keys(cfg, CFG_KEYS)
    if unknown:
        raise ValueError(f"LLM cfg 含白名单外的键：{unknown}——静默丢弃等于配置写了没人读")
    transport = cfg.get("transport", DEFAULT_TRANSPORT)
    # 手搓 cfg 的调用点（含测试）仍在这里被拦；`_load` 那条真实配置路已提前验过并**跳过**坏 entry，
    # 所以这一发 raise 不再有机会打死启动（W7-B1，判据见 tests/test_llm_registry_boot_impl.py）。
    if transport not in TRANSPORTS:
        raise ValueError(f"未知 transport：{transport!r}（可用 {list(TRANSPORTS)}）")
    if not cfg.get("api_key") or not cfg.get("base_url"):
        raise RuntimeError("缺少 LLM_API_KEY / LLM_BASE_URL，请在 backend/.env 配置")
    extra_body: dict[str, Any] = {}
    # thinking:disabled 是 DashScope qwen 专属参数；deepseek/glm/kimi 经兼容端点
    # 可能 400（审查 I6）——只对 qwen 系发，第三方模型默认无思考不改行为
    if cfg.get("disable_thinking") and str(cfg.get("model", "")).startswith("qwen"):
        extra_body["thinking"] = {"type": "disabled"}
    # 语音转写（M2）：livetranslate 必需 top-level translation_options（source/target 均 zh=转写），
    # 缺了直接 InvalidParameter（2026-08-06 门禁实测）；经 model_kwargs.extra_body 合并进请求体。
    if cfg.get("translation_options"):
        extra_body["translation_options"] = cfg["translation_options"]
    model_kwargs: dict[str, Any] = {"extra_body": extra_body} if extra_body else {}
    kwargs: dict[str, Any] = dict(
        model=cfg["model"],
        api_key=cfg["api_key"],
        base_url=cfg["base_url"],
        streaming=True,
        model_kwargs=model_kwargs,
        timeout=cfg.get("timeout", 120),
        max_retries=3,
    )
    if share_llm is not None:
        # 传输层复用（生命周期收尾）：仅改 model/思考参数时经已验证的 client/async_client
        # 注入字段共用原 entry 的 SDK 根客户端，避免每次 variant/reload 新建连接池；
        # 请求参数语义仍由新 ChatOpenAI 自身的 model/model_kwargs 决定。
        # 传输参数（端点/凭据/超时）不同不得共用同一客户端——显式失败而不是静默新建池。
        if share_cfg is None or any(share_cfg.get(k) != cfg.get(k) for k in ("base_url", "api_key", "timeout")):
            raise RuntimeError(
                "传输参数(base_url/api_key/timeout)变化时禁止共用 SDK 客户端；"
                "如确需新建连接池，须同步扩展 LLMRegistry 的资源归属与 aclose 覆盖"
            )
        kwargs["client"] = share_llm.client
        kwargs["async_client"] = share_llm.async_client
    return ChatOpenAI(**kwargs)


def estimate_tokens(text: str) -> int:
    """中文 token 近似估算（无真实 usage 时用）：约 1.5 字符 / token。

    ADR-011 code-review 收敛：唯一实现在 quota_utils，此处 re-export 保兼容
    （main.py / tests/test_routing.py 继续按 llm_registry.estimate_tokens 引用）。
    """
    return quota_utils.estimate_tokens(text)


def _load_roles() -> list[Any]:
    """`LLM_MODELS_JSON` → entry 列表；**整段解析不了**就回退 `DEFAULT_ROLES` 并落归因读数。

    R2-F1（复核第二轮）：改前这里是裸的 `json.loads(raw)`，排在任何 try 之外——`.env` 里少一个逗号
    就多一个引号都能把 `_load→__init__→模块作用域 registry = LLMRegistry()` 一路炸穿到 **import 期**：
    后端起不来，而九腿纯树门全绿（上一轮 W7-B1 的判据只咬住 transport 一个字段，同一类还留着）。
    这里回退而不是抛，是因为这只 registry 建在模块作用域——导入期**没有**能接住它的调用方。
    读数只带异常**类名**或结构性词汇：`JSONDecodeError` 的正文会复述配置片段，而配置里可能写着 api_key
    （与 W7-B9「上游文本可能回显请求字节」同一口径：不落正文）。
    """
    raw = (settings.llm_models_json or "").strip()
    if not raw:
        return [dict(r) for r in DEFAULT_ROLES]
    try:
        parsed: Any = json.loads(raw)
    except json.JSONDecodeError as exc:
        reason: str | None = type(exc).__name__
        parsed = None
    else:
        reason = None if isinstance(parsed, list) else f"顶层是 {type(parsed).__name__} 而不是数组"
    if reason is not None:
        logging.getLogger("legal.llm").warning(
            f"llm_cfg_malformed LLM_MODELS_JSON 不可用（{reason}）⇒ 回退 DEFAULT_ROLES",
            extra={"llm_cfg_malformed": [reason]},
        )
        return [dict(r) for r in DEFAULT_ROLES]
    return parsed


# entry 里必须是整数的字段（名字＝默认值）。R2-F1：改前这四个 `int(...)` 直接写在 cfg/ModelEntry
# 构造式里，排在 per-entry try 之外 ⇒ 一个 `"timeout": "abc"` 就打死启动。
_ENTRY_INT_FIELDS: tuple[tuple[str, Any], ...] = (
    ("timeout", 120),
    ("priority", 0),
    ("quota_total", DEFAULT_QUOTA),
    ("initial_used", 0),
)


def _entry_shape(r: Any, index: int = 0) -> tuple[str, dict[str, int], list[str]]:
    """一条 entry 的**形状**校验：返回 (key, 取好的整数, 缺陷列表)；缺陷列表非空＝这条不该进册。

    与 `_unknown_keys` 并列的第二把 entry 面尺子：那把管「键名拼错」，这把管「值写不成它该有的形状」。
    刻意做成**返回缺陷**而不是 `except Exception` 兜底——只认定「配置值不是它声称的那个类型」这一类，
    代码 bug（AttributeError/TypeError 之类）仍当场炸（判据：
    tests/test_llm_registry_boot_impl.py::test_load_does_not_swallow_the_real_failure_shapes）。

    刻意**不**校验 `model` 的类型：`model` 键在而值不对（例如 null）要留给 `_build`——那里 pydantic 抛的
    `ValidationError` 是 `ValueError` 的子类，正是 R2-F2 说的「真实配置路径上唯一还够得着的 ValueError 腿」。
    在半路把它拦下来等于把那条腿重新变成不可达（然后 `(RuntimeError, ValueError)` 又只剩凭据一条腿）。
    """
    if not isinstance(r, dict):
        return f"<第 {index} 条非对象 entry>", {}, [f"entry 应为 JSON 对象，实得 {type(r).__name__}"]
    defects: list[str] = []
    key = r.get("key")
    if not isinstance(key, str) or not key:
        defects.append(f"key 缺失或不是字符串（{key!r}）")
        key = "<无 key 的 entry>"
    if "model" not in r:
        defects.append("缺 model 字段")
    if "capabilities" in r and not isinstance(r["capabilities"], (list, tuple)):
        defects.append(f"capabilities={r['capabilities']!r} 不是数组")
    ints: dict[str, int] = {}
    for name, default in _ENTRY_INT_FIELDS:
        raw = r.get(name, default)
        try:
            ints[name] = int(raw)
        except (TypeError, ValueError):
            defects.append(f"{name}={raw!r} 不是整数")
            ints[name] = default if isinstance(default, int) else 0
    return key, ints, defects


class LLMRegistry:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._entries: dict[str, ModelEntry] = {}
        # R2-F3：被降级跳过的 entry（`"key: 原因"`），与 `_entries` 同批维护。
        # 0 条在册**不是**「一切正常」：计数走 `entry_count()`/`skipped_count()`，出口在 `/api/health`。
        self._skipped: list[str] = []
        self._admin_disabled: set[str] = set()  # 管理员禁用开关：只影响 pick 自动路由
        self._aclose_done = False  # 应用退出收尾一次性标记（aclose 幂等）
        self._load()

    def _skip_entry(self, r: Any, key: str, reason: str) -> None:
        """一条 entry 降级跳过（不致命）＋落一条**已登记**的归因读数，并计入 `skipped_count()`。

        W7-B1（可用性回退）修的是 transport 那**一个字段**：改前 `_load` 只 `except RuntimeError: continue`，
        而 `_build` 对未知 transport 抛的是 `ValueError`，且 `registry = LLMRegistry()` 跑在模块作用域 ⇒
        `LLM_MODELS_JSON` 里一个拼错的值让整只后端 import 就炸（判据：
        tests/test_llm_registry_boot_impl.py::test_import_time_bad_transport_value_does_not_kill_the_backend）。

        R2-F1（复核第二轮）把同一件事扩到**整段 entry 构造**：`int(timeout)`／`int(priority)`／
        `int(quota_total)`／`int(initial_used)`／`r["model"]`／`json.loads(LLM_MODELS_JSON)` 当时仍排在
        per-entry try 之外，同一类故障还在（复核判词：moved, not closed）。现在这些形状问题
        由 `_entry_shape()` 在构造**之前**验掉，验不过就走这里——跳过这一条，而不是带走整只服务。

        读数只带 entry key／原因（闭集词汇，不是凭据）／异常类名——不带任何 key 的值，
        也不带异常正文（W7-B9 同一口径：上游文本可能回显请求字节）。
        """
        self._skipped.append(f"{key}: {reason}")
        raw_model = r.get("model", "") if isinstance(r, dict) else ""
        # 非字符串的 model（例如 null）不落值本身，落它的**类型名**：读数要指得出是哪条，不该把
        # 配置内容原样抄进日志（与上面「不带凭据值」同一条纪律）。
        model_name = raw_model if isinstance(raw_model, str) else type(raw_model).__name__
        logging.getLogger("legal.llm").warning(
            f"llm_entry_skipped entry={key} reason={reason}",
            extra={"model": model_name, "llm_cfg_entry_rejected": [f"{key}: {reason}"]},
        )

    def entry_count(self) -> int:
        """在册（构造成功）的 entry 条数。R2-F3：0 条必须**被读得到**，不许等于「健康」。"""
        with self._lock:
            return len(self._entries)

    def skipped_count(self) -> int:
        """本次 `_load` 降级跳过的 entry 条数（`/api/health` 的 `llm_entry_rejected` 读它）。"""
        with self._lock:
            return len(self._skipped)

    def _load(self) -> None:
        with self._lock:
            self._entries = {}
            self._skipped = []
            for index, r in enumerate(_load_roles()):
                # R2-F1：entry 的**形状**先过一遍尺（key/model/整数字段/capabilities 数组）。
                # 位置在取凭据与构造 cfg 之前——改前这些取值语句本身就是启动期的雷。
                key, ints, defects = _entry_shape(r, index)
                if defects:
                    self._skip_entry(r, key, "；".join(defects))
                    continue
                # 票 W07 §1 ①：entry 输入面的 transport（缺省＝chat ⇒ 旧条目逐字不变）。
                # W7-B2：未知键检查作用在 entry 的**原始 dict** 上（`_build` 那只 cfg 白名单在真实
                # 配置路径上够不着，因为下面的 cfg 是用固定键名重建的），拼错的键在这里点名，
                # 而不是让它的值无声消失。msg 带 entry key ⇒ 运维知道去改哪一条。
                stray = _unknown_keys(r, ROLE_KEYS)
                if stray:
                    logging.getLogger("legal.llm").warning(
                        f"llm_role_unknown_keys entry={key}",
                        extra={"model": r.get("model", ""), "llm_cfg_unknown_keys": stray},
                    )
                transport = r.get("transport", DEFAULT_TRANSPORT)
                # W7-B1：transport 的值在这一层就验，验不过**只跳过这一条 entry**。
                # 位置在取凭据之前，顺带修掉复核说的顺序问题：缺 key 的 RuntimeError 检查原本排在
                # transport 校验之后，于是一个坏值连「本来会被跳过的未配置 provider」一起炸死。
                if transport not in TRANSPORTS:
                    self._skip_entry(r, key, f"未知 transport={transport!r}（可用 {list(TRANSPORTS)}）")
                    continue
                provider = r.get("provider", "aliyun")
                if provider == "zhipu":  # 智谱平台（8-23 到期免费 token）：独立 base_url/key
                    base_url = r.get("base_url") or settings.zhipu_base_url
                    api_key = r.get("api_key") or settings.zhipuai_api_key
                elif provider == "dashscope":  # 阿里云百炼：全模态角色（vision/voice）专用
                    base_url = r.get("base_url") or settings.dashscope_base_url
                    api_key = r.get("api_key") or settings.dashscope_api_key
                else:
                    base_url = r.get("base_url") or settings.llm_base_url
                    api_key = r.get("api_key") or settings.api_key
                cfg = {
                    "model": r["model"],
                    "base_url": base_url,
                    "api_key": api_key,
                    "capabilities": list(r.get("capabilities", ["text"])),
                    "disable_thinking": bool(r.get("disable_thinking", False)),
                    # R2-F1：整数已经由 `_entry_shape()` 取好（写不成整数的 entry 根本到不了这里）
                    "timeout": ints["timeout"],
                    "translation_options": r.get("translation_options"),
                    # F11：这里**不再**写 transport ⇒ 它的唯一存放处就是下一段 `ModelEntry.transport`
                    # （由 `_load` 派生一次，调用方经 `transport_of` 读）。往 cfg 再塞一份等于同一值存两处，
                    # 而 `_build` 那次读取在真实配置路径上永远只会读到默认值（判据：
                    # tests/test_multimodal_transport_impl.py::test_registry_entry_is_the_only_store_of_transport）。
                }
                e = ModelEntry(
                    key=key,
                    model=r["model"],
                    modality=r.get("modality", "text"),
                    tier=r.get("tier", "flag"),
                    priority=ints["priority"],
                    capabilities=set(cfg["capabilities"]),
                    cfg=cfg,
                    quota_total=ints["quota_total"],
                    initial_used=ints["initial_used"],
                    runtime_used=quota_store.get_used(key),
                    transport=transport,
                )
                # 校准覆盖（块 3）：管理员从控制台读数后用 /api/admin/llm-quota 校准，
                # 覆盖默认 initial_used——看门狗 remaining 与真实值对齐
                ov = quota_store.initial_override(key)
                if ov is not None:
                    e.initial_used = ov
                try:
                    e.llm = _build(cfg)
                except (RuntimeError, ValueError) as exc:
                    # 这条 except 现在**只**接两种类别，且两类的到达路径要说实话（R2-F2）：
                    # - `RuntimeError`＝该 provider 没配 key/base_url（2026-08-08 服务器部署修复：
                    #   用户只配了部分模型 key 时原先整个后端启动失败）；
                    # - `ValueError`＝`_build` 里 pydantic 对**取值**的校验失败（现量：`model` 键在但值为
                    #   null ⇒ ValidationError，它是 ValueError 的子类）。
                    # 注意 `_build` 开头那两处 `raise ValueError`（cfg 键白名单／transport 闭集）在真实
                    # 配置路径上**够不着**：下面的 cfg 是用固定键名重建的，transport 也已在上面验过并跳过，
                    # 所以那两处的读者是手搓 cfg 的调用点（`variant`／`reload`／测试），不是 `_load`。
                    # 两者都**只降级这一条 entry**，其余照常可用。
                    # 刻意不写 `except Exception`：结构性 bug（KeyError/TypeError 等）必须当场炸，
                    # 否则真故障会被配置降级通道一起吞掉（判据见 tests/test_llm_registry_boot_impl.py）。
                    self._skip_entry(r, key, type(exc).__name__)
                    continue
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
            return _build(cfg, share_llm=e.llm, share_cfg=e.cfg)

    def variant_of(self, key: str, disable_thinking: bool) -> ChatOpenAI:
        """按指定 entry 的 cfg 临时构建关/开思考实例（旗舰流式重试用）。"""
        with self._lock:
            e = self._entries.get(key) or self._default_entry()
            assert e is not None, "LLM 未初始化"
            cfg = dict(e.cfg)
            cfg["disable_thinking"] = disable_thinking
            return _build(cfg, share_llm=e.llm, share_cfg=e.cfg)

    def config(self) -> dict[str, Any]:
        with self._lock:
            e = self._default_entry()
            return {"model": e.model if e else "", "capabilities": sorted(e.capabilities) if e else []}

    def has_modality(self, modality: str) -> bool:
        """该模态是否注册了已构建实例的模型（Capability Gate：无则上游必须显式 501，
        禁止借 _safe_pick 静默回退文本模型——2026-09-05 阶段B：LongCat 无视觉/语音能力，
        实测其会静默忽略图片内容块）。"""
        with self._lock:
            return any(e.modality == modality and e.llm is not None for e in self._entries.values())

    def reload(self, model: str | None = None) -> dict[str, Any]:
        """兼容：仅重建默认 entry（旧单模型热切换语义）。多模型整体重载用 _load。

        仅改 model（传输参数不变）→ 新实例复用原 entry 的 SDK 根客户端，
        旧连接池不再被丢弃成孤儿。
        """
        with self._lock:
            e = self._entries.get(DEFAULT_KEY)
            if e and model:
                previous = e.llm
                e.cfg["model"] = model
                e.model = model
                e.llm = _build(e.cfg, share_llm=previous, share_cfg=e.cfg)
            return self.config()

    # ---------- 应用退出收尾 ----------
    async def aclose(self) -> None:
        """关闭 registry 实际拥有的 SDK 根客户端（同步+异步），由 main.lifespan 在
        事件循环仍运行时调用。

        - 幂等：重复调用不再重复关闭（一次性标记）。
        - 锁只保护快照与标记，不跨 await 持有。
        - 失败隔离：单个根关闭失败记录"资源类别:模型key + 异常类型"（不含
          URL/凭据/异常消息），继续尝试其余，最终显式 raise 供上层判定门禁失败。
        - 覆盖范围：当前 entries 可达的唯一根（variant/reload 复用同一对根）。
        """
        with self._lock:
            if self._aclose_done:
                return
            self._aclose_done = True
            roots: dict[int, tuple[str, Any]] = {}
            for e in self._entries.values():
                llm = e.llm
                if llm is None:
                    continue
                for attr, kind in (("client", "sync"), ("async_client", "async")):
                    root = getattr(getattr(llm, attr, None), "_client", None)
                    if root is not None and id(root) not in roots:
                        roots[id(root)] = (f"{kind}:{e.key}", root)
        failures: list[dict[str, str]] = []
        for label, root in roots.values():
            try:
                outcome = root.close()
                if inspect.isawaitable(outcome):
                    await outcome
            except Exception as error:  # noqa: BLE001 - 失败隔离后统一显式上抛
                failures.append({"resource": label, "error_type": type(error).__name__})
        if failures:
            raise RuntimeError("LLMRegistry.aclose 存在未关闭的 SDK 资源: " + json.dumps(failures, ensure_ascii=False))

    # ---------- 路由接口（主回答用） ----------
    def pick_by_key(self, key: str) -> ChatOpenAI:
        """按 key 取指定模型实例（judge 等指定模型场景——如智谱免费量做专业度评分）。

        unavailable（耗尽/低于阈值）→ KeyError，调用方回落默认。
        """
        with self._lock:
            e = self._entries.get(key)
            if e is None or e.llm is None or e.unavailable:
                raise KeyError(f"模型不可用: {key}")
            return e.llm

    def pick(self, modality: str, tier: str, *, exclude: set[str] | None = None) -> tuple[str, ChatOpenAI]:
        """按 (modality, tier) 选模型：从请求 tier 沿回退链找首个可用；全不可用抛 QuotaExhausted。

        exclude（2026-09-14，失败即换模型）：排除**本次调用中已尝试过**的 key。
        动机：瞬时故障（429/5xx/连接抖动）**不标记 `unavailable`**（模型其实还可用，
        见 `llm_errors.is_transient_error`），故不能靠 `unavailable` 推进到下一个模型 ——
        改由调用方把已试过的 key 放进 `exclude`，既换到下一个模型、又不会回头重试同一 key
        （也正因此，循环以「已尝试集合」而非「是否成功」为终止条件，构造上必然终止）。
        缺省 None 时行为与历史逐字一致。
        """
        with self._lock:
            chain = TIER_CHAIN.get(modality, ["flag"])
            try:
                start = chain.index(tier)
            except ValueError:
                start = 0
            skipped = exclude or set()
            for t in chain[start:]:
                candidates = [e for e in self._entries.values() if e.modality == modality and e.tier == t]
                # 同档按能力优先级（priority 升序）选，配额只判可用；同优先级再比剩余配额
                candidates.sort(key=lambda e: (e.priority, -e.quota_left))
                for e in candidates:
                    if e.key in skipped:
                        continue
                    if e.rejected_now:
                        continue  # DB-17：4xx 冷却期内退出自动路由，过期自愈（不动配额账）
                    if not e.unavailable and e.key not in self._admin_disabled:
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

    def is_rejected(self, key: str) -> bool:
        """该 key 是否处于 4xx **冷却**中（DB-17，2026-10-09 复核轮 B 路补）。

        为什么单独要这个口子：`_safe_pick` 在 `QuotaExhausted` 时直接回落 `registry.get()`，
        那条路**绕过了 `pick` 的冷却过滤**。若只看配额（`is_unavailable`），"整池都在冷却"
        会被读成"默认模型健康"，于是每个请求都再烧一次刚被打回的调用、还不标降级——
        冷却就只剩"少选它"没有"别打它"。语义与 `unavailable` 严格分开：这里不涉配额。
        """
        with self._lock:
            e = self._entries.get(key)
            return bool(e and e.rejected_now)

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

    def transport_of(self, key: str | None) -> str:
        """key → 该 entry 的 transport（票 W07 §1 ③：调用方读的就是 entry 上那一位，不另存）。

        为什么走访问器而不是改 `pick()` 的返回形状：`pick` 的 `(key, llm)` 元组被十几处调用点
        与既有判据钉着，本票明令不改。未知/None key 回落 `DEFAULT_TRANSPORT`＝chat，
        语义是「不知道该用哪种传输时，走旧的那条」——回落不改变任何既有行为。
        """
        with self._lock:
            e = self._entries.get(key) if key else None
            return e.transport if e else DEFAULT_TRANSPORT

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
        # DB-17：`reason` 参数此前**被整个丢弃**（连日志都不落）。保留原有幂等早退语义
        # （已 depleted 不重复记账、不重复落日志），只在真正置尽的那一次落一条。
        logging.getLogger("legal.llm").warning(
            "llm_model_depleted",
            extra={"model": self.model_of(key), "model_failure_channel": "exhausted", "model_failure_reason": reason},
        )

    def mark_rejected(self, key: str, reason: str, *, status: int | None = None) -> None:
        """请求形状类 4xx ⇒ **短期冷却**，不改任何配额数字（DB-17 / 报告 B-48）。

        与 `mark_depleted` 的分工：耗尽→配额账 + 直到重启或人工校准；拒绝→只进冷却 + 自动到期。
        `reason`/`status` 进结构化日志（`model_failure_channel` 等字段已登记白名单），
        因为"被拒"与"没钱"在管理台上必须一眼分得开——这是本票的全部动机。
        """
        with self._lock:
            e = self._entries.get(key)
            if not e:
                return
            cooldown = reject_cooldown_s(status)
            e.rejected_kind = reject_kind(status)
            e.rejected_until = time.monotonic() + cooldown
        logging.getLogger("legal.llm").warning(
            "llm_request_rejected",
            extra={
                "model": self.model_of(key),
                "model_failure_channel": "rejected",
                "model_failure_reason": reason,
                "llm_error_status_code": status,
                "llm_reject_cooldown_s": cooldown,
                "llm_reject_kind": e.rejected_kind,
            },
        )

    def calibrate(self, key: str, remaining: int) -> dict[str, Any]:
        """配额校准（块 3）：按控制台真实剩余值写入**完整基线**，看门狗对齐真实值。

        quota_left = quota_total - initial_used - runtime_used；设 remaining=R ⇒ 把 baseline
        整体重置为 `runtime_used = 0`、`initial_used = max(0, total - R)`——**内存与持久两侧
        同时写**（runtime 归零也落库），否则二者分叉。

        R19：改前只改 initial_used（`max(0, total - R - runtime_used)`）而保留 runtime_used。
        一旦 runtime_used 已被 `mark_depleted` 记满（runtime_used = total），无论 R 取何值都算出
        initial_used = 0 ⇒ **校准对"已耗尽"的模型完全无效**（quota_left 仍 0）；且内存里的
        runtime_used 本就不落库 ⇒ 重启后 initial_used 已生效、内存侧不然 —— 内存与持久不一致。
        """
        with self._lock:
            e = self._entries.get(key)
            if not e:
                raise KeyError(f"未知模型 key: {key}")
            e.runtime_used = 0
            e.initial_used = max(0, e.quota_total - int(remaining))
        # 两侧一起写：runtime 归零 + initial 覆盖（两行不同 key，互不覆盖，顺序无关）。
        quota_store.set_used(key, 0)
        quota_store.set_initial(key, e.initial_used)
        return {"key": key, "model": e.model, "quota_left": e.quota_left, "initial_used": e.initial_used}

    def set_disabled(self, key: str, disabled: bool) -> None:
        """管理员开关（2026-09-15）：禁用/启用某模型参与**自动路由**（pick）。

        与配额 `unavailable` 语义独立：禁用只影响自动路由，不影响 `pick_by_key`
        （judge 等显式指定场景）。运行时生效，重启后回落 .env 配置。
        """
        with self._lock:
            if key not in self._entries:
                raise KeyError(f"未知模型 key: {key}")
            if disabled:
                self._admin_disabled.add(key)
            else:
                self._admin_disabled.discard(key)

    def promote(self, key: str) -> int:
        """管理员开关（2026-09-15）：把某模型提为所在 (modality, tier) 链首。

        实现为其 priority 置为同链其他模型的最小值 -1（确定性：重复 promote 同一
        key 无变化）。运行时生效，重启后回落 .env 配置。返回新 priority。
        """
        with self._lock:
            e = self._entries.get(key)
            if e is None or e.llm is None:
                raise KeyError(f"未知模型 key: {key}")
            peers = [
                x.priority
                for x in self._entries.values()
                if x.modality == e.modality and x.tier == e.tier and x.key != key
            ]
            e.priority = (min(peers) - 1) if peers else 0
            return e.priority

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
                    # DB-17：冷却是**另一个通道**，管理台要看得见，否则会把它误读成配额耗尽
                    "rejected_remaining_s": round(max(0.0, e.rejected_until - time.monotonic()), 1),
                    "rejected_kind": e.rejected_kind if e.rejected_now else None,
                    "below_threshold": e.below_threshold,
                    "admin_disabled": e.key in self._admin_disabled,
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
