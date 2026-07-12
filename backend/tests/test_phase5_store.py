"""Tests for the pluggable store backends (JSON and SQL)."""

from __future__ import annotations

import pytest

from app.core.config import get_settings
from app.models.records import DocumentStatus
from app.services.storage import JsonDocumentStore
from app.services.storage.sql_store import SqlDocumentStore


@pytest.fixture(params=["json", "sql"])
def store(request, tmp_path, monkeypatch):
    pytest.importorskip("sqlalchemy")
    monkeypatch.setenv("DOCCHAT_STORAGE_DIR", str(tmp_path / "data"))
    get_settings.cache_clear()
    settings = get_settings()
    impl = JsonDocumentStore if request.param == "json" else SqlDocumentStore
    yield impl(settings)
    get_settings.cache_clear()


def test_create_get_list(store):
    rec = store.create("a.txt", "text/plain", b"hello", owner="alice")
    assert rec.owner == "alice"
    assert store.get(rec.id).filename == "a.txt"
    assert [r.id for r in store.list()] == [rec.id]
    assert store.list(owner="alice")
    assert store.list(owner="bob") == []


def test_mark_and_delete(store):
    rec = store.create("b.txt", "text/plain", b"hi")
    store.mark(rec.id, DocumentStatus.READY, stats={"sentences": 3})
    assert store.get(rec.id).status is DocumentStatus.READY
    assert store.get(rec.id).stats == {"sentences": 3}
    assert store.delete(rec.id) is True
    assert store.get(rec.id) is None
    assert store.delete(rec.id) is False


def test_persistence_across_reload(store):
    rec = store.create("c.txt", "text/plain", b"data", owner="carol")
    store.mark(rec.id, DocumentStatus.READY)
    # A fresh store of the same backend must see the persisted record.
    fresh = type(store)(get_settings())
    reloaded = fresh.get(rec.id)
    assert reloaded is not None
    assert reloaded.owner == "carol"
    assert reloaded.status is DocumentStatus.READY


def test_ephemeral_document_is_not_persisted(store):
    """A persist=False document works in-session but is never written to the DB."""

    rec = store.create("secret.txt", "text/plain", b"data", persist=False)
    store.mark(rec.id, DocumentStatus.READY, stats={"sentences": 1})
    # Usable within the session.
    assert store.get(rec.id) is not None
    assert store.get(rec.id).status is DocumentStatus.READY
    assert rec.persist is False
    # But a fresh store (simulating a restart) sees nothing.
    fresh = type(store)(get_settings())
    assert fresh.get(rec.id) is None
    assert fresh.list() == []


def test_engine_cache_evicts_lru(store, monkeypatch):
    """The engine cache is bounded; the least-recently-used engine is evicted."""

    class FakeEngine:
        def __init__(self, tag):
            self.tag = tag

    monkeypatch.setattr(store._settings, "engine_cache_size", 2)
    a = store.create("a.txt", "text/plain", b"a")
    b = store.create("b.txt", "text/plain", b"b")
    c = store.create("c.txt", "text/plain", b"c")

    store.set_engine(a.id, FakeEngine("a"))
    store.set_engine(b.id, FakeEngine("b"))
    store.get_engine(a.id)  # touch a → b becomes least-recently-used
    store.set_engine(c.id, FakeEngine("c"))  # should evict b

    assert store.get_engine(a.id) is not None
    assert store.get_engine(c.id) is not None
    assert store.get_engine(b.id) is None  # evicted


def test_ephemeral_not_leaked_when_persisted_doc_saved_after(store):
    """A later persisted save must not drag an earlier ephemeral doc to disk."""

    eph = store.create("eph.txt", "text/plain", b"secret", persist=False)
    kept = store.create("kept.txt", "text/plain", b"public", persist=True)
    store.mark(kept.id, DocumentStatus.READY)  # triggers a persist write

    fresh = type(store)(get_settings())
    assert fresh.get(kept.id) is not None  # persisted doc survives
    assert fresh.get(eph.id) is None  # ephemeral doc did NOT leak
    assert [r.id for r in fresh.list()] == [kept.id]
