"""Text preprocessing for retrieval.

Pure classical NLP: regex word tokenization, lowercasing, stopword removal, and
a compact Porter-style suffix stripper so that "obligations" and "obligation"
match. No models, no network, deterministic.
"""

from __future__ import annotations

import re

# A pragmatic English stopword list. Kept inline to avoid an NLTK download.
STOPWORDS: frozenset[str] = frozenset(
    """
    a an and are as at be by for from has have he in is it its of on that the
    to was were will with or if then than this these those they you your we our
    but not no do does did done can could should would may might must shall
    i me my mine us who whom whose which what when where why how all any both
    each few more most other some such only own same so too very s t just don
    """.split()
)

# question words are semantically useful for answer-typing; keep them separate
QUESTION_WORDS: frozenset[str] = frozenset(
    "who what when where why how which whom whose".split()
)

_TOKEN_RE = re.compile(r"[a-z0-9]+(?:[.\-/][a-z0-9]+)*")


def _make_stemmer():
    """Return a Snowball (Porter2) stem function, or a conservative fallback.

    Snowball is a classic rule-based stemmer (no model, no network) that maps
    "termination", "terminate", and "terminated" to a common root — which is
    exactly what makes lexical retrieval robust on legal/financial prose.
    """

    try:
        import snowballstemmer

        stemmer = snowballstemmer.stemmer("english")
        return stemmer.stemWord
    except ImportError:  # pragma: no cover - fallback path
        def _fallback(token: str) -> str:
            if len(token) <= 3:
                return token
            for suffix in ("ies", "ing", "ed", "ly", "es", "s"):
                if token.endswith(suffix) and len(token) - len(suffix) >= 3:
                    return token[: -len(suffix)]
            return token

        return _fallback


_STEM = _make_stemmer()


def _stem(token: str) -> str:
    # Leave alphanumeric identifiers (dates, clause numbers) untouched.
    if any(ch.isdigit() for ch in token):
        return token
    return _STEM(token)


def tokenize(text: str, *, remove_stopwords: bool = True, stem: bool = True) -> list[str]:
    """Turn raw text into normalized retrieval tokens.

    Preserves tokens like ``section 7.2`` and ``2023-01-01`` because dotted and
    hyphenated identifiers matter in legal/financial documents.
    """

    tokens = _TOKEN_RE.findall(text.lower())
    out: list[str] = []
    for tok in tokens:
        if remove_stopwords and tok in STOPWORDS:
            continue
        out.append(_stem(tok) if stem else tok)
    return out
