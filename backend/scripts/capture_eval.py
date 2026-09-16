"""Real-but-isolated dual-run capture adapter for Legal Agent evaluation (Phase C).

Drives one isolated local container over HTTP with the frozen capture controls
(never touches production, never runs against the public `/api/chat`), records
every case row (failures retained), and emits a DRAFT ``legal-agent-eval-answers/v1``
file plus raw traces in an isolated directory.

Deterministic mapping only — the adapter never asks a model to label itself:
- latency_ms / tool_calls / budget_exceeded: measured client-side and from the
  isolated DB run steps (harness-side counting, not model self-report);
- clarification: verbatim from the actual clarification SSE event;
- evidence_ids: extracted from citations actually present in the answer text;
- claims[].text: actual answer sentences (human review finalises the
  important-claim binding later; the independent audit re-verifies every row).
"""

from __future__ import annotations

import argparse
import hashlib
import http.client
import json
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.capture_protocol import load_capture_protocol

_ANSWERS_SCHEMA = "legal-agent-eval-answers/v1"
# 主格式：《法名》第X条（条号在书名号外）
_CITATION_RE = re.compile(
    r"《([^》]{1,24}?)》\s*(第[零〇○一二两三四五六七八九十百千万亿0-9０-９]+条"
    r"(?:之[零〇○一二两三四五六七八九十百千万亿0-9０-９]+)?)"
)
# 变体：[法名 第X条]、[法名第X条]（法名与条号都在方括号内，可含空格）。
# 2026-09-07 修复：010 实证 agent 输出 "[民法典 第六百八十条]" 形式的合法引用，
# 主正则不匹配导致 evidence 绑定空、coverage 被冤枉拉低。适配器公平收录
# （评估器 v1.2.0 冻结不改）。
_BRACKET_CITATION_RE = re.compile(
    r"\[([^\[\]]{1,20}?)[\s\u3000]*(第[零〇○一二两三四五六七八九十百千万亿0-9０-９]+条"
    r"(?:之[零〇○一二两三四五六七八九十百千万亿0-9０-９]+)?)\]"
)


def _strip_cn_prefix(name: str) -> str:
    name = name.strip()
    return name[len("中华人民共和国") :] if name.startswith("中华人民共和国") else name


def _extract_citations(text: str) -> set[str]:
    """Actual citations present in the answer, normalised to ``法名:条`` keys."""
    found: set[str] = set()
    normalized = unicodedata.normalize("NFKC", text)
    for match in _CITATION_RE.finditer(normalized):
        law = _strip_cn_prefix(match.group(1))
        article = match.group(2)
        found.add(f"{law}:{article}")
        found.add(f"{law}:{_canonical_article(article)}")
    for match in _BRACKET_CITATION_RE.finditer(normalized):
        law = _strip_cn_prefix(match.group(1))
        article = match.group(2)
        found.add(f"{law}:{article}")
        found.add(f"{law}:{_canonical_article(article)}")
    return found


_CN_DIGITS = {
    "零": 0,
    "〇": 0,
    "○": 0,
    "一": 1,
    "二": 2,
    "两": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
}
_CN_UNITS = {"十": 10, "百": 100, "千": 1000, "万": 10_000, "亿": 100_000_000}


def _canonical_number(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value)
    if normalized.isdigit():
        return normalized.lstrip("0") or "0"
    total = section = current = 0
    for ch in normalized:
        if ch in _CN_DIGITS:
            current = _CN_DIGITS[ch]
            continue
        if ch in _CN_UNITS:
            unit = _CN_UNITS[ch]
            if unit < 10_000:
                section += (current or 1) * unit
            else:
                section = (section + current) * unit
                total += section
                section = 0
            current = 0
    return str(total + section + current)


def _canonical_article(article: str) -> str:
    body = article[1 : article.index("条")]
    return _canonical_number(body)


def _split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[。！？；;\n])", text.strip())
    return [p.strip() for p in parts if p.strip()]


def _match_case_issues(case_issues: list[str], texts: list[str]) -> list[str]:
    """detected_issues: a case issue counts as detected only when its term appears
    in the actual answer/clarification texts (deterministic containment)."""
    haystack = unicodedata.normalize("NFKC", "\n".join(texts))
    detected = []
    for issue in case_issues:
        if unicodedata.normalize("NFKC", issue) in haystack:
            detected.append(issue)
    return detected


