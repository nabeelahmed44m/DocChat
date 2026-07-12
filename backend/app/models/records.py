"""Document lifecycle records.

A :class:`DocumentRecord` tracks an uploaded file as it moves through the
ingestion pipeline (queued → processing → ready / failed). It is the unit the
API returns for status polling and the unit the store persists to disk, kept
separate from the heavyweight in-memory :class:`~app.models.document.Document`.
"""

from __future__ import annotations

import enum
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path


class DocumentStatus(str, enum.Enum):
    """Where an uploaded document is in its processing lifecycle."""

    QUEUED = "queued"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class DocumentRecord:
    """Persistent metadata about one uploaded document."""

    id: str
    filename: str
    mime_type: str
    size_bytes: int
    stored_path: str
    status: DocumentStatus = DocumentStatus.QUEUED
    error: str | None = None
    stats: dict[str, int] = field(default_factory=dict)
    owner: str = "public"  # API-key identity that uploaded it (auth-scoped)
    # When False the document is processed in-memory only for the session and is
    # never written to the database/registry (the user opted out of saving it).
    persist: bool = True
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)

    def touch(self, status: DocumentStatus | None = None) -> None:
        if status is not None:
            self.status = status
        self.updated_at = _now()

    def to_dict(self) -> dict[str, object]:
        data = asdict(self)
        data["status"] = self.status.value
        return data

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "DocumentRecord":
        payload = dict(data)
        payload["status"] = DocumentStatus(payload["status"])
        # Ignore unknown keys defensively so registry schema can evolve.
        allowed = cls.__dataclass_fields__.keys()
        return cls(**{k: v for k, v in payload.items() if k in allowed})

    @property
    def path(self) -> Path:
        return Path(self.stored_path)
