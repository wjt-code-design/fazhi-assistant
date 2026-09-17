"""非付费判定探针：确认运行中的服务 AGENT_ENABLED 是否真正生效。

原理（main.py:1366-1372）：当 body.agent_run_id 非空时，
  - settings.agent_enabled 为 False → 抛 503「Agent 当前已停用，请稍后重试」
  - 为 True → 继续 resume_with_user_fact → 伪造 run_id 必然 ResumeRunNotFound → 404
故 404 = 开关生效，503 = 未生效。不触发任何 LLM 外呼。

显式 ProxyHandler({}) 绕开沙箱注入的 HTTP_PROXY（否则 localhost 请求被代理劫持成 502）。
"""

from __future__ import annotations

import json
import pathlib
import urllib.error
import urllib.request
import uuid

ROOT = pathlib.Path(__file__).resolve().parents[2]
BASE = "http://127.0.0.1:8001"

lines: list[str] = []


def _creds() -> tuple[str, str]:
    user = pw = ""
    for line in (ROOT / "backend" / ".env").read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("ADMIN_USERNAME="):
            user = line.split("=", 1)[1].strip()
        elif line.startswith("ADMIN_PASSWORD="):
            pw = line.split("=", 1)[1].strip()
    return user, pw


OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def post(path: str, payload: dict, token: str | None = None, timeout: int = 20) -> tuple[int, str]:
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(
        BASE + path, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST"
    )
    try:
        with OPENER.open(req, timeout=timeout) as resp:
            return resp.status, resp.read(4000).decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read(4000).decode("utf-8", "replace")
    except Exception as exc:  # noqa: BLE001
        return -1, f"{type(exc).__name__}: {exc}"


def main() -> None:
    user, pw = _creds()
    lines.append(f"creds_present user={bool(user)} pw={bool(pw)}")

    status, body = post("/api/auth/login", {"username": user, "password": pw})
    lines.append(f"login -> {status}")
    token = None
    if status == 200:
        try:
            data = json.loads(body)
            lines.append(f"login_body_keys={sorted(data.keys())}")
            token = data.get("access_token") or data.get("token")
        except Exception as exc:  # noqa: BLE001
            lines.append(f"login_parse_error={exc} body[:120]={body[:120]}")

    status2, body2 = post(
        "/api/chat",
        {
            "content": "probe-agent-enabled-flag",
            "conversation_id": 1,
            "agent_run_id": str(uuid.uuid4()),
            "agent_state_version": 1,
        },
        token=token,
    )
    lines.append(f"chat(resume,bogus_run) -> {status2} body[:200]={body2[:200]}")

    if status2 == 404:
        verdict = "AGENT_ENABLED=TRUE（已通过 503 门，落到 ResumeRunNotFound）"
    elif status2 == 503:
        verdict = "AGENT_ENABLED=FALSE（被 503 门拦下，run 数据会作废）"
    else:
        verdict = f"不确定（status={status2}）——需人工判读"
    lines.append("VERDICT: " + verdict)

    out = ROOT / "dispatch-output" / "t2-persistence-20260910" / "agent_enabled_probe.log"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    for line in lines:
        print(line, flush=True)


if __name__ == "__main__":
    main()
