"""Persistence for uploaded documents and their built QA engines."""

from __future__ import annotations

from app.core.config import Settings, get_settings
from app.services.storage.base import BaseDocumentStore
from app.services.storage.document_store import DocumentStore, JsonDocumentStore


def create_store(settings: Settings | None = None) -> BaseDocumentStore:
    """Instantiate the configured store backend ('json' or 'sql')."""

    settings = settings or get_settings()
    if settings.store_backend == "sql":
        from app.services.storage.sql_store import SqlDocumentStore

        return SqlDocumentStore(settings)
    return JsonDocumentStore(settings)


__all__ = [
    "BaseDocumentStore",
    "DocumentStore",
    "JsonDocumentStore",
    "create_store",
]
