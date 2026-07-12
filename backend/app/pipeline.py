"""End-to-end ingestion pipeline.

``ingest(path)`` runs the full Phase 1 flow — extract → segment → build passages
→ build retrieval index — and returns a ready-to-query :class:`QAEngine`. This is
the seam the future API/worker layer will call; the CLI uses it too.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.models.document import Document
from app.services.extraction import extract
from app.services.nlp.segmentation import build_passages, segment_sentences
from app.services.qa import QAEngine, RetrievalIndex

logger = get_logger(__name__)


@dataclass
class IngestResult:
    """Everything produced by ingesting one document."""

    document: Document
    engine: QAEngine
    elapsed_seconds: float

    @property
    def stats(self) -> dict[str, int]:
        return {
            "pages": self.document.page_count,
            "characters": self.document.char_count,
            "sentences": len(self.document.sentences),
            "passages": len(self.document.passages),
        }


def analyze(document: Document, settings: Settings | None = None) -> Document:
    """Populate ``sentences`` and ``passages`` on an extracted document."""

    cfg = settings or get_settings()
    document.sentences = segment_sentences(document)
    document.passages = build_passages(
        document, window=cfg.passage_window, stride=cfg.passage_stride
    )
    return document


def ingest(path: str | Path, settings: Settings | None = None) -> IngestResult:
    """Run the full pipeline and return a queryable result."""

    cfg = settings or get_settings()
    started = time.perf_counter()

    document = extract(path)
    analyze(document, cfg)
    index = RetrievalIndex(document, cfg)
    engine = QAEngine(index, cfg)

    elapsed = time.perf_counter() - started
    logger.info(
        "ingested %s in %.2fs (%d sentences, %d passages)",
        document.filename,
        elapsed,
        len(document.sentences),
        len(document.passages),
    )
    return IngestResult(document=document, engine=engine, elapsed_seconds=elapsed)
