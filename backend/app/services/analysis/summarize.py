"""Extractive summarization via TextRank + MMR.

TextRank builds a graph whose nodes are sentences and whose edges are TF-IDF
cosine similarities, then runs PageRank to score each sentence by centrality —
the more a sentence resembles the rest of the document, the more it summarizes
it. MMR (Maximal Marginal Relevance) then greedily selects high-scoring
sentences while penalizing redundancy, so the summary isn't three phrasings of
the same clause.

No LLM: selected sentences are verbatim, ordered as they appear, each carrying a
page citation.
"""

from __future__ import annotations

import numpy as np

from app.models.analysis import Summary, SummarySentence
from app.models.document import Document
from app.services.nlp.preprocess import tokenize

# Sentences shorter than this (in tokens) are ignored as summary candidates —
# they're usually headings or fragments, not summarizing statements.
_MIN_TOKENS = 4
_DAMPING = 0.85
_MMR_LAMBDA = 0.7


def _similarity_matrix(sentences: list[str]) -> np.ndarray:
    """TF-IDF cosine similarity between every pair of sentences."""

    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity

    vec = TfidfVectorizer(
        tokenizer=tokenize, preprocessor=lambda x: x, token_pattern=None, lowercase=False
    )
    matrix = vec.fit_transform(sentences)
    sim = cosine_similarity(matrix)
    np.fill_diagonal(sim, 0.0)
    return sim


def _textrank(sim: np.ndarray, iterations: int = 60, tol: float = 1e-6) -> np.ndarray:
    """PageRank over the sentence similarity graph (power iteration)."""

    n = sim.shape[0]
    if n == 0:
        return np.zeros(0)
    row_sums = sim.sum(axis=1, keepdims=True)
    row_sums[row_sums == 0] = 1.0  # avoid divide-by-zero for isolated sentences
    transition = sim / row_sums

    scores = np.full(n, 1.0 / n)
    teleport = (1.0 - _DAMPING) / n
    for _ in range(iterations):
        prev = scores
        scores = teleport + _DAMPING * transition.T.dot(scores)
        if np.abs(scores - prev).sum() < tol:
            break
    return scores


def _mmr_select(
    candidates: list[int],
    scores: np.ndarray,
    sim: np.ndarray,
    k: int,
) -> list[int]:
    """Greedily pick k sentences balancing importance and non-redundancy."""

    selected: list[int] = []
    pool = list(candidates)
    # Normalize relevance to [0, 1] so lambda blends cleanly with similarity.
    rel = scores.copy()
    span = rel.max() - rel.min()
    if span > 0:
        rel = (rel - rel.min()) / span

    while pool and len(selected) < k:
        best_idx = None
        best_val = -np.inf
        for i in pool:
            redundancy = max((sim[i, j] for j in selected), default=0.0)
            val = _MMR_LAMBDA * rel[i] - (1 - _MMR_LAMBDA) * redundancy
            if val > best_val:
                best_val = val
                best_idx = i
        selected.append(best_idx)  # type: ignore[arg-type]
        pool.remove(best_idx)  # type: ignore[arg-type]
    return selected


def summarize(document: Document, max_sentences: int = 5) -> Summary:
    """Return an extractive summary of ``document``.

    ``max_sentences`` caps the summary length; the effective count also scales
    down for short documents so a 4-sentence doc isn't "summarized" whole.
    """

    sentences = document.sentences
    # Candidate indices: long enough to be summarizing statements.
    candidates = [
        s.index for s in sentences if len(tokenize(s.text)) >= _MIN_TOKENS
    ]
    if not candidates:
        candidates = [s.index for s in sentences]

    if len(candidates) <= max_sentences:
        chosen = candidates
        scores = np.ones(len(sentences))
    else:
        texts = [sentences[i].text for i in candidates]
        sim = _similarity_matrix(texts)
        local_scores = _textrank(sim)
        # Target length grows slowly with document size.
        k = min(max_sentences, max(3, len(candidates) // 8 + 3))
        local_selected = _mmr_select(list(range(len(candidates))), local_scores, sim, k)
        chosen = [candidates[i] for i in local_selected]
        # Map local scores back onto global sentence indices for ranking.
        scores = np.zeros(len(sentences))
        for local_i, global_i in enumerate(candidates):
            scores[global_i] = local_scores[local_i]

    # Rank chosen by importance, then present in reading order.
    ranked = sorted(chosen, key=lambda i: scores[i], reverse=True)
    rank_of = {idx: r for r, idx in enumerate(ranked)}
    ordered = sorted(chosen)

    summary_sentences = tuple(
        SummarySentence(
            text=sentences[i].text,
            page_number=sentences[i].page_number,
            char_start=sentences[i].char_start,
            char_end=sentences[i].char_end,
            rank=rank_of[i],
            order=order,
        )
        for order, i in enumerate(ordered)
    )
    return Summary(
        method="textrank+mmr",
        sentences=summary_sentences,
        source_sentence_count=len(sentences),
    )
