"""qwen3.8-flash 冒烟测试：确认默认模型已切换 + 真实可调用（1 次低成本外呼）。

为什么必须先做：`.env` 里 LLM_MODELS_JSON 换成百炼 qwen3.8-flash 后，若模型 id
不被账号支持，run-13 的 10 题会全部失败在第一步、白烧预算。
本脚本按生产导入顺序（import main → dotenv 先于 registry 生效）读取配置，
打印 registry 实际解析到的 key/model，并发一次最小请求。

注意：不设 NO_PROXY（百炼是外部服务，必须走沙箱代理）。
"""

from __future__ import annotations

import os
import pathlib
import sys
import time

HERE = pathlib.Path(__file__).resolve()
BACKEND = HERE.parents[2] / "backend"
sys.path.insert(0, str(BACKEND))
os.chdir(BACKEND)

import main  # noqa: E402
from llm_registry import registry  # noqa: E402

print("entries:", sorted(registry._entries.keys()), flush=True)
print("default_key:", registry.default_key(), flush=True)
try:
    print("registry.config():", registry.config(), flush=True)
except Exception as exc:  # noqa: BLE001
    print("registry.config() 不可用:", exc, flush=True)

entry = registry._entries.get(registry.default_key())
if entry is not None:
    print("resolved model:", entry.model, "| provider cfg base_url:", entry.cfg.get("base_url"), flush=True)
    print("disable_thinking:", entry.cfg.get("disable_thinking"), flush=True)

llm = registry.get()
t0 = time.perf_counter()
try:
    resp = llm.invoke("只回复两个字：就绪")
except Exception as exc:  # noqa: BLE001
    print(f"SMOKE_FAIL {type(exc).__name__}: {exc}"[:900], flush=True)
    raise SystemExit(1)
elapsed = round(time.perf_counter() - t0, 1)
print(f"SMOKE_OK elapsed={elapsed}s content={getattr(resp, 'content', None)!r}"[:600], flush=True)
