"""Does LongCat-2.0 hit the same empty-answer-under-streaming problem as 2.5-Preview?

Two calls, one per model, through a client built exactly like ll_registry._build does
(streaming=True, timeout from cfg, retries off in this runner). Records only counts:
chunks seen, content chars, reasoning chars, finish reason, token usage. No text.
"""
from __future__ import annotations

import asyncio
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import p3_env  # noqa: E402
import p3_transport_guard as tg  # noqa: E402

PROMPT = "合同约定试用期八个月、合同期限两年，这样约定合法吗？依据是什么？"
MODELS = ("LongCat-2.0", "LongCat-2.5-Preview")


async def one(model: str) -> dict:
    from langchain_openai import ChatOpenAI

    llm = ChatOpenAI(model=model, api_key=os.environ["LLM_API_KEY"], base_url=os.environ["LLM_BASE_URL"],
                     streaming=True, timeout=120, max_retries=0, max_tokens=512)
    t0 = time.monotonic()
    chunks = content = reasoning = 0
    finish = ""
    usage: dict = {}
    try:
        async for c in llm.astream([("user", PROMPT)]):
            chunks += 1
            msg = getattr(c, "content", "") or ""
            if isinstance(msg, list):
                msg = "".join(str(x.get("text", "")) if isinstance(x, dict) else str(x) for x in msg)
            content += len(msg)
            extra = getattr(c, "additional_kwargs", {}) or {}
            reasoning += len(str(extra.get("reasoning_content") or ""))
            if getattr(c, "response_metadata", None):
                finish = c.response_metadata.get("finish_reason") or finish
            if getattr(c, "usage_metadata", None):
                usage = dict(c.usage_metadata)
    except Exception as exc:
        return {"model": model, "exception": type(exc).__name__, "chunks": chunks}
    finally:
        try:
            await llm.async_client.close()
        except Exception:
            pass
    return {"model": model, "chunks": chunks, "content_chars": content, "reasoning_chars": reasoning,
            "finish_reason": finish, "usage": {k: usage.get(k) for k in ("input_tokens", "output_tokens", "total_tokens") if k in usage},
            "elapsed_s": round(time.monotonic() - t0, 2)}


def main() -> int:
    import json
    env = p3_env.bind_private_root(p3_env.read_env())
    os.environ.update(env)
    guard = tg.TransportGuard(allowed=dict(p3_env.MODEL_HOSTS), max_calls=4)
    tg.install(guard)
    out = [asyncio.run(one(m)) for m in MODELS]
    tg.uninstall()
    for r in out:
        print(json.dumps(r, ensure_ascii=False, sort_keys=True))
    print("sends:", len(guard.calls))
    (HERE / "logs" / "probe-llm5.json").write_text(json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
