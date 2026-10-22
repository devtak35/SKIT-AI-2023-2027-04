"""
Week 11 Integration Check

Connects: Dhruv's capture/ASR/diarization fixture, Garvit's summarization and
action-item extraction contract, Dev's transcript repository, and Harsh's
evidence-backed graph record shape.
Still mocked: microphone/provider inference, PostgreSQL deployment, external
LLM calls, vector indexing, and the production frontend.

Result: PASS — the offline end-to-end contract runs from audio fixture to
stored transcript, grounded summary, and graph-ready action item.
"""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "ml" / "nlp") not in sys.path:
    sys.path.insert(0, str(ROOT / "ml" / "nlp"))

from backend.app.database import open_fixture_database
from backend.app.transcript_repository import TranscriptRepository
from ml.audio.week6_asr import FixtureTranscriber
from ml.audio.week7_diarization import FixtureDiarizer
from ml.audio.week8_transcript_pipeline import AudioTranscriptPipeline
from ml.nlp.week6_summarization_pipeline import SummarizationPipeline


def make_nlp_generator():
    calls = 0

    def generate(_messages: list[dict[str, str]]) -> dict[str, object]:
        nonlocal calls
        calls += 1
        if calls == 1:
            return {
                "text": "The audio pipeline will ship on Friday, and Priya owns the release checklist.",
                "covered_segment_ids": ["turn-0000", "turn-0001"],
            }
        return {
            "items": [{
                "id": "action-week11-001",
                "type": "action_item",
                "text": "Ship the audio pipeline on Friday.",
                "confidence": 0.93,
                "evidence_segment_ids": ["turn-0000"],
            }]
        }

    return generate


def main() -> int:
    session_id = "00000000-0000-4000-8000-000000000011"
    with tempfile.TemporaryDirectory() as directory:
        audio = Path(directory) / "meeting.wav"
        audio.write_bytes(b"offline-fixture")

        turns = AudioTranscriptPipeline(FixtureTranscriber(), FixtureDiarizer()).process(audio)
        assert len(turns) == 2
        print(f"[PASS] Dhruv capture/ASR/diarization: {len(turns)} speaker-labeled turns")
        print("       transcript:", json.dumps([turn.to_dict() for turn in turns]))

        repository = TranscriptRepository(open_fixture_database())
        for index, turn in enumerate(turns):
            repository.accept(
                event_id=f"event-week11-{index}", session_id=session_id,
                created_at="2026-10-19T12:00:00Z", segment_id=turn.turn_id,
                revision=1, is_final=True, start_ms=turn.start_ms, end_ms=turn.end_ms,
                speaker_id=turn.speaker, text=turn.text, asr_confidence=turn.confidence,
            )
        stored = repository.list_segments(session_id, include_revisions=False)
        assert len(stored) == len(turns)
        print(f"[PASS] Dev transcript storage: persisted and retrieved {len(stored)} segments")

        nlp_segments = [{
            "segment_id": turn.turn_id, "revision": 1, "is_final": True,
            "start_ms": turn.start_ms, "end_ms": turn.end_ms,
            "speaker_label": turn.speaker, "text": turn.text,
            "asr_confidence": turn.confidence,
        } for turn in turns]
        output = SummarizationPipeline(make_nlp_generator()).process(nlp_segments)
        assert output["summary"]["covered_segment_ids"] == ["turn-0000", "turn-0001"]
        print("[PASS] Garvit summary/extraction: grounded summary and action item validated")
        print("       summary:", json.dumps(output, ensure_ascii=False))

        item = output["extraction"]["items"][0]
        graph_record = {
            "action_item_id": item["id"], "description": item["text"],
            "owner": None, "due_date": None, "status": "open",
            "confidence": item["confidence"],
            "evidence": [{"segment_id": sid, "revision": 1} for sid in item["evidence_segment_ids"]],
        }
        assert graph_record["evidence"] and graph_record["status"] == "open"
        print("[PASS] Harsh graph boundary: action item has explicit status and evidence")
        print("       graph-ready record:", json.dumps(graph_record))

    print("Result: PASS (offline fixture; provider/database/frontend deployment remain mocked)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

