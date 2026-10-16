"""W10 / D-45 / C08：把「只支持已测闭包」变成**机器判据**，而不是一句注释。

Owner 2026-10-17 裁 C08＝**固定闭包**（plan:204 推荐原文：「精确可复现闭包与诚实支持边界；
兼容性未证不称全窗支持」）。所以本票不许做两件事：不许写「其他合规版本也支持」这种注释当契约
（plan:408 明令），也不许用 `try/except ImportError` 或 `skip` 把私有 SDK 面失效遮过去。

三条判据，每条都能红：

1. `test_windowed_requirements_are_exact_pins`——碰过私有 SDK 面的包必须 `==` 精确 pin。
   今天它们是 `>=x,<y` 这种**窗**，而窗内只有装的那一版被跑过 ⇒ 这条现在就是红的，
   红得很诚实：声明面比验证面宽，正是 D-45 的原话。
2. `test_installed_matches_the_declared_closure`——`requirements.txt` 的 pin 必须等于**当前解释器**
   实际安装版本。CI 装到别的版本时这里红，而不是等到某个私有函数不见了才红。
3. `test_private_sdk_symbols_are_reachable_and_not_guarded`——本仓依赖 `langchain_openai` 的两个
   **私有**函数（`_client_utils._cached_sync_httpx_client` / `_cached_async_httpx_client`）。
   这里直接导入并断言可调用；**不套 try/except**：版本换了就该收集期炸，而不是静默 skip。
   另钉一条源码事实：`test_llm_lifecycle.py` 里那段私有 import 不许被包进异常处理。
"""

from __future__ import annotations

import importlib
import importlib.metadata
import re
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
REQ = BACKEND / "requirements.txt"

# 只列**私有面相关**的包：这几家的次版本改动打过我们的脸（D-45 的成因就是 langchain-openai
# 从 0.1.7 换到 1.7.0 时私有工具面变了；sentence-transformers/chromadb 同理影响嵌入与向量面）。
CLOSURE_PACKAGES = (
    "langchain-openai",
    "langchain-core",
    "langchain-chroma",
    "chromadb",
    "sentence-transformers",
)

_PIN_RE = re.compile(rf"^(?P<name>{'|'.join(re.escape(p) for p in CLOSURE_PACKAGES)})\s*(?P<spec>.+)$")


def _declared() -> dict[str, str]:
    out: dict[str, str] = {}
    for line in REQ.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        m = _PIN_RE.match(line)
        if m:
            out[m.group("name").lower()] = m.group("spec").strip()
    return out


def test_windowed_requirements_are_exact_pins():
    """C08 的字面效果：闭包内的包一律 `==`，不再声明未验证的窗。"""
    declared = _declared()
    assert declared, "requirements.txt 里找不到被追踪的包——追踪名单和文件脱节了，这条判据已失效"
    windowed = {k: v for k, v in declared.items() if not v.startswith("==")}
    assert not windowed, (
        f"这些包仍声明为窗而非已测闭包：{windowed}；C08 已裁「固定闭包」⇒ 未验证的版本区间不得写成支持面"
    )


def test_installed_matches_the_declared_closure():
    """声明等于装机：CI/本机装歪一版就该在这里红。

    第一版这里直接 `spec.split("==", 1)[1]`，在窗声明（`>=0.4,<0.5`）上抛 `IndexError`——
    **崩掉的判据不叫判据**，读的人看不到"哪里不一致"。改成先收集精确 pin，
    缺 pin 的包点名报出来（它同时也是第 1 条要修的东西），有 pin 的才比装机版本。
    """
    declared = _declared()
    exact = {k: v.split("==", 1)[1].strip() for k, v in declared.items() if v.startswith("==")}
    unpinned = sorted(set(declared) - set(exact))
    assert not unpinned, f"这些包还是窗声明、无从核对装机版本：{unpinned}（C08 要求先固定闭包）"

    bad = {}
    for name, want in exact.items():
        try:
            got = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            got = "MISSING"
        if got != want:
            bad[name] = {"declared": want, "installed": got}
    assert not bad, f"当前解释器与在册闭包不一致：{bad}"


def test_private_sdk_symbols_are_reachable_and_not_guarded():
    """私有面失效要**硬显现**：直接导入、直接断言，不 catch、不 skip。"""
    mod = importlib.import_module("langchain_openai.chat_models._client_utils")
    for attr in ("_cached_sync_httpx_client", "_cached_async_httpx_client"):
        assert callable(getattr(mod, attr)), f"私有 SDK 符号 {attr} 不在或不可调用 ⇒ 依赖闭包变了"

    src = (BACKEND / "tests" / "test_llm_lifecycle.py").read_text(encoding="utf-8")
    # 钉"没被包进异常处理"：这段私有 import 一旦被 try/except 兜住，版本漂移就会变成静默 skip
    head = src.split("import pytest", 1)[-1][:400]
    assert "try:" not in head, "私有 import 被包进了 try ⇒ D-45 要求的『硬显现』被破坏"
