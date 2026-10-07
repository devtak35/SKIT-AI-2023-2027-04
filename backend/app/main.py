"""FastAPI application entry point for the meeting summarization pipeline."""

from datetime import datetime
from typing import Literal

from fastapi import FastAPI, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, model_validator

from backend.app.transcript_store import StaleTranscriptRevisionError, transcript_store


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


@app.post(
    "/v1/transcript-segments",
    response_model=TranscriptUploadResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["transcripts"],
)
def upload_transcript_segment(event: TranscriptUploadRequest) -> TranscriptUploadResponse:
    """Validate and accept one revision-aware ASR transcript segment.

    Persistence is deliberately in memory in Week 6. Week 8 replaces this
    boundary's storage implementation with the Week 3 database schema.
    """
    accepted, is_new = transcript_store.accept(
        event_id=event.event_id,
        session_id=event.session_id,
        segment_id=event.payload.segment_id,
        revision=event.payload.revision,
    )
    return TranscriptUploadResponse(
        status="accepted" if is_new else "duplicate",
        event_id=accepted.event_id,
        session_id=accepted.session_id,
        segment_id=accepted.segment_id,
        revision=accepted.revision,
    )
