"""Document endpoints: upload, list, status, ask, analysis, delete.

Upload validates size and format *before* persisting, then hands off to the
background ingestion service and returns ``202 Accepted`` with a ``queued``
record. The client polls ``/status`` until ``ready``, then calls ``/ask``.

When auth is enabled every document is scoped to the API key that uploaded it;
requests for another owner's document get a 404 (existence is not leaked).
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from pathlib import Path

from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse, StreamingResponse

from app.api.auth import get_owner
from app.api.deps import get_ingestion, get_store
from app.api.schemas import (
    AskRequest,
    AskResponse,
    DocumentListResponse,
    DocumentResponse,
    KeyPointsResponse,
    StatusResponse,
    SummaryResponse,
    TablesResponse,
)
from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.records import DocumentRecord, DocumentStatus
from app.services.llm import (
    ask_with_context,
    extract_key_points,
    extract_tables_ai,
    parse_keypoints,
    parse_summary,
    render_keypoints,
    render_summary,
    stream_answer,
    stream_keypoints,
    stream_summary,
    summarize_document,
)
from app.services.extraction import supported_extensions
from app.services.ingestion import IngestionService
from app.services.qa import QAEngine
from app.services.storage import BaseDocumentStore

logger = get_logger(__name__)
router = APIRouter(prefix="/documents", tags=["documents"])

# The payload is raw text, but we declare text/event-stream: Cloudflare (and
# most proxies) exempt SSE from compression and buffering, so chunks reach the
# client the moment they're generated. `no-transform` blocks re-encoding.
_STREAM_MEDIA_TYPE = "text/event-stream; charset=utf-8"
_STREAM_HEADERS = {
    "Cache-Control": "no-cache, no-transform",
    "X-Accel-Buffering": "no",
}


def _prime(stream: Iterator[str]) -> tuple[str, Iterator[str]]:
    """Pull the first chunk so Gemini errors surface *before* headers are sent.

    Once a StreamingResponse starts, the status code is committed; priming lets
    quota/key errors still flow through the registered exception handlers.
    """
    first = next(stream, "")
    return first, stream


def _text_stream(first: str, rest: Iterator[str]) -> StreamingResponse:
    def gen() -> Iterator[str]:
        if first:
            yield first
        yield from rest

    return StreamingResponse(
        gen(), media_type=_STREAM_MEDIA_TYPE, headers=_STREAM_HEADERS
    )


def _require(store: BaseDocumentStore, doc_id: str, owner: str) -> DocumentRecord:
    record = store.get(doc_id)
    # A record owned by someone else is reported as "not found" to avoid leaking
    # that the id exists at all.
    if record is None or record.owner != owner:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"document '{doc_id}' not found",
        )
    return record


def _require_ready(
    store: BaseDocumentStore, doc_id: str, owner: str
) -> tuple[DocumentRecord, QAEngine]:
    """Return the record + a ready engine, or raise the right HTTP error.

    Rebuilds the engine transparently on a cold cache (e.g. after a restart the
    record is READY but the in-memory index is gone).
    """

    record = _require(store, doc_id, owner)
    if record.status is DocumentStatus.FAILED:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"document processing failed: {record.error}",
        )
    if record.status is not DocumentStatus.READY:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"document is not ready (status: {record.status.value})",
        )
    engine = store.get_engine(doc_id)
    if engine is None:
        logger.info("rebuilding engine for %s (cold cache)", doc_id)
        from app.pipeline import ingest

        engine = ingest(store.get_file_path(doc_id)).engine
        store.set_engine(doc_id, engine)
    return record, engine


@router.post(
    "",
    response_model=DocumentResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Upload a document for processing",
)
async def upload_document(
    file: UploadFile,
    persist: bool = Form(
        default=True,
        description="If false, process for this session only and never store the document",
    ),
    display_name: str | None = Form(
        default=None,
        description="Human-readable filename to use instead of the raw upload filename",
    ),
    store: BaseDocumentStore = Depends(get_store),
    ingestion: IngestionService = Depends(get_ingestion),
    owner: str = Depends(get_owner),
) -> DocumentResponse:
    settings = get_settings()

    ext = Path(file.filename or "").suffix.lower()
    if ext not in supported_extensions():
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=(
                f"unsupported file type '{ext or 'unknown'}'. "
                f"Supported: {', '.join(supported_extensions())}"
            ),
        )

    data = await file.read()
    if not data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="uploaded file is empty"
        )
    if len(data) > settings.max_file_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=(
                f"file exceeds the {settings.max_file_bytes} byte limit "
                f"({len(data)} bytes)"
            ),
        )

    # Free-tier gate: files above the free limit require an active Pro subscription.
    if settings.billing_enabled and len(data) > settings.free_tier_bytes:
        from app.services.storage.subscription_store import get_subscription_store

        sub = get_subscription_store().get(owner)
        if sub is None or not sub.is_pro:
            raise HTTPException(
                status_code=402,
                detail={
                    "code": "upgrade_required",
                    "message": (
                        f"Free plan supports documents up to "
                        f"{settings.free_tier_bytes // (1024 * 1024)} MB. "
                        "Upgrade to Pro for files up to 50 MB."
                    ),
                    "file_size_bytes": len(data),
                    "limit_bytes": settings.free_tier_bytes,
                },
            )

    record = store.create(
        filename=display_name or file.filename or f"upload{ext}",
        mime_type=file.content_type or "application/octet-stream",
        data=data,
        owner=owner,
        persist=persist,
    )
    ingestion.submit(record.id)
    return DocumentResponse.from_record(record)


@router.get("", response_model=DocumentListResponse, summary="List documents")
async def list_documents(
    store: BaseDocumentStore = Depends(get_store),
    owner: str = Depends(get_owner),
) -> DocumentListResponse:
    records = store.list(owner=owner)
    return DocumentListResponse(
        documents=[DocumentResponse.from_record(r) for r in records],
        count=len(records),
    )


@router.get(
    "/{doc_id}", response_model=DocumentResponse, summary="Get a document record"
)
async def get_document(
    doc_id: str,
    store: BaseDocumentStore = Depends(get_store),
    owner: str = Depends(get_owner),
) -> DocumentResponse:
    return DocumentResponse.from_record(_require(store, doc_id, owner))


@router.get(
    "/{doc_id}/file",
    summary="Download or view the original uploaded file",
)
async def get_file(
    doc_id: str,
    store: BaseDocumentStore = Depends(get_store),
    owner: str = Depends(get_owner),
) -> FileResponse:
    record = _require(store, doc_id, owner)
    try:
        file_path = store.get_file_path(doc_id)
    except FileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found",
        )
    return FileResponse(
        path=str(file_path),
        media_type=record.mime_type,
        filename=record.filename,
        headers={"Content-Disposition": f'inline; filename="{record.filename}"'},
    )


@router.get(
    "/{doc_id}/status",
    response_model=StatusResponse,
    summary="Poll processing status",
)
async def get_status(
    doc_id: str,
    store: BaseDocumentStore = Depends(get_store),
    owner: str = Depends(get_owner),
) -> StatusResponse:
    record = _require(store, doc_id, owner)
    return StatusResponse(
        id=record.id, status=record.status, error=record.error, stats=record.stats
    )


@router.post(
    "/{doc_id}/ask",
    response_model=AskResponse,
    summary="Ask a question about a processed document",
)
async def ask_document(
    doc_id: str,
    payload: AskRequest,
    store: BaseDocumentStore = Depends(get_store),
    owner: str = Depends(get_owner),
) -> AskResponse:
    record, engine = _require_ready(store, doc_id, owner)
    passage_hits = engine.index.search_passages(payload.question, top_k=payload.top_k)
    passages = [p.text for p, _ in passage_hits]
    answer = await asyncio.to_thread(
        ask_with_context,
        passages,
        payload.question,
        record.filename,
        payload.history,
    )
    return AskResponse(document_id=doc_id, question=payload.question, answer=answer)


@router.post(
    "/{doc_id}/ask/stream",
    summary="Ask a question and stream the answer as plain-text chunks",
)
async def ask_document_stream(
    doc_id: str,
    payload: AskRequest,
    store: BaseDocumentStore = Depends(get_store),
    owner: str = Depends(get_owner),
) -> StreamingResponse:
    record, engine = _require_ready(store, doc_id, owner)
    passage_hits = engine.index.search_passages(payload.question, top_k=payload.top_k)
    passages = [p.text for p, _ in passage_hits]
    stream = stream_answer(passages, payload.question, record.filename, payload.history)
    first, rest = await asyncio.to_thread(_prime, stream)
    return _text_stream(first, rest)


@router.get(
    "/{doc_id}/summary/stream",
    summary="Stream the raw summary text (SUMMARY:/BULLET POINTS: format)",
)
async def get_summary_stream(
    doc_id: str,
    store: BaseDocumentStore = Depends(get_store),
    owner: str = Depends(get_owner),
) -> StreamingResponse:
    record, engine = _require_ready(store, doc_id, owner)
    cached = store.get_analysis(doc_id, "summary_gemini")
    if cached is not None:
        return _text_stream(render_summary(cached), iter(()))

    stream = stream_summary(engine.document.full_text, record.filename)
    first, rest = await asyncio.to_thread(_prime, stream)

    def gen() -> Iterator[str]:
        parts = [first] if first else []
        if first:
            yield first
        for chunk in rest:
            parts.append(chunk)
            yield chunk
        store.set_analysis(doc_id, "summary_gemini", parse_summary("".join(parts)))

    return StreamingResponse(
        gen(), media_type=_STREAM_MEDIA_TYPE, headers=_STREAM_HEADERS
    )


@router.get(
    "/{doc_id}/keypoints/stream",
    summary="Stream the raw key points text (KEY POINTS:/IMPORTANT TERMS: format)",
)
async def get_keypoints_stream(
    doc_id: str,
    store: BaseDocumentStore = Depends(get_store),
    owner: str = Depends(get_owner),
) -> StreamingResponse:
    record, engine = _require_ready(store, doc_id, owner)
    cached = store.get_analysis(doc_id, "keypoints_gemini")
    if cached is not None:
        return _text_stream(render_keypoints(cached), iter(()))

    stream = stream_keypoints(engine.document.full_text, record.filename)
    first, rest = await asyncio.to_thread(_prime, stream)

    def gen() -> Iterator[str]:
        parts = [first] if first else []
        if first:
            yield first
        for chunk in rest:
            parts.append(chunk)
            yield chunk
        store.set_analysis(doc_id, "keypoints_gemini", parse_keypoints("".join(parts)))

    return StreamingResponse(
        gen(), media_type=_STREAM_MEDIA_TYPE, headers=_STREAM_HEADERS
    )


@router.get(
    "/{doc_id}/summary",
    response_model=SummaryResponse,
    summary="AI-generated summary of a document",
)
async def get_summary(
    doc_id: str,
    store: BaseDocumentStore = Depends(get_store),
    owner: str = Depends(get_owner),
) -> SummaryResponse:
    record, engine = _require_ready(store, doc_id, owner)
    cached = store.get_analysis(doc_id, "summary_gemini")
    if cached is None:
        cached = await asyncio.to_thread(
            summarize_document, engine.document.full_text, record.filename
        )
        store.set_analysis(doc_id, "summary_gemini", cached)
    return SummaryResponse(document_id=doc_id, **cached)  # type: ignore[arg-type]


@router.get(
    "/{doc_id}/keypoints",
    response_model=KeyPointsResponse,
    summary="AI-extracted key points and important terms from a document",
)
async def get_keypoints(
    doc_id: str,
    store: BaseDocumentStore = Depends(get_store),
    owner: str = Depends(get_owner),
) -> KeyPointsResponse:
    record, engine = _require_ready(store, doc_id, owner)
    cached = store.get_analysis(doc_id, "keypoints_gemini")
    if cached is None:
        cached = await asyncio.to_thread(
            extract_key_points, engine.document.full_text, record.filename
        )
        store.set_analysis(doc_id, "keypoints_gemini", cached)
    return KeyPointsResponse(document_id=doc_id, **cached)  # type: ignore[arg-type]


@router.get(
    "/{doc_id}/tables",
    response_model=TablesResponse,
    summary="Genuine data tables extracted from the document by Gemini",
)
async def get_tables(
    doc_id: str,
    store: BaseDocumentStore = Depends(get_store),
    owner: str = Depends(get_owner),
) -> TablesResponse:
    record, engine = _require_ready(store, doc_id, owner)
    # The full document text always goes to Gemini — no local layout heuristics.
    cached = store.get_analysis(doc_id, "tables_v3")
    if cached is None:
        cached = await asyncio.to_thread(
            extract_tables_ai, engine.document.full_text, record.filename
        )
        store.set_analysis(doc_id, "tables_v3", cached)
    return TablesResponse(document_id=doc_id, **cached)  # type: ignore[arg-type]


@router.delete(
    "/{doc_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a document",
)
async def delete_document(
    doc_id: str,
    store: BaseDocumentStore = Depends(get_store),
    owner: str = Depends(get_owner),
) -> None:
    # Ownership check first (404 if not owned), then delete.
    _require(store, doc_id, owner)
    store.delete(doc_id)
