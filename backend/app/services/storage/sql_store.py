"""SQL-backed document store (SQLAlchemy Core).

Persists record metadata to a relational database — SQLite by default, or any
SQLAlchemy-supported engine (e.g. Postgres) via ``DOCCHAT_DATABASE_URL``. This
is the multi-node / durable backend from the Phase 5 roadmap.

Uses SQLAlchemy Core (not the ORM) to keep the mapping explicit and the
dependency surface small. Per-record writes are upserts, so this scales to many
documents without the JSON backend's whole-file rewrite.
"""

from __future__ import annotations

import json

from app.core.config import Settings
from app.core.logging import get_logger
from app.models.records import DocumentRecord, DocumentStatus
from app.services.storage.base import BaseDocumentStore

logger = get_logger(__name__)


class SqlDocumentStore(BaseDocumentStore):
    """Record metadata persisted in a SQL table via SQLAlchemy Core."""

    def __init__(self, settings: Settings | None = None):
        # Engine/table must exist before BaseDocumentStore.__init__ calls _load_all.
        from sqlalchemy import (
            Column,
            Integer,
            MetaData,
            String,
            Table,
            Text,
            create_engine,
        )

        from app.core.config import get_settings

        resolved = settings or get_settings()
        url = resolved.resolved_database_url
        # Ensure the SQLite parent dir exists.
        resolved.storage_dir.mkdir(parents=True, exist_ok=True)

        # pool_pre_ping keeps serverless Postgres (e.g. Neon) robust: it
        # validates a pooled connection before use, transparently reconnecting
        # after the provider drops an idle connection.
        engine_kwargs: dict[str, object] = {"future": True, "pool_pre_ping": True}
        if url.startswith("sqlite"):
            # Allow the store to be used across the ingestion thread pool.
            engine_kwargs["connect_args"] = {"check_same_thread": False}
        self._engine = create_engine(url, **engine_kwargs)
        self._metadata = MetaData()
        self._table = Table(
            "documents",
            self._metadata,
            Column("id", String(64), primary_key=True),
            Column("filename", Text, nullable=False),
            Column("mime_type", String(255), nullable=False),
            Column("size_bytes", Integer, nullable=False),
            Column("stored_path", Text, nullable=False),
            Column("status", String(32), nullable=False),
            Column("error", Text, nullable=True),
            Column("stats", Text, nullable=False, default="{}"),
            Column("owner", String(128), nullable=False, default="public"),
            Column("created_at", String(64), nullable=False),
            Column("updated_at", String(64), nullable=False),
        )
        self._metadata.create_all(self._engine)
        super().__init__(settings)

    # -- row <-> record ----------------------------------------------------
    @staticmethod
    def _to_record(row) -> DocumentRecord:
        m = row._mapping
        return DocumentRecord(
            id=m["id"],
            filename=m["filename"],
            mime_type=m["mime_type"],
            size_bytes=m["size_bytes"],
            stored_path=m["stored_path"],
            status=DocumentStatus(m["status"]),
            error=m["error"],
            stats=json.loads(m["stats"] or "{}"),
            owner=m["owner"],
            created_at=m["created_at"],
            updated_at=m["updated_at"],
        )

    @staticmethod
    def _to_values(record: DocumentRecord) -> dict[str, object]:
        return {
            "id": record.id,
            "filename": record.filename,
            "mime_type": record.mime_type,
            "size_bytes": record.size_bytes,
            "stored_path": record.stored_path,
            "status": record.status.value,
            "error": record.error,
            "stats": json.dumps(record.stats),
            "owner": record.owner,
            "created_at": record.created_at,
            "updated_at": record.updated_at,
        }

    # -- persistence hooks -------------------------------------------------
    def _load_all(self) -> list[DocumentRecord]:
        from sqlalchemy import select

        with self._engine.connect() as conn:
            rows = conn.execute(select(self._table)).fetchall()
        return [self._to_record(r) for r in rows]

    def _save_record(self, record: DocumentRecord) -> None:
        from sqlalchemy.dialects.sqlite import insert as sqlite_insert

        values = self._to_values(record)
        with self._engine.begin() as conn:
            if self._engine.dialect.name == "sqlite":
                stmt = sqlite_insert(self._table).values(**values)
                update_cols = {c: stmt.excluded[c] for c in values if c != "id"}
                stmt = stmt.on_conflict_do_update(index_elements=["id"], set_=update_cols)
                conn.execute(stmt)
            else:  # generic upsert: delete-then-insert within the transaction
                from sqlalchemy import delete, insert

                conn.execute(delete(self._table).where(self._table.c.id == record.id))
                conn.execute(insert(self._table).values(**values))

    def _delete_record(self, doc_id: str) -> None:
        from sqlalchemy import delete

        with self._engine.begin() as conn:
            conn.execute(delete(self._table).where(self._table.c.id == doc_id))
