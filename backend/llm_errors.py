"""瞬时故障 vs 永久失败的统一判定（2026-09-14；2026-09-17 增补 SDK 包装形态）。

背景（三个独立实证，同一缺陷类）：
- **rerank**（`retrieval._rerank_docs`）：SiliconFlow 免费但**会限速**；原实现把 429/5xx/连接抖动
  一律按"模型坏了"永久标记 → 实测一次偶发失败导致同进程内**后续 35 次全部静默降级**。
  修复见 `docs/project-quality-guide-20260914.md` §10（1k），门禁：全量 983 绿 + 自愈注入 PASS。
- **LLM 主链路**：同一分类被 `agent/runtime.py` 的失败换模型与 `rag_chain.stream_with_retry` 复用。
- **SDK 包装形态漏判（2026-09-17 online 批次实证）**：openai 系 SDK 把底层 httpx 连接/超时错误
  **包装**为 `APIConnectionError` / `APITimeoutError`（其 `__cause__` 才是 httpx.TransportError）；
  原实现只判 `isinstance(exc, httpx.TransportError)` → 包装异常被判"永久" → failover 把
  **全部模型 mark_depleted** → 一次网络抖动触发连锁 `QuotaExhausted`（实证：6 模型全标死，
  后续案例集体 PLANNER_PARSE_ERROR）。修复=**类名 + 异常链上溯**双重判定（不 import openai）。
  **留痕**：证据 `dispatch-output/r1ob-online-20260917/serve.log`（permanent×6 连锁）+
  `planner-parse-error-diagnosis.md`（根因报告）+ `r1ob-prodform-20260917/watch-it-fail-llmerr.txt`
  （回滚→2 红→恢复 41 绿）。

设计约束：本模块**必须零重依赖**，尤其**不得 import `llm_registry`**
—— `retrieval.py` 头部明确"不 import llm_registry（其模块级初始化需 LLM key）"。
"""

from __future__ import annotations

import httpx

# 瞬时类 HTTP 状态：限速(429) / 请求超时(408) / 服务端临时不可用(5xx 常见子集)。
# 其余 4xx（400 模型名或参数错、401/403 鉴权、404 端点点错）属**永久失败**，应标记降级。
TRANSIENT_STATUS = frozenset({408, 429, 500, 502, 503, 504})

# 传输/网络类异常**类名**（跨 SDK 通用，不 import 各 SDK）：
# - openai 系（含兼容端点）：APIConnectionError / APITimeoutError；
# - httpx 系：ConnectError / TimeoutException / ReadTimeout / RemoteProtocolError 等；
# - 通用网络栈（requests/urllib3 形态——本仓当前未引入，**前瞻预留**；如出现同名非网络异常
#   存在误判风险，属保守方向可接受）。
# ⚠️ 只列"网络与超时"——**不含** APIStatusError 等状态类（状态走 status_of 判定）；
#   判定顺序说明（code-review 2026-09-17 澄清）：`_is_transport_like` 先于 `status_of`——
#   若某 SDK 把带 5xx 的错误包装成传输类异常，将按"传输类"判瞬时（failover 换模型不标记），
#   这是**有意的保守方向**：连接层抖动优先于状态语义处理，最坏多试一次下一模型（不放大伤害）。
_TRANSPORT_EXC_NAMES = frozenset(
    {
        "APIConnectionError",
        "APITimeoutError",
        "ConnectError",
        "ConnectTimeout",
        "ReadError",
        "ReadTimeout",
        "WriteError",
        "WriteTimeout",
        "PoolTimeout",
        "RemoteProtocolError",
        "TimeoutException",
        "TransportError",
        "NetworkError",
    }
)
_MAX_CAUSE_DEPTH = 6  # 异常链上溯上限（有界；超出即按当前判定终止）


def status_of(exc: BaseException) -> int | None:
    """尽力取出异常携带的 HTTP 状态码（覆盖多 SDK 形态）。

    - `openai.APIStatusError` / 多数 SDK：状态码直接在 `.status_code`；
    - `httpx.HTTPStatusError`：在 `.response.status_code`；
    - 取不到（本地异常、解析错、超时）→ None。
    """
    status = getattr(exc, "status_code", None)
    if status is None:
        status = getattr(getattr(exc, "response", None), "status_code", None)
    return status if isinstance(status, int) else None


def _is_transport_like(exc: BaseException) -> bool:
    """网络/超时类异常判定：类名匹配或异常链上溯命中（均不依赖 import 各 SDK）。

    终止性：链上溯步数上限 `_MAX_CAUSE_DEPTH`（异常链环状引用时必然终止）。
    """
    current: BaseException | None = exc
    for _ in range(_MAX_CAUSE_DEPTH):
        if current is None:
            return False
        if isinstance(current, httpx.TransportError):
            return True
        if type(current).__name__ in _TRANSPORT_EXC_NAMES:
            return True
        current = current.__cause__ or current.__context__
    return False


def is_transient_error(exc: BaseException) -> bool:
    """瞬时故障 → True（**不应**标记模型永久耗尽）；否则 False（按真实失败处理）。

    判定顺序：
    1. 网络/超时类（`_is_transport_like`：httpx.TransportError 本体，或 openai 系
       APIConnectionError/APITimeoutError 等**包装形态**——含异常链上溯）→ 瞬时。
    2. 状态码命中 `TRANSIENT_STATUS` → 瞬时。
    3. 其余（含无状态码的本地异常）→ 非瞬时（保守：按真实失败处理）。
    """
    if _is_transport_like(exc):
        return True
    return status_of(exc) in TRANSIENT_STATUS
