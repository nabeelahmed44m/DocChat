"""Key-point extraction: keyphrases (RAKE) + rule-based domain highlights.

Two classical, model-free signals:

* **Keyphrases** via RAKE (Rapid Automatic Keyword Extraction): candidate phrases
  are runs of content words between stopwords/punctuation, scored by word
  degree ÷ frequency. Unsupervised, deterministic, no training data.
* **Domain highlights**: regex rules surface the spans professionals care about —
  monetary amounts, dates, deadlines, percentages, obligation language ("shall",
  "must"), and clause topics (termination, liability, indemnity, confidentiality,
  payment, governing law). This rule layer is the differentiator for legal and
  financial documents.

Every highlight is a verbatim sentence with a page citation.
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict

from app.models.analysis import KeyPoint, KeyPoints
from app.models.document import Document
from app.services.nlp.preprocess import STOPWORDS

_WORD_RE = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9'\-.]*")
_PHRASE_SPLIT_RE = re.compile(r"[^a-zA-Z0-9'\-.\s]+|\s+(?=and\b|or\b|of\b|the\b|to\b)")

# --- domain rules ---------------------------------------------------------
_MONEY_RE = re.compile(
    r"(?:[$€£]\s?\d[\d,]*(?:\.\d+)?|\b\d[\d,]*(?:\.\d+)?\s?(?:dollars|usd|eur|gbp)\b)",
    re.IGNORECASE,
)
_PERCENT_RE = re.compile(r"\b\d+(?:\.\d+)?\s?(?:percent|%)\b", re.IGNORECASE)
_DATE_RE = re.compile(
    r"\b(?:\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}[/-]\d{1,2}[/-]\d{1,2}|"
    r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+\d{1,2},?\s*\d{0,4}|"
    r"\d{1,2}\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*)\b",
    re.IGNORECASE,
)
_DEADLINE_RE = re.compile(
    r"\b(?:within\s+\w+\s+(?:days|months|years|business days)|"
    r"no later than|on or before|by the|prior to|due (?:on|within)|"
    r"\(\d+\)\s*(?:days|months))\b",
    re.IGNORECASE,
)
_OBLIGATION_RE = re.compile(
    r"\b(?:shall|must|is required to|are required to|agrees to|agree to|"
    r"is obligated to|will not|shall not|may not)\b",
    re.IGNORECASE,
)

# Clause-topic keyword categories.
_TOPIC_PATTERNS: dict[str, re.Pattern[str]] = {
    "termination": re.compile(r"\b(?:terminat\w+|cancel\w+|expir\w+)\b", re.IGNORECASE),
    "liability": re.compile(r"\b(?:liabilit\w+|liable|damages|limitation of)\b", re.IGNORECASE),
    "indemnity": re.compile(r"\b(?:indemnif\w+|indemnit\w+|hold harmless)\b", re.IGNORECASE),
    "confidentiality": re.compile(r"\b(?:confidential\w*|non-disclosure|proprietary)\b", re.IGNORECASE),
    "payment": re.compile(r"\b(?:payment|retainer|fee|invoice|remuneration|compensation)\b", re.IGNORECASE),
    "governing_law": re.compile(r"\b(?:governing law|governed by|jurisdiction|laws of)\b", re.IGNORECASE),
}

# Order defines which category "wins" as a sentence's primary label.
_PRIORITY = [
    "obligation",
    "monetary",
    "deadline",
    "termination",
    "liability",
    "indemnity",
    "confidentiality",
    "payment",
    "governing_law",
    "percentage",
    "date",
]

_CATEGORY_WEIGHT: dict[str, float] = {
    "obligation": 1.3,
    "monetary": 1.25,
    "deadline": 1.2,
    "termination": 1.15,
    "liability": 1.15,
    "indemnity": 1.15,
    "confidentiality": 1.0,
    "payment": 1.0,
    "governing_law": 1.0,
    "percentage": 0.9,
    "date": 0.85,
}


def _rake_keyphrases(text: str, top_n: int) -> list[str]:
    """Extract keyphrases with the RAKE algorithm."""

    # 1. Split into candidate phrases at stopwords and punctuation.
    phrases: list[list[str]] = []
    current: list[str] = []
    for token in re.split(r"([^\w'\-]+)", text.lower()):
        word = token.strip()
        if not word:
            continue
        if not _WORD_RE.fullmatch(word) or word in STOPWORDS or len(word) < 2:
            if current:
                phrases.append(current)
                current = []
        else:
            current.append(word)
    if current:
        phrases.append(current)

    # 2. Score words: degree ÷ frequency.
    freq: Counter[str] = Counter()
    degree: Counter[str] = Counter()
    for phrase in phrases:
        deg = len(phrase) - 1
        for w in phrase:
            freq[w] += 1
            degree[w] += deg
    word_score = {w: (degree[w] + freq[w]) / freq[w] for w in freq}

    # 3. Phrase score = sum of member word scores; keep best unique phrases.
    scored: dict[str, float] = {}
    for phrase in phrases:
        if len(phrase) > 4:
            continue
        key = " ".join(phrase)
        score = sum(word_score.get(w, 0.0) for w in phrase)
        scored[key] = max(scored.get(key, 0.0), score)

    ranked = sorted(scored.items(), key=lambda kv: kv[1], reverse=True)
    return [phrase for phrase, _ in ranked[:top_n]]


def _match_categories(sentence: str) -> tuple[dict[str, list[str]], float]:
    """Return {category: matched spans} and an aggregate score for a sentence."""

    found: dict[str, list[str]] = defaultdict(list)

    def add(cat: str, matches: list[str]) -> None:
        for m in matches:
            span = m if isinstance(m, str) else next((x for x in m if x), "")
            if span:
                found[cat].append(span.strip())

    add("monetary", _MONEY_RE.findall(sentence))
    add("percentage", _PERCENT_RE.findall(sentence))
    add("date", _DATE_RE.findall(sentence))
    add("deadline", _DEADLINE_RE.findall(sentence))
    add("obligation", _OBLIGATION_RE.findall(sentence))
    for topic, pattern in _TOPIC_PATTERNS.items():
        add(topic, pattern.findall(sentence))

    score = sum(
        _CATEGORY_WEIGHT.get(cat, 1.0) * len(spans) for cat, spans in found.items()
    )
    return found, score


def extract_key_points(
    document: Document, max_points: int = 20, max_keyphrases: int = 12
) -> KeyPoints:
    """Extract keyphrases and categorized domain highlights from ``document``."""

    keyphrases = tuple(_rake_keyphrases(document.full_text, max_keyphrases))

    scored_points: list[tuple[float, KeyPoint]] = []
    for sentence in document.sentences:
        found, score = _match_categories(sentence.text)
        if not found:
            continue
        primary = next((c for c in _PRIORITY if c in found), next(iter(found)))
        highlights = tuple(dict.fromkeys(  # dedupe, preserve order
            span for spans in found.values() for span in spans
        ))[:6]
        scored_points.append(
            (
                score,
                KeyPoint(
                    text=sentence.text,
                    category=primary,
                    page_number=sentence.page_number,
                    char_start=sentence.char_start,
                    char_end=sentence.char_end,
                    score=round(score, 3),
                    highlights=highlights,
                ),
            )
        )

    scored_points.sort(key=lambda t: t[0], reverse=True)
    points = tuple(kp for _, kp in scored_points[:max_points])
    return KeyPoints(keyphrases=keyphrases, points=points)
