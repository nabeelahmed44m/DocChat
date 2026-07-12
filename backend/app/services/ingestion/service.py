"""Background ingestion service.

Uploading returns immediately with a ``queued`` record; the actual
extract → segment → index work happens on a thread pool so the request thread
(and the mobile client) never blocks on a slow PDF. Status transitions are
written back to the :class:`DocumentStore` for polling.

A thread pool is the right primitive for Phase 2: ingestion is CPU/IO bound and
self-contained per document. Phase 5 can swap this class for a Celery/Redis
producer with no change to the API — the ``submit`` contract stays the same.
"""

from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor

from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.models.records import DocumentStatus
from app.pipeline import ingest
from app.services.storage import BaseDocumentStore

logger = get_logger(__name__)


class IngestionService:
    """Runs document ingestion off the request path and records status."""

    def __init__(self, store: BaseDocumentStore, settings: Settings | None = None):
        self._store = store
        self._settings = settings or get_settings()
        self._executor = ThreadPoolExecutor(
            max_workers=self._settings.ingest_workers,
            thread_name_prefix="ingest",
        )

    def submit(self, doc_id: str) -> Future:
        """Schedule ingestion of a queued document. Returns the Future."""

        logger.info("queued ingestion for %s", doc_id)
        return self._executor.submit(self._run, doc_id)

    def _run(self, doc_id: str) -> None:
        record = self._store.get(doc_id)
        if record is None:  # deleted before the worker started
            logger.warning("ingestion skipped; %s no longer exists", doc_id)
            return

        self._store.mark(doc_id, DocumentStatus.PROCESSING)
        try:
            result = ingest(record.path, self._settings)
            self._store.set_engine(doc_id, result.engine)
            self._store.mark(doc_id, DocumentStatus.READY, stats=result.stats)
            logger.info("ingestion complete for %s: %s", doc_id, result.stats)
        except Exception as exc:  # noqa: BLE001 - record any failure for the client
            logger.exception("ingestion failed for %s", doc_id)
            self._store.mark(doc_id, DocumentStatus.FAILED, error=str(exc))

    def shutdown(self) -> None:
        self._executor.shutdown(wait=False, cancel_futures=True)
