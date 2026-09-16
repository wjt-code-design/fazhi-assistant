"""隐藏验收集正式运行执行器（审查侧，任务书 dispatch-tasks-20260908.md 任务 1 第 4 步）。

与实施侧 gate2_runner.py 同协议：
1. POST /api/chat {"content": initial_question, "no_cache": true, "force_agent": true} → SSE 解析
2. clarification.prompt 与 hidden-round-protocol fact 的 match_keywords 跨轮匹配；
   命中→resume 携带该 fact 正文；未命中→固定话术"我没有保留这方面的信息。"
3. resume body: {"content": ..., "no_cache": true, "conversation_id": ..., "agent_run_id": ..., "agent_state_version": ...}
4. 最多两轮；第 3 次 clarification → over2 红线候选
5. 禁止重试；失败原样保留
差异：raw SSE 全文逐轮原样落盘（任务书通用纪律 4），关键词取自 hidden-round-protocol-v1.json。

用法：python hidden_runner.py --runs a,b
输出：dispatch-output/task1/run-<x>.json 与 run-<x>-raw/<case>-<req>.sse
"""
from __future__ import annotations

import argparse
import datetime
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
CASES = json.loads((HERE / "hidden-cases-v1.json").read_text(encoding="utf-8"))["cases"]
BY_ID = {c["id"]: c for c in CASES}
PROTO = json.loads((HERE / "hidden-round-protocol-v1.json").read_text(encoding="utf-8"))

# 从 protocol 抽取 fact 文本与关键词（跨轮匹配，与 gate2_runner 语义一致）
FACT_TEXT: dict[str, str] = {}
KEYWORDS: dict[str, list[str]] = {}
for _case, _rounds in PROTO["fact_units"].items():
    for _rn, _units in _rounds.items():
        for _u in _units:
            FACT_TEXT[_u["fact_id"]] = _u["text"]
            KEYWORDS[_u["fact_id"]] = _u["match_keywords"]

NO_MATCH_REPLY = PROTO.get("no_match_reply", "我没有保留这方面的信息。")
ENV = Path(__file__).resolve().parents[2] / "backend" / ".env"

# ---- 评测器共享事实投放（2026-09-08，评测器纠偏任务）----
# 与 backend/scripts/gate2_runner.py 共用 harness_fact_reveal 单一实现（§4.1）。
import sys as _sys

_SCRIPTS = Path(__file__).resolve().parents[2] / "backend" / "scripts"
if str(_SCRIPTS) not in _sys.path:
    _sys.path.insert(0, str(_SCRIPTS))
from harness_fact_reveal import match_revealable_facts, FactMatchResult  # noqa: E402


def _build_fact_meta() -> dict[str, dict]:
    import re as _re

    facts: dict[str, dict] = {}
    for fid, kws in KEYWORDS.items():
        m = _re.search(r"-r(\d+)-f", fid)
        rnd = int(m.group(1)) if m else 99
        facts[fid] = {"round": rnd, "keywords": list(kws), "text": FACT_TEXT.get(fid, "")}
    return facts


_FACTS = _build_fact_meta()


def _match_facts(case: str, prompt: str) -> tuple[list[str], list[str]]:
    """兼容旧签名（= 第一轮、无已答）：轮次隔离 + 去重由共享模块保证。"""
    res = match_revealable_facts(
        case_id=case, prompt=prompt, current_round=1, answered_fact_ids=set(), facts=_FACTS
    )
    return [m["text"] for m in res.matched_facts], res.answered_fact_ids


