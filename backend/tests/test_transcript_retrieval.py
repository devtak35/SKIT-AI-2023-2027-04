from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.transcript_repository import transcript_repository


client = TestClient(app)


def setup_function() -> None:
    transcript_repository.clear()


def event(event_id: str, revision: int, text: str) -> dict[str, object]:
    return {"schema_version": "1.0", "event_id": event_id, "session_id": "session-retrieval",
            "created_at": "2026-09-27T10:00:00Z", "payload": {"segment_id": "segment-1",
            "revision": revision, "is_final": revision > 1, "start_ms": 100, "end_ms": 900,
            "speaker_id": "SPEAKER_01", "text": text, "asr_confidence": 0.95}}


def test_retrieval_returns_only_the_latest_revision_by_default() -> None:
    assert client.post("/v1/transcript-segments", json=event("event-1", 1, "Draft wording.")).status_code == 201
    assert client.post("/v1/transcript-segments", json=event("event-2", 2, "Corrected wording.")).status_code == 201
    response = client.get("/v1/sessions/session-retrieval/transcript-segments")
    assert response.status_code == 200
    assert [(item["revision"], item["text"]) for item in response.json()["segments"]] == [(2, "Corrected wording.")]


def test_retrieval_can_include_immutable_revision_history() -> None:
    client.post("/v1/transcript-segments", json=event("event-1", 1, "Draft wording."))
    client.post("/v1/transcript-segments", json=event("event-2", 2, "Corrected wording."))
    response = client.get("/v1/sessions/session-retrieval/transcript-segments?include_revisions=true")
    assert response.status_code == 200
    assert [item["revision"] for item in response.json()["segments"]] == [1, 2]


def test_retrieval_reports_an_unknown_session() -> None:
    response = client.get("/v1/sessions/missing/transcript-segments")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "SESSION_NOT_FOUND"
