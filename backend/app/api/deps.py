"""FastAPI dependency providers.

The store and ingestion service are created once at startup and stashed on
``app.state``. These helpers expose them to routes via ``Depends`` so tests can
override them with in-memory doubles.
"""

from __future__ import annotations

from fastapi import Request

from app.services.ingestion import IngestionService
from app.services.storage import BaseDocumentStore


def get_store(request: Request) -> BaseDocumentStore:
    return request.app.state.store


def get_ingestion(request: Request) -> IngestionService:
    return request.app.state.ingestion
