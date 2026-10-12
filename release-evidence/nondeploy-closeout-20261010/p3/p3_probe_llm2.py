"""Second diagnostic on the longcat route: is the 400 a request-shape error or a dead route?

Auth passed on leg 1 (400 invalid_parameter, not 401), so the key is live. These two
requests ask: does the frozen model id exist, and does a body without max_tokens work.
Prints status, model-id list (public names), token usage. No key, no body text.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import httpx

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import p3_env  # noqa: E402
import p3_transport_guard as tg  # noqa: E402

CFG = json.loads((HERE / "p3_models_frozen.json").read_text(encoding="utf-8"))
BASE = CFG["llm"]["base_url"]
MODEL = CFG["llm"]["model"]


def main() -> int:
    env = p3_env.bind_private_root(p3_env.read_env())
    os.environ.update(env)
    guard = tg.TransportGuard(allowed=dict(p3_env.MODEL_HOSTS), max_calls=5)
    tg.install(guard)          # counting happens at the transport: 1 send == 1 count
    key = os.environ.get("LLM_API_KEY", "")
    out = []
    r = httpx.get(BASE + "/models", headers={"Authorization": "Bearer " + key}, timeout=30.0)
    ids = []
    if r.status_code == 200:
        d = r.json()
        rows = d.get("data") or d.get("models") or []
        ids = sorted({str(x.get("id")) for x in rows if isinstance(x, dict)})
    rec = {"leg": "models_list", "status": r.status_code, "count": len(ids),
           "frozen_model_present": MODEL in ids, "prefix3": ids[:3]}
    out.append(rec)
    print(json.dumps(rec, ensure_ascii=False, sort_keys=True))

    for name, body in (
        ("no_max_tokens", {"model": MODEL, "messages": [{"role": "user", "content": "只回一个字：好"}]}),
        ("minimal_other", {"model": MODEL, "messages": [{"role": "user", "content": "只回一个字：好"}], "max_completion_tokens": 8}),
    ):
        t0 = time.monotonic()
        rec = {"leg": name, "model": MODEL}
        try:
            r = httpx.post(BASE + "/chat/completions", json=body, headers={"Authorization": "Bearer " + key}, timeout=60.0)
            rec["status"] = r.status_code
            data = r.json() if r.content else {}
            usage = data.get("usage") or {}
            rec["usage"] = {k: usage.get(k) for k in ("prompt_tokens", "completion_tokens", "total_tokens") if k in usage}
            rec["has_choices"] = bool(data.get("choices"))
            if r.status_code >= 400:
                err = data.get("error") if isinstance(data.get("error"), dict) else {}
                rec["error"] = str(err.get("code") or err.get("type") or data.get("message") or "")[:90]
        except Exception as exc:
            rec["exception"] = type(exc).__name__
        rec["elapsed_s"] = round(time.monotonic() - t0, 2)
        out.append(rec)
        print(json.dumps(rec, ensure_ascii=False, sort_keys=True))
        if rec.get("has_choices"):
            break
    tg.uninstall()
    print("sends:", len(guard.calls), sorted(c.split("/")[2] + "//" + "/".join(c.split("/")[3:]) for c in guard.calls))
    (HERE / "logs" / "probe-llm2.json").write_text(json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
