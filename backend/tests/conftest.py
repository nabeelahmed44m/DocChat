"""Shared pytest fixtures."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from app.pipeline import IngestResult, ingest

DATA_DIR = Path(__file__).parent / "data"
SAMPLE_CONTRACT = DATA_DIR / "sample_contract.txt"


@pytest.fixture(scope="session", autouse=True)
def _warm_pipeline() -> None:
    """Pre-import heavy deps (scipy/sklearn) and warm caches once.

    The first ingest in a fresh process pays a large one-time import cost. Doing
    it here keeps background-ingestion timing in the API tests representative and
    avoids a spurious poll timeout on whichever test happens to run first.
    """

    ingest(SAMPLE_CONTRACT)


@pytest.fixture(scope="session")
def sample_contract_path() -> Path:
    return SAMPLE_CONTRACT


@pytest.fixture()
def contract_result(sample_contract_path: Path) -> IngestResult:
    """Full ingest of the sample contract, ready to query."""

    return ingest(sample_contract_path)


@pytest.fixture()
def client(tmp_path, monkeypatch) -> Iterator["TestClient"]:  # noqa: F821
    """A TestClient backed by an isolated temp storage directory."""

    from fastapi.testclient import TestClient

    from app.api import create_app
    from app.core.config import get_settings

    monkeypatch.setenv("DOCCHAT_STORAGE_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("DOCCHAT_INGEST_WORKERS", "2")
    get_settings.cache_clear()

    app = create_app()
    with TestClient(app) as test_client:
        yield test_client

    get_settings.cache_clear()


def wait_until_ready(client, doc_id: str, timeout: float = 30.0) -> dict:
    """Poll a document's status until it leaves the in-flight states."""

    import time

    deadline = time.time() + timeout
    while time.time() < deadline:
        body = client.get(f"/documents/{doc_id}/status").json()
        if body["status"] in ("ready", "failed"):
            return body
        time.sleep(0.05)
    raise AssertionError(f"document {doc_id} did not finish within {timeout}s")
