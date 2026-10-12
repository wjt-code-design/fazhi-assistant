"""Does LongCat-2.0 ever return visible content? One call, output budget 1024 (cap is 2048).

Recorded as diagnostic spend, not an acceptance case. Prints field names, lengths,
sha8 of the answer, token usage. The answer text itself is not printed.
"""
from __future__ import annotations

import hashlib
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
PROMPT = "我签合同约定试用期八个月，合同期限两年。这样约定合法吗？请给出依据。"


def main() -> int:
    env = p3_env.bind_private_root(p3_env.read_env())
    os.environ.update(env)
    guard = tg.TransportGuard(allowed=dict(p3_env.MODEL_HOSTS), max_calls=2)
    tg.install(guard)
    key = os.environ.get("LLM_API_KEY", "")
    out = []
    for model in ("LongCat-2.0", "LongCat-2.5-Preview"):
        t0 = time.monotonic()
        body = {"model": model, "messages": [{"role": "user", "content": PROMPT}], "max_tokens": 1024}
        rec = {"model": model}
        try:
            r = httpx.post(BASE + "/chat/completions", json=body, headers={"Authorization": "Bearer " + key}, timeout=120.0)
            data = r.json() if r.content else {}
            msg = (data.get("choices") or [{}])[0].get("message", {}) if data.get("choices") else {}
            content = str(msg.get("content") or "")
            reasoning = str(msg.get("reasoning_content") or "")
            usage = data.get("usage") or {}
            rec.update({"status": r.status_code, "msg_fields": sorted(msg), "content_chars": len(content),
                        "reasoning_chars": len(reasoning), "content_sha8": hashlib.sha256(content.encode()).hexdigest()[:8],
                        "usage": {k: usage.get(k) for k in ("prompt_tokens", "completion_tokens", "total_tokens", "reasoning_tokens") if k in usage},
                        "finish_reason": (data.get("choices") or [{}])[0].get("finish_reason")})
            if r.status_code >= 400:
                err = data.get("error") if isinstance(data.get("error"), dict) else {}
                rec["error"] = str(err.get("code") or data.get("message") or "")[:90]
        except Exception as exc:
            rec["exception"] = type(exc).__name__
        rec["elapsed_s"] = round(time.monotonic() - t0, 2)
        out.append(rec)
        print(json.dumps(rec, ensure_ascii=False, sort_keys=True))
    tg.uninstall()
    print("sends:", len(guard.calls))
    (HERE / "logs" / "probe-llm4.json").write_text(json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
