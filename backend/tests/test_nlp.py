"""Tests for tokenization, segmentation, and passage building."""

from __future__ import annotations

from app.models.document import Document
from app.services.extraction import extract
from app.services.nlp.preprocess import tokenize
from app.services.nlp.segmentation import build_passages, segment_sentences


def test_tokenize_removes_stopwords_and_keeps_identifiers():
    tokens = tokenize("The payment under Section 7.2 is due on 2024-01-01.")
    assert "the" not in tokens
    assert "section" in tokens
    assert "7.2" in tokens
    assert "2024-01-01" in tokens


def test_tokenize_stems_plurals():
    assert tokenize("obligations", remove_stopwords=False) == tokenize(
        "obligation", remove_stopwords=False
    )


def test_segmentation_offsets_point_at_source_text(sample_contract_path):
    doc = extract(sample_contract_path)
    sentences = segment_sentences(doc)
    assert len(sentences) > 5
    for sent in sentences:
        assert doc.full_text[sent.char_start : sent.char_end] == sent.text


def test_abbreviations_do_not_oversplit():
    doc = Document(
        filename="x.txt",
        mime_type="text/plain",
        full_text="Dr. Smith signed the deal. He was pleased.",
        pages=[],
    )
    from app.models.document import Page

    doc.pages = [Page(1, doc.full_text, 0, len(doc.full_text))]
    sents = segment_sentences(doc)
    assert len(sents) == 2
    assert sents[0].text.startswith("Dr. Smith")


def test_build_passages_windows_and_overlap(sample_contract_path):
    doc = extract(sample_contract_path)
    doc.sentences = segment_sentences(doc)
    passages = build_passages(doc, window=3, stride=2)
    assert passages
    # Every passage's text must be a substring of full_text at its offsets.
    for p in passages:
        assert doc.full_text[p.char_start : p.char_end] == p.text
    # Overlap: consecutive passages should share at least one sentence index.
    if len(passages) >= 2:
        assert set(passages[0].sentence_indices) & set(passages[1].sentence_indices)
