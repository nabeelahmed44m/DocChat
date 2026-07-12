"""Excel (.xlsx) extractor via openpyxl.

Each worksheet becomes one page. Rows are flattened to pipe-delimited lines so
the QA/keypoint layers can read cell values as ordinary text.
"""

from __future__ import annotations

from pathlib import Path

from app.core.exceptions import ExtractionError
from app.models.document import Document
from app.services.extraction.base import BaseExtractor


class XlsxExtractor(BaseExtractor):
    extensions = (".xlsx",)
    mime_types = ("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",)

    def extract(self, path: Path) -> Document:
        try:
            import openpyxl
        except ImportError as exc:  # pragma: no cover - env dependent
            raise ExtractionError(
                "openpyxl is required for XLSX extraction. "
                "Install with `pip install openpyxl`."
            ) from exc

        try:
            wb = openpyxl.load_workbook(str(path), read_only=True, data_only=True)
        except Exception as exc:
            raise ExtractionError(f"failed to parse XLSX {path.name}: {exc}") from exc

        sheet_texts: list[str] = []
        try:
            for sheet in wb.worksheets:
                lines: list[str] = [f"Sheet: {sheet.title}"]
                for row in sheet.iter_rows(values_only=True):
                    cells = [str(c).strip() for c in row if c is not None and str(c).strip()]
                    if cells:
                        lines.append(" | ".join(cells))
                sheet_texts.append("\n".join(lines))
        finally:
            wb.close()

        return self.assemble(
            filename=path.name,
            mime_type=self.mime_types[0],
            page_texts=sheet_texts,
            metadata={"extractor": "openpyxl"},
        )
