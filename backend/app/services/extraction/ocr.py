"""OCR helpers (Tesseract via pytesseract).

Kept in one module so both the image extractor and the scanned-PDF fallback
share a single, lazily-imported Tesseract entry point. If Tesseract or its
Python binding is unavailable, callers get a clear :class:`ExtractionError`
rather than an ImportError deep in the stack.

OCR is still classical computer vision + a text recognizer — no LLM involved.
"""

from __future__ import annotations

from app.core.config import get_settings
from app.core.exceptions import ExtractionError
from app.core.logging import get_logger

logger = get_logger(__name__)


def ocr_available() -> bool:
    """Return True if pytesseract and the tesseract binary are both usable."""

    try:
        import pytesseract

        pytesseract.get_tesseract_version()
        return True
    except Exception:  # ImportError or TesseractNotFoundError
        return False


def image_to_text(image, language: str | None = None) -> str:
    """Run OCR on a PIL image (or path) and return recognized text."""

    try:
        import pytesseract
    except ImportError as exc:  # pragma: no cover - env dependent
        raise ExtractionError(
            "pytesseract is required for OCR. Install with `pip install pytesseract` "
            "and ensure the `tesseract` binary is on PATH."
        ) from exc

    lang = language or get_settings().ocr_language
    try:
        return pytesseract.image_to_string(image, lang=lang)
    except Exception as exc:  # TesseractNotFoundError, etc.
        raise ExtractionError(
            f"OCR failed (is the tesseract binary installed?): {exc}"
        ) from exc
