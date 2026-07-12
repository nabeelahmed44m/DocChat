"""Plain-text / Markdown extractor.

Plain text has no intrinsic pages, so we treat the whole file as page 1. This
also acts as the reliable fallback for any UTF-8 decodable content.
"""

from __future__ import annotations

from pathlib import Path

from app.core.exceptions import ExtractionError
from app.models.document import Document
from app.services.extraction.base import BaseExtractor


class TextExtractor(BaseExtractor):
    extensions = (".txt", ".md", ".markdown", ".text", ".log", ".csv")
    mime_types = ("text/plain", "text/markdown", "text/csv")

    def extract(self, path: Path) -> Document:
        try:
            # utf-8 first; fall back to latin-1 which never raises on bytes.
            try:
                raw = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                raw = path.read_text(encoding="latin-1")
        except OSError as exc:  # pragma: no cover - filesystem edge
            raise ExtractionError(f"could not read {path.name}: {exc}") from exc

        return self.assemble(
            filename=path.name,
            mime_type="text/plain",
            page_texts=[raw],
            metadata={"extractor": "text"},
        )
