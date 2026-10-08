
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any


NLP_DIR = Path(__file__).resolve().parent
FIXTURE_PATH = NLP_DIR.parent.parent / "fixtures" / "sample_transcripts.json"
PROMPTS_PATH = NLP_DIR / "refined_prompt_templates.py"


def load_prompts() -> Any:
    sys.dont_write_bytecode = True
    spec = importlib.util.spec_from_file_location("meeting_prompts", PROMPTS_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load prompt templates from {PROMPTS_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_checks() -> list[str]:
    prompts = load_prompts()
    fixtures = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    failures: list[str] = []

    for case in fixtures["cases"]:
        case_id = case["case_id"]
        segments = case["transcript_segments"]
        valid_ids = {segment["segment_id"] for segment in segments}

        for label, builder, output_fields in (
            (
                "summary",
                prompts.build_summary_messages,
                ("text", "covered_segment_ids"),
            ),
            (
                "extraction",
                prompts.build_extraction_messages,
                ("id", "type", "text", "confidence", "evidence_segment_ids"),
            ),
        ):
            messages = builder(segments)
            if [message["role"] for message in messages] != ["system", "user"]:
                failures.append(f"{case_id}: {label} must render system and user messages")
            system_text = messages[0]["content"]
            for field in output_fields:
                if field not in system_text:
                    failures.append(f"{case_id}: {label} prompt omits contract field {field}")
            if "source_segment_ids" in system_text or "speaker_id" in system_text:
                failures.append(f"{case_id}: {label} prompt contains stale field names")

            user_text = messages[1]["content"]
            marker = "TRANSCRIPT_SEGMENTS_JSON:\n"
            if marker not in user_text:
                failures.append(f"{case_id}: {label} prompt omits its transcript JSON marker")
            else:
                rendered = json.loads(user_text.split(marker, 1)[1])
                if rendered != segments:
                    failures.append(f"{case_id}: {label} prompt changed or omitted source segments")

        summary = case["reference_summary"]
        if not isinstance(summary.get("text"), str):
            failures.append(f"{case_id}: reference summary text must be a string")
        if not isinstance(summary.get("covered_segment_ids"), list):
            failures.append(f"{case_id}: reference summary must have covered_segment_ids")
        elif set(summary["covered_segment_ids"]) - valid_ids:
            failures.append(f"{case_id}: reference summary cites unknown segment IDs")

        items = case["reference_extraction"].get("items")
        if not isinstance(items, list):
            failures.append(f"{case_id}: reference extraction items must be a list")
            continue
        for index, item in enumerate(items):
            prefix = f"{case_id}: reference item {index}"
            evidence = item.get("evidence_segment_ids")
            if not isinstance(evidence, list) or not evidence:
                failures.append(f"{prefix} needs evidence_segment_ids")
            elif set(evidence) - valid_ids:
                failures.append(f"{prefix} cites unknown segment IDs")
            confidence = item.get("confidence")
            if not isinstance(confidence, (int, float)) or not 0 <= confidence <= 1:
                failures.append(f"{prefix} confidence must be within 0.0-1.0")

    # Input validation must prevent provisional ASR text from driving durable
    # summary/extraction records and reject segments outside the agreed shape.
    first_segments = fixtures["cases"][0]["transcript_segments"]
    provisional = [dict(segment) for segment in first_segments]
    provisional[0]["is_final"] = False
    for label, builder in (
        ("summary", prompts.build_summary_messages),
        ("extraction", prompts.build_extraction_messages),
    ):
        try:
            builder(provisional)
            failures.append(f"{label}: provisional transcript segment was accepted")
        except ValueError:
            pass

    missing_field = [dict(first_segments[0])]
    del missing_field[0]["speaker_label"]
    try:
        prompts.build_summary_messages(missing_field)
        failures.append("input validation: accepted segment missing speaker_label")
    except ValueError:
        pass

    return failures


if __name__ == "__main__":
    errors = run_checks()
    if errors:
        print(f"FAIL: {len(errors)} prompt-refinement check(s)")
        for error in errors:
            print(f"- {error}")
        raise SystemExit(1)
    print("PASS: refined summary and extraction prompts match the current payload fields.")
    print("PASS: fixture evidence IDs are valid; missing and provisional transcript inputs are rejected.")
    print("LIMITATION: checks use hand-written reference outputs; there are no LLM-generated results to score.")
