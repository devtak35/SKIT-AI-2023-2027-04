from fastapi.testclient import TestClient
from urllib.error import URLError

from ml.audio.asr import TranscriptSegment
from backend.app.main import app
from backend.app.transcript_repository import transcript_repository


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
    transcript_repository.clear()


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


def test_create_named_session_before_transcript_delivery() -> None:
    response = client.post("/v1/sessions", json={"session_id": "sprint-planning", "title": "Sprint planning"})

    assert response.status_code == 201
    assert response.json()["title"] == "Sprint planning"
    assert response.json()["status"] == "created"
    assert response.json()["segment_count"] == 0
    duplicate = client.post("/v1/sessions", json={"session_id": "sprint-planning", "title": "Another name"})
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "SESSION_ALREADY_EXISTS"


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


def test_audio_upload_requires_real_provider_credentials(monkeypatch) -> None:
    monkeypatch.setenv("DEEPGRAM_API_KEY", "")
    response = client.post(
        "/v1/sessions/audio-key-required/audio",
        data={"title": "Audio key check"},
        files={"file": ("recording.wav", b"RIFF-audio", "audio/wav")},
    )
    assert response.status_code == 503
    assert "DEEPGRAM_API_KEY" in response.json()["detail"]


def test_audio_upload_transcribes_and_persists_provider_segments(monkeypatch) -> None:
    monkeypatch.setenv("DEEPGRAM_API_KEY", "test-provider-key")

    class Provider:
        def __init__(self, api_key: str) -> None:
            assert api_key == "test-provider-key"

        def transcribe(self, audio_path, *, content_type: str):
            assert audio_path.is_file()
            assert audio_path.read_bytes() == b"RIFF-audio"
            assert content_type == "audio/wav"
            return [TranscriptSegment("asr-0001", 100, 1250, "A real provider transcript.", 0.91, "SPEAKER_00")]

    monkeypatch.setattr("backend.app.main.DeepgramTranscriber", Provider)
    response = client.post(
        "/v1/sessions/audio-integration/audio",
        data={"title": "Audio integration check"},
        files={"file": ("recording.wav", b"RIFF-audio", "audio/wav")},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["provider"] == "deepgram"
    assert body["segments_stored"] == 1
    transcript = client.get("/v1/sessions/audio-integration/transcript-segments")
    assert transcript.status_code == 200
    assert transcript.json()["segments"][0]["text"] == "A real provider transcript."
    assert transcript.json()["segments"][0]["speaker_id"] == "SPEAKER_00"


def test_video_upload_transcribes_its_audio_track_and_persists_segments(monkeypatch) -> None:
    monkeypatch.setenv("DEEPGRAM_API_KEY", "test-provider-key")

    class Provider:
        def __init__(self, api_key: str) -> None:
            assert api_key == "test-provider-key"

        def transcribe(self, media_path, *, content_type: str):
            assert media_path.is_file()
            assert media_path.read_bytes() == b"fake-mp4-container"
            assert content_type == "video/mp4"
            return [TranscriptSegment("asr-0001", 250, 1400, "The meeting video contains speech.", 0.93, "SPEAKER_00")]

    monkeypatch.setattr("backend.app.main.DeepgramTranscriber", Provider)
    response = client.post(
        "/v1/sessions/video-integration/audio",
        data={"title": "Video integration check"},
        files={"file": ("meeting.mp4", b"fake-mp4-container", "video/mp4")},
    )

    assert response.status_code == 201
    assert response.json()["segments_stored"] == 1
    transcript = client.get("/v1/sessions/video-integration/transcript-segments")
    assert transcript.status_code == 200
    assert transcript.json()["segments"][0]["text"] == "The meeting video contains speech."


def test_recording_upload_rejects_non_audio_and_video_content(monkeypatch) -> None:
    monkeypatch.setenv("DEEPGRAM_API_KEY", "test-provider-key")
    response = client.post(
        "/v1/sessions/invalid-recording/audio",
        data={"title": "Invalid recording"},
        files={"file": ("document.pdf", b"not media", "application/pdf")},
    )
    assert response.status_code == 415


def test_video_provider_timeout_has_actionable_error(monkeypatch) -> None:
    monkeypatch.setenv("DEEPGRAM_API_KEY", "test-provider-key")

    class Provider:
        def __init__(self, api_key: str) -> None:
            pass

        def transcribe(self, media_path, *, content_type: str):
            raise URLError(TimeoutError("timed out"))

    monkeypatch.setattr("backend.app.main.DeepgramTranscriber", Provider)
    response = client.post(
        "/v1/sessions/video-timeout/audio",
        data={"title": "Video timeout check"},
        files={"file": ("meeting.mp4", b"fake-mp4-container", "video/mp4")},
    )

    assert response.status_code == 502
    assert "timed out while uploading or transcribing" in response.json()["detail"]
