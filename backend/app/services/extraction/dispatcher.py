"""Format dispatcher — the single public entry point for extraction.

``extract(path)`` picks the right :class:`BaseExtractor` by file extension
(falling back to MIME sniffing), runs it, and validates the result. The registry
is ordered; the first extractor claiming an extension wins.
"""

from __future__ import annotations

import mimetypes
from pathlib import Path

from app.core.exceptions import (
    EmptyDocumentError,
    UnsupportedFormatError,
)
from app.core.logging import get_logger
from app.models.document import Document
from app.services.extraction.base import BaseExtractor
from app.services.extraction.docx import DocxExtractor
from app.services.extraction.image import ImageExtractor
from app.services.extraction.libreoffice import LibreOfficeExtractor
from app.services.extraction.pdf import PdfExtractor
from app.services.extraction.pptx import PptxExtractor
from app.services.extraction.text import TextExtractor
from app.services.extraction.xlsx import XlsxExtractor

logger = get_logger(__name__)

# Order matters only when extensions overlap (they do not, today).
_REGISTRY: tuple[BaseExtractor, ...] = (
    PdfExtractor(),
    DocxExtractor(),
    PptxExtractor(),
    XlsxExtractor(),
    ImageExtractor(),
    LibreOfficeExtractor(),
    TextExtractor(),
)

_BY_EXTENSION: dict[str, BaseExtractor] = {
    ext: extractor for extractor in _REGISTRY for ext in extractor.extensions
}
_BY_MIME: dict[str, BaseExtractor] = {
    mime: extractor for extractor in _REGISTRY for mime in extractor.mime_types
}


def supported_extensions() -> tuple[str, ...]:
    """Return the sorted tuple of extensions the pipeline currently accepts."""

    return tuple(sorted(_BY_EXTENSION))


def _select(path: Path) -> BaseExtractor:
    ext = path.suffix.lower()
    if ext in _BY_EXTENSION:
        return _BY_EXTENSION[ext]

    guessed, _ = mimetypes.guess_type(path.name)
    if guessed and guessed in _BY_MIME:
        return _BY_MIME[guessed]

    raise UnsupportedFormatError(
        f"no extractor for '{path.name}' (extension '{ext or 'none'}'). "
        f"Supported: {', '.join(supported_extensions())}"
    )


def extract(path: str | Path) -> Document:
    """Extract a normalized :class:`Document` from any supported file.

    Raises:
        UnsupportedFormatError: no registered extractor matches the file.
        ExtractionError: the matched extractor failed to parse the file.
        EmptyDocumentError: parsing succeeded but produced no usable text.
    """

    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"file not found: {path}")

    extractor = _select(path)
    logger.info("extracting %s with %s", path.name, type(extractor).__name__)
    document = extractor.extract(path)

    if not document.full_text.strip():
        raise EmptyDocumentError(
            f"'{path.name}' produced no extractable text "
            "(it may be a scanned/image-only file — OCR arrives in Phase 2)."
        )

    logger.info(
        "extracted %s: %d chars, %d page(s)",
        path.name,
        document.char_count,
        document.page_count,
    )
    return document