def _case_laws_for_sentence(sentence: str, case_laws: list[str]) -> list[str]:
    """Map a sentence's actual citations onto this case's expected_laws ids."""
    cited = _extract_citations(sentence)
    out = []
    for law_id in case_laws:
        law, _, article = law_id.partition(":")
        for c in cited:
            c_law, _, c_article = c.partition(":")
            if c_law == law and (not article or c_article == article or c_article == _canonical_number(article)):
                out.append(law_id)
                break
    return out


class CaptureClient:
    """Sequential single-user HTTP driver; no concurrency, no shared sessions."""

    def __init__(self, base_url: str) -> None:
        self.base = base_url.rstrip("/")
        self.token: str | None = None

    def _post(self, path: str, payload: dict, timeout: float, raw: bool = False) -> tuple[int, Any]:
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        req = urllib.request.Request(
            self.base + path, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST"
        )
        try:
            resp = urllib.request.urlopen(req, timeout=timeout)
        except urllib.error.HTTPError as exc:
            return exc.code, exc.read().decode("utf-8", "replace") if raw else {}
        body = resp.read().decode("utf-8", "replace")
        return resp.status, body if raw else json.loads(body)

    def register_and_login(self) -> str:
        suffix = uuid.uuid4().hex[:8]
        username, password = f"capture_{suffix}", f"Capture-{suffix}-Pass1"
        status, _ = self._post("/api/auth/register", {"username": username, "password": password}, 60)
        if status != 200:
            raise RuntimeError(f"register failed: HTTP {status}")
        status, body = self._post("/api/auth/login", {"username": username, "password": password}, 60)
        if status != 200:
            raise RuntimeError(f"login failed: HTTP {status}")
        self.token = body["token"]
        return username

    def chat_stream(self, content: str, *, no_cache: bool, timeout: float) -> tuple[int, str]:
        status, body = self._post("/api/chat", {"content": content, "no_cache": no_cache}, timeout, raw=True)
        return status, body


def parse_sse(raw: str) -> list[dict]:
    events = []
    for line in raw.splitlines():
        if line.startswith("data: ") and line[6:] != "[DONE]":
            try:
                events.append(json.loads(line[6:]))
            except json.JSONDecodeError:
                events.append({"type": "_unparseable"})
    return events


def answer_chars(events: list[dict]) -> int:
    return sum(len(e["content"]) for e in events if isinstance(e.get("content"), str))


def is_agent_routed(events: list[dict]) -> bool:
    return any(e.get("type") == "agent_status" for e in events)


def deidentify(events: list[dict]) -> list[dict]:
    """Drop routing identifiers (conversation/run ids) from public events before
    any trace leaves the isolated machine; message content is synthetic case text."""
    clean = []
    for e in events:
        e = dict(e)
        for k in ("conversation_id", "run_id"):
            e.pop(k, None)
        clean.append(e)
    return clean


def query_db_tool_calls(container: str | None, execution_db_path: str = "/data/app.db") -> dict | None:
    """Read-only harness-side counting of THIS case's agent run.

    每次采集请求都新建会话（payload 不带 conversation_id），因此"最新会话"即本题：
    run 必须按 conversation_id 关联，而不是取全库最新 run（那会把无 run 的题错挂
    上一题的计数）。找不到 run 时如实返回 None（行内记 failed_db_lookup）。
    """
    if not container:
        return None
    import subprocess

    script = (
        "import sqlite3,json;con=sqlite3.connect('file:"
        + execution_db_path
        + "?mode=ro',uri=True);con.row_factory=sqlite3.Row;"
        "conv=con.execute('select id from conversations order by id desc limit 1').fetchone();"
        "r=con.execute('select id,status,state_version,last_error_code,degraded_reason from agent_runs "
        "where conversation_id=? order by created_at desc limit 1',(conv['id'],)).fetchone() if conv else None;"
        "print(json.dumps({'run':dict(r) if r else None,"
        "'tool_calls':con.execute(\"select count(*) from agent_steps where agent_run_id=? and decision='tool_call'\",(r['id'],)).fetchone()[0] if r else 0}))"
    )
    try:
        out = subprocess.check_output(
            ["docker", "exec", container, "python", "-c", script], text=True, timeout=30, stderr=subprocess.DEVNULL
        )
        return json.loads(out.strip().splitlines()[-1])
    except (subprocess.SubprocessError, json.JSONDecodeError, KeyError):
        return None


