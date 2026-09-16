"""Gate 2A RAG 对照矩阵采集器（dispatch-tasks-20260908.md 任务 2）。

对开发集 10 题各建立两种普通 RAG 对照（默认回答路径，不带 force_agent、不带 agent_run_id）：
- RAG-initial:    {"content": <initial_question>, "no_cache": true}
- RAG-full-facts: {"content": <initial_question> + 补充信息拼接 round1_facts/round2_facts, "no_cache": true}
 clarification 事件或空内容如实记录，不重试替换。

用法：python rag_runner.py --cases C01-C10
输出：dispatch-output/task2/<case>-<mode>.raw（SSE 全文原样）
"""
from __future__ import annotations

import argparse
import datetime
import json
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
CASES = json.loads((REPO / "release-evidence/legal-agent-v1-complex-v1-20260907/frozen-cases-v1.json").read_text(encoding="utf-8"))["cases"]
BY_ID = {c["id"]: c for c in CASES}
ENV = REPO / "backend" / ".env"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", default=",".join(sorted(BY_ID)))
    ap.add_argument("--base-url", default="http://127.0.0.1:8000")
    args = ap.parse_args()
    targets = [c.strip() for c in args.cases.split(",") if c.strip()]

    user = pw = None
    for line in ENV.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("ADMIN_USERNAME="):
            user = line.split("=", 1)[1].strip()
        elif line.startswith("ADMIN_PASSWORD="):
            pw = line.split("=", 1)[1].strip()

    def post(payload: dict, token: str, timeout: int = 1500) -> tuple[int, str]:
        req = urllib.request.Request(
            args.base_url + "/api/chat",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.status, resp.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            return exc.code, exc.read().decode("utf-8")

    req = urllib.request.Request(
        args.base_url + "/api/auth/login",
        data=json.dumps({"username": user, "password": pw}).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=30) as resp:
        token = json.loads(resp.read().decode("utf-8")).get("token")
    if not token:
        print("login failed", flush=True)
        return 2

    print(f"RAG baseline collect start {datetime.datetime.now().isoformat(timespec='seconds')}", flush=True)
    for cid in targets:
        c = BY_ID[cid]
        jobs = [
            ("rag-initial", {"content": c["initial_question"], "no_cache": True}),
            ("rag-full-facts", {"content": c["initial_question"] + "\n\n补充信息：" + str(c["round1_facts"]) + "\n" + str(c["round2_facts"]), "no_cache": True}),
        ]
        for mode, payload in jobs:
            t0 = datetime.datetime.now()
            status, raw = post(payload, token)
            out = HERE / f"{cid}-{mode}.raw"
            out.write_text(f"# case={cid} mode={mode} status={status} started={t0.isoformat(timespec='seconds')}\n" + raw, encoding="utf-8")
            ev_types = []
            for part in raw.split("\n\n"):
                line = part.strip()
                if line.startswith("data: ") and "[DONE]" not in line:
                    try:
                        ev_types.append(json.loads(line[6:]).get("type", "content"))
                    except json.JSONDecodeError:
                        pass
            final_chars = raw.count('"content"')
            print(f"[{cid}] {mode} status={status} events={ev_types[:8]} t={(datetime.datetime.now()-t0).seconds}s", flush=True)
    print("done", flush=True)
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
