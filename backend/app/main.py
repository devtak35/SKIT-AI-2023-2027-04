"""FastAPI application entry point for the meeting summarization pipeline."""

from datetime import datetime
from typing import Literal

from fastapi import FastAPI, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, model_validator

from backend.app.transcript_store import StaleTranscriptRevisionError
from backend.app.transcript_repository import SessionNotFoundError, transcript_repository


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


app = FastAPI(
    title="AI Realtime Video Summary Generator API",
    description="Backend entry point for the meeting summarization pipeline.",
    version="0.1.0",
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
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
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
