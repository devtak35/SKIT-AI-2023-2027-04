from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.transcript_repository import transcript_repository


client = TestClient(app)


def setup_function() -> None:
    transcript_repository.clear()


def upload() -> None:
    response = client.post("/v1/transcript-segments", json={
        "schema_version": "1.0", "event_id": "embedding-event", "session_id": "embedding-session",
        "created_at": "2026-10-25T10:00:00Z",
        "payload": {"segment_id": "embedding-segment", "revision": 1, "is_final": True,
                    "start_ms": 0, "end_ms": 1000, "speaker_id": "SPEAKER_00",
                    "text": "The release checklist is owned by Priya.", "asr_confidence": 0.99},
    })
    assert response.status_code == 201


def test_upload_indexes_revision_for_semantic_retrieval() -> None:
    upload()
    response = client.get("/v1/semantic-search", params={"question": "release checklist"})
    assert response.status_code == 200
    assert response.json()["model"] == "hashing-v1"
    assert response.json()["matches"] == [{
        "session_id": "embedding-session", "segment_id": "embedding-segment",
        "revision": 1, "score": response.json()["matches"][0]["score"],
    }]
    assert response.json()["matches"][0]["score"] > 0


def test_summary_requires_stored_evidence_and_is_dashboard_readable() -> None:
    upload()
    payload = {"summary_id": "running-summary", "version": 1,
               "text": "Priya owns the release checklist.",
               "source_segment_ids": ["embedding-segment"], "is_final": False,
               "created_at": "2026-10-25T10:01:00Z"}
    saved = client.post("/v1/sessions/embedding-session/summaries", json=payload)
    assert saved.status_code == 201
    assert saved.json()["session_id"] == "embedding-session"
    latest = client.get("/v1/sessions/embedding-session/summaries/latest")
    assert latest.status_code == 200
    assert latest.json()["text"] == payload["text"]
    sessions = client.get("/v1/sessions")
    assert sessions.status_code == 200
    assert sessions.json()[0]["segment_count"] == 1


def test_summary_rejects_unknown_evidence() -> None:
    upload()
    response = client.post("/v1/sessions/embedding-session/summaries", json={
        "summary_id": "bad-summary", "version": 1, "text": "Unsupported claim.",
        "source_segment_ids": ["missing-segment"], "created_at": "2026-10-25T10:01:00Z",
    })
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "SUMMARY_VALIDATION_ERROR"


def test_segment_ids_are_scoped_to_a_session_in_storage_and_vector_search() -> None:
    """Dhruv's labels are session-local, so identical IDs must not collide."""
    upload()
    second = client.post("/v1/transcript-segments", json={
        "schema_version": "1.0", "event_id": "other-session-event", "session_id": "other-session",
        "created_at": "2026-10-25T10:02:00Z",
        "payload": {"segment_id": "embedding-segment", "revision": 1, "is_final": True,
                    "start_ms": 0, "end_ms": 1000, "speaker_id": "SPEAKER_00",
                    "text": "Budget approval is pending.", "asr_confidence": 0.99},
    })
    assert second.status_code == 201

    matches = client.get("/v1/semantic-search", params=[("question", "budget approval"), ("session_ids", "other-session")])
    assert matches.status_code == 200
    assert matches.json()["matches"][0]["session_id"] == "other-session"
