"""Tests for LSA (latent-semantic) dense retrieval in the hybrid index."""

from __future__ import annotations

from app.core.config import get_settings
from app.services.extraction import extract
from app.services.nlp.segmentation import build_passages, segment_sentences
from app.services.qa import RetrievalIndex


def _index(path, settings=None):
    settings = settings or get_settings()
    doc = extract(path)
    doc.sentences = segment_sentences(doc)
    doc.passages = build_passages(doc, settings.passage_window, settings.passage_stride)
    return RetrievalIndex(doc, settings), doc


def test_lsa_model_is_built(sample_contract_path):
    index, _ = _index(sample_contract_path)
    assert index.has_lsa  # the sample contract is large enough for SVD


def test_lsa_similarity_scores_are_bounded(sample_contract_path):
    index, doc = _index(sample_contract_path)
    indices = [s.index for s in doc.sentences[:8]]
    sims = index.lsa_similarity("payment and fees", indices)
    assert set(sims) == set(indices)
    assert all(0.0 <= v <= 1.0001 for v in sims.values())


def test_lsa_disabled_returns_zeros(sample_contract_path, monkeypatch):
    monkeypatch.setenv("DOCCHAT_LSA_ENABLED", "false")
    get_settings.cache_clear()
    try:
        settings = get_settings()
        index, doc = _index(sample_contract_path, settings)
        assert not index.has_lsa
        sims = index.lsa_similarity("anything", [0, 1])
        assert sims == {0: 0.0, 1: 0.0}
    finally:
        get_settings.cache_clear()


def test_hybrid_answer_still_correct(contract_result):
    # With LSA blended in, the core QA answers must not regress.
    answers = contract_result.engine.answer("How much is the monthly retainer?", top_k=3)
    assert any("$12,500" in a.text for a in answers)
