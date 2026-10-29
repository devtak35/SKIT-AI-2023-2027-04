"""
Week 13 Integration Check

Connects: Dhruv's latest crosstalk-aware transcript contract, Garvit's
combined NLP flow, Dev's revision-aware storage/vector index, and Harsh's
evidence-backed graph and RAG boundary.
Still mocked: provider inference, PostgreSQL deployment, and external answer
generation. The integration uses deterministic fixtures so every stage is
repeatable in CI.

Result: PASS when run from the repository root.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.database import open_fixture_database
from backend.app.graph_repository import GraphRepository
from backend.app.rag import GroundedRAG
from backend.app.transcript_repository import TranscriptRepository
from ml.audio.week6_asr import FixtureTranscriber
from ml.audio.week7_diarization import FixtureDiarizer
from ml.audio.week8_transcript_pipeline import AudioTranscriptPipeline
from ml.nlp.combined_pipeline import MeetingNlpPipeline


def _generator(turn_ids: list[str]):
    responses = iter((
        {
            "text": "The audio pipeline will ship on Friday, and Priya owns the release checklist.",
            "covered_segment_ids": turn_ids,
        },
        {
            "items": [{
                "id": "week-13-action-001",
                "type": "action_item",
                "text": "Ship the audio pipeline on Friday.",
                "confidence": 0.93,
                "evidence_segment_ids": [turn_ids[0]],
            }]
        },
    ))
    return lambda _messages: next(responses)


def main() -> int:
    session_id = "week-13-integration-session"
    with TemporaryDirectory() as directory:
        audio_path = Path(directory) / "meeting.wav"
        audio_path.write_bytes(b"offline-fixture")
        turns = AudioTranscriptPipeline(FixtureTranscriber(), FixtureDiarizer()).process(audio_path)
        assert turns
        print(f"[PASS] Dhruv transcript: {len(turns)} speaker-labelled turns")

        connection = open_fixture_database()
        transcripts = TranscriptRepository(connection)
        graph = GraphRepository(connection)
        for turn in turns:
            transcripts.accept(
                event_id=f"week-13-event-{turn.turn_id}", session_id=session_id,
                created_at="2026-10-29T12:00:00Z", segment_id=turn.turn_id,
                revision=1, is_final=True, start_ms=turn.start_ms, end_ms=turn.end_ms,
                speaker_id=turn.speaker, text=turn.text, asr_confidence=turn.confidence,
            )
        stored = transcripts.list_segments(session_id, include_revisions=False)
        assert len(stored) == len(turns)
        print(f"[PASS] Dev storage/vector index: {len(stored)} current segments")

        nlp_segments = [turn.to_nlp_segment() for turn in turns]
        output = MeetingNlpPipeline(_generator([turn.turn_id for turn in turns])).process(
            session_id=session_id, segments=nlp_segments
        )
        assert output["graph_batch"]["action_items"]
        transcripts.save_summary(
            summary_id="week-13-summary", session_id=session_id, version=1,
            text=output["summary"]["text"], source_segment_ids=output["summary"]["source_segment_ids"],
            is_final=False, created_at="2026-10-29T12:01:00Z",
        )
        graph.ingest(**output["graph_batch"])
        print("[PASS] Garvit NLP: summary and graph batch accepted with evidence")

        result = GroundedRAG(transcripts, graph).answer(
            "What did we decide about the audio pipeline?", [session_id]
        )
        assert result["insufficient_evidence"] is False
        assert result["citations"]
        assert all(citation["revision"] == 1 for citation in result["citations"])
        print("[PASS] Harsh graph/RAG: answer returned with revisioned citations")
        print(json.dumps({"answer": result["answer"], "citations": result["citations"]}, indent=2))

    print("Result: PASS (provider and production database stages remain mocked)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
