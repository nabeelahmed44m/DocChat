"""Retrieval index over a single document's passages.

Two complementary classical signals:

* **BM25** (``rank_bm25``) — sparse lexical scoring; excellent for exact terms
  such as "Section 7.2" or "indemnification".
* **TF-IDF cosine** (scikit-learn) — vector-space similarity used to re-rank the
  individual sentences inside the passages BM25 surfaced.

Neither is an LLM. If ``rank_bm25`` is unavailable, a self-contained BM25Okapi
implementation is used so the core never hard-fails.
"""

from __future__ import annotations

import math
from collections import Counter

from app.core.exceptions import IndexNotBuiltError
from app.models.document import Document, Passage
from app.services.nlp.preprocess import tokenize


class _FallbackBM25:
    """Minimal BM25Okapi used only when rank_bm25 is not installed."""

    def __init__(self, corpus: list[list[str]], k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.corpus = corpus
        self.doc_len = [len(d) for d in corpus]
        self.avgdl = (sum(self.doc_len) / len(corpus)) if corpus else 0.0
        self.freqs = [Counter(d) for d in corpus]
        df: Counter[str] = Counter()
        for doc in corpus:
            df.update(set(doc))
        n = len(corpus)
        self.idf = {
            term: math.log(1 + (n - freq + 0.5) / (freq + 0.5))
            for term, freq in df.items()
        }

    def get_scores(self, query: list[str]) -> list[float]:
        scores = [0.0] * len(self.corpus)
        for i, freqs in enumerate(self.freqs):
            dl = self.doc_len[i] or 1
            for term in query:
                if term not in freqs:
                    continue
                tf = freqs[term]
                idf = self.idf.get(term, 0.0)
                denom = tf + self.k1 * (1 - self.b + self.b * dl / (self.avgdl or 1))
                scores[i] += idf * (tf * (self.k1 + 1)) / denom
        return scores


def _make_bm25(corpus: list[list[str]]):
    try:
        from rank_bm25 import BM25Okapi

        return BM25Okapi(corpus)
    except ImportError:
        return _FallbackBM25(corpus)


class RetrievalIndex:
    """Hybrid index: BM25 (sparse) + TF-IDF cosine + LSA (dense) sentence scoring."""

    def __init__(self, document: Document, settings=None):
        if not document.passages:
            raise IndexNotBuiltError(
                "document has no passages; run the pipeline before indexing"
            )
        from app.core.config import get_settings

        self.document = document
        self._settings = settings or get_settings()
        self._passages: list[Passage] = document.passages

        # --- BM25 over passages ------------------------------------------
        self._passage_tokens = [tokenize(p.text) for p in self._passages]
        # Guard against all-empty token lists (e.g. numeric-only docs).
        self._passage_tokens = [t or ["\x00"] for t in self._passage_tokens]
        self._bm25 = _make_bm25(self._passage_tokens)

        # --- TF-IDF + LSA over sentences (for intra-passage re-ranking) ---
        self._sentence_texts = [s.text for s in document.sentences]
        self._tfidf = None
        self._sentence_matrix = None
        self._lsa = None  # TruncatedSVD
        self._sentence_lsa = None  # normalized LSA vectors per sentence
        self._build_vector_models()

    @property
    def has_lsa(self) -> bool:
        return self._lsa is not None and self._sentence_lsa is not None

    def _build_vector_models(self) -> None:
        if not self._sentence_texts:
            return
        try:
            from sklearn.feature_extraction.text import TfidfVectorizer

            self._tfidf = TfidfVectorizer(
                tokenizer=tokenize,
                preprocessor=lambda x: x,
                token_pattern=None,
                lowercase=False,
            )
            self._sentence_matrix = self._tfidf.fit_transform(self._sentence_texts)
        except ImportError:
            self._tfidf = None  # engine falls back to BM25-only sentence scoring
            return

        # --- LSA: TruncatedSVD over the TF-IDF matrix --------------------
        # Latent Semantic Analysis captures synonymy/topic structure so a query
        # can match sentences that share meaning but few exact words — dense
        # retrieval, no neural model. Skipped for tiny docs where SVD is moot.
        if not self._settings.lsa_enabled:
            return
        n_docs, n_terms = self._sentence_matrix.shape
        max_components = max(1, min(n_docs, n_terms) - 1)
        if max_components < 2:
            return
        try:
            import numpy as np
            from sklearn.decomposition import TruncatedSVD
            from sklearn.preprocessing import normalize

            k = min(self._settings.lsa_components, max_components)
            self._lsa = TruncatedSVD(n_components=k, random_state=42)
            reduced = self._lsa.fit_transform(self._sentence_matrix)
            self._sentence_lsa = normalize(reduced)
            self._np = np
            self._normalize = normalize
        except Exception:  # SVD can fail on degenerate matrices
            self._lsa = None
            self._sentence_lsa = None

    # -- retrieval ---------------------------------------------------------
    def search_passages(self, query: str, top_k: int) -> list[tuple[Passage, float]]:
        """Return up to ``top_k`` passages ranked by BM25, with scores."""

        q_tokens = tokenize(query) or ["\x00"]
        scores = self._bm25.get_scores(q_tokens)
        ranked = sorted(
            zip(self._passages, scores), key=lambda pair: pair[1], reverse=True
        )
        return ranked[:top_k]

    def sentence_similarity(self, query: str, sentence_indices: list[int]) -> dict[int, float]:
        """Cosine similarity between the query and specific sentences.

        Falls back to lexical overlap when scikit-learn is unavailable.
        """

        if not sentence_indices:
            return {}

        if self._tfidf is not None and self._sentence_matrix is not None:
            from sklearn.metrics.pairwise import cosine_similarity

            q_vec = self._tfidf.transform([query])
            sub = self._sentence_matrix[sentence_indices]
            sims = cosine_similarity(q_vec, sub)[0]
            return {idx: float(sim) for idx, sim in zip(sentence_indices, sims)}

        # Lexical-overlap fallback (Jaccard on token sets).
        q_set = set(tokenize(query))
        out: dict[int, float] = {}
        for idx in sentence_indices:
            s_set = set(tokenize(self._sentence_texts[idx]))
            if not q_set or not s_set:
                out[idx] = 0.0
            else:
                out[idx] = len(q_set & s_set) / len(q_set | s_set)
        return out

    def lsa_similarity(self, query: str, sentence_indices: list[int]) -> dict[int, float]:
        """Latent-semantic cosine similarity between query and sentences.

        Returns all-zeros when LSA is disabled/unavailable, so the engine can
        blend it in unconditionally.
        """

        if not sentence_indices or not self.has_lsa or self._tfidf is None:
            return {idx: 0.0 for idx in sentence_indices}

        q_tfidf = self._tfidf.transform([query])
        q_lsa = self._normalize(self._lsa.transform(q_tfidf))
        sub = self._sentence_lsa[sentence_indices]
        sims = sub.dot(q_lsa[0])  # cosine (both L2-normalized)
        return {idx: float(max(0.0, s)) for idx, s in zip(sentence_indices, sims)}
