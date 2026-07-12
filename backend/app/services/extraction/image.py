"""Image extractor — OCR for photos and scans.

Handles the mobile "scan a paper document with the camera" flow: a JPG/PNG comes
in, Tesseract reads the text out, and the rest of the pipeline treats it exactly
like any other document.
"""

from __future__ import annotations

from pathlib import Path

from app.core.config import get_settings
from app.core.exceptions import ExtractionError
from app.models.document import Document
from app.services.extraction.base import BaseExtractor
from app.services.extraction.ocr import image_to_text


class ImageExtractor(BaseExtractor):
    extensions = (".png", ".jpg", ".jpeg", ".tiff", ".tif", ".bmp", ".webp")
    mime_types = (
        "image/png",
        "image/jpeg",
        "image/tiff",
        "image/bmp",
        "image/webp",
    )

    def extract(self, path: Path) -> Document:
        settings = get_settings()
        if not settings.ocr_enabled:
            raise ExtractionError(
                f"OCR is disabled; cannot read image '{path.name}'. "
                "Set DOCCHAT_OCR_ENABLED=true to enable."
            )
        try:
            from PIL import Image
        except ImportError as exc:  # pragma: no cover - env dependent
            raise ExtractionError(
                "Pillow is required for image OCR. Install with `pip install pillow`."
            ) from exc

        try:
            with Image.open(path) as img:
                text = image_to_text(img, settings.ocr_language)
        except ExtractionError:
            raise
        except Exception as exc:
            raise ExtractionError(f"failed to open image {path.name}: {exc}") from exc

        return self.assemble(
            filename=path.name,
            mime_type="image/*",
            page_texts=[text],
            metadata={"extractor": "tesseract-ocr", "ocr": "true"},
        )