def capture(args: argparse.Namespace) -> int:
    protocol, _protocol_sha = load_capture_protocol(Path(args.protocol))
    controls = protocol.controls
    cases_bytes = Path(args.cases).read_bytes()
    cases_sha = hashlib.sha256(cases_bytes).hexdigest()
    if cases_sha != protocol.case_set_sha256 and not args.allow_case_set_mismatch:
        print(
            "FAIL: cases file sha256 != protocol.case_set_sha256 "
            f"({cases_sha} != {protocol.case_set_sha256}); official captures must bind the frozen set"
        )
        return 2
    cases = json.loads(cases_bytes)
    # v1.2 混合题集为 30 题；policy minimum_sample_size=20 为下限
    if not isinstance(cases, list) or (len(cases) < 20 and not args.allow_case_set_mismatch):
        print(f"FAIL: expected >=20 frozen cases, got {len(cases) if isinstance(cases, list) else type(cases)}")
        return 2

    trace_dir = Path(args.trace_dir)
    trace_dir.mkdir(parents=True, exist_ok=True)
    out_path = Path(args.out)
    if out_path.exists():
        print(f"FAIL: output exists (never overwrite): {out_path}")
        return 2

    client = CaptureClient(args.base_url)
    client.register_and_login()
    per_case_timeout = float(controls.timeout_seconds)
    deadline = time.monotonic() + controls.total_timeout_seconds

    rows: list[dict] = []
    for index, case in enumerate(cases):
        if time.monotonic() > deadline:
            for remaining in cases[index:]:
                rows.append(
                    {
                        "id": remaining["id"],
                        "status": "failed",
                        "failure_reasons": ["total_timeout_reached"],
                        "http_status": 0,
                        "error_codes": [],
                        "routed_agent": None,
                        "retry_attempts": 0,
                        "latency_ms": 0.0,
                        "content_chars": 0,
                        "answer": "",
                        "clarification": None,
                        "detected_issues_draft": [],
                        "claims_draft": [],
                        "tool_calls": 0,
                        "budget_exceeded": False,
                        "trace_ref": f"trace://{args.execution_id}/{remaining['id']}",
                    }
                )
            break
        case_id = case["id"]
        attempt = 0
        while True:
            started = time.perf_counter()
            try:
                http_status, raw = client.chat_stream(case["query"], no_cache=True, timeout=per_case_timeout + 10)
                latency_ms = (time.perf_counter() - started) * 1000
                events = parse_sse(raw)
                (trace_dir / f"{case_id}.sse.json").write_text(
                    json.dumps(deidentify(events), ensure_ascii=False, indent=1), encoding="utf-8"
                )
                break
            except (urllib.error.URLError, TimeoutError, OSError, http.client.HTTPException) as exc:
                # IncompleteRead/BadStatusLine 等分块传输中断不是 OSError 子类，
                # 但同属可重试传输失败（009 RAG 采集实证：第 24 题击穿循环）
                latency_ms = (time.perf_counter() - started) * 1000
                attempt += 1
                if attempt > controls.max_retries:
                    events, http_status = [], 0
                    (trace_dir / f"{case_id}.error.txt").write_text(
                        f"transport failure after retry: {exc}", encoding="utf-8"
                    )
                    break

        db = query_db_tool_calls(args.container) if args.mode == "agent" else None
        error_codes = [e.get("code") for e in events if e.get("type") == "error"]
        clar = next((e.get("prompt") for e in events if e.get("type") == "clarification"), None)
        answer = "".join(e["content"] for e in events if isinstance(e.get("content"), str))
        routed_agent = is_agent_routed(events)

        # 协议控制的 harness 侧独立执行（不信任应用自报）：
        # - 单题 90s：latency 实测超限即失败（+10s 只是传输容忍，记录仍按实测判）；
        # - max_tool_calls：隔离库 steps 计数超限即失败；
        # - max_output_tokens：按 quota_utils 的 1.5 字符/token 估算折算字符上限（记录估算语义）。
        failure_reasons: list[str] = []
        if http_status != 200:
            failure_reasons.append(f"http_{http_status}")
        if error_codes:
            failure_reasons.append("sse_error:" + ",".join(str(c) for c in error_codes))
        if latency_ms > controls.timeout_seconds * 1000:
            failure_reasons.append("case_timeout")
        chars_cap = int(controls.max_output_tokens * 1.5)
        output_over = len(answer) > chars_cap
        if output_over:
            failure_reasons.append("output_exceeds_protocol_cap")

        sentences = _split_sentences(answer)
        claims = []
        for sentence in sentences:
            laws = _case_laws_for_sentence(sentence, case.get("expected_laws", []))
            claims.append(
                {
                    "text": sentence,
                    "evidence_ids": laws,
                    "trace_ref": f"trace://{args.execution_id}/{case_id}",
                }
            )
        detected = _match_case_issues(
            case.get("issues", []),
            [answer, clar or ""],
        )
        db_failed_lookup = args.mode == "agent" and db is None
        if db_failed_lookup:
            failure_reasons.append("db_tool_count_unavailable")
        tool_calls = int(db["tool_calls"]) if db and db.get("run") else 0
        if tool_calls > controls.max_tool_calls:
            failure_reasons.append(f"tool_calls_{tool_calls}_exceeds_{controls.max_tool_calls}")
        budget_exceeded = bool(db and db.get("run") and db["run"].get("last_error_code") == "AGENT_BUDGET_EXCEEDED")

        rows.append(
            {
                "id": case_id,
                "status": "ok" if not failure_reasons else "failed",
                "failure_reasons": failure_reasons,
                "http_status": http_status,
                "error_codes": error_codes,
                "routed_agent": routed_agent,
                "retry_attempts": attempt,
                "latency_ms": round(latency_ms, 1),
                "content_chars": len(answer),
                "answer": answer,
                "clarification": clar,
                "detected_issues_draft": detected,
                "claims_draft": claims,
                "tool_calls": tool_calls,
                "budget_exceeded": budget_exceeded,
                "trace_ref": f"trace://{args.execution_id}/{case_id}",
            }
        )
        flag = "OK" if rows[-1]["status"] == "ok" else "FAILED(" + ";".join(failure_reasons) + ")"
        print(
            f"[{index + 1}/{len(cases)}] {case_id} {flag} http={http_status} chars={len(answer)} "
            f"agent_routed={routed_agent} tool_calls={tool_calls} retry={attempt}"
        )

    answers = {
        "schema_version": _ANSWERS_SCHEMA,
        "cases": [
            {
                "id": r["id"],
                "answer": {
                    "claims": r.get("claims_draft", []),
                    "detected_issues": r.get("detected_issues_draft", []),
                    "clarification": r.get("clarification"),
                    "trace_ref": r["trace_ref"],
                    "latency_ms": r.get("latency_ms", 0.0),
                    "tool_calls": r.get("tool_calls", 0),
                    "budget_exceeded": r.get("budget_exceeded", False),
                },
            }
            for r in rows
        ],
    }
    out_path.write_text(json.dumps(answers, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    rows_path = trace_dir / "rows.json"
    rows_path.write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    meta_path = trace_dir / "capture-meta.json"
    meta_path.write_text(
        json.dumps(
            {
                "mode": args.mode,
                "execution_id": args.execution_id,
                "case_set_sha256": cases_sha,
                "allow_case_set_mismatch": args.allow_case_set_mismatch,
                "controls": {
                    "timeout_seconds": controls.timeout_seconds,
                    "total_timeout_seconds": controls.total_timeout_seconds,
                    "max_retries": controls.max_retries,
                    "concurrency": controls.concurrency,
                    "cache_policy": controls.cache_policy,
                    "max_output_tokens": controls.max_output_tokens,
                    "max_tool_calls": controls.max_tool_calls,
                },
            },
            ensure_ascii=False,
            indent=1,
        )
        + "\n",
        encoding="utf-8",
    )

    failed = [r["id"] for r in rows if r.get("status") != "ok"]
    skipped = [r["id"] for r in rows if r.get("failure_reasons") == ["total_timeout_reached"]]
    print(f"captured {len(rows)} rows -> {out_path}; failed={len(failed)} skipped={len(skipped)}")
    if failed:
        print("failed case ids:", failed)
    if skipped:
        print("BLOCKED: total timeout reached; rows skipped:", skipped)
        return 3
    return 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Isolated dual-run capture adapter (Phase C).")
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--mode", required=True, choices=["existing_rag", "agent"])
    parser.add_argument("--cases", required=True)
    parser.add_argument("--protocol", required=True)
    parser.add_argument("--execution-id", required=True, help="opaque batch id, no paths/user ids")
    parser.add_argument(
        "--container", default=None, help="isolated container name for read-only DB counting (agent mode)"
    )
    parser.add_argument("--trace-dir", required=True, help="isolated directory for raw traces")
    parser.add_argument("--out", required=True, help="draft legal-agent-eval-answers/v1 path (must not exist)")
    parser.add_argument(
        "--allow-case-set-mismatch",
        action="store_true",
        help="dry-run only: permit a partial/temp case set that does not match the frozen case_set_sha256",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    return capture(parse_args(argv))


if __name__ == "__main__":
    sys.exit(main())
