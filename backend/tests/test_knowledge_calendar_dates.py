"""Calendar contract tests; can run outside repository conftest/model/DB setup."""

import os
import socket
import sys
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

SOURCE = Path(os.environ.get("KNOWLEDGE_SCHEMA_ROOT", str(Path(__file__).resolve().parents[1]))).resolve()
sys.path.insert(0, str(SOURCE))


from schemas import KnowledgeAddIn  # noqa: E402

FIELDS = ("effective_from", "effective_to", "promulgated_at", "reviewed_at")


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    real_connect = socket.socket.connect
    real_connect_ex = socket.socket.connect_ex

    def checked_connect(sock, address):
        if not isinstance(address, tuple) or address[0] not in {"127.0.0.1", "::1", "localhost"}:
            raise RuntimeError("No external network is permitted in schema-only tests")
        return real_connect(sock, address)

    def checked_connect_ex(sock, address):
        if not isinstance(address, tuple) or address[0] not in {"127.0.0.1", "::1", "localhost"}:
            raise RuntimeError("No external network is permitted in schema-only tests")
        return real_connect_ex(sock, address)

    monkeypatch.setattr(socket.socket, "connect", checked_connect)
    monkeypatch.setattr(socket.socket, "connect_ex", checked_connect_ex)


@pytest.fixture
def client():
    app = FastAPI()

    @app.post("/schema-only")
    def validate_only(payload: KnowledgeAddIn):
        return {"effective_from": payload.effective_from}

    with TestClient(app) as test_client:
        yield test_client


@pytest.mark.parametrize("field", FIELDS)
@pytest.mark.parametrize(
    "value",
    (
        "2026-13-45",
        "2026-02-29",
        "2026-04-31",
        "1900-02-29",
        "0000-01-01",
        "2026-1-01",
        " 2026-01-01",
        "２０２６-０１-０１",
    ),
)
def test_rejects_invalid_calendar_dates(field, value):
    with pytest.raises(ValidationError):
        KnowledgeAddIn(title="法规", content="正文", **{field: value})


@pytest.mark.parametrize("field", FIELDS)
@pytest.mark.parametrize("value", ("2026-01-01", "2024-02-29", "2000-02-29", "9999-12-31"))
def test_accepts_valid_calendar_dates_without_changing_string(field, value):
    model = KnowledgeAddIn(title="法规", content="正文", **{field: value})
    assert getattr(model, field) == value


@pytest.mark.parametrize("field", FIELDS)
@pytest.mark.parametrize("value", (None, ""))
def test_preserves_optional_empty_date(field, value):
    model = KnowledgeAddIn(title="一般知识", content="正文", **{field: value})
    assert getattr(model, field) == value


def test_article_still_requires_effective_date():
    with pytest.raises(ValidationError):
        KnowledgeAddIn(title="法规", article="第一条", content="正文")


def test_version_period_still_rejects_reverse_interval():
    with pytest.raises(ValidationError):
        KnowledgeAddIn(title="法规", content="正文", effective_from="2026-10-04", effective_to="2026-10-03")


def test_same_day_interval_remains_allowed():
    model = KnowledgeAddIn(
        title="法规", article="第一条", content="正文", effective_from="2026-10-04", effective_to="2026-10-04"
    )
    assert model.effective_from == model.effective_to


@pytest.mark.parametrize("field", FIELDS)
@pytest.mark.parametrize("value", ("2026-13-45", "2026-02-29", "1900-02-29"))
def test_http_contract_rejects_invalid_calendar_dates(client, field, value):
    response = client.post("/schema-only", json={"title": "法规", "content": "正文", field: value})
    assert response.status_code == 422


def test_http_contract_preserves_valid_leap_day(client):
    response = client.post(
        "/schema-only",
        json={
            "title": "法规",
            "article": "第一条",
            "content": "正文",
            "effective_from": "2024-02-29",
        },
    )
    assert response.status_code == 200
    assert response.json()["effective_from"] == "2024-02-29"
