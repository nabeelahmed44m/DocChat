"""JSON-file document store — the default, dependency-free backend.

Persists all record metadata to a single JSON registry, rewritten atomically on
every change. Ideal for single-node deployments and development. For multi-node
or high-write deployments, use the SQL backend instead.
"""

from __future__ import annotations

import json

from app.core.logging import get_logger
from app.models.records import DocumentRecord
from app.services.storage.base import BaseDocumentStore

logger = get_logger(__name__)


class JsonDocumentStore(BaseDocumentStore):
    """Registry persisted as one JSON file under ``storage_dir``."""

    def _load_all(self) -> list[DocumentRecord]:
        path = self._settings.registry_path
        if not path.exists():
            return []
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:  # pragma: no cover
            logger.warning("could not read registry %s: %s", path, exc)
            return []
        return [DocumentRecord.from_dict(raw) for raw in data.get("documents", [])]

    def _flush(self) -> None:
        path = self._settings.registry_path
        path.parent.mkdir(parents=True, exist_ok=True)
        # Only persisted records go to disk. Ephemeral (persist=False) documents
        # live in memory for the session and must never leak into the registry —
        # even when an unrelated persisted document triggers this whole-file flush.
        payload = {
            "documents": [r.to_dict() for r in self._records.values() if r.persist]
        }
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(path)  # atomic swap

    # The JSON backend rewrites the whole file on any change.
    def _save_record(self, record: DocumentRecord) -> None:
        self._flush()

    def _delete_record(self, doc_id: str) -> None:
        self._flush()


# Backward-compatible alias: earlier phases imported ``DocumentStore`` directly.
DocumentStore = JsonDocumentStore
