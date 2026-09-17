"""G-4 fault-injection 辅助：OpenAI 兼容 mock LLM 端点，一律返回 HTTP 500。

用于 S6 fail-closed 实证（技术故障 → Agent 必须拒答而非硬答）。
用法：python scripts/mock_llm_500.py 8091
"""

from __future__ import annotations

import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class Handler(BaseHTTPRequestHandler):
    def _send(self) -> None:
        body = json.dumps({"error": {"type": "server_error", "message": "SIMULATED LLM FAILURE"}}).encode("utf-8")
        self.send_response(500)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length") or 0)
        if length:
            self.rfile.read(length)
        self._send()

    def do_GET(self) -> None:  # noqa: N802
        self._send()

    def log_message(self, *args: object) -> None:  # silence
        pass


def main() -> int:
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8091
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()
    return 0


if __name__ == "__main__":
    sys.exit(main())
