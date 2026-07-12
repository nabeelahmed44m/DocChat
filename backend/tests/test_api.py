"""API integration tests using FastAPI's TestClient.

These exercise the real upload → background-ingest → poll → ask lifecycle end to
end, plus the error paths the mobile client depends on.
"""

from __future__ import annotations

import io

from tests.conftest import wait_until_ready

CONTRACT_TEXT = (
    "SERVICE AGREEMENT\n\n"
    "This Agreement shall commence on February 1, 2024. Either party may terminate "
    "this Agreement by providing sixty (60) days written notice. The monthly "
    "retainer is $12,500, governed by the laws of Delaware.\n"
)


def _upload(client, name="contract.txt", content: bytes | None = None, ctype="text/plain"):
    content = content if content is not None else CONTRACT_TEXT.encode()
    return client.post(
        "/documents",
        files={"file": (name, io.BytesIO(content), ctype)},
    )


def test_health_reports_capabilities(client):
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert ".pdf" in body["supported_extensions"]
    assert ".txt" in body["supported_extensions"]
    assert "ocr_available" in body


def test_upload_returns_queued_then_becomes_ready(client):
    resp = _upload(client)
    assert resp.status_code == 202
    doc = resp.json()
    # The background worker may already have picked the job up; both in-flight
    # states are valid immediately after upload.
    assert doc["status"] in ("queued", "processing")
    assert doc["filename"] == "contract.txt"

    final = wait_until_ready(client, doc["id"])
    assert final["status"] == "ready"
    assert final["stats"]["sentences"] > 0


def test_full_ask_flow(client):
    doc_id = _upload(client).json()["id"]
    assert wait_until_ready(client, doc_id)["status"] == "ready"

    resp = client.post(
        f"/documents/{doc_id}/ask",
        json={"question": "What is the termination notice period?", "top_k": 3},
    )
    assert resp.status_code == 200
    answers = resp.json()["answers"]
    assert answers
    assert any("sixty (60) days" in a["text"] for a in answers)
    top = answers[0]
    assert top["page_number"] >= 1
    assert top["citation"].startswith("page ")


def test_how_much_question_boosts_money(client):
    doc_id = _upload(client).json()["id"]
    wait_until_ready(client, doc_id)
    resp = client.post(
        f"/documents/{doc_id}/ask", json={"question": "How much is the retainer?"}
    )
    answers = resp.json()["answers"]
    assert any("$12,500" in a["text"] for a in answers)


def test_ask_before_ready_returns_409(client, monkeypatch):
    # Force ingestion to never run so the doc stays queued.
    from app.services.ingestion import IngestionService

    monkeypatch.setattr(IngestionService, "submit", lambda self, doc_id: None)
    doc_id = _upload(client).json()["id"]
    resp = client.post(f"/documents/{doc_id}/ask", json={"question": "hi"})
    assert resp.status_code == 409


def test_unsupported_format_rejected(client):
    resp = _upload(client, name="malware.exe", content=b"MZ", ctype="application/octet-stream")
    assert resp.status_code == 415
    assert resp.json()["detail"]


def test_empty_upload_rejected(client):
    resp = _upload(client, content=b"")
    assert resp.status_code == 400


def test_list_and_get_and_delete(client):
    doc_id = _upload(client).json()["id"]
    wait_until_ready(client, doc_id)

    listing = client.get("/documents").json()
    assert listing["count"] >= 1
    assert any(d["id"] == doc_id for d in listing["documents"])

    assert client.get(f"/documents/{doc_id}").status_code == 200

    assert client.delete(f"/documents/{doc_id}").status_code == 204
    assert client.get(f"/documents/{doc_id}").status_code == 404


def test_ask_unknown_document_404(client):
    resp = client.post("/documents/does-not-exist/ask", json={"question": "hi"})
    assert resp.status_code == 404


def test_summary_endpoint(client):
    doc_id = _upload(client).json()["id"]
    wait_until_ready(client, doc_id)
    resp = client.get(f"/documents/{doc_id}/summary?max_sentences=3")
    assert resp.status_code == 200
    body = resp.json()
    assert body["method"] == "textrank+mmr"
    assert 0 < len(body["sentences"]) <= 3


def test_keypoints_endpoint(client):
    doc_id = _upload(client).json()["id"]
    wait_until_ready(client, doc_id)
    resp = client.get(f"/documents/{doc_id}/keypoints")
    assert resp.status_code == 200
    body = resp.json()
    assert body["keyphrases"]
    assert any(p["category"] == "obligation" for p in body["points"])


def test_tables_endpoint_on_text_returns_note(client):
    doc_id = _upload(client).json()["id"]
    wait_until_ready(client, doc_id)
    resp = client.get(f"/documents/{doc_id}/tables")
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == 0
    assert body["note"]


def test_analysis_requires_ready_document(client, monkeypatch):
    from app.services.ingestion import IngestionService

    monkeypatch.setattr(IngestionService, "submit", lambda self, doc_id: None)
    doc_id = _upload(client).json()["id"]
    assert client.get(f"/documents/{doc_id}/summary").status_code == 409
    assert client.get(f"/documents/{doc_id}/keypoints").status_code == 409


def test_registry_persists_across_store_reload(client, tmp_path):
    """A new store instance should see previously uploaded documents."""

    doc_id = _upload(client).json()["id"]
    wait_until_ready(client, doc_id)

    from app.core.config import get_settings
    from app.services.storage import DocumentStore

    fresh = DocumentStore(get_settings())
    reloaded = fresh.get(doc_id)
    assert reloaded is not None
    assert reloaded.status.value == "ready"
