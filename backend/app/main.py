"""FastAPI application entry point for the meeting summarization pipeline."""

from datetime import datetime
from typing import Literal

from fastapi import FastAPI, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, model_validator

from backend.app.transcript_store import StaleTranscriptRevisionError
from backend.app.transcript_repository import (
    SessionNotFoundError,
    SummaryValidationError,
    transcript_repository,
)
from backend.app.graph_repository import GraphRepository, GraphValidationError
from backend.app.rag import GroundedRAG


class HealthResponse(BaseModel):
    status: Literal["ok"]
    service: str
    api_version: str


class TranscriptSegmentPayload(BaseModel):
    """The canonical ASR-to-backend transcript-segment hand-off."""

    segment_id: str = Field(min_length=1)
    revision: int = Field(ge=1)
    is_final: bool
    start_ms: int = Field(ge=0)
    end_ms: int = Field(ge=0)
    speaker_id: str = Field(min_length=1)
    text: str = Field(min_length=1)
    asr_confidence: float | None = Field(default=None, ge=0, le=1)

    @model_validator(mode="after")
    def validate_timing(self) -> "TranscriptSegmentPayload":
        if self.end_ms < self.start_ms:
            raise ValueError("end_ms must be greater than or equal to start_ms")
        return self


class TranscriptUploadRequest(BaseModel):
    """Versioned envelope received from the ASR/diarization adapter."""

    schema_version: Literal["1.0"]
    event_id: str = Field(min_length=1)
    session_id: str = Field(min_length=1)
    created_at: datetime
    payload: TranscriptSegmentPayload


class TranscriptUploadResponse(BaseModel):
    """Acknowledge accepted or idempotently repeated transcript input."""

    status: Literal["accepted", "duplicate"]
    event_id: str
    session_id: str
    segment_id: str
    revision: int


class TranscriptSegmentResponse(TranscriptSegmentPayload):
    created_at: datetime


class TranscriptRetrievalResponse(BaseModel):
    session_id: str
    segments: list[TranscriptSegmentResponse]


class SessionResponse(BaseModel):
    session_id: str
    title: str
    status: str
    created_at: datetime
    updated_at: datetime
    segment_count: int


class SummaryWriteRequest(BaseModel):
    summary_id: str = Field(min_length=1)
    version: int = Field(ge=1)
    text: str
    source_segment_ids: list[str] = Field(default_factory=list)
    is_final: bool = False
    created_at: datetime

    @model_validator(mode="after")
    def validate_evidence(self) -> "SummaryWriteRequest":
        if self.text.strip() and not self.source_segment_ids:
            raise ValueError("a non-empty summary requires source_segment_ids")
        if len(self.source_segment_ids) != len(set(self.source_segment_ids)):
            raise ValueError("source_segment_ids must not contain duplicates")
        return self


class SummaryResponse(SummaryWriteRequest):
    session_id: str


class EvidenceRefPayload(BaseModel):
    segment_id: str = Field(min_length=1)
    revision: int = Field(default=1, ge=1)
    start_ms: int | None = Field(default=None, ge=0)
    end_ms: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_timing(self) -> "EvidenceRefPayload":
        if self.start_ms is not None and self.end_ms is not None and self.end_ms < self.start_ms:
            raise ValueError("end_ms must be greater than or equal to start_ms")
        return self


class GraphEntityPayload(BaseModel):
    id: str | None = None
    entity_id: str | None = None
    entity_type: Literal["person", "topic", "decision"] | None = None
    type: Literal["person", "topic", "decision"] | None = None
    display_name: str | None = None
    text: str | None = None
    aliases: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1)
    evidence: list[EvidenceRefPayload] | None = None
    evidence_segment_ids: list[str] | None = None
    properties: dict[str, object] = Field(default_factory=dict)


class GraphActionItemPayload(BaseModel):
    id: str | None = None
    action_item_id: str | None = None
    description: str | None = None
    text: str | None = None
    owner_entity_id: str | None = None
    owner: str | None = None
    owner_status: Literal["assigned", "unassigned", "uncertain"] | None = None
    due_at: datetime | None = None
    due_date_text: str | None = None
    due_date: str | None = None
    status: Literal["open", "in_progress", "blocked", "completed", "cancelled", "needs_review"] = "open"
    confidence: float = Field(ge=0, le=1)
    evidence: list[EvidenceRefPayload] | None = None
    evidence_segment_ids: list[str] | None = None
    source_segment_ids: list[str] | None = None
    related_decision_id: str | None = None
    properties: dict[str, object] = Field(default_factory=dict)


