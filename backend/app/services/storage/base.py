"""Document store abstraction.

The store is the source of truth for uploaded documents. All backends share:

* an in-memory record map (the working set) guarded by a re-entrant lock,
* on-disk storage of the uploaded bytes,
* in-memory caches for the built QA engine and analysis results (these are
  derived data, cheap to rebuild, never persisted).

Backends differ only in how :class:`DocumentRecord` metadata is *persisted* —
the three abstract hooks ``_load_all`` / ``_save_record`` / ``_delete_record``.
This is what lets the JSON and SQL backends coexist behind one interface, so the
API and ingestion layers never know which is in use.
"""

from __future__ import annotations

import abc
import threading
import uuid
from collections import OrderedDict
from pathlib import Path

from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.models.records import DocumentRecord, DocumentStatus
from app.services.qa import QAEngine

logger = get_logger(__name__)


class BaseDocumentStore(abc.ABC):
    """Shared store behavior; subclasses implement metadata persistence."""

    def __init__(self, settings: Settings | None = None):
        self._settings = settings or get_settings()
        self._lock = threading.RLock()
        self._records: dict[str, DocumentRecord] = {}
        # LRU-bounded engine cache: each engine holds TF-IDF/LSA matrices and can
        # be large, so we cap the count and rebuild evicted ones on demand.
        self._engines: OrderedDict[str, QAEngine] = OrderedDict()
        self._analysis: dict[tuple[str, str], object] = {}

        self._settings.uploads_dir.mkdir(parents=True, exist_ok=True)
        self._initialize()

    # -- abstract persistence hooks ---------------------------------------
    @abc.abstractmethod
    def _load_all(self) -> list[DocumentRecord]:
        """Load all persisted records (called once at startup)."""

    @abc.abstractmethod
    def _save_record(self, record: DocumentRecord) -> None:
        """Upsert one record's metadata."""

    @abc.abstractmethod
    def _delete_record(self, doc_id: str) -> None:
        """Remove one record's metadata."""

    # -- startup -----------------------------------------------------------
    def _initialize(self) -> None:
        for record in self._load_all():
            # A process that died mid-ingest leaves stale in-flight states.
            if record.status in (DocumentStatus.QUEUED, DocumentStatus.PROCESSING):
                record.touch(DocumentStatus.FAILED)
                record.error = "ingestion interrupted by restart; re-upload to retry"
                self._save_record(record)
            self._records[record.id] = record

    # -- writes ------------------------------------------------------------
    def create(
        self,
        filename: str,
        mime_type: str,
        data: bytes,
        owner: str = "public",
        persist: bool = True,
    ) -> DocumentRecord:
        """Register an uploaded file as QUEUED.

        When ``persist`` is False the document is kept in memory for the session
        only — its metadata is never written to the database/registry, so it
        disappears on restart and leaves no stored trace.
        """

        doc_id = uuid.uuid4().hex
        suffix = Path(filename).suffix
        stored = self._settings.uploads_dir / f"{doc_id}{suffix}"
        stored.write_bytes(data)

        record = DocumentRecord(
            id=doc_id,
            filename=filename,
            mime_type=mime_type,
            size_bytes=len(data),
            stored_path=str(stored),
            owner=owner,
            persist=persist,
        )
        with self._lock:
            self._records[doc_id] = record
            if persist:
                self._save_record(record)
        logger.info(
            "registered document %s (%s, %d bytes, owner=%s, persist=%s)",
            doc_id,
            filename,
            len(data),
            owner,
            persist,
        )
        return record

    def mark(
        self,
        doc_id: str,
        status: DocumentStatus,
        *,
        error: str | None = None,
        stats: dict[str, int] | None = None,
    ) -> None:
        with self._lock:
            record = self._records.get(doc_id)
            if record is None:
                return
            record.touch(status)
            if error is not None:
                record.error = error
            if stats is not None:
                record.stats = stats
            if record.persist:
                self._save_record(record)

    def delete(self, doc_id: str) -> bool:
        with self._lock:
            record = self._records.pop(doc_id, None)
            self._engines.pop(doc_id, None)
            for key in [k for k in self._analysis if k[0] == doc_id]:
                self._analysis.pop(key, None)
            if record is None:
                return False
            try:
                record.path.unlink(missing_ok=True)
            except OSError:  # pragma: no cover
                logger.warning("could not delete file for %s", doc_id)
            if record.persist:
                self._delete_record(doc_id)
        return True

    # -- reads -------------------------------------------------------------
    def get(self, doc_id: str) -> DocumentRecord | None:
        with self._lock:
            return self._records.get(doc_id)

    def list(self, owner: str | None = None) -> list[DocumentRecord]:
        with self._lock:
            records = self._records.values()
            if owner is not None:
                records = [r for r in records if r.owner == owner]
            return sorted(records, key=lambda r: r.created_at, reverse=True)

    # -- derived in-memory caches -----------------------------------------
    def set_engine(self, doc_id: str, engine: QAEngine) -> None:
        with self._lock:
            self._engines[doc_id] = engine
            self._engines.move_to_end(doc_id)
            while len(self._engines) > self._settings.engine_cache_size:
                self._engines.popitem(last=False)  # evict least-recently-used

    def get_engine(self, doc_id: str) -> QAEngine | None:
        with self._lock:
            engine = self._engines.get(doc_id)
            if engine is not None:
                self._engines.move_to_end(doc_id)
            return engine

    def get_analysis(self, doc_id: str, kind: str) -> object | None:
        with self._lock:
            return self._analysis.get((doc_id, kind))

    def set_analysis(self, doc_id: str, kind: str, value: object) -> None:
        with self._lock:
            self._analysis[(doc_id, kind)] = value
