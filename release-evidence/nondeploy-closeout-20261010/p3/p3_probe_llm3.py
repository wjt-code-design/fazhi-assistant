"""Is there any live route in the current config at all?

Part 1 reads LLM_MODELS_JSON and prints only structure (provider/model/host/key-presence).
Part 2 spends ONE call on a model the account actually serves, to separate
"account dead" from "frozen model id not on this account".
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from urllib.parse import urlparse

import httpx

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import p3_env  # noqa: E402
import p3_transport_guard as tg  # noqa: E402

CFG = json.loads((HERE / "p3_models_frozen.json").read_text(encoding="utf-8"))
BASE = CFG["llm"]["base_url"]


def shape(raw: str) -> list[dict]:
    data = json.loads(raw)
    rows = data if isinstance(data, list) else data.get("models") or []
    out = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        url = r.get("base_url") or r.get("api_base") or ""
        out.append({"key": r.get("key"), "provider": r.get("provider"), "model": r.get("model"),
                    "host": urlparse(url).netloc if url else "", "caps": r.get("caps") or r.get("capabilities"),
                    "has_key_field": bool(r.get("api_key")), "default": r.get("is_default") or r.get("default")})
    return out


def main() -> int:
    env = p3_env.bind_private_root(p3_env.read_env())
    os.environ.update(env)
    raw = os.environ.get("LLM_MODELS_JSON", "")
    rows = shape(raw) if raw.strip() else []
    hosts = sorted({r["host"] for r in rows if r["host"]})
    print("LLM_MODELS_JSON entries=%d hosts=%s" % (len(rows), hosts))
    for r in rows[:30]:
        print("  " + json.dumps(r, ensure_ascii=False, sort_keys=True))
    guard = tg.TransportGuard(allowed=dict(p3_env.MODEL_HOSTS), max_calls=2)
    tg.install(guard)
    key = os.environ.get("LLM_API_KEY", "")
    body = {"model": "LongCat-2.0", "messages": [{"role": "user", "content": "用一句话说明：试用期的法定上限是多少？"}], "max_tokens": 200}
    r = httpx.post(BASE + "/chat/completions", json=body, headers={"Authorization": "Bearer " + key}, timeout=90.0)
    data = r.json() if r.content else {}
    usage = data.get("usage") or {}
    text = ""
    try:
        text = data["choices"][0]["message"]["content"] or ""
    except Exception:
        pass
    rec = {"model": "LongCat-2.0", "status": r.status_code, "has_choices": bool(data.get("choices")),
           "usage": {k: usage.get(k) for k in ("prompt_tokens", "completion_tokens", "total_tokens") if k in usage},
           "answer_chars": len(text), "answer_sha8": __import__("hashlib").sha256(text.encode()).hexdigest()[:8],
           "reasoning_field": sorted((data.get("choices") or [{}])[0].get("message", {}).keys()) if data.get("choices") else []}
    if r.status_code >= 400:
        err = data.get("error") if isinstance(data.get("error"), dict) else {}
        rec["error"] = str(err.get("code") or data.get("message") or "")[:90]
    print(json.dumps(rec, ensure_ascii=False, sort_keys=True))
    tg.uninstall()
    print("sends:", len(guard.calls))
    (HERE / "logs" / "probe-llm3.json").write_text(json.dumps({"rows": rows, "hosts": hosts, "probe": rec}, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
