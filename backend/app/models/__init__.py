"""Domain models shared across extraction, NLP, and QA layers."""

from app.models.document import (
    Answer,
    Document,
    Page,
    Passage,
    Sentence,
)

__all__ = ["Answer", "Document", "Page", "Passage", "Sentence"]
