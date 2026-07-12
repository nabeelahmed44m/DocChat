"""Extractor interface.

Adding a new format = implementing one :class:`BaseExtractor` subclass and
registering it in the dispatcher. Nothing else in the codebase changes.
"""

from __future__ import annotations

import abc
import re
from pathlib import Path

from app.models.document import Document, Page

_PARAGRAPH_SPLIT_RE = re.compile(r"\n\s*\n")
_WS_RE = re.compile(r"[ \t\f\v]*\n[ \t\f\v]*|\s{2,}")


def normalize_text(text: str) -> str:
    """Clean extracted text so sentence segmentation isn't fooled by layout.

    Source documents are frequently hard-wrapped (a newline mid-sentence). We
    collapse each paragraph's internal whitespace — including single newlines —
    into single spaces, while preserving blank-line paragraph breaks. All
    downstream offsets index into this normalized text, so highlighting stays
    accurate.
    """

    if not text:
        return ""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    paragraphs = _PARAGRAPH_SPLIT_RE.split(text)
    cleaned = [re.sub(r"\s+", " ", p).strip() for p in paragraphs]
    return "\n\n".join(p for p in cleaned if p)


class BaseExtractor(abc.ABC):
    """Convert one file format into a normalized :class:`Document`."""

    #: File extensions (lowercase, with leading dot) this extractor handles.
    extensions: tuple[str, ...] = ()
    #: MIME types this extractor handles.
    mime_types: tuple[str, ...] = ()

    @abc.abstractmethod
    def extract(self, path: Path) -> Document:
        """Parse ``path`` and return a populated ``Document`` (text + pages)."""
        raise NotImplementedError

    # -- helpers shared by concrete extractors ------------------------------
    @staticmethod
    def assemble(
        filename: str,
        mime_type: str,
        page_texts: list[str],
        metadata: dict[str, str] | None = None,
        separator: str = "\n\n",
    ) -> Document:
        """Join page texts into ``full_text`` while recording page offsets.

        This is the single place where global character offsets are computed,
        so every extractor produces consistent, highlightable coordinates.
        """

        pages: list[Page] = []
        chunks: list[str] = []
        cursor = 0
        for i, raw in enumerate(page_texts, start=1):
            text = normalize_text(raw or "")
            start = cursor
            end = start + len(text)
            pages.append(Page(number=i, text=text, char_start=start, char_end=end))
            chunks.append(text)
            # Account for the separator inserted between pages.
            cursor = end + (len(separator) if i < len(page_texts) else 0)

        full_text = separator.join(chunks)
        return Document(
            filename=filename,
            mime_type=mime_type,
            full_text=full_text,
            pages=pages,
            metadata=metadata or {},
        )
