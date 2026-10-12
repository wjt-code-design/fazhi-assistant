"""Auth/reachability probe for the frozen LLM routes. Two minimal calls, no product path.

Registered as spend OUTSIDE the F2 case table (it decides whether the table is runnable
at all). Prints status code, token usage and elapsed only - no body, no key.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import p3_env  # noqa: E402
import p3_transport_guard as tg  # noqa: E402

CFG = json.loads((HERE / "p3_models_frozen.json").read_text(encoding="utf-8"))
PROBES = [
    ("llm_default", CFG["llm"]["base_url"] + "/chat/completions", CFG["llm"]["model"], "LLM_API_KEY"),
    ("dashscope_first", CFG["dashscope"]["base_url"] + "/chat/completions", CFG["registry"][0]["model"], "DASHSCOPE_API_KEY"),
]


def main() -> int:
    env = p3_env.bind_private_root(p3_env.read_env())
    os.environ.update({k: v for k, v in env.items() if not k.endswith("_URL") or k in ("LLM_BASE_URL",)})
    guard = tg.TransportGuard(allowed=dict(p3_env.MODEL_HOSTS), max_calls=4)
    tg.install(guard)
    out = []
    for name, url, model, keyname in PROBES:
        key = os.environ.get(keyname) or env.get(keyname) or ""
        body = {"model": model, "messages": [{"role": "user", "content": "只回一个字：好"}], "max_tokens": 8, "stream": False}
        t0 = time.monotonic()
        rec = {"probe": name, "model": model, "host": url.split("/")[2], "key_len": len(key)}
        try:
            r = guard.post(url, json=body, headers={"Authorization": "Bearer " + key}, timeout=60.0)
            rec["status"] = r.status_code
            rec["elapsed_s"] = round(time.monotonic() - t0, 2)
            data = r.json() if r.content else {}
            usage = data.get("usage") or {}
            rec["usage_keys"] = sorted(usage)
            rec["prompt_tokens"] = usage.get("prompt_tokens")
            rec["completion_tokens"] = usage.get("completion_tokens")
            rec["has_choices"] = bool(data.get("choices"))
            if r.status_code >= 400:
                err = data.get("error") if isinstance(data.get("error"), dict) else {}
                rec["error_code"] = str(err.get("code") or err.get("type") or data.get("code") or data.get("message") or "")[:60]
        except Exception as exc:
            rec["exception"] = type(exc).__name__
            rec["elapsed_s"] = round(time.monotonic() - t0, 2)
        out.append(rec)
        print(json.dumps(rec, ensure_ascii=False, sort_keys=True))
    tg.uninstall()
    print("guard_calls:", len(guard.calls), "paths:", sorted(c.split("/")[2] + "/" + "/".join(c.split("/")[3:]) for c in guard.calls))
    (HERE / "logs" / "probe-llm.json").write_text(json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
