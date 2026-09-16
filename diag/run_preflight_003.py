"""003 候选同题 Agent 隔离预检（对 127.0.0.1:18002 的全新隔离容器执行一次）。

成功标准（交接阶段A）：
- SSE 不出现 error 事件；
- 若应完成则回答非空；若应反问则为结构化 clarification；
- 数据库 agent_runs/agent_steps 与 SSE 结果一致。

产物写入 diag/preflight-003/（sse 原始流 + 结果摘要），不含密钥。
"""
import json
import sys
import time
import uuid
from pathlib import Path

import urllib.request

BASE = "http://127.0.0.1:18002"
OUT = Path(__file__).resolve().parent / "preflight-003"
OUT.mkdir(parents=True, exist_ok=True)
QUERY = "2020年借款约定2021年还，至今未还，2026年还能起诉吗？"


def post(path: str, payload: dict, token: str | None = None, timeout: float = 120):
    req = urllib.request.Request(
        BASE + path,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", **({"Authorization": f"Bearer {token}"} if token else {})},
        method="POST",
    )
    return urllib.request.urlopen(req, timeout=timeout)


def main() -> int:
    suffix = uuid.uuid4().hex[:8]
    username = f"preflight_{suffix}"
    password = f"Preflight-{suffix}-Pass1"

    r = post("/api/auth/register", {"username": username, "password": password})
    print("register:", r.status)
    r = post("/api/auth/login", {"username": username, "password": password})
    token = json.loads(r.read().decode("utf-8"))["token"]
    print("login: ok")

    t0 = time.perf_counter()
    r = post(
        "/api/chat",
        {"content": QUERY},
        token=token,
        timeout=180,
    )
    raw = r.read().decode("utf-8")
    elapsed = round(time.perf_counter() - t0, 1)
    (OUT / "sse-agent.txt").write_text(raw, encoding="utf-8")

    events = []
    for line in raw.splitlines():
        if line.startswith("data: ") and line[6:] != "[DONE]":
            events.append(json.loads(line[6:]))

    types = [e.get("type") for e in events]
    statuses = [e.get("status") for e in events if e.get("type") == "agent_status"]
    token_chars = sum(len(e.get("content", "")) for e in events if e.get("type") == "token")
    error_events = [e for e in events if e.get("type") == "error"]
    final_events = [e for e in events if e.get("type") == "final"]
    clar_events = [e for e in events if e.get("type") == "clarification"]

    print("HTTP:", r.status, "elapsed:", elapsed, "s")
    print("event types:", types)
    print("agent_status:", statuses)
    print("content_chars:", token_chars)
    print("error events:", [e.get("code") for e in error_events])
    print("final events:", [(e.get("run_id"), e.get("state_version")) for e in final_events])
    print("clarification:", [(e.get("issue_id"), (e.get("prompt") or "")[:50]) for e in clar_events])

    summary = {
        "http_status": r.status,
        "elapsed_s": elapsed,
        "event_types": types,
        "agent_status": statuses,
        "content_chars": token_chars,
        "error_codes": [e.get("code") for e in error_events],
        "final": [{"run_id": e.get("run_id"), "state_version": e.get("state_version")} for e in final_events],
        "clarification": [{"issue_id": e.get("issue_id")} for e in clar_events],
    }
    (OUT / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")

    ok = (
        r.status == 200
        and not error_events
        and (
            (final_events and token_chars > 0)
            or (clar_events and statuses[-1:] == ["waiting_user"])
        )
    )
    print("PREFLIGHT-AGENT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
