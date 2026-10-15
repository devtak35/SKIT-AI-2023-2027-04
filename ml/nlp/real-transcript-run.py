"""
Week 07 (21-09-2026 - 27-09-2026)
Task: Run the summarization pipeline on real transcripts from Dhruv's pipeline

Why this matters:
The Week 6 pipeline was exercised with hand-written responses, so it has not yet been shown to accept Dhruv's transcript output or process real model responses. This runner provides a repeatable handoff for a stable transcript and captured summary/extraction JSON while keeping fixture use clearly identified until those inputs are available.

What this script does:
Loads a Dhruv transcript and a JSON file containing provider responses, normalizes the transcript to the NLP contract, and runs the Week 6 pipeline. With no arguments it demonstrates the same path using repository fixtures and clearly labels the run as mocked.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
NLP_DIR = REPO_ROOT / "ml" / "nlp"
if str(NLP_DIR) not in sys.path:
    sys.path.insert(0, str(NLP_DIR))

from week6_summarization_pipeline import SummarizationPipeline  # noqa: E402


FIXTURE_TRANSCRIPT_PATH = REPO_ROOT / "fixtures" / "week_02_transcript.json"


def normalize_transcript(raw: Any, *, fixture_mode: bool = False) -> list[dict[str, Any]]:
    """Map a transcript payload to the stable Week 5/6 segment contract.

    Real-input mode requires explicit revision and finality fields. Fixture mode
    may fill those two historical fields for the repository's static sample.
    """
    segments = raw.get("segments") if isinstance(raw, dict) else raw
    if not isinstance(segments, list) or not segments:
        raise ValueError("transcript must be a non-empty list or an object with a non-empty 'segments' list")

    normalized: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for index, source in enumerate(segments):
        label = f"transcript.segments[{index}]"
        if not isinstance(source, dict):
            raise ValueError(f"{label} must be an object")

        segment_id = source.get("segment_id")
        if not isinstance(segment_id, str) or not segment_id.strip():
            raise ValueError(f"{label}.segment_id must be a non-empty string")
        if segment_id in seen_ids:
            raise ValueError(f"duplicate transcript segment ID: {segment_id}")
        seen_ids.add(segment_id)

        revision = source.get("revision", 1 if fixture_mode else None)
        is_final = source.get("is_final", True if fixture_mode else None)
        if isinstance(revision, bool) or not isinstance(revision, int) or revision < 1:
            raise ValueError(f"{label}.revision must be a positive integer")
        if not isinstance(is_final, bool) or not is_final:
            raise ValueError(f"{label}.is_final must be true for pipeline input")

        start_ms = source.get("start_ms")
        end_ms = source.get("end_ms")
        if (
            isinstance(start_ms, bool)
            or not isinstance(start_ms, int)
            or isinstance(end_ms, bool)
            or not isinstance(end_ms, int)
            or start_ms < 0
            or end_ms <= start_ms
        ):
            raise ValueError(f"{label} must have valid start_ms/end_ms timestamps")

        speaker_label = source.get("speaker_label", source.get("speaker_id"))
        if not isinstance(speaker_label, str) or not speaker_label.strip():
            raise ValueError(f"{label} must have a non-empty speaker_label or speaker_id")

        text = source.get("text")
        if not isinstance(text, str):
            raise ValueError(f"{label}.text must be a string")
        asr_confidence = source.get("asr_confidence")
        if (
            isinstance(asr_confidence, bool)
            or not isinstance(asr_confidence, (int, float))
            or not math.isfinite(asr_confidence)
            or not 0.0 <= asr_confidence <= 1.0
        ):
            raise ValueError(f"{label}.asr_confidence must be between 0.0 and 1.0")

        normalized.append(
            {
                "segment_id": segment_id,
                "revision": revision,
                "is_final": is_final,
                "start_ms": start_ms,
                "end_ms": end_ms,
                "speaker_label": speaker_label,
                "text": text,
                "asr_confidence": asr_confidence,
            }
        )
    return normalized


def load_fixture_run() -> tuple[list[dict[str, Any]], dict[str, Any], str]:
    raw = json.loads(FIXTURE_TRANSCRIPT_PATH.read_text(encoding="utf-8"))
    segments = normalize_transcript(raw, fixture_mode=True)
    ids = [segment["segment_id"] for segment in segments]
    summary = {
        "text": "The team will review the capture prototype next week; a speaker will review it by Friday and send notes.",
        "covered_segment_ids": ids,
    }
    extraction = {
        "items": [
            {
                "id": "week7-fixture-action-001",
                "type": "action_item",
                "text": "Review the capture prototype by Friday and send notes.",
                "confidence": 0.94,
                "evidence_segment_ids": [ids[1]],
            }
        ]
    }
    return segments, {"summary": summary, "extraction": extraction}, "repository fixture"


def load_real_run(transcript_path: Path, responses_path: Path) -> tuple[list[dict[str, Any]], dict[str, Any], str]:
    raw_transcript = json.loads(transcript_path.read_text(encoding="utf-8"))
    segments = normalize_transcript(raw_transcript)
    responses = json.loads(responses_path.read_text(encoding="utf-8"))
    if not isinstance(responses, dict) or set(responses) != {"summary", "extraction"}:
        raise ValueError("responses JSON must contain exactly 'summary' and 'extraction' objects")
    return segments, responses, str(transcript_path)


def run_pipeline(
    segments: list[dict[str, Any]], responses: dict[str, Any], source_label: str
) -> dict[str, Any]:
    response_sequence = iter((responses["summary"], responses["extraction"]))

    def response_adapter(_messages: list[dict[str, str]]) -> str:
        try:
            return json.dumps(next(response_sequence), ensure_ascii=False)
        except StopIteration as error:
            raise RuntimeError("pipeline requested more outputs than provided") from error

    output = SummarizationPipeline(response_adapter).process(segments)
    print(f"Transcript source: {source_label}")
    print(f"Segments processed: {len(segments)}")
    print(json.dumps(output, ensure_ascii=False, indent=2))
    if source_label == "repository fixture":
        print("LIMITATION: transcript and expected responses are mocked; this is not a real-transcript evaluation.")
    else:
        print("NOTE: this run validates supplied responses; it calls no LLM provider.")
    return output


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the NLP pipeline on a stable transcript.")
    parser.add_argument("--transcript", type=Path, help="Dhruv transcript JSON with final segment revisions")
    parser.add_argument("--responses", type=Path, help="JSON with summary and extraction model responses")
    args = parser.parse_args(argv)

    if bool(args.transcript) != bool(args.responses):
        parser.error("--transcript and --responses must be supplied together")

    if args.transcript:
        segments, responses, source = load_real_run(args.transcript, args.responses)
    else:
        segments, responses, source = load_fixture_run()
    run_pipeline(segments, responses, source)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


# WEEK OUTPUT CONTRACT:
# Input: A stable Dhruv transcript JSON and JSON model responses with
#        {"summary": {"text", "covered_segment_ids"},
#         "extraction": {"items": [...]}}; default is a labeled repo fixture.
# Output: Validated Week 6 pipeline result with transcript source and count.
# External requirement: real Dhruv transcript and actual provider responses.
