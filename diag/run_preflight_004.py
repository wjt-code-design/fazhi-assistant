"""004 候选四项隔离预检。

phase1（AGENT_ENABLED=false）：Existing RAG smoke（同冻结题）+ 图片端到端 + 语音端到端
phase2（AGENT_ENABLED=true/100%）：Agent smoke（同冻结题）

产物写 diag/preflight-004/。断言均独立于实现（SSE 形状/HTTP 码/答案内容特征）。
"""
import base64
import io
import json
import math
import struct
import sys
import urllib.error
import urllib.request
import uuid
import wave
from pathlib import Path

BASE = "http://127.0.0.1:18003"
OUT = Path(__file__).resolve().parent / "preflight-004"
OUT.mkdir(parents=True, exist_ok=True)
QUERY = "2020年借款约定2021年还，至今未还，2026年还能起诉吗？"


def post(path, payload=None, token=None, files=None, timeout=180):
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = None
    if files:
        boundary = uuid.uuid4().hex
        field, fname, blob = files
        body = (
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"{field}\"; filename=\"{fname}\"\r\n"
            f"Content-Type: application/octet-stream\r\n\r\n"
        ).encode() + blob + f"\r\n--{boundary}--\r\n".encode()
        headers["Content-Type"] = f"multipart/form-data; boundary={boundary}"
        data = body
    else:
        headers["Content-Type"] = "application/json"
        data = json.dumps(payload).encode()
    req = urllib.request.Request(BASE + path, data=data, headers=headers, method="POST")
    return urllib.request.urlopen(req, timeout=timeout)


def png_solid(w, h, rgb):
    import zlib

    def chunk(t, d):
        c = t + d
        return struct.pack(">I", len(d)) + c + struct.pack(">I", zlib.crc32(c) & 0xffffffff)
    raw = b"".join(b"\x00" + bytes(rgb) * w for _ in range(h))
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw))
        + chunk(b"IEND", b"")
    )


def tiny_wav():
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        for i in range(9600):
            w.writeframesraw(struct.pack("<h", int(12000 * math.sin(2 * math.pi * 440 * i / 16000))))
    return buf.getvalue()


def auth():
    sfx = uuid.uuid4().hex[:8]
    u, p = f"pf4_{sfx}", f"Pf4-{sfx}-Pass1"
    post("/api/auth/register", {"username": u, "password": p}, timeout=60)
    r = post("/api/auth/login", {"username": u, "password": p}, timeout=60)
    return json.loads(r.read().decode())["token"]


def sse_answer(raw: str):
    """解析 SSE：Agent 风格 {"type":"token","content":...} 与 fast path 裸 {"content":...} 都计入。"""
    events = []
    for line in raw.splitlines():
        if line.startswith("data: ") and line[6:] != "[DONE]":
            try:
                events.append(json.loads(line[6:]))
            except json.JSONDecodeError:
                pass
    types = [e.get("type") for e in events]
    chars = sum(len(e.get("content", "")) for e in events if isinstance(e.get("content"), str))
    return events, types, chars


def main():
    phase = sys.argv[1]
    token = auth()
    results = {}

    if phase == "phase1":
        # 1) Existing RAG smoke（同冻结题；Agent 关闭 → 必须 fast path）
        r = post("/api/chat", {"content": QUERY, "no_cache": True}, token=token)
        raw = r.read().decode("utf-8")
        (OUT / "sse-rag.txt").write_text(raw, encoding="utf-8")
        events, types, chars = sse_answer(raw)
        results["rag_smoke"] = {
            "http": r.status, "types_head": types[:4], "content_chars": chars,
            "pass": r.status == 200 and chars > 200 and "agent_status" not in types,
        }

        # 2) 图片端到端（64x64 纯红，问题断言颜色词）
        img = base64.b64encode(png_solid(64, 64, (255, 0, 0))).decode()
        r = post("/api/chat", {"content": "这张图片主要是什么颜色？只回答颜色词。", "image": f"data:image/png;base64,{img}", "no_cache": True}, token=token)
        raw = r.read().decode("utf-8")
        (OUT / "sse-image.txt").write_text(raw, encoding="utf-8")
        events, types, chars = sse_answer(raw)
        answer = "".join(e.get("content", "") for e in events if isinstance(e.get("content"), str))
        errors = [e for e in events if e.get("type") == "error"]
        results["image_e2e"] = {
            "http": r.status, "answer_head": answer[:120], "content_chars": len(answer),
            "pass": r.status == 200 and not errors and len(answer) > 2 and ("红" in answer),
        }

        # 3) 语音端到端（0.6s 440Hz 正弦 → 转写非空即通过；内容不作强断言）
        r = post("/api/chat/transcribe", files=("file", "probe.wav", tiny_wav()), token=token)
        body = json.loads(r.read().decode())
        (OUT / "transcribe.json").write_text(json.dumps(body, ensure_ascii=False), encoding="utf-8")
        results["voice_e2e"] = {
            "http": r.status, "text": str(body.get("text", ""))[:60],
            "pass": r.status == 200 and len(str(body.get("text", ""))) > 0,
        }

    elif phase == "phase2":
        # 4) Agent smoke（同冻结题；Agent 100% → 结构化反问或完成，禁止 error）
        r = post("/api/chat", {"content": QUERY}, token=token)
        raw = r.read().decode("utf-8")
        (OUT / "sse-agent.txt").write_text(raw, encoding="utf-8")
        events, types, chars = sse_answer(raw)
        errors = [e.get("code") for e in events if e.get("type") == "error"]
        clar = [e for e in events if e.get("type") == "clarification"]
        finals = [e for e in events if e.get("type") == "final"]
        results["agent_smoke"] = {
            "http": r.status, "types": types, "error_codes": errors,
            "clarification": bool(clar), "final": bool(finals), "content_chars": chars,
            "pass": r.status == 200 and not errors and (clar or (finals and chars > 0)),
        }

    (OUT / f"summary-{phase}.json").write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
    for name, res in results.items():
        print(name, "->", "PASS" if res["pass"] else "FAIL", json.dumps({k: v for k, v in res.items() if k != "pass"}, ensure_ascii=False)[:220])
    sys.exit(0 if all(r["pass"] for r in results.values()) else 1)


if __name__ == "__main__":
    main()
