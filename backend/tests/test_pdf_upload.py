"""PDF parser and both upload boundaries; no real knowledge-store writes or LLM calls."""

from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

import knowledge_service as ks
import main


def _pdf_with_text(content: bytes) -> bytes:
    """Build a tiny PDF from fixed PDF syntax, independently of pypdf's writer."""
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 300] "
        b"/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
        b"<< /Length " + str(len(content)).encode() + b" >>\nstream\n" + content + b"\nendstream",
        b"<< /Type /Font /Subtype /Type0 /BaseFont /STSong-Light /Encoding /UniGB-UCS2-H /DescendantFonts [6 0 R] >>",
        b"<< /Type /Font /Subtype /CIDFontType0 /BaseFont /STSong-Light "
        b"/CIDSystemInfo << /Registry (Adobe) /Ordering (GB1) /Supplement 4 >> >>",
    ]
    raw = b"%PDF-1.4\n"
    offsets = [0]
    for number, obj in enumerate(objects, 1):
        offsets.append(len(raw))
        raw += f"{number} 0 obj\n".encode() + obj + b"\nendobj\n"
    xref = len(raw)
    raw += f"xref\n0 {len(offsets)}\n0000000000 65535 f \n".encode()
    raw += b"".join(f"{offset:010d} 00000 n \n".encode() for offset in offsets[1:])
    return raw + f"trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()


# UTF-16BE bytes for 劳动法第四十四条, a fixed independent extraction oracle.
CHINESE_PDF = _pdf_with_text(b"BT /F1 12 Tf 20 200 Td <52b352a86cd57b2c56db534156db6761> Tj ET")
EMPTY_PDF = _pdf_with_text(b"")


@pytest.fixture
def client(monkeypatch):
    user = SimpleNamespace(id=1, username="pdf-test-admin", role="admin")
    monkeypatch.setitem(main.app.dependency_overrides, main.get_current_user, lambda: user)
    monkeypatch.setitem(main.app.dependency_overrides, main.require_admin, lambda: user)
    with TestClient(main.app, raise_server_exceptions=False) as test_client:
        yield test_client


def test_chinese_pdf_extraction():
    assert ks.parse_upload_or_raise("sample.pdf", CHINESE_PDF) == (".pdf", "劳动法第四十四条")


@pytest.mark.parametrize("route", ["/api/chat/file", "/api/admin/knowledge/upload"])
@pytest.mark.parametrize(
    ("raw", "expected_detail"),
    [(EMPTY_PDF, "未从文件中识别到文字"), (b"%PDF-1.4\nbroken", "PDF 文件损坏或无法解析")],
    ids=["empty", "corrupt"],
)
def test_invalid_pdf_is_client_error(client, route, raw, expected_detail):
    response = client.post(route, files={"file": ("sample.pdf", raw, "application/pdf")})
    assert response.status_code == 400, response.text
    assert expected_detail in response.json()["detail"]


def test_chat_pdf_returns_extracted_text(client):
    response = client.post("/api/chat/file", files={"file": ("sample.pdf", CHINESE_PDF, "application/pdf")})
    assert response.status_code == 200, response.text
    assert response.json()["text"] == "劳动法第四十四条"


def test_admin_pdf_passes_extracted_text_to_store(client, monkeypatch):
    received = []
    monkeypatch.setattr(ks, "add_text", lambda text, **kwargs: received.append(text) or 1)
    monkeypatch.setattr(main, "retrieve_for_test", lambda *args, **kwargs: [])
    monkeypatch.setattr(main, "log_audit", lambda *args, **kwargs: None)
    response = client.post(
        "/api/admin/knowledge/upload", files={"file": ("sample.pdf", CHINESE_PDF, "application/pdf")}
    )
    assert response.status_code == 200, response.text
    assert received == ["劳动法第四十四条"]
