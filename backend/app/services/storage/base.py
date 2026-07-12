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

# Prefix stored in the `stored_path` DB column to flag an R2 object key.
_R2_PREFIX = "r2:"


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

        # R2 is optional — only initialised when all four credentials are set.
        self._r2 = None
        if self._settings.r2_enabled:
            from app.services.storage.r2_file_store import R2FileStore

            self._r2 = R2FileStore(
                account_id=self._settings.r2_account_id,
                access_key_id=self._settings.r2_access_key_id,
                secret_access_key=self._settings.r2_secret_access_key,
                bucket_name=self._settings.r2_bucket_name,
            )
            logger.info("R2 file store enabled (bucket: %s)", self._settings.r2_bucket_name)

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

        When ``persist`` is False the document is session-only — never written to
        the database, auto-deleted when the user leaves the chat screen.

        When ``persist`` is True and R2 is configured, the bytes are uploaded to
        R2 for durability in addition to the local disk copy (used for ingestion).
        ``stored_path`` is set to ``r2:<key>``; callers resolve the actual local
        path via :meth:`get_file_path`.
        """

        doc_id = uuid.uuid4().hex
        suffix = Path(filename).suffix
        local = self._settings.uploads_dir / f"{doc_id}{suffix}"
        local.write_bytes(data)

        # Upload to R2 for persistent docs when R2 is configured.
        if persist and self._r2 is not None:
            r2_key = f"uploads/{doc_id}{suffix}"
            self._r2.upload(r2_key, data, mime_type)
            stored_path = f"{_R2_PREFIX}{r2_key}"
        else:
            stored_path = str(local)

        record = DocumentRecord(
            id=doc_id,
            filename=filename,
            mime_type=mime_type,
            size_bytes=len(data),
            stored_path=stored_path,
            owner=owner,
            persist=persist,
        )
        with self._lock:
            self._records[doc_id] = record
            if persist:
                self._save_record(record)
        logger.info(
            "registered document %s (%s, %d bytes, owner=%s, persist=%s, r2=%s)",
            doc_id,
            filename,
            len(data),
            owner,
            persist,
            stored_path.startswith(_R2_PREFIX),
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

    def get_file_path(self, doc_id: str) -> Path:
        """Return a local ``Path`` for the file, downloading from R2 if needed.

        For ephemeral (non-persist) documents the file is always local. For R2
        documents the local copy is kept as a hot cache; if it has been purged
        (e.g. server redeployed) this method re-downloads it transparently.
        """
        with self._lock:
            record = self._records.get(doc_id)
        if record is None:
            raise FileNotFoundError(f"document {doc_id} not found in store")

        sp = record.stored_path
        if sp.startswith(_R2_PREFIX):
            r2_key = sp[len(_R2_PREFIX):]
            local = self._settings.uploads_dir / Path(r2_key).name
            if not local.exists():
                if self._r2 is None:
                    raise FileNotFoundError(
                        f"R2 not configured but stored_path is an R2 key: {sp}"
                    )
                logger.info("R2 cache miss — downloading %s", r2_key)
                local.write_bytes(self._r2.download(r2_key))
            return local
        return Path(sp)

    def delete(self, doc_id: str) -> bool:
        with self._lock:
            record = self._records.pop(doc_id, None)
            self._engines.pop(doc_id, None)
            for key in [k for k in self._analysis if k[0] == doc_id]:
                self._analysis.pop(key, None)
            if record is None:
                return False

            # Delete the local file (local path or local cache of R2 object).
            sp = record.stored_path
            if sp.startswith(_R2_PREFIX):
                r2_key = sp[len(_R2_PREFIX):]
                local = self._settings.uploads_dir / Path(r2_key).name
                local.unlink(missing_ok=True)
                if self._r2 is not None:
                    try:
                        self._r2.delete(r2_key)
                    except Exception:  # noqa: BLE001
                        logger.warning("could not delete R2 object %s", r2_key)
            else:
                try:
                    Path(sp).unlink(missing_ok=True)
                except OSError:  # pragma: no cover
                    logger.warning("could not delete local file for %s", doc_id)

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
