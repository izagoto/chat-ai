import io
import json

from fastapi.testclient import TestClient

from app.api.chat import _wants_document_context
from app.main import app
from app.services.citations import format_location, sources_from_hits
from app.services.document_store import DocumentChunk
from tests.conftest import wait_until_ready

client = TestClient(app)


def test_casual_messages_skip_rag():
    assert _wants_document_context("hai") is False
    assert _wants_document_context("hello") is False
    assert _wants_document_context("chating") is False


def test_document_questions_use_rag():
    assert _wants_document_context("Ringkas dokumen yang sudah saya unggah") is True
    assert _wants_document_context("account 12345") is True
    assert _wants_document_context("perbedaan samsung dan iphone apa?") is True


def test_format_location_labels():
    assert format_location({"type": "pdf_page", "page": 3}) == "p. 3"
    assert format_location({"type": "excel_sheet", "sheet": "Sales", "row_start": 1, "row_end": 50}) == "Sales · rows 1–50"
    assert format_location({"type": "csv_rows", "row_start": 1, "row_end": 20}) == "rows 1–20"
    assert format_location({"type": "docx_section", "heading": "Incident summary", "paragraph_start": 1, "paragraph_end": 4}) == "Incident summary"
    assert format_location({"type": "docx_table", "index": 2}) == "table 2"
    assert format_location({"type": "url", "url": "https://example.com/a"}) == "example.com"
    assert format_location({"type": "full_file"}) is None


def test_sources_from_hits_dedupes_file_location():
    chunk_a = DocumentChunk(
        chunk_id="a",
        collection_id="default",
        document_id="d1",
        source_file="report.pdf",
        artifact_type="pdf",
        text="alpha",
        chunk_index=0,
        location={"type": "pdf_page", "page": 2},
    )
    chunk_b = DocumentChunk(
        chunk_id="b",
        collection_id="default",
        document_id="d1",
        source_file="report.pdf",
        artifact_type="pdf",
        text="beta",
        chunk_index=1,
        location={"type": "pdf_page", "page": 2},
    )
    sources = sources_from_hits([(chunk_a, 0.9), (chunk_b, 0.8)])
    assert len(sources) == 1
    assert sources[0].file == "report.pdf"
    assert sources[0].location == "p. 2"


def test_chat_returns_citations(tmp_path, monkeypatch):
    monkeypatch.setattr("app.services.document_store.settings.documents_path", str(tmp_path / "documents"))
    monkeypatch.setattr("app.services.document_store.settings.rag_use_embeddings", False)

    class FakeOllama:
        async def chat(self, messages, temperature=0.5):
            return "Account 12345 is listed in the uploaded note."

    monkeypatch.setattr("app.api.chat.ollama_client", FakeOllama())
    files = {
        "file": (
            "pay.json",
            io.BytesIO(json.dumps({"note": "transfer to account 12345"}).encode()),
            "application/json",
        )
    }
    up = client.post("/v1/documents", files=files)
    assert up.status_code == 200
    wait_until_ready(client, up.json()["document"]["document_id"])

    res = client.post(
        "/v1/chat",
        json={"message": "account 12345", "session_id": "cite-chat", "use_documents": True},
    )
    assert res.status_code == 200, res.text
    sources = res.json()["sources"]
    assert sources
    assert sources[0]["file"] == "pay.json"


def test_casual_chat_has_no_citations(monkeypatch):
    class FakeOllama:
        async def chat(self, messages, temperature=0.5):
            return "Halo!"

    monkeypatch.setattr("app.api.chat.ollama_client", FakeOllama())
    res = client.post("/v1/chat", json={"message": "hai", "session_id": "cite-hi", "use_documents": True})
    assert res.status_code == 200, res.text
    assert res.json()["sources"] == []
