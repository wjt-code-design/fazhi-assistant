"""瞬时故障 vs 永久失败的统一判定（2026-09-14）。

背景（两个独立实证，同一缺陷类）：
- **rerank**（`retrieval._rerank_docs`）：SiliconFlow 免费但**会限速**；原实现把 429/5xx/连接抖动
  一律按"模型坏了"永久标记 → 实测一次偶发失败导致同进程内**后续 35 次全部静默降级**。
  修复见 `docs/project-quality-guide-20260914.md` §10（1k），门禁：全量 983 绿 + 自愈注入 PASS。
- **LLM 主链路**：同一分类被 `agent/runtime.py` 的失败换模型与 `rag_chain.stream_with_retry` 复用。

设计约束：本模块**必须零重依赖**，尤其**不得 import `llm_registry`**
—— `retrieval.py` 头部明确"不 import llm_registry（其模块级初始化需 LLM key）"。
"""

from __future__ import annotations

import httpx

# 瞬时类 HTTP 状态：限速(429) / 请求超时(408) / 服务端临时不可用(5xx 常见子集)。
# 其余 4xx（400 模型名或参数错、401/403 鉴权、404 端点点错）属**永久失败**，应标记降级。
TRANSIENT_STATUS = frozenset({408, 429, 500, 502, 503, 504})


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


def is_transient_error(exc: BaseException) -> bool:
    """瞬时故障 → True（**不应**标记模型永久耗尽）；否则 False（按真实失败处理）。

    判定顺序：
    1. `httpx.TransportError`（连接/读写/协议抖动）→ 瞬时。
       注意其子类 `httpx.TimeoutException` 亦为瞬时，与本模块口径一致；
       调用方若对超时有**额外**语义（如"降级但不再换模型"），需在调用点自行先判超时。
    2. 状态码命中 `TRANSIENT_STATUS` → 瞬时。
    3. 其余（含无状态码的本地异常）→ 非瞬时（保守：按真实失败处理）。
    """
    if isinstance(exc, httpx.TransportError):
        return True
    return status_of(exc) in TRANSIENT_STATUS