class GraphBatchRequest(BaseModel):
    session_id: str = Field(min_length=1)
    producer: str = Field(default="garvit", min_length=1)
    producer_version: str = Field(default="1", min_length=1)
    entities: list[GraphEntityPayload] = Field(default_factory=list)
    action_items: list[GraphActionItemPayload] = Field(default_factory=list)
    relationships: list[dict[str, object]] = Field(default_factory=list)


class GraphBatchResponse(BaseModel):
    entities: list[dict[str, object]]
    action_items: list[dict[str, object]]


class QueryRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    session_ids: list[str] = Field(default_factory=list)
    top_k: int = Field(default=8, ge=1, le=20)


class Citation(BaseModel):
    session_id: str
    segment_id: str
    revision: int
    start_ms: int
    end_ms: int
    quote: str


class QueryResponse(BaseModel):
    answer: str
    citations: list[Citation]
    insufficient_evidence: bool
    retrieval_metadata: dict[str, object]


graph_repository = GraphRepository(transcript_repository._connection)
rag = GroundedRAG(transcript_repository, graph_repository)


app = FastAPI(
    title="AI Realtime Video Summary Generator API",
    description="Backend entry point for the meeting summarization pipeline.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


@app.get("/health", response_model=HealthResponse, tags=["operations"])
def health() -> HealthResponse:
    """Report that the API process is ready to receive requests."""
    return HealthResponse(status="ok", service="backend", api_version="v1")


@app.exception_handler(RequestValidationError)
async def request_validation_error(
    _request: object, exc: RequestValidationError
) -> JSONResponse:
    """Return the project error envelope for malformed API input."""
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "The request does not match the expected transcript event contract.",
                "fields": [
                    {"path": ".".join(str(part) for part in error["loc"]), "reason": error["msg"]}
                    for error in exc.errors()
                ],
                "retryable": False,
            }
        },
    )


@app.exception_handler(StaleTranscriptRevisionError)
async def stale_transcript_revision(
    _request: object, exc: StaleTranscriptRevisionError
) -> JSONResponse:
    """Return a conflict when a delivery would regress a segment revision."""
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={
            "error": {
                "code": "STALE_TRANSCRIPT_REVISION",
                "message": "A newer or equal revision is already accepted for this segment.",
                "fields": [
                    {
                        "path": "payload.revision",
                        "reason": f"latest accepted revision is {exc.latest_revision}",
                    }
                ],
                "retryable": False,
            }
        },
    )


@app.exception_handler(SessionNotFoundError)
async def session_not_found(_request: object, _exc: SessionNotFoundError) -> JSONResponse:
    """Return the project error envelope for an unknown transcript session."""
    return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={
        "error": {"code": "SESSION_NOT_FOUND", "message": "No transcript session matches this ID.", "fields": [], "retryable": False}
    })


@app.exception_handler(SummaryValidationError)
async def summary_validation_error(_request: object, exc: SummaryValidationError) -> JSONResponse:
    return JSONResponse(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, content={
        "error": {"code": "SUMMARY_VALIDATION_ERROR", "message": str(exc), "fields": [], "retryable": False}
    })


@app.post(
    "/v1/transcript-segments",
    response_model=TranscriptUploadResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["transcripts"],
)
def upload_transcript_segment(event: TranscriptUploadRequest) -> TranscriptUploadResponse:
    """Validate and accept one revision-aware ASR transcript segment.

    The Week 8 repository persists the event, immutable revision, and raw
    speaker attribution atomically using the Week 3 schema.
    """
    accepted, is_new = transcript_repository.accept(
        event_id=event.event_id,
        session_id=event.session_id,
        created_at=event.created_at.isoformat(),
        segment_id=event.payload.segment_id,
        revision=event.payload.revision,
        is_final=event.payload.is_final,
        start_ms=event.payload.start_ms,
        end_ms=event.payload.end_ms,
        speaker_id=event.payload.speaker_id,
        text=event.payload.text,
        asr_confidence=event.payload.asr_confidence,
    )
    return TranscriptUploadResponse(
        status="accepted" if is_new else "duplicate",
        event_id=accepted.event_id,
        session_id=accepted.session_id,
        segment_id=accepted.segment_id,
        revision=accepted.revision,
    )


