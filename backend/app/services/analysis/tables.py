"""Table extraction from PDFs (pdfplumber).

Table detection is a geometry problem, not NLP: pdfplumber finds tables from the
page's ruling lines and text alignment. We normalize each detected table to a
header row plus data rows, cleaning whitespace and dropping empty rows/columns.

Only PDFs have the layout information tables need; other formats return an empty
result with an explanatory note. pdfplumber is optional at runtime — if it (or
the file type) is unavailable, a clear note is returned instead of an error.
"""

from __future__ import annotations

from pathlib import Path

from app.core.logging import get_logger
from app.models.analysis import Table, Tables

logger = get_logger(__name__)

# pdfplumber table detection strategy: try ruled lines first, then text alignment.
_SETTINGS = [
    {"vertical_strategy": "lines", "horizontal_strategy": "lines"},
    {"vertical_strategy": "text", "horizontal_strategy": "text"},
]


def _clean_cell(value: object) -> str:
    if value is None:
        return ""
    return " ".join(str(value).split())


def _normalize(raw: list[list[object]]) -> Table | None:
    """Turn a raw pdfplumber table into a cleaned :class:`Table`, or drop it."""

    rows = [[_clean_cell(c) for c in row] for row in raw if row]
    rows = [r for r in rows if any(cell for cell in r)]
    if len(rows) < 2:  # need at least a header + one data row
        return None

    width = max(len(r) for r in rows)
    rows = [r + [""] * (width - len(r)) for r in rows]

    # Drop columns that are entirely empty.
    keep = [i for i in range(width) if any(r[i] for r in rows)]
    if not keep:
        return None
    rows = [[r[i] for i in keep] for r in rows]

    header, *data = rows
    if not data:
        return None
    return Table(
        header=tuple(header),
        rows=tuple(tuple(r) for r in data),
        page_number=0,  # filled in by the caller
    )


def extract_tables(path: str | Path, mime_type: str, max_tables: int = 20) -> Tables:
    """Extract tables from a PDF at ``path``."""

    if mime_type != "application/pdf" and Path(path).suffix.lower() != ".pdf":
        return Tables(
            engine="none",
            note="Table extraction is currently supported for PDF files only.",
        )

    try:
        import pdfplumber
    except ImportError:  # pragma: no cover - env dependent
        return Tables(
            engine="none",
            note="pdfplumber is not installed; table extraction is unavailable.",
        )

    collected: list[Table] = []
    try:
        with pdfplumber.open(path) as pdf:
            for page_index, page in enumerate(pdf.pages, start=1):
                seen_signatures: set[str] = set()
                for settings in _SETTINGS:
                    try:
                        raw_tables = page.extract_tables(settings)
                    except Exception:  # pdfplumber can raise on odd pages
                        continue
                    for raw in raw_tables or []:
                        table = _normalize(raw)
                        if table is None:
                            continue
                        # Avoid emitting the same table twice from both strategies.
                        signature = f"{page_index}:{table.header}:{table.n_rows}"
                        if signature in seen_signatures:
                            continue
                        seen_signatures.add(signature)
                        collected.append(
                            Table(
                                header=table.header,
                                rows=table.rows,
                                page_number=page_index,
                            )
                        )
                    if collected and settings is _SETTINGS[0]:
                        # Ruled-line pass found tables on this page; trust it and
                        # skip the noisier text-alignment pass for this page.
                        break
                if len(collected) >= max_tables:
                    break
    except Exception as exc:
        logger.warning("table extraction failed for %s: %s", path, exc)
        return Tables(engine="pdfplumber", note=f"Could not parse tables: {exc}")

    note = None if collected else "No tables were detected in this document."
    return Tables(engine="pdfplumber", tables=tuple(collected[:max_tables]), note=note)