def _match_facts_tracked(
    case: str, prompt: str, current_round: int, answered_fact_ids: set[str]
) -> tuple[list[str], list[str], FactMatchResult]:
    res = match_revealable_facts(
        case_id=case,
        prompt=prompt,
        current_round=current_round,
        answered_fact_ids=answered_fact_ids,
        facts=_FACTS,
    )
    return [m["text"] for m in res.matched_facts], res.answered_fact_ids, res


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", default="a,b")
    ap.add_argument("--base-url", default="http://127.0.0.1:8000")
    args = ap.parse_args()

    user = pw = None
    for line in ENV.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("ADMIN_USERNAME="):
            user = line.split("=", 1)[1].strip()
        elif line.startswith("ADMIN_PASSWORD="):
            pw = line.split("=", 1)[1].strip()

    def post(path: str, payload: dict, token: str | None = None, timeout: int = 3000) -> tuple[int | None, str | None, str | None]:
        """返回 (status, raw, exc_name)；网络异常时 status=None 且 exc_name 为异常类名，不抛出。"""
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        req = urllib.request.Request(
            args.base_url + path, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.status, resp.read().decode("utf-8"), None
        except urllib.error.HTTPError as exc:
            return exc.code, exc.read().decode("utf-8"), None
        except Exception as exc:  # RemoteDisconnected/timeout/URLError 等：如实记录，继续运行
            return None, None, type(exc).__name__

    _, body, _exc = post("/api/auth/login", {"username": user, "password": pw})
    token = json.loads(body).get("token") if body else None
    if not token:
        print("login failed", flush=True)
        return 2

    def _events(raw: str) -> list[dict]:
        out = []
        for part in raw.split("\n\n"):
            line = part.strip()
            if line.startswith("data: ") and "[DONE]" not in line:
                try:
                    out.append(json.loads(line[6:]))
                except json.JSONDecodeError:
                    pass
        return out

    def _error_codes(events: list[dict]) -> list[str]:
        return [
            str(e.get("code") or e.get("reason_code"))
            for e in events
            if e.get("type") in ("error", "restart") and (e.get("code") or e.get("reason_code"))
        ]

    for run_id in [r.strip() for r in args.runs.split(",") if r.strip()]:
        raw_dir = HERE / f"run-{run_id}-raw"
        raw_dir.mkdir(exist_ok=True)
        results = {}
        print(f"===== RUN {run_id} start {datetime.datetime.now().isoformat(timespec='seconds')} =====", flush=True)
        for case_id in sorted(BY_ID):
            c = BY_ID[case_id]
            asked, answered, unmatched = [], [], []
            rounds = []
            conv_id = None
            t0 = time.time()
            payload = {"content": c["initial_question"], "no_cache": True, "force_agent": True}
            status, raw, exc_name = post("/api/chat", payload, token)
            (raw_dir / f"{case_id}-initial.sse").write_text(f"# status={status} exc={exc_name}\n" + (raw or ""), encoding="utf-8")
            events = _events(raw) if raw else []
            if exc_name:
                events = [{"type": "error", "code": f"HTTP_CLIENT_EXCEPTION:{exc_name}"}]
            rounds.append({
                "request": "initial", "status": status,
                "client_exception": exc_name,
                "event_types": [e.get("type", "content") for e in events],
                "error_codes": _error_codes(events),
            })

            for round_no in (1, 2):
                clar = [e for e in events if e.get("type") == "clarification"]
                if not clar:
                    break
                prompt = clar[0].get("prompt", "")
                conv_id = clar[0].get("conversation_id") if conv_id is None else conv_id
                asked.append({"round": round_no, "prompt": prompt})
                answered_facts, matched_ids, res = _match_facts_tracked(
                    case_id, prompt, current_round=round_no, answered_fact_ids=set(answered)
                )
                if matched_ids:
                    answered += matched_ids
                    reply = "；".join(answered_facts)
                else:
                    unmatched.append({"round": round_no, "prompt": prompt, "reason": "no_rule_match"})
                    reply = NO_MATCH_REPLY
                payload = {
                    "content": reply, "no_cache": True,
                    "conversation_id": clar[0].get("conversation_id"),
                    "agent_run_id": clar[0].get("run_id"),
                    "agent_state_version": clar[0].get("state_version"),
                }
                status, raw, exc_name = post("/api/chat", payload, token)
                (raw_dir / f"{case_id}-round{round_no}.sse").write_text(f"# status={status} exc={exc_name}\n" + (raw or ""), encoding="utf-8")
                events = _events(raw) if raw else []
                if exc_name:
                    events = [{"type": "error", "code": f"HTTP_CLIENT_EXCEPTION:{exc_name}"}]
                rounds.append({
                    "request": f"round{round_no}", "status": status,
                    "client_exception": exc_name,
                    "answered_facts": answered_facts,
                    "event_types": [e.get("type", "content") for e in events],
                    "error_codes": _error_codes(events),
                    "clar_meta": {
                        "run_id": clar[0].get("run_id"),
                        "state_version": clar[0].get("state_version"),
                        "conv_id": clar[0].get("conversation_id"),
                    },
                    "raw_tail": raw[-300:] if (status != 200 and raw) else None,
                })

            all_error_codes = [code for r in rounds for code in r.get("error_codes", [])]
            final_text = "".join(str(e.get("content", "")) for e in events if e.get("content"))
            over_rounds = any(e.get("type") == "clarification" for e in events) and not exc_name
            results[case_id] = {
                "rounds": rounds,
                "asked": asked,
                "answered_fact_ids": answered,
                "unmatched_questions": unmatched,
                "manual_review_required": [],
                "protocol_violations": [],
                "unknown_fact_ids": [],  # deprecated（评测器纠偏 §4.2）
                "error_codes": all_error_codes,
                "conv_id": conv_id,
                "final_chars": len(final_text),
                "final_text": final_text,
                "final_excerpt": final_text[:120],
                "redline_candidate_over_2_rounds": over_rounds,
                "elapsed_s": round(time.time() - t0, 1),
            }
            print(f"[{case_id}] rounds={len(rounds)} clar={len(asked)} answered={len(answered)} "
                  f"unmatched={len(unmatched)} final_chars={len(final_text)} over2={over_rounds} "
                  f"errors={all_error_codes} t={results[case_id]['elapsed_s']}s", flush=True)
            # 增量持久化：每题完成即写盘，防后续题异常丢失
            (HERE / f"run-{run_id}.json").write_text(json.dumps({
                "run": run_id,
                "results": results,
            }, ensure_ascii=False, indent=1), encoding="utf-8")

        out = HERE / f"run-{run_id}.json"
        out.write_text(json.dumps({
            "run": run_id,
            "started_at": None,  # 占位：由外层日志记录
            "results": results,
        }, ensure_ascii=False, indent=1), encoding="utf-8")
        print("written:", out.name, f"{datetime.datetime.now().isoformat(timespec='seconds')}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
