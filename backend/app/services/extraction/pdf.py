"""PDF extractor backed by PyMuPDF (fitz).

PyMuPDF gives per-page text quickly and, importantly, exposes word-level
bounding boxes later on — which is what will let the mobile viewer highlight the
exact answer span. Here in Phase 1 we only need page-granular text + offsets.

The import is done lazily so the rest of the package (and its tests) work even
in an environment where PyMuPDF is not installed.
"""

from __future__ import annotations

from pathlib import Path

from app.core.config import get_settings
from app.core.exceptions import ExtractionError
from app.core.logging import get_logger
from app.models.document import Document
from app.services.extraction.base import BaseExtractor
from app.services.extraction.ocr import image_to_text, ocr_available

logger = get_logger(__name__)

# Below this many characters of embedded text, a page is treated as scanned and
# routed through OCR (when enabled and available).
_OCR_CHAR_THRESHOLD = 12


class PdfExtractor(BaseExtractor):
    extensions = (".pdf",)
    mime_types = ("application/pdf",)

    def extract(self, path: Path) -> Document:
        try:
            import fitz  # PyMuPDF
        except ImportError as exc:  # pragma: no cover - env dependent
            raise ExtractionError(
                "PyMuPDF is required for PDF extraction. Install with "
                "`pip install pymupdf`."
            ) from exc

        settings = get_settings()
        allow_ocr = settings.ocr_enabled and ocr_available()
        did_ocr = False

        try:
            page_texts: list[str] = []
            with fitz.open(path) as doc:
                meta = {k: str(v) for k, v in (doc.metadata or {}).items() if v}
                for page in doc:
                    text = page.get_text("text")
                    if len(text.strip()) < _OCR_CHAR_THRESHOLD and allow_ocr:
                        ocr_text = self._ocr_page(page, fitz, settings.ocr_language)
                        if ocr_text.strip():
                            text = ocr_text
                            did_ocr = True
                    page_texts.append(text)
        except ExtractionError:
            raise
        except Exception as exc:  # PyMuPDF raises assorted errors
            raise ExtractionError(f"failed to parse PDF {path.name}: {exc}") from exc

        meta["extractor"] = "pymupdf+ocr" if did_ocr else "pymupdf"
        if did_ocr:
            meta["ocr"] = "true"
        return self.assemble(
            filename=path.name,
            mime_type="application/pdf",
            page_texts=page_texts,
            metadata=meta,
        )

    @staticmethod
    def _ocr_page(page, fitz, language: str) -> str:
        """Rasterize a text-less page at 2x and OCR it."""

        try:
            from PIL import Image
        except ImportError:  # pragma: no cover - env dependent
            return ""
        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
        img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
        logger.info("OCR fallback for scanned PDF page %d", page.number + 1)
        return image_to_text(img, language)
