"""Extractive QA engine.

Given an indexed document and a natural-language question, it:

1. Retrieves the top passages by BM25.
2. Scores every candidate sentence inside those passages by a weighted blend of
   BM25 (passage-level) and TF-IDF cosine (sentence-level).
3. Applies a light answer-type boost: e.g. "when" questions favor sentences
   containing dates, "how much" favors monetary/numeric spans. This is done with
   regex patterns (and spaCy NER when available) — still no LLM.
4. Returns the best sentences as :class:`Answer` objects with page citations and
   surrounding context.
"""

from __future__ import annotations

import re

from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.models.document import Answer, Document
from app.services.nlp.preprocess import QUESTION_WORDS, tokenize
from app.services.qa.index import RetrievalIndex

logger = get_logger(__name__)

# Regex signals for answer typing (fast, dependency-free).
_DATE_RE = re.compile(
    r"\b(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}[/-]\d{1,2}[/-]\d{1,2}|"
    r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+\d{1,2}|"
    r"\d{1,2}\s+(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*)\b",
    re.IGNORECASE,
)
_MONEY_RE = re.compile(r"(\$|usd|eur|gbp|€|£)\s?\d[\d,]*(\.\d+)?|\b\d[\d,]*(\.\d+)?\s?(dollars|percent|%)\b", re.IGNORECASE)
_PERSON_ORG_RE = re.compile(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+|[A-Z]{2,})\b")

# Map question intent -> the regex whose matches should be boosted.
_INTENT_PATTERNS = {
    "when": _DATE_RE,
    "how_much": _MONEY_RE,
    "how_many": _MONEY_RE,
    "who": _PERSON_ORG_RE,
    "where": _PERSON_ORG_RE,
}

_ANSWER_TYPE_BOOST = 0.15


def _detect_intent(question: str) -> str | None:
    q = question.lower().strip()
    if q.startswith("when") or "what date" in q or "what time" in q:
        return "when"
    if "how much" in q or "what amount" in q or "what price" in q or "what cost" in q:
        return "how_much"
    if "how many" in q:
        return "how_many"
    if q.startswith("who"):
        return "who"
    if q.startswith("where"):
        return "where"
    return None


class QAEngine:
    """Answer questions extractively against a single indexed document."""

    def __init__(self, index: RetrievalIndex, settings: Settings | None = None):
        self.index = index
        self.document: Document = index.document
        self.settings = settings or get_settings()

    def answer(self, question: str, top_k: int | None = None) -> list[Answer]:
        """Return ranked :class:`Answer` objects for ``question``."""

        if not question.strip():
            return []

        cfg = self.settings
        top_k = top_k or cfg.top_k_answers
        intent = _detect_intent(question)
        boost_pattern = _INTENT_PATTERNS.get(intent) if intent else None

        passages = self.index.search_passages(question, cfg.top_k_passages)
        if not passages:
            return []

        # Normalize BM25 passage scores to [0, 1] for stable blending.
        max_bm25 = max((s for _, s in passages), default=0.0) or 1.0

        # Gather candidate sentences from the retrieved passages.
        candidate_indices: list[int] = []
        passage_score_by_sentence: dict[int, float] = {}
        passage_of_sentence: dict[int, int] = {}
        for passage, p_score in passages:
            norm = p_score / max_bm25
            for s_idx in passage.sentence_indices:
                # A sentence may appear in overlapping passages; keep its best.
                if norm >= passage_score_by_sentence.get(s_idx, -1.0):
                    passage_score_by_sentence[s_idx] = norm
                    passage_of_sentence[s_idx] = passage.index
                if s_idx not in candidate_indices:
                    candidate_indices.append(s_idx)

        sims = self.index.sentence_similarity(question, candidate_indices)
        lsa_sims = self.index.lsa_similarity(question, candidate_indices)

        scored: list[tuple[int, float, tuple[str, ...]]] = []
        for s_idx in candidate_indices:
            sentence = self.document.sentences[s_idx]
            bm25_part = passage_score_by_sentence.get(s_idx, 0.0)
            tfidf_part = sims.get(s_idx, 0.0)
            lsa_part = lsa_sims.get(s_idx, 0.0)
            score = (
                cfg.bm25_weight * bm25_part
                + cfg.tfidf_weight * tfidf_part
                + cfg.lsa_weight * lsa_part
            )

            entities: tuple[str, ...] = ()
            if boost_pattern is not None:
                matches = boost_pattern.findall(sentence.text)
                if matches:
                    score += _ANSWER_TYPE_BOOST
                    entities = tuple(
                        m if isinstance(m, str) else next((x for x in m if x), "")
                        for m in matches
                    )[:5]

            scored.append((s_idx, score, entities))

        scored.sort(key=lambda t: t[1], reverse=True)

        answers: list[Answer] = []
        seen_pages: set[tuple[int, int]] = set()
        for s_idx, score, entities in scored:
            if score < cfg.min_answer_score:
                continue
            sentence = self.document.sentences[s_idx]
            key = (sentence.page_number, s_idx)
            if key in seen_pages:
                continue
            seen_pages.add(key)
            answers.append(
                Answer(
                    text=sentence.text,
                    score=score,
                    page_number=sentence.page_number,
                    char_start=sentence.char_start,
                    char_end=sentence.char_end,
                    passage_index=passage_of_sentence.get(s_idx, -1),
                    context=self._context_for(s_idx, cfg.context_sentences),
                    matched_entities=entities,
                )
            )
            if len(answers) >= top_k:
                break

        logger.info(
            "answered %r -> %d result(s), intent=%s", question, len(answers), intent
        )
        return answers

    def _context_for(self, s_idx: int, radius: int) -> str:
        """Return the answer sentence plus ``radius`` neighbors on each side."""

        if radius <= 0:
            return self.document.sentences[s_idx].text
        sents = self.document.sentences
        lo = max(0, s_idx - radius)
        hi = min(len(sents), s_idx + radius + 1)
        return " ".join(s.text for s in sents[lo:hi])
