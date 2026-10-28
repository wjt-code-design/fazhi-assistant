"""Exercise the real upload limiter, which conftest normally disables."""

from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

import main


@pytest.mark.parametrize(("route", "limit"), [("/api/chat/file", 20), ("/api/admin/knowledge/upload", 10)])
def test_upload_limit_returns_429(monkeypatch, route, limit):
    user = SimpleNamespace(id=1, username="limit-test-admin", role="admin")
    monkeypatch.setitem(main.app.dependency_overrides, main.get_current_user, lambda: user)
    monkeypatch.setitem(main.app.dependency_overrides, main.require_admin, lambda: user)
    monkeypatch.setattr(main.limiter, "enabled", True)
    main.limiter.reset()
    try:
        with TestClient(main.app) as client:
            # Rejected at file validation: no model or vector-store writes, but the
            # real route decorator must still count each authenticated request.
            statuses = [
                client.post(route, files={"file": ("bad.exe", b"invalid", "application/octet-stream")}).status_code
                for _ in range(limit + 1)
            ]
        assert statuses == [400] * limit + [429]
    finally:
        main.limiter.reset()
