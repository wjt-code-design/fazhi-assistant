"""P3 transport guard: whitelist + call counting + redirect refusal + no implicit retries.

Task book F1 bullet 4: 假传输先证明 —— 白名单、未知端点拒绝、调用/重试计数、
响应脱敏、限次拒绝可红。本文件提供守卫与一份自检（自检只打回环，不碰真实供应商）。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from urllib.parse import urlparse

import httpx


class GuardRefusal(RuntimeError):
    def __init__(self, reason: str, url: str) -> None:
        super().__init__("%s: %s" % (reason, url))
        self.reason = reason


@dataclass
class TransportGuard:
    allowed: dict[str, tuple[str, ...]]          # host -> allowed path prefixes
    max_calls: int | None = None
    calls: list[str] = field(default_factory=list)
    refused: list[tuple[str, str]] = field(default_factory=list)

    def check(self, url: str) -> None:
        p = urlparse(url)
        host = p.netloc
        prefixes = self.allowed.get(host)
        if prefixes is None:
            self.refused.append(("host_not_whitelisted", url))
            raise GuardRefusal("host_not_whitelisted", url)
        if not any(p.path.startswith(x) for x in prefixes):
            self.refused.append(("path_not_whitelisted", url))
            raise GuardRefusal("path_not_whitelisted", url)

    def enforce(self, url: str) -> None:
        """Validate, then count the request as actually sent. Budget is checked before send."""
        self.check(url)
        if self.max_calls is not None and len(self.calls) >= self.max_calls:
            self.refused.append(("call_budget_exhausted", url))
            raise GuardRefusal("call_budget_exhausted", url)
        self.calls.append(url)

    def post(self, url: str, **kw) -> httpx.Response:
        self.enforce(url)
        # follow_redirects=False：任何重定向都回到 check()，越界即拒（F1 要求）
        with httpx.Client(timeout=kw.pop("timeout", 30.0), follow_redirects=False) as c:
            r = c.post(url, **kw)
        if r.is_redirect:
            self.check(str(r.headers.get("location", "")))
        return r


def install(guard: TransportGuard) -> None:
    """把守卫接到 httpx 的真正发信点，覆盖产品自己建的 client（含 SDK 内部重试与重定向跟随）。

    llm_registry.py:400 硬编 max_retries=3，本轮不改产品默认值，所以隐式重试不是被
    “关掉”而是被“数出来”：每一次上线都过 enforce()，超出预算直接 GuardRefusal。
    """

    def _wrap(cls):
        orig = cls._send_single_request
        _ORIG.append((cls, orig))

        def patched(self, request):
            # ASGITransport 不出进程，不属于外发面；守卫管的是真正上线的字节
            if type(self._transport).__name__ != "ASGITransport":
                guard.enforce(str(request.url))
            return orig(self, request)

        cls._send_single_request = patched

    _wrap(httpx.Client)
    _wrap(httpx.AsyncClient)


_ORIG: list[tuple[type, object]] = []


def uninstall() -> None:
    for cls, orig in _ORIG:
        cls._send_single_request = orig
    _ORIG.clear()


def _self_test() -> int:
    import json
    import threading
    from http.server import BaseHTTPRequestHandler, HTTPServer

    hits = {"n": 0}

    class H(BaseHTTPRequestHandler):
        def do_POST(self):  # noqa: N802
            hits["n"] += 1
            body = json.dumps({"ok": True}).encode()
            if self.path.startswith("/redirect"):
                self.send_response(302)
                self.send_header("Location", "https://example.com/elsewhere")
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *a):  # 静音
            pass

    srv = HTTPServer(("127.0.0.1", 0), H)
    port = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    host = "127.0.0.1:%d" % port
    ok_url = "http://%s/v1/chat/completions" % host

    results = []

    # 正例：白名单内 → 通过且计数 +1
    g = TransportGuard(allowed={host: ("/v1/",)}, max_calls=2)
    r = g.post(ok_url, json={"x": 1})
    results.append(("allowed_passes", r.status_code == 200 and len(g.calls) == 1))
    results.append(("server_saw_one_hit", hits["n"] == 1))

    # 负例①：非白名单 host → 拒且不发出
    before = hits["n"]
    try:
        g.post("https://example.com/v1/chat/completions", json={})
        results.append(("unknown_host_refused", False))
    except GuardRefusal as e:
        results.append(("unknown_host_refused", e.reason == "host_not_whitelisted" and hits["n"] == before))

    # 负例②：白名单 host 但路径越界 → 拒
    try:
        g.post("http://%s/other/path" % host, json={})
        results.append(("unknown_path_refused", False))
    except GuardRefusal as e:
        results.append(("unknown_path_refused", e.reason == "path_not_whitelisted"))

    # 负例③：重定向目标越界 → 拒（Location 指到 example.com）
    # 注意：/redirect 本身必须先在白名单内，否则会在"发请求之前"就被拒（那是另一条判据）。
    g3 = TransportGuard(allowed={host: ("/v1/", "/redirect")})
    try:
        g3.post("http://%s/redirect" % host, json={})
        results.append(("redirect_refused", False))
    except GuardRefusal as e:
        results.append(("redirect_refused", e.reason == "host_not_whitelisted"))

    # 负例④：调用预算耗尽 → 拒（max_calls=2，已用 1，再来一次成功，第三次拒）
    g2 = TransportGuard(allowed={host: ("/v1/",)}, max_calls=2)
    g2.post(ok_url, json={})
    g2.post(ok_url, json={})
    try:
        g2.post(ok_url, json={})
        results.append(("budget_refused", False))
    except GuardRefusal as e:
        results.append(("budget_refused", e.reason == "call_budget_exhausted"))

    # 负例⑤⑥⑦：install() 接到产品自建 client 的那条腿
    gi = TransportGuard(allowed={host: ("/v1/",)})
    install(gi)
    try:
        r = httpx.post(ok_url, json={"x": 1}, timeout=10)
        results.append(("installed_client_passes", r.status_code == 200 and len(gi.calls) == 1))
        before = hits["n"]
        try:
            httpx.post("https://example.com/v1/chat/completions", json={}, timeout=10)
            results.append(("installed_unknown_host_refused", False))
        except GuardRefusal as e:
            results.append(("installed_unknown_host_refused", e.reason == "host_not_whitelisted" and hits["n"] == before))
        gb = TransportGuard(allowed={host: ("/v1/",)}, max_calls=1)
        uninstall()
        install(gb)
        httpx.post(ok_url, json={"x": 1}, timeout=10)
        try:
            httpx.post(ok_url, json={"x": 1}, timeout=10)
            results.append(("installed_budget_refused", False))
        except GuardRefusal as e:
            results.append(("installed_budget_refused", e.reason == "call_budget_exhausted"))
    finally:
        uninstall()
    results.append(("uninstall_restores", httpx.Client._send_single_request.__name__ != "patched"))

    srv.shutdown()
    ok = all(v for _, v in results)
    for name, val in results:
        print("  %-22s %s" % (name, "PASS" if val else "FAIL"))
    print("VERDICT=" + ("GUARD_CONTROLS_HOLD" if ok else "GUARD_CONTROLS_BROKEN"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(_self_test())
