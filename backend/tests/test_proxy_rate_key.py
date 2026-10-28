"""Client-supplied proxy headers must not select rate-limit buckets."""

import pytest
from fastapi.testclient import TestClient
from starlette.requests import Request
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

import main


@pytest.mark.parametrize("header", ["CF-Connecting-IP", "X-Forwarded-For"])
def test_rotating_proxy_headers_cannot_bypass_login_limit(monkeypatch, header):
    monkeypatch.setattr(main.limiter, "enabled", True)
    main.limiter.reset()
    try:
        with TestClient(main.app) as client:
            statuses = [
                client.post(
                    "/api/auth/login",
                    json={"username": "proxy-missing-user", "password": "incorrect"},
                    headers={header: f"198.51.100.{i + 1}"},
                ).status_code
                for i in range(11)
            ]
        assert statuses == [401] * 10 + [429]
    finally:
        main.limiter.reset()


@pytest.mark.parametrize(
    ("peer", "expected"),
    [("127.0.0.1", "198.51.100.9"), ("203.0.113.8", "203.0.113.8")],
)
def test_only_server_trusted_proxy_can_supply_client_address(peer, expected):
    import asyncio

    observed = []

    async def app(scope, receive, send):
        observed.append(main._rate_key(Request(scope)))

    scope = {
        "type": "http",
        "client": (peer, 12345),
        "headers": [(b"x-forwarded-for", b"198.51.100.9"), (b"cf-connecting-ip", b"192.0.2.99")],
    }
    asyncio.run(ProxyHeadersMiddleware(app, trusted_hosts="127.0.0.1")(scope, None, None))
    assert observed == [expected]


def test_missing_client_uses_one_unknown_bucket():
    assert main._rate_key(Request({"type": "http", "headers": []})) == "unknown"
