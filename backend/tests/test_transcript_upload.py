from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.transcript_store import transcript_store


client = TestClient(app)


def make_event(*, event_id: str = "evt-001", revision: int = 1) -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "event_id": event_id,
        "session_id": "session-001",
        "created_at": "2026-09-14T09:00:00Z",
        "payload": {
            "segment_id": "segment-001",
            "revision": revision,
            "is_final": revision > 1,
            "start_ms": 0,
            "end_ms": 1800,
            "speaker_id": "SPEAKER_01",
            "text": "We will review the upload contract.",
            "asr_confidence": 0.97,
        },
    }


def setup_function() -> None:
    transcript_store.clear()


def test_upload_accepts_a_valid_transcript_event() -> None:
    response = client.post("/v1/transcript-segments", json=make_event())

    assert response.status_code == 201
    assert response.json() == {
        "status": "accepted",
        "event_id": "evt-001",
        "session_id": "session-001",
        "segment_id": "segment-001",
        "revision": 1,
    }


def test_upload_is_idempotent_for_the_same_event_id() -> None:
    first = client.post("/v1/transcript-segments", json=make_event())
    second = client.post("/v1/transcript-segments", json=make_event())

    assert first.status_code == 201
    assert second.status_code == 201
    assert second.json()["status"] == "duplicate"


def test_upload_rejects_a_stale_segment_revision() -> None:
    client.post("/v1/transcript-segments", json=make_event(event_id="evt-002", revision=2))
    response = client.post("/v1/transcript-segments", json=make_event(event_id="evt-003"))

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "STALE_TRANSCRIPT_REVISION"


def test_upload_rejects_invalid_timing() -> None:
    event = make_event()
    event["payload"]["start_ms"] = 1801  # type: ignore[index]
    response = client.post("/v1/transcript-segments", json=event)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
