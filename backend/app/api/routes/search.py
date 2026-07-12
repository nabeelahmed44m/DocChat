"""Cross-document search.

Exact-match search: a document appears in the results only if it literally
contains the query text (case-insensitive). Each result is the verbatim
sentence (or snippet) where the phrase occurs, with its page citation —
no fuzzy ranking, no LLM.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.auth import get_owner
from app.api.deps import get_store
from app.api.schemas import (
    AnswerResponse,
    SearchRequest,
    SearchResponse,
    SearchResultItem,
)
from app.core.logging import get_logger
from app.models.document import Answer, Document
from app.models.records import DocumentStatus
from app.services.storage import BaseDocumentStore

logger = get_logger(__name__)
router = APIRouter(tags=["search"])


def _exact_matches(doc: Document, query: str, limit: int) -> list[Answer]:
    """Find sentences that literally contain *query* (case-insensitive).

    Falls back to a raw full-text snippet when the phrase spans a sentence
    boundary, so a document that does contain the phrase is never missed.
    """
    needle = query.casefold()
    matches: list[Answer] = []

    for s in doc.sentences:
        if needle in s.text.casefold():
            neighbors = doc.sentences[max(0, s.index - 1) : s.index + 2]
            matches.append(
                Answer(
                    text=s.text,
                    score=1.0,
                    page_number=s.page_number,
                    char_start=s.char_start,
                    char_end=s.char_end,
                    passage_index=0,
                    context=" ".join(n.text for n in neighbors),
                )
            )
            if len(matches) >= limit:
                return matches

    if not matches:
        pos = doc.full_text.casefold().find(needle)
        if pos >= 0:
            snippet = doc.full_text[max(0, pos - 80) : pos + len(query) + 120].strip()
            page = 1
            for s in doc.sentences:
                if s.char_end > pos:
                    page = s.page_number
                    break
            matches.append(
                Answer(
                    text=snippet,
                    score=1.0,
                    page_number=page,
                    char_start=pos,
                    char_end=pos + len(query),
                    passage_index=0,
                    context=snippet,
                )
            )

    return matches


@router.post(
    "/search",
    response_model=SearchResponse,
    summary="Exact-match search across all documents",
)
async def search_documents(
    payload: SearchRequest,
    store: BaseDocumentStore = Depends(get_store),
    owner: str = Depends(get_owner),
) -> SearchResponse:
    query = payload.question.strip()
    ready = [r for r in store.list(owner=owner) if r.status is DocumentStatus.READY]

    items: list[SearchResultItem] = []
    searched = 0
    for record in ready:
        engine = store.get_engine(record.id)
        if engine is None:
            # Rebuild a cold engine on demand so search still covers the document.
            from app.pipeline import ingest

            try:
                engine = ingest(record.path).engine
                store.set_engine(record.id, engine)
            except Exception:  # a single bad document shouldn't fail the search
                logger.warning("search skipped %s (rebuild failed)", record.id)
                continue

        searched += 1
        for answer in _exact_matches(engine.document, query, payload.per_document):
            items.append(
                SearchResultItem(
                    document_id=record.id,
                    filename=record.filename,
                    answer=AnswerResponse.from_answer(answer),
                )
            )

    return SearchResponse(
        question=query,
        searched_documents=searched,
        results=items[: payload.top_k],
    )
