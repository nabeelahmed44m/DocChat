"""API request/response schemas.

Kept separate from the internal dataclasses so the wire format can evolve
independently of the domain model, and so FastAPI generates a clean OpenAPI spec
for the mobile client to consume.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.models.document import Answer
from app.models.records import DocumentRecord, DocumentStatus


class DocumentResponse(BaseModel):
    """Public view of a document record."""

    id: str
    filename: str
    mime_type: str
    size_bytes: int
    status: DocumentStatus
    error: str | None = None
    stats: dict[str, int] = Field(default_factory=dict)
    persist: bool = True
    created_at: str
    updated_at: str

    @classmethod
    def from_record(cls, record: DocumentRecord) -> "DocumentResponse":
        return cls(
            id=record.id,
            filename=record.filename,
            mime_type=record.mime_type,
            size_bytes=record.size_bytes,
            status=record.status,
            error=record.error,
            stats=record.stats,
            persist=record.persist,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )


class DocumentListResponse(BaseModel):
    documents: list[DocumentResponse]
    count: int


class StatusResponse(BaseModel):
    """Lightweight payload for polling."""

    id: str
    status: DocumentStatus
    error: str | None = None
    stats: dict[str, int] = Field(default_factory=dict)


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=1000)
    top_k: int = Field(default=6, ge=1, le=20)
    history: list[dict] = Field(
        default_factory=list,
        description="Conversation history: [{role: user|model, content: str}]",
    )


class AnswerResponse(BaseModel):
    text: str
    score: float
    page_number: int
    char_start: int
    char_end: int
    passage_index: int
    context: str
    matched_entities: list[str] = Field(default_factory=list)
    citation: str

    @classmethod
    def from_answer(cls, answer: Answer) -> "AnswerResponse":
        return cls(**answer.to_dict())


class AskResponse(BaseModel):
    document_id: str
    question: str
    answer: str  # Gemini-generated response


class ErrorResponse(BaseModel):
    detail: str
    code: str


# --- Phase 4: analysis ---------------------------------------------------
class SummarySentenceOut(BaseModel):
    text: str
    page_number: int
    char_start: int
    char_end: int
    rank: int
    order: int


class SummaryResponse(BaseModel):
    document_id: str
    summary: str
    bullet_points: list[str]


class KeyPointsResponse(BaseModel):
    document_id: str
    points: list[str]
    keyphrases: list[str]


class TableOut(BaseModel):
    page_number: int
    header: list[str]
    rows: list[list[str]]
    n_rows: int
    n_cols: int
    title: str | None = None


class TablesResponse(BaseModel):
    document_id: str
    engine: str
    count: int
    note: str | None = None
    tables: list[TableOut]


# --- Phase 5: multi-document search --------------------------------------
class SearchRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=1000)
    top_k: int = Field(default=5, ge=1, le=50)
    per_document: int = Field(default=1, ge=1, le=5)


class SearchResultItem(BaseModel):
    document_id: str
    filename: str
    answer: AnswerResponse


class SearchResponse(BaseModel):
    question: str
    searched_documents: int
    results: list[SearchResultItem]
