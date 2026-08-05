"""评测共享 HTTP 客户端：登录 + SSE chat + 429 限流退避（code-review S2/P1-6）。

消除 eval_redteam/consistency/relevance/hallucination/negative_run 各自内联的
_login/_chat 逐字重复（S2）；补上 spec 要求的 429 退避——撞限流按 5/10/20/40/60s
递增等待重试，最多 5 次，替代只 sleep(1.2) 无重试的现状（P1-6）。

注意：urllib 读 SSE 首帧有 ~2s 假象（http.client readline），本模块只取内容不计时，
时延口径一律用 node 脚本（bench_latency.mjs）。
"""

import json
import os
import time
import urllib.error
import urllib.request

BASE = os.getenv("API_BASE", "http://localhost:8000")

# 429 递增退避间隔（秒）：撞 60/min 限流时等待后再试，超次向上抛
_429_DELAYS = (5, 10, 20, 40, 60)
_MAX_429_RETRIES = 5


def _retry_429(fn):
    """包裹调用：HTTPError 429 → 递增等待重试；其余异常原样抛。"""
    for attempt in range(_MAX_429_RETRIES):
        try:
            return fn()
        except urllib.error.HTTPError as e:
            if e.code != 429:
                raise
            if attempt >= len(_429_DELAYS) - 1:
                raise
            wait = _429_DELAYS[attempt]
            print(f"  ⏳ 429 限流，{wait}s 后重试（{attempt + 1}/{_MAX_429_RETRIES}）", flush=True)
            time.sleep(wait)
    raise RuntimeError("429 退避重试次数耗尽")  # 理论不可达，防御 linter


def login() -> str:
    """管理员登录，返回 JWT。"""
    def _do():
        req = urllib.request.Request(
            BASE + "/api/auth/login",
            data=json.dumps({"username": os.getenv("ADMIN_USERNAME", "admin"), "password": os.getenv("ADMIN_PASSWORD", "")}).encode(),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())["token"]
    return _retry_429(_do)


def chat(token: str, q: str, timeout: int = 180, no_cache: bool = False) -> str:
    """调 chat API（SSE），拼 content 返回。带 429 退避。no_cache 绕过 QA/答案缓存（评测用）。"""
    body = {"conversation_id": None, "question": q, "content": q, "no_cache": no_cache}

    def _do():
        req = urllib.request.Request(
            BASE + "/api/chat",
            data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
        )
        out = ""
        with urllib.request.urlopen(req, timeout=timeout) as r:
            for line in r:
                line = line.decode().strip()
                if not line.startswith("data: "):
                    continue
                raw = line[6:]
                if raw == "[DONE]":
                    break
                try:
                    d = json.loads(raw)
                except Exception:
                    continue
                if isinstance(d, dict) and d.get("content"):
                    out += d["content"]
        return out

    return _retry_429(_do)


def post_json(path: str, body: dict, token: str | None = None, timeout: int = 120) -> dict:
    """非 SSE POST（登录/管理端）。带 429 退避。"""
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    def _do():
        req = urllib.request.Request(BASE + path, data=json.dumps(body).encode(), headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())

    return _retry_429(_do)
