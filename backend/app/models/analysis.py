"""Result types for the Phase 4 analysis features.

Summaries, key points, and tables all stay faithful to the no-LLM contract:
every summary sentence and key point is a verbatim span with a page citation,
and tables are parsed from the document's geometry, not generated.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass(frozen=True)
class SummarySentence:
    """One sentence selected for the extractive summary."""

    text: str
    page_number: int
    char_start: int
    char_end: int
    rank: int  # importance rank (0 = most important)
    order: int  # position in the original document


@dataclass(frozen=True)
class Summary:
    method: str
    sentences: tuple[SummarySentence, ...]
    source_sentence_count: int

    def to_dict(self) -> dict[str, object]:
        return {
            "method": self.method,
            "source_sentence_count": self.source_sentence_count,
            "sentences": [asdict(s) for s in self.sentences],
        }


@dataclass(frozen=True)
class KeyPoint:
    """A salient sentence flagged by a domain rule, with its category."""

    text: str
    category: str  # e.g. "obligation", "monetary", "date", "termination"
    page_number: int
    char_start: int
    char_end: int
    score: float
    highlights: tuple[str, ...] = ()  # the matched spans that triggered it

    def to_dict(self) -> dict[str, object]:
        data = asdict(self)
        data["highlights"] = list(self.highlights)
        return data


@dataclass(frozen=True)
class KeyPoints:
    keyphrases: tuple[str, ...]
    points: tuple[KeyPoint, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "keyphrases": list(self.keyphrases),
            "points": [p.to_dict() for p in self.points],
        }


@dataclass(frozen=True)
class Table:
    page_number: int
    header: tuple[str, ...]
    rows: tuple[tuple[str, ...], ...]

    @property
    def n_rows(self) -> int:
        return len(self.rows)

    @property
    def n_cols(self) -> int:
        return len(self.header) if self.header else (len(self.rows[0]) if self.rows else 0)

    def to_dict(self) -> dict[str, object]:
        return {
            "page_number": self.page_number,
            "header": list(self.header),
            "rows": [list(r) for r in self.rows],
            "n_rows": self.n_rows,
            "n_cols": self.n_cols,
        }


@dataclass(frozen=True)
class Tables:
    engine: str
    tables: tuple[Table, ...] = field(default_factory=tuple)
    note: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "engine": self.engine,
            "count": len(self.tables),
            "note": self.note,
            "tables": [t.to_dict() for t in self.tables],
        }
