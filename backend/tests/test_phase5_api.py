"""API tests for Phase 5: auth, ownership isolation, search, SQL backend."""

from __future__ import annotations

import io
from collections.abc import Iterator

import pytest

from tests.conftest import wait_until_ready

CONTRACT_A = (
    "MASTER SERVICES AGREEMENT\n\n"
    "The monthly retainer is $12,500. Either party may terminate on sixty (60) days notice.\n"
)
CONTRACT_B = (
    "LEASE AGREEMENT\n\n"
    "Rent is $4,000 per month. The security deposit is two months' rent, refundable.\n"
)


def _make_client(monkeypatch, tmp_path, **env) -> Iterator:
    from fastapi.testclient import TestClient

    from app.api import create_app
    from app.core.config import get_settings

    monkeypatch.setenv("DOCCHAT_STORAGE_DIR", str(tmp_path / "data"))
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    get_settings.cache_clear()
    app = create_app()
    with TestClient(app) as c:
        yield c
    get_settings.cache_clear()


@pytest.fixture()
def authed_client(monkeypatch, tmp_path):
    yield from _make_client(
        monkeypatch, tmp_path, DOCCHAT_API_KEYS='["key-a", "key-b"]'
    )


@pytest.fixture()
def sql_client(monkeypatch, tmp_path):
    pytest.importorskip("sqlalchemy")
    yield from _make_client(monkeypatch, tmp_path, DOCCHAT_STORE_BACKEND="sql")


def _upload(client, content: bytes, name="doc.txt", headers=None, persist=None):
    data = {}
    if persist is not None:
        data["persist"] = str(persist).lower()
    return client.post(
        "/documents",
        files={"file": (name, io.BytesIO(content), "text/plain")},
        data=data,
        headers=headers or {},
    )


# --- auth ----------------------------------------------------------------
def test_health_reports_auth_and_capabilities(authed_client):
    body = authed_client.get("/health").json()
    assert body["auth_required"] is True
    assert body["multi_document_search"] is True
    assert "lsa_enabled" in body


def test_requests_without_key_are_rejected(authed_client):
    assert _upload(authed_client, b"x").status_code == 401
    assert authed_client.get("/documents").status_code == 401


def test_valid_key_works(authed_client):
    h = {"Authorization": "Bearer key-a"}
    resp = _upload(authed_client, CONTRACT_A.encode(), headers=h)
    assert resp.status_code == 202
    assert authed_client.get("/documents", headers=h).json()["count"] == 1


def test_ownership_isolation(authed_client):
    ha = {"Authorization": "Bearer key-a"}
    hb = {"Authorization": "Bearer key-b"}
    doc_id = _upload(authed_client, CONTRACT_A.encode(), headers=ha).json()["id"]

    # key-b cannot see or reach key-a's document.
    assert authed_client.get("/documents", headers=hb).json()["count"] == 0
    assert authed_client.get(f"/documents/{doc_id}", headers=hb).status_code == 404
    assert (
        authed_client.post(
            f"/documents/{doc_id}/ask", json={"question": "hi"}, headers=hb
        ).status_code
        == 404
    )
    # but key-a can.
    assert authed_client.get(f"/documents/{doc_id}", headers=ha).status_code == 200


def test_x_api_key_header_accepted(authed_client):
    resp = _upload(authed_client, CONTRACT_A.encode(), headers={"X-API-Key": "key-b"})
    assert resp.status_code == 202


# --- multi-document search -----------------------------------------------
def test_search_across_documents(client):
    a = _upload(client, CONTRACT_A.encode(), name="msa.txt").json()["id"]
    b = _upload(client, CONTRACT_B.encode(), name="lease.txt").json()["id"]
    wait_until_ready(client, a)
    wait_until_ready(client, b)

    resp = client.post("/search", json={"question": "what is the security deposit?", "top_k": 5})
    assert resp.status_code == 200
    body = resp.json()
    assert body["searched_documents"] == 2
    assert body["results"]
    top = body["results"][0]
    # The best answer should come from the lease and mention the deposit.
    assert top["filename"] == "lease.txt"
    assert "deposit" in top["answer"]["text"].lower()
    assert top["document_id"] == b


# --- SQL backend end-to-end ----------------------------------------------
def test_sql_backend_full_flow(sql_client):
    assert sql_client.get("/health").json()["store_backend"] == "sql"
    doc_id = _upload(sql_client, CONTRACT_A.encode()).json()["id"]
    wait_until_ready(sql_client, doc_id)
    resp = sql_client.post(
        f"/documents/{doc_id}/ask", json={"question": "What is the retainer?"}
    )
    assert resp.status_code == 200
    assert any("$12,500" in a["text"] for a in resp.json()["answers"])


def test_sql_backend_ephemeral_not_persisted(sql_client):
    """persist=false: the doc works in-session but is never written to Postgres/SQLite."""

    resp = _upload(sql_client, CONTRACT_A.encode(), persist=False)
    assert resp.status_code == 202
    doc_id = resp.json()["id"]
    assert resp.json()["persist"] is False
    wait_until_ready(sql_client, doc_id)

    # Answers work this session.
    ask = sql_client.post(f"/documents/{doc_id}/ask", json={"question": "retainer?"})
    assert ask.status_code == 200

    # A fresh store built from the same SQLite DB must not contain the document.
    from app.core.config import get_settings
    from app.services.storage.sql_store import SqlDocumentStore

    fresh = SqlDocumentStore(get_settings())
    assert fresh.get(doc_id) is None


def test_persist_true_survives_store_reload(sql_client):
    doc_id = _upload(sql_client, CONTRACT_A.encode(), persist=True).json()["id"]
    wait_until_ready(sql_client, doc_id)
    from app.core.config import get_settings
    from app.services.storage.sql_store import SqlDocumentStore

    fresh = SqlDocumentStore(get_settings())
    assert fresh.get(doc_id) is not None
