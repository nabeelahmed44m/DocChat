"""Sentence segmentation and passage construction.

Segmentation prefers ``pysbd`` (a rule-based, model-free sentence boundary
detector — a good fit for the "NLP concepts, no LLM" constraint). If pysbd is
unavailable we fall back to a regex splitter with abbreviation handling.

Both paths return offsets into ``Document.full_text`` so answers remain
locatable in the source file.
"""

from __future__ import annotations

import re

from app.models.document import Document, Page, Sentence
from app.services.nlp.preprocess import tokenize

# Common abbreviations that must NOT end a sentence.
_ABBREVIATIONS = {
    "mr", "mrs", "ms", "dr", "prof", "sr", "jr", "st", "inc", "ltd", "co",
    "corp", "llc", "llp", "no", "vs", "etc", "e.g", "i.e", "al", "fig", "sec",
    "art", "para", "vol", "ch",
}

_SENT_BOUNDARY_RE = re.compile(r"([.!?])[\"')\]]?\s+(?=[A-Z0-9])")


def _page_for_offset(pages: list[Page], offset: int) -> int:
    """Return the 1-based page number containing ``offset`` (binary-ish scan)."""

    for page in pages:
        if page.char_start <= offset < page.char_end:
            return page.number
    return pages[-1].number if pages else 1


def _regex_spans(text: str) -> list[tuple[int, int]]:
    """Yield (start, end) sentence spans using regex + abbreviation guard."""

    spans: list[tuple[int, int]] = []
    start = 0
    for match in _SENT_BOUNDARY_RE.finditer(text):
        end = match.end(1)  # position just after the . ! ?
        candidate = text[start:end].strip()
        # Guard: don't split right after a known abbreviation.
        last_word = re.split(r"[\s]", candidate)[-1].rstrip(".").lower()
        if last_word in _ABBREVIATIONS:
            continue
        if candidate:
            spans.append((start, end))
        start = match.end()
    tail = text[start:].strip()
    if tail:
        spans.append((start, len(text.rstrip())))
    return spans


def _pysbd_spans(text: str) -> list[tuple[int, int]] | None:
    """Use pysbd for char-offset spans if it is installed, else ``None``."""

    try:
        import pysbd
    except ImportError:
        return None
    seg = pysbd.Segmenter(language="en", clean=False, char_span=True)
    return [(s.start, s.end) for s in seg.segment(text)]


def segment_sentences(document: Document) -> list[Sentence]:
    """Split ``document.full_text`` into :class:`Sentence` objects with offsets."""

    text = document.full_text
    spans = _pysbd_spans(text) or _regex_spans(text)

    sentences: list[Sentence] = []
    idx = 0
    for start, end in spans:
        raw = text[start:end]
        stripped = raw.strip()
        if not stripped:
            continue
        # Re-anchor offsets to the stripped sentence so they point at real text.
        lead = len(raw) - len(raw.lstrip())
        abs_start = start + lead
        abs_end = abs_start + len(stripped)
        sentences.append(
            Sentence(
                index=idx,
                text=stripped,
                char_start=abs_start,
                char_end=abs_end,
                page_number=_page_for_offset(document.pages, abs_start),
            )
        )
        idx += 1
    return sentences


def build_passages(document: Document, window: int, stride: int):
    """Group sentences into overlapping windows (the BM25 retrieval unit)."""

    from app.models.document import Passage

    sentences = document.sentences
    passages: list[Passage] = []
    if not sentences:
        return passages

    p_idx = 0
    i = 0
    n = len(sentences)
    while i < n:
        window_sents = sentences[i : i + window]
        indices = tuple(s.index for s in window_sents)
        char_start = window_sents[0].char_start
        char_end = window_sents[-1].char_end
        passages.append(
            Passage(
                index=p_idx,
                text=document.full_text[char_start:char_end],
                sentence_indices=indices,
                char_start=char_start,
                char_end=char_end,
                page_number=window_sents[0].page_number,
            )
        )
        p_idx += 1
        if i + window >= n:
            break
        i += stride
    return passages


def content_tokens(text: str) -> list[str]:
    """Convenience wrapper used by the index/engine."""

    return tokenize(text)
