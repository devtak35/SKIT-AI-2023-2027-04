from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.transcript_repository import transcript_repository


client = TestClient(app)


def setup_function() -> None:
    transcript_repository.clear()


def add_segment(session_id: str, event_id: str) -> None:
    response = client.post("/v1/transcript-segments", json={
        "schema_version": "1.0",
        "event_id": event_id,
        "session_id": session_id,
        "created_at": "2026-11-13T10:00:00Z",
        "payload": {
            "segment_id": f"segment-{session_id}", "revision": 1, "is_final": True,
            "start_ms": 0, "end_ms": 1200, "speaker_id": "SPEAKER_01",
            "text": "Stored meeting evidence.", "asr_confidence": 0.95,
        },
    })
    assert response.status_code == 201


def test_meeting_can_be_renamed_and_keeps_its_evidence() -> None:
    add_segment("planning", "planning-event")

    response = client.patch("/v1/sessions/planning", json={"title": "  Sprint review  "})

    assert response.status_code == 200
    assert response.json()["title"] == "Sprint review"
    assert response.json()["segment_count"] == 1
    assert client.get("/v1/sessions/planning/transcript-segments").json()["segments"][0]["text"] == "Stored meeting evidence."


def test_meeting_can_be_deleted_with_its_evidence_without_removing_other_meetings() -> None:
    add_segment("planning", "planning-event")
    add_segment("retrospective", "retro-event")
    for session_id in ("planning", "retrospective"):
        graph_response = client.post("/v1/graph/records", json={
            "session_id": session_id,
            "entities": [{
                "entity_id": "shared-topic", "entity_type": "topic", "display_name": "Release plan",
                "confidence": 0.8,
                "evidence": [{"segment_id": f"segment-{session_id}", "revision": 1}],
            }],
        })
        assert graph_response.status_code == 201

    response = client.delete("/v1/sessions/planning")

    assert response.status_code == 204
    assert [item["session_id"] for item in client.get("/v1/sessions").json()] == ["retrospective"]
    assert client.get("/v1/sessions/planning/transcript-segments").status_code == 404
    assert client.get("/v1/sessions/retrospective/transcript-segments").json()["segments"][0]["text"] == "Stored meeting evidence."
    records = client.get("/v1/sessions/retrospective/records").json()["records"]
    shared_topic = next(record for record in records if record["record_id"] == "shared-topic")
    assert [item["segment_id"] for item in shared_topic["evidence"]] == ["segment-retrospective"]


def test_meeting_rename_validates_title_and_reports_unknown_meetings() -> None:
    add_segment("planning", "planning-event")

    blank = client.patch("/v1/sessions/planning", json={"title": "   "})
    missing = client.delete("/v1/sessions/unknown")

    assert blank.status_code == 422
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "SESSION_NOT_FOUND"


def test_meeting_mutation_routes_allow_browser_cors_preflight() -> None:
    for method in ("PATCH", "DELETE"):
        response = client.options(
            "/v1/sessions/planning",
            headers={
                "Origin": "http://127.0.0.1:5173",
                "Access-Control-Request-Method": method,
                "Access-Control-Request-Headers": "content-type",
            },
        )

        assert response.status_code == 200
        assert method in response.headers["access-control-allow-methods"]
