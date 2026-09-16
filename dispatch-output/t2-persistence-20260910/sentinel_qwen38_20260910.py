"""运行中服务的非付费哨兵（0 次 LLM 外呼）。

1) GET /api/admin/stats → llm_model，确认**进程内**实际解析到的模型（不是读 .env 猜的）；
2) POST /api/chat 带伪造 agent_run_id → 503=AGENT_ENABLED 未生效 / 404=已生效
   （门在 main.py:1370，早于任何 LLM 外呼）。

显式 ProxyHandler({}) 绕开沙箱注入的 HTTP_PROXY。
"""

from __future__ import annotations

import json
import pathlib
import urllib.error
import urllib.request
import uuid

ROOT = pathlib.Path(__file__).resolve().parents[2]
BASE = "http://127.0.0.1:8001"
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))

lines: list[str] = []


def _creds() -> tuple[str, str]:
    user = pw = ""
    for line in (ROOT / "backend" / ".env").read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("ADMIN_USERNAME="):
            user = line.split("=", 1)[1].strip()
        elif line.startswith("ADMIN_PASSWORD="):
            pw = line.split("=", 1)[1].strip()
    return user, pw


def call(path: str, payload: dict | None = None, token: str | None = None, method: str = "GET") -> tuple[int, str]:
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(BASE + path, data=data, headers=headers, method=method)
    try:
        with OPENER.open(req, timeout=20) as resp:
            return resp.status, resp.read(6000).decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read(4000).decode("utf-8", "replace")
    except Exception as exc:  # noqa: BLE001
        return -1, f"{type(exc).__name__}: {exc}"


def main() -> None:
    user, pw = _creds()
    status, body = call("/api/auth/login", {"username": user, "password": pw}, method="POST")
    lines.append(f"login -> {status}")
    token = json.loads(body).get("token") if status == 200 else None

    status, body = call("/api/admin/stats", token=token)
    model = None
    if status == 200:
        try:
            data = json.loads(body)
            model = data.get("llm_model")
            lines.append(f"admin/stats -> 200  llm_model={model!r}")
            for k in ("llm_model", "provider", "embedding_model"):
                if k in data:
                    lines.append(f"   {k}={data[k]!r}")
        except Exception as exc:  # noqa: BLE001
            lines.append(f"admin/stats 解析失败 {exc} body[:200]={body[:200]}")
    else:
        lines.append(f"admin/stats -> {status} body[:200]={body[:200]}")

    status, body = call(
        "/api/chat",
        {"content": "sentinel", "conversation_id": 1, "agent_run_id": str(uuid.uuid4()), "agent_state_version": 1},
        token=token,
        method="POST",
    )
    lines.append(f"chat(resume,bogus) -> {status}")
    if status == 404:
        lines.append("AGENT_ENABLED: TRUE（穿过 503 门）")
    elif status == 503:
        lines.append("AGENT_ENABLED: FALSE（被 503 门拦下）")
    else:
        lines.append(f"AGENT_ENABLED: 不确定（status={status}）")

    verdict = []
    verdict.append("MODEL_OK" if model == "qwen3.8-flash" else f"MODEL_MISMATCH({model!r})")
    out = ROOT / "dispatch-output" / "t2-persistence-20260910" / "sentinel_qwen38_20260910.log"
    out.write_text("\n".join(lines) + f"\nVERDICT: {' '.join(verdict)}\n", encoding="utf-8")
    for line in lines:
        print(line, flush=True)
    print("VERDICT: " + " ".join(verdict), flush=True)


if __name__ == "__main__":
    main()
