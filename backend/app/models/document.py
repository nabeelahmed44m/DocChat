"""Normalized document representation.

Every extractor, regardless of source format, produces a :class:`Document`.
Downstream NLP and QA code depends only on these types, which is what makes the
pipeline format-agnostic.

Character offsets are *global* — they index into ``Document.full_text`` — so an
answer can be located precisely and, later, highlighted in the original file.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class Page:
    """A single page/slide/sheet of a source document."""

    number: int  # 1-based
    text: str
    char_start: int  # inclusive offset into Document.full_text
    char_end: int  # exclusive offset into Document.full_text


@dataclass(frozen=True)
class Sentence:
    """A sentence with its position in the document."""

    index: int  # 0-based ordinal across the whole document
    text: str
    char_start: int
    char_end: int
    page_number: int


@dataclass(frozen=True)
class Passage:
    """A retrieval unit: a sliding window over consecutive sentences."""

    index: int
    text: str
    sentence_indices: tuple[int, ...]
    char_start: int
    char_end: int
    page_number: int  # page of the first sentence in the window


@dataclass
class Document:
    """The normalized, format-agnostic document.

    ``sentences`` and ``passages`` are populated by the NLP stage; extractors
    only fill ``full_text`` and ``pages``.
    """

    filename: str
    mime_type: str
    full_text: str
    pages: list[Page] = field(default_factory=list)
    sentences: list[Sentence] = field(default_factory=list)
    passages: list[Passage] = field(default_factory=list)
    metadata: dict[str, str] = field(default_factory=dict)

    @property
    def page_count(self) -> int:
        return len(self.pages)

    @property
    def char_count(self) -> int:
        return len(self.full_text)


@dataclass(frozen=True)
class Answer:
    """A retrieved answer: a verbatim quote plus provenance and score.

    Because this project uses no LLM, an answer is always an exact span of the
    source document, which is why it carries offsets and a page citation.
    """

    text: str
    score: float
    page_number: int
    char_start: int
    char_end: int
    passage_index: int
    context: str  # answer sentence plus neighboring sentences
    matched_entities: tuple[str, ...] = ()

    def citation(self) -> str:
        return f"page {self.page_number}"

    def to_dict(self) -> dict[str, object]:
        """Serialize for the future API layer."""

        return {
            "text": self.text,
            "score": round(self.score, 4),
            "page_number": self.page_number,
            "char_start": self.char_start,
            "char_end": self.char_end,
            "passage_index": self.passage_index,
            "context": self.context,
            "matched_entities": list(self.matched_entities),
            "citation": self.citation(),
        }
