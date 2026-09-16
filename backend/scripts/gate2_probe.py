"""Gate 2 可行性探测（只读测基线形态，不改业务代码）：对指定题发初始问题，解析 SSE 事件。

- 报告：是否进入 agent（agent_status/clarification）、澄清事件字段、或 RAG 直接回答
- 用途：确认当前实现下开发集可达性，把"未 routed"如实记录为基线入口限制
用法：python scripts/gate2_probe.py --case C01 [--base-url ...]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CASES = json.loads(
    (REPO / "release-evidence/legal-agent-v1-complex-v1-20260907/frozen-cases-v1.json").read_text(encoding="utf-8")
)["cases"]
BY_ID = {c["id"]: c for c in CASES}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--case", choices=sorted(BY_ID))
    ap.add_argument("--all", action="store_true", help="探测全部 10 题 baseline 形态")
    ap.add_argument("--force", action="store_true", help="手动深入分析：force_agent=true")
    ap.add_argument("--base-url", default="http://127.0.0.1:8000")
    args = ap.parse_args()
    targets = sorted(BY_ID) if args.all else [args.case]
    assert args.all or args.case, "需 --case 或 --all"
    args.force = bool(getattr(args, "force", False))

    import urllib.parse  # noqa: PLC0415

    env_file = REPO / "backend" / ".env"
    user = pw = None
    for line in env_file.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("ADMIN_USERNAME="):
            user = line.split("=", 1)[1].strip()
        elif line.startswith("ADMIN_PASSWORD="):
            pw = line.split("=", 1)[1].strip()

    def post(path: str, payload: dict) -> tuple[int, str]:
        req = urllib.request.Request(
            args.base_url + path,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=150) as resp:
                return resp.status, resp.read().decode("utf-8")
        except urllib.error.HTTPError as exc:  # noqa: PLC0415
            return exc.code, exc.read().decode("utf-8")

    st, body = post("/api/auth/login", {"username": user, "password": pw})
    if st != 200:
        print("login failed", st, body[:200])
        return 2
    token = json.loads(body)["token"]

    for case_id in targets:
        c = BY_ID[case_id]
        payload = {"content": c["initial_question"], "no_cache": True}
        if args.force:
            payload["force_agent"] = True
        req = urllib.request.Request(
            args.base_url + "/api/chat",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=200) as resp:
                raw = resp.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            print(f"case={case_id} chat failed", exc.code, exc.read().decode("utf-8")[:200])
            continue

        events = []
        for part in raw.split("\n\n"):
            line = part.strip()
            if line.startswith("data: ") and "[DONE]" not in line:
                try:
                    events.append(json.loads(line[6:]))
                except json.JSONDecodeError:
                    pass
        clar = [e for e in events if e.get("type") == "clarification"]
        text = "".join(str(e.get("content", "")) for e in events if e.get("content"))
        routed = any(e.get("type") == "agent_status" for e in events) or bool(clar)
        print(
            f"[{'ROUTED' if routed else 'RAG   '}] {case_id} events={len(events)} clar={'Y' if clar else 'N'} ans_chars={len(text)}"
        )
        if clar:
            c0 = clar[0]
            print("    clar_prompt:", c0.get("prompt", "")[:120])
    return 0


if __name__ == "__main__":
    sys.exit(main())
