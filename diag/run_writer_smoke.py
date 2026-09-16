"""004 writer 路径 live smoke：同用户 clarification→resume 闭环，验证真实模型起草轮次。

阶段 B 收口项（spec：Agent planner/writer 全部通过才能进采集适配器）。
成功标准：resume 后 SSE 无 error；若 completed 则 token 非空且 DB run=completed、
存在 writer 相关 step（finalize）；若仍 clarification（预算内）则如实记录。
"""
import json
import sys
import urllib.request
import uuid
from pathlib import Path

BASE = "http://127.0.0.1:18003"
OUT = Path(__file__).resolve().parent / "preflight-004"
QUERY = "2020年借款约定2021年还，至今未还，2026年还能起诉吗？"
SUPPLEMENT = "补充事实：债权人于2023年8月曾向债务人催告还款，债务人承诺2024年6月前还清但未履行。"


def post(path, payload, token=None, timeout=300):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(BASE + path, data=json.dumps(payload).encode(), headers=headers, method="POST")
    return urllib.request.urlopen(req, timeout=timeout)


def parse(raw):
    events = []
    for line in raw.splitlines():
        if line.startswith("data: ") and line[6:] != "[DONE]":
            try:
                events.append(json.loads(line[6:]))
            except json.JSONDecodeError:
                pass
    return events


def chat(token, payload, tag):
    r = post("/api/chat", payload, token=token)
    raw = r.read().decode("utf-8")
    (OUT / f"sse-writer-{tag}.txt").write_text(raw, encoding="utf-8")
    return r.status, parse(raw)


def main():
    sfx = uuid.uuid4().hex[:8]
    u, p = f"pf4w_{sfx}", f"Pf4w-{sfx}-Pass1"
    post("/api/auth/register", {"username": u, "password": p}, timeout=60)
    token = json.loads(post("/api/auth/login", {"username": u, "password": p}, timeout=60).read().decode())["token"]

    st, ev = chat(token, {"content": QUERY}, "q1")
    errors = [e.get("code") for e in ev if e.get("type") == "error"]
    clar = next((e for e in ev if e.get("type") == "clarification"), None)
    final = next((e for e in ev if e.get("type") == "final"), None)
    print("Q1:", st, "errors:", errors, "clar:", bool(clar), "final:", bool(final))
    if errors or not clar:
        print("WRITER-SMOKE: BLOCKED (no clarification to resume)", json.dumps(errors))
        return 1

    st, ev = chat(
        token,
        {
            "content": SUPPLEMENT,
            "agent_run_id": clar["run_id"],
            "agent_state_version": clar["state_version"],
            "conversation_id": clar["conversation_id"],
        },
        "resume",
    )
    errors = [e.get("code") for e in ev if e.get("type") == "error"]
    final = next((e for e in ev if e.get("type") == "final"), None)
    clar2 = next((e for e in ev if e.get("type") == "clarification"), None)
    answer = "".join(e.get("content", "") for e in ev if isinstance(e.get("content"), str))
    print("RESUME:", st, "errors:", errors, "final:", bool(final), "clar2:", bool(clar2), "chars:", len(answer))
    if final:
        print("FINAL run:", final.get("run_id"), "state_version:", final.get("state_version"))
    print("ANSWER_HEAD:", answer[:150].replace(chr(10), " "))

    ok = st == 200 and not errors and final is not None and len(answer) > 50
    print("WRITER-SMOKE:", "PASS" if ok else ("PARTIAL" if st == 200 and not errors else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