@app.get("/v1/sessions/{session_id}/transcript-segments", response_model=TranscriptRetrievalResponse, tags=["transcripts"])
def retrieve_transcript_segments(session_id: str, include_revisions: bool = False) -> TranscriptRetrievalResponse:
    """Retrieve ordered transcript segments; default to the latest revision."""
    records = transcript_repository.list_segments(session_id, include_revisions=include_revisions)
    return TranscriptRetrievalResponse(
        session_id=session_id,
        segments=[TranscriptSegmentResponse(**record.__dict__) for record in records],
    )


@app.get("/v1/sessions", response_model=list[SessionResponse], tags=["sessions"])
def list_sessions() -> list[SessionResponse]:
    """List persisted meeting sessions for the dashboard."""
    return [SessionResponse(**record) for record in transcript_repository.list_sessions()]


@app.post("/v1/sessions/{session_id}/summaries", response_model=SummaryResponse, status_code=status.HTTP_201_CREATED, tags=["summaries"])
def save_summary(session_id: str, summary: SummaryWriteRequest) -> SummaryResponse:
    """Store Garvit's evidence-linked running or final summary."""
    stored = transcript_repository.save_summary(
        session_id=session_id,
        **summary.model_dump(mode="json"),
    )
    return SummaryResponse(**stored.__dict__)


@app.get("/v1/sessions/{session_id}/summaries/latest", response_model=SummaryResponse | None, tags=["summaries"])
def retrieve_latest_summary(session_id: str) -> SummaryResponse | None:
    """Return the most recently stored summary, if the producer has emitted one."""
    summary = transcript_repository.latest_summary(session_id)
    return SummaryResponse(**summary.__dict__) if summary else None


@app.get("/v1/semantic-search", tags=["embeddings"])
def semantic_search(
    question: str = Query(min_length=1),
    session_ids: list[str] = Query(default_factory=list),
    top_k: int = Query(default=8, ge=1, le=20),
) -> dict[str, object]:
    """Expose Dev's derived vector-index seam for retrieval integration tests."""
    matches = transcript_repository.embeddings.search(question, session_ids=session_ids, top_k=top_k)
    return {"matches": [match.__dict__ for match in matches], "model": "hashing-v1"}


@app.exception_handler(GraphValidationError)
async def graph_validation_error(_request: object, exc: GraphValidationError) -> JSONResponse:
    return JSONResponse(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, content={
        "error": {"code": "GRAPH_VALIDATION_ERROR", "message": str(exc), "fields": [], "retryable": False}
    })


@app.post("/v1/graph/records", response_model=GraphBatchResponse, status_code=status.HTTP_201_CREATED, tags=["graph"])
def ingest_graph_records(batch: GraphBatchRequest) -> GraphBatchResponse:
    """Persist Garvit's extracted records after evidence and type validation."""
    def as_dict(value):
        return value.model_dump(mode="json", exclude_none=True)

    result = graph_repository.ingest(
        session_id=batch.session_id,
        producer=batch.producer,
        producer_version=batch.producer_version,
        entities=[as_dict(item) for item in batch.entities],
        action_items=[as_dict(item) for item in batch.action_items],
        relationships=batch.relationships,
    )
    return GraphBatchResponse(**result)


@app.get("/v1/sessions/{session_id}/records", tags=["graph"])
def retrieve_graph_records(session_id: str) -> dict[str, object]:
    """Return current graph records and their exact transcript evidence."""
    if session_id not in transcript_repository.list_session_ids():
        raise SessionNotFoundError(session_id)
    records = graph_repository.list_session_records(session_id)
    return {"session_id": session_id, "records": [record.__dict__ for record in records]}


@app.post("/v1/query", response_model=QueryResponse, tags=["rag"])
def query_memory(request: QueryRequest) -> QueryResponse:
    """Answer across stored sessions, or explicitly report insufficient evidence."""
    result = rag.answer(request.question, request.session_ids, request.top_k)
    return QueryResponse(**result)
