"""Smoke-test the currently checked-in offline pipeline."""

from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient

from backend.app.main import app
from ml.audio.asr import FixtureTranscriber
from ml.audio.diarization import FixtureDiarizer
from ml.audio.transcript_pipeline import AudioTranscriptPipeline
from ml.rag.retriever import EvidenceRecord, EvidenceRetriever


def main() -> int:
    client = TestClient(app)
    assert client.get("/health").status_code == 200
    with tempfile.TemporaryDirectory() as directory:
        audio_path = Path(directory) / "fixture.wav"
        audio_path.touch()
        turns = AudioTranscriptPipeline(FixtureTranscriber(), FixtureDiarizer()).process(audio_path)
        assert turns and all(turn.speaker for turn in turns)
    result = EvidenceRetriever([
        EvidenceRecord("r1", "demo", "topic", "The audio pipeline is ready.", ("seg-1",), 0.9)
    ]).answer("demo", "audio pipeline")
    assert result["source_segment_ids"] == ["seg-1"]
    print(f"current pipeline check passed: {len(turns)} aligned turns")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
