"""FastAPI application entry point for the meeting summarization pipeline."""

from datetime import datetime
import mimetypes
import os
from pathlib import Path
import socket
import tempfile
from typing import Literal
from urllib.error import HTTPError, URLError
from uuid import uuid4

from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, ValidationError, model_validator

from backend.app.transcript_store import StaleTranscriptRevisionError
from backend.app.transcript_repository import (
    SessionAlreadyExistsError,
    SessionNotFoundError,
    SummaryValidationError,
    transcript_repository,
)
from backend.app.graph_repository import GraphRepository, GraphValidationError
from backend.app.intelligence import refresh_session_intelligence
from backend.app.llm import ProviderNotConfiguredError, ProviderRequestError
from backend.app.rag import GroundedRAG
from ml.audio.asr import DeepgramTranscriber


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


class SessionCreateRequest(BaseModel):
    session_id: str = Field(min_length=1, max_length=120, pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]*$")
    title: str = Field(min_length=1, max_length=200)

    @model_validator(mode="after")
    def normalize_title(self) -> "SessionCreateRequest":
        self.title = self.title.strip()
        if not self.title:
            raise ValueError("title must not be blank")
        return self


class SessionUpdateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)

    @model_validator(mode="after")
    def normalize_title(self) -> "SessionUpdateRequest":
        self.title = self.title.strip()
        if not self.title:
            raise ValueError("title must not be blank")
        return self


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
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
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


@app.exception_handler(SessionAlreadyExistsError)
async def session_already_exists(_request: object, _exc: SessionAlreadyExistsError) -> JSONResponse:
    return JSONResponse(status_code=status.HTTP_409_CONFLICT, content={
        "error": {"code": "SESSION_ALREADY_EXISTS", "message": "A meeting already uses this session ID.", "fields": [], "retryable": False}
    })


@app.exception_handler(SummaryValidationError)
async def summary_validation_error(_request: object, exc: SummaryValidationError) -> JSONResponse:
    return JSONResponse(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, content={
        "error": {"code": "SUMMARY_VALIDATION_ERROR", "message": str(exc), "fields": [], "retryable": False}
    })


@app.exception_handler(ProviderNotConfiguredError)
async def provider_not_configured(_request: object, exc: ProviderNotConfiguredError) -> JSONResponse:
    return JSONResponse(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, content={
        "error": {"code": "PROVIDER_NOT_CONFIGURED", "message": str(exc), "fields": [], "retryable": False}
    })


