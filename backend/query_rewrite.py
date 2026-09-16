"""LLM 查询改写（1d 第三候选，2026-09-15；验证链见 dispatch-output/quality-1d-20260914）。

⚠️ 状态：**真实路径口径已否证**（离线并集救回 5/16，真实口径 2~3/16 < DoD 4；聚焦词并入
实验 aug 臂 3/16 亦不达标，2026-09-15 §10）→ `query_rewrite_enabled` 长期保持默认关。
实现与契约测试保留为「已验证否证的分支」（同 `retrieval_pool_k` 先例），供后续换打分方案时复用。

背景（机制诊断，`recall_generation_diag.py`）：16 条硬缺口对真实争点问句的
bigram-Jaccard 仅 0.0086（比问句到其实际召回 top-1 的 0.0322 还低）；两路 @40 命中
向量 3/78、BM25 0/78；而条文自身正文自检索两路 78/78 rank-1 ⇒ 索引健全、**缺口在 query 侧**。
本模块把"事实语言"的争点问句映射为"法条语言"的检索句（概念/制度词，如「定金罚则」
「格式条款排除消费者主要权利无效」），由 `retrieval.hybrid_retrieve` 作为**附加 slice 单元**
送入候选池（不吃锚点保底位、`docs[:k]` 返回条数不变）。

失败语义（全部 **fail-open**，静默回落原问句路径——改写是纯增强，绝不拖垮检索）：
- 无可用模型 / 调用异常 / 超时 / JSON 坏 / 空结果 → 返回 `()`；
- 单次调用硬超时：`settings.query_rewrite_timeout_s`（默认 6s）；调用方带剩余预算时取更小值
  （`timeout_s_override`），超时经线程池 future 强制生效——registry 的 ChatOpenAI 构建期
  timeout=120s + SDK 内 3 次重试，**不可**依赖其自身超时兜热路径（实测该版本无 with_options）。
- 结果按问句 LRU 缓存（含负缓存，防对坏模型每请求重复烧）；检索自身也缓存，正常热路径
  每问句只付一次改写费。
- llm_registry **懒加载**（retrieval.py 头部有"不 import llm_registry"的模块级约束；
  本模块顶层同样不 import，仅在真实发起调用时取）。

可观测：仅记错误类名与计数（`query_rewrite_failed kind=...`），**不记录问句文本/改写内容**，
不新增日志白名单字段。
"""

from __future__ import annotations

import json
import logging
import re
import threading
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor

from settings import settings

logger = logging.getLogger("legal.query_rewrite")

# 与离线验证（llm_rewrite_probe.py，prompt_version=rewrite-v1）同一系统提示的**单问句版**。
# 离线冻结词表是"每案例一次批量"，生产是"每问句一次"；机制一致性以真实路径重测为准。
_SYSTEM = (
    "你是法律检索查询改写器。用户给出一个案件争点问句（事实性表述）。"
    "请把它改写成 2~3 条「法条语言」的检索查询句，用于在法条全文库中召回应当适用的条文。\n"
    "要求：\n"
    "1) 检索句用法律术语表述争点对应的法律概念/制度，"
    "示例仅演示「事实语言→法条概念」的转换方式，与争点内容无关，**不要套用示例词**"
    "（示例用无关物权制度：用益物权设立登记、地役权从属性、居住权不得转让、动产抵押对抗效力……）；\n"
    "2) 不要复述案情事实，不要写寒暄或解释；每条检索句 ≤ 30 字；\n"
    '3) 严格输出 JSON：{"queries":["检索句1","检索句2"]}。'
)
# ⚠️ 示例词纪律（2026-09-15 审查 R1，§10 勘误）：示例词必须与评测集金标条文**概念域正交**。
# rewrite-v1 曾用「违约责任/定金罚则/格式条款/欺诈可撤销/加班时限/工资支付义务」作示例
# = 直接泄漏缺口答案概念（17/105 改写句含示例词；真实口径救回对几乎全由示例词句达成）。
# v2 示例改用本案完全不涉的物权制度（用益物权/地役权/居住权/动产抵押——金标 39 条零字面重合）：
# 即便模型套用也只向池里塞无关物权条（污染=拉低召回，方向保守，绝不虚高缺口救回）。
# 泄漏只会高估救回，不改写路线"<4 证伪"的终判（真值只会更低），但任何数字须按 v2 重测。
_MAX_SENT_LEN = 80  # 兜底截断（提示已要求 ≤30 字，防跑偏长句稀释池）
_CACHE_CAP = 2048

_JSON_RE = re.compile(r"\{.*\}", re.S)


