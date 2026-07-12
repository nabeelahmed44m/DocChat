"""Legacy-format extractor via headless LibreOffice.

Handles the formats that have no clean pure-Python reader — legacy Word (.doc),
Rich Text (.rtf), and OpenDocument (.odt) — by shelling out to ``soffice`` to
convert them to PDF, then reusing the PDF extractor. This is the "LibreOffice
fallback" from the roadmap (an alternative to Apache Tika).

Optional at runtime: if ``soffice`` isn't installed (or is disabled), a clear
:class:`ExtractionError` is raised instead of failing obscurely.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

from app.core.config import get_settings
from app.core.exceptions import ExtractionError
from app.core.logging import get_logger
from app.models.document import Document
from app.services.extraction.base import BaseExtractor

logger = get_logger(__name__)


def soffice_binary() -> str | None:
    """Return the path to a usable LibreOffice binary, or None."""

    for name in ("soffice", "libreoffice"):
        found = shutil.which(name)
        if found:
            return found
    return None


class LibreOfficeExtractor(BaseExtractor):
    extensions = (".doc", ".rtf", ".odt")
    mime_types = (
        "application/msword",
        "application/rtf",
        "text/rtf",
        "application/vnd.oasis.opendocument.text",
    )

    def extract(self, path: Path) -> Document:
        settings = get_settings()
        binary = soffice_binary()
        if not settings.libreoffice_enabled or binary is None:
            raise ExtractionError(
                f"cannot read '{path.name}': LibreOffice (soffice) is required for "
                f"legacy {path.suffix} files but was not found. Install LibreOffice "
                "or convert the file to PDF/DOCX."
            )

        with tempfile.TemporaryDirectory() as tmp:
            try:
                subprocess.run(
                    [binary, "--headless", "--convert-to", "pdf", "--outdir", tmp, str(path)],
                    check=True,
                    capture_output=True,
                    timeout=120,
                )
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
                raise ExtractionError(
                    f"LibreOffice failed to convert {path.name}: {exc}"
                ) from exc

            pdf_path = Path(tmp) / f"{path.stem}.pdf"
            if not pdf_path.exists():
                raise ExtractionError(
                    f"LibreOffice produced no output for {path.name}"
                )

            # Reuse the PDF extractor (with its OCR fallback) on the conversion.
            from app.services.extraction.pdf import PdfExtractor

            document = PdfExtractor().extract(pdf_path)

        # Restore the original filename/type on the normalized document.
        document.filename = path.name
        document.metadata["extractor"] = "libreoffice+pymupdf"
        document.metadata["converted_from"] = path.suffix.lstrip(".")
        return document