@app.exception_handler(ProviderRequestError)
async def provider_request_failed(_request: object, exc: ProviderRequestError) -> JSONResponse:
    return JSONResponse(status_code=status.HTTP_502_BAD_GATEWAY, content={
        "error": {"code": "PROVIDER_REQUEST_FAILED", "message": str(exc), "fields": [], "retryable": True}
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


@app.post("/v1/sessions", response_model=SessionResponse, status_code=status.HTTP_201_CREATED, tags=["sessions"])
def create_session(request: SessionCreateRequest) -> SessionResponse:
    """Create a named meeting before recording or transcript delivery begins."""
    record = transcript_repository.create_session(
        session_id=request.session_id,
        title=request.title,
        created_at=datetime.now().astimezone().isoformat(),
    )
    return SessionResponse(**record)


@app.patch("/v1/sessions/{session_id}", response_model=SessionResponse, tags=["sessions"])
def update_session(session_id: str, request: SessionUpdateRequest) -> SessionResponse:
    """Rename a persisted meeting without changing its evidence."""
    return SessionResponse(**transcript_repository.update_session_title(session_id, request.title))


@app.delete("/v1/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["sessions"])
def delete_session(session_id: str) -> None:
    """Remove a meeting and all evidence and derived records owned by it."""
    transcript_repository.delete_session(session_id)


def _audio_provider_error(exc: Exception) -> str:
    """Translate provider failures to useful messages without exposing payloads."""
    if isinstance(exc, HTTPError):
        if exc.code == 401:
            return "Deepgram rejected the configured API key. Check that it is valid and has speech-to-text access."
        if exc.code == 402:
            return "Deepgram account billing is inactive or out of credits. Check the Deepgram project."
        if exc.code == 403:
            return "The configured Deepgram key does not have permission to transcribe recordings."
        if exc.code in (400, 415):
            return "Deepgram rejected this recording or its encoding. Try a supported audio or video format."
        if exc.code == 429:
            return "Deepgram rate limit reached. Wait a moment and try again."
        return f"Deepgram returned HTTP {exc.code}. Check the Deepgram service and project configuration."
    if isinstance(exc, URLError):
        reason = exc.reason
        if isinstance(reason, (TimeoutError, socket.timeout)) or "timed out" in str(reason).lower():
            return "Deepgram timed out while uploading or transcribing this recording. Try a shorter recording or retry."
        if isinstance(reason, socket.gaierror):
            return "The API server could not resolve Deepgram's address. Check its DNS and network connection."
        return "Could not connect to Deepgram. Check the API server's network connection and try again."
    return "Deepgram returned an unreadable or unexpected response. Check the API logs and try again."


@app.post("/v1/sessions/{session_id}/audio", status_code=status.HTTP_201_CREATED, tags=["audio"])
async def transcribe_session_audio(
    session_id: str,
    file: UploadFile = File(...),
    title: str = Form(default=""),
) -> dict[str, object]:
    """Transcribe audio or the audio track of an uploaded meeting video.

    Media bytes are buffered only for this request and removed after
    transcription. Provider or configuration failures never fall back to
    fixture transcripts.
    """
    normalized_title = title.strip() or session_id
    try:
        SessionCreateRequest(session_id=session_id, title=normalized_title)
    except ValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="The session ID or meeting title is invalid.") from exc

    api_key = os.getenv("DEEPGRAM_API_KEY", "").strip()
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="DEEPGRAM_API_KEY is not configured. Set it in the root .env file and restart the API.",
        )

    content_type = (file.content_type or "").split(";", 1)[0].strip().lower()
    if content_type in ("", "application/octet-stream"):
        content_type = mimetypes.guess_type(file.filename or "")[0] or content_type
    if not (content_type.startswith("audio/") or content_type.startswith("video/")):
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="Upload an audio or video recording in a supported format.")

    max_upload_bytes = int(os.getenv("MAX_MEDIA_UPLOAD_BYTES", os.getenv("MAX_AUDIO_UPLOAD_BYTES", str(100 * 1024 * 1024))))
    media_bytes = await file.read(max_upload_bytes + 1)
    await file.close()
    if len(media_bytes) > max_upload_bytes:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail=f"Recording uploads are limited to {max_upload_bytes} bytes.")
    if not media_bytes:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="The uploaded recording is empty.")

    temporary_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(prefix="skit-recording-", suffix=".upload", delete=False) as media_file:
            media_file.write(media_bytes)
            temporary_path = media_file.name
        segments = DeepgramTranscriber(api_key).transcribe(Path(temporary_path), content_type=content_type)
    except Exception as exc:
        # Do not expose provider response bodies or request headers, which may
        # contain sensitive transcript/provider information.
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=_audio_provider_error(exc)) from exc
    finally:
        if temporary_path:
            Path(temporary_path).unlink(missing_ok=True)

    if not segments:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="The provider returned no transcript segments for this recording. Check that it contains audible speech.")

    known_sessions = {record["session_id"] for record in transcript_repository.list_sessions()}
    if session_id not in known_sessions:
        transcript_repository.create_session(
            session_id=session_id,
            title=normalized_title,
            created_at=datetime.now().astimezone().isoformat(),
        )

    upload_id = uuid4().hex
    created_at = datetime.now().astimezone().isoformat()
    stored_segments: list[str] = []
    for segment in segments:
        segment_id = f"audio-{upload_id}-{segment.segment_id}"
        transcript_repository.accept(
            event_id=f"{upload_id}:{segment.segment_id}",
            session_id=session_id,
            created_at=created_at,
            segment_id=segment_id,
            revision=1,
            is_final=True,
            start_ms=segment.start_ms,
            end_ms=segment.end_ms,
            speaker_id=segment.speaker_id,
            text=segment.text,
            asr_confidence=segment.confidence,
        )
        stored_segments.append(segment_id)
    return {
        "session_id": session_id,
        "provider": "deepgram",
        "segments_stored": len(stored_segments),
        "segment_ids": stored_segments,
    }


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


@app.post("/v1/sessions/{session_id}/intelligence", tags=["intelligence"])
def generate_session_intelligence(session_id: str) -> dict[str, object]:
    """Generate an evidence-cited summary and graph records with configured Groq."""
    try:
        return refresh_session_intelligence(session_id, transcript_repository, graph_repository)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


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