class RewriteCache:
    """问句 → 改写句元组 的线程安全 LRU（含负缓存）。"""

    def __init__(self, cap: int = _CACHE_CAP) -> None:
        self._cap = cap
        self._data: OrderedDict[str, tuple[str, ...]] = OrderedDict()
        self._lock = threading.Lock()

    def get(self, key: str) -> tuple[str, ...] | None:
        with self._lock:
            if key not in self._data:
                return None
            self._data.move_to_end(key)
            return self._data[key]

    def put(self, key: str, value: tuple[str, ...]) -> None:
        with self._lock:
            self._data[key] = value
            self._data.move_to_end(key)
            while len(self._data) > self._cap:
                self._data.popitem(last=False)

    def clear(self) -> None:
        with self._lock:
            self._data.clear()


_cache = RewriteCache()
_pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix="qrewriter")


def parse_rewrite_response(text: str) -> tuple[str, ...]:
    """从模型输出提取 `{"queries":[...]}`；任何不符合 → ()（fail-open 的统一入口）。"""
    m = _JSON_RE.search(text or "")
    if not m:
        return ()
    try:
        data = json.loads(m.group(0))
    except Exception:  # noqa: BLE001
        return ()
    raw = data.get("queries") if isinstance(data, dict) else None
    if not isinstance(raw, list):
        return ()
    out: list[str] = []
    seen: set[str] = set()
    for x in raw:
        s = re.sub(r"\s+", " ", str(x)).strip()
        if not s or len(s) > _MAX_SENT_LEN or s in seen:
            continue
        seen.add(s)
        out.append(s)
    return tuple(out[: settings.query_rewrite_max_units])


def _invoke_llm(user_prompt: str, timeout_s: float) -> tuple[tuple[str, ...], int]:
    """真实调用路径（懒加载 registry）。返回 (改写句, 消耗 token)。异常原样上抛由调用方吞。

    token 记账（2026-09-15 审查 R2）：该兼容端点实测**不返回 usage_metadata**（49 次全 0）——
    tokens=0 时按项目既有约定 `quota_utils.estimate_tokens`（约 1.5 字/token）估算兜底
    （同 main.py 语音转写的同步 deduct 先例），保证未来开启后配额闸门对改写可见。
    超时经线程池 future 强制生效，但挂起的底层 HTTP 不会真死：最坏 4 个 worker 被占、
    后续改写排队即超时 → fail-open 返回 ()（自愈降级，无正确性风险）。
    """
    from llm_registry import registry
    from quota_utils import estimate_tokens

    key, llm = registry.pick("text", "flag")
    fut = _pool.submit(
        llm.invoke,
        [{"role": "system", "content": _SYSTEM}, {"role": "user", "content": user_prompt}],
    )
    resp = fut.result(timeout=timeout_s)  # 硬超时：超时抛 CancelledError/futures TimeoutError
    um = getattr(resp, "usage_metadata", None) or {}
    try:
        tokens = int(um.get("total_tokens") or 0)
    except (TypeError, ValueError):
        tokens = 0
    parsed = parse_rewrite_response(str(getattr(resp, "content", "") or ""))
    if tokens <= 0:
        tokens = estimate_tokens(user_prompt + str(getattr(resp, "content", "") or ""))
    registry.deduct(key, tokens)
    return parsed, tokens


def expand_queries(query: str, *, timeout_s_override: float | None = None) -> tuple[str, ...]:
    """问句 → 至多 `query_rewrite_max_units` 条法条语言检索句；失败/超时 → ()。

    `timeout_s_override`：调用方剩余预算（秒）较小时以更紧的超时生效；None → 用配置默认。
    预算 < 1s 直接放弃（省得调用作废）。
    """
    q = (query or "").strip()
    if len(q) < 5:  # 过短问句无改写价值
        return ()
    budget = settings.query_rewrite_timeout_s if timeout_s_override is None else float(timeout_s_override)
    if budget < 1.0:
        return ()
    hit = _cache.get(q)
    if hit is not None:
        return hit
    try:
        out, _ = _invoke_llm(f"争点问句：{q}", timeout_s=budget)
    except Exception as exc:  # noqa: BLE001 任何失败 → 负缓存 + 回落（不记问句内容）
        logger.warning("query_rewrite_failed kind=%s", type(exc).__name__)
        out = ()
    _cache.put(q, out)
    return out


def reset_cache() -> None:
    """测试/热重载用：清空改写缓存。"""
    _cache.clear()


__all__ = ["expand_queries", "parse_rewrite_response", "reset_cache"]
