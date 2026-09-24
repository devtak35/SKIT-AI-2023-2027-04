from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any, Mapping


NLP_DIR = Path(__file__).resolve().parent
FIXTURE_PATH = NLP_DIR.parent.parent / "fixtures" / "sample_transcripts.json"
PROMPT_MODULE_PATH = NLP_DIR / "initial-prompt-templates.py"
ALLOWED_TYPES = {"person", "topic", "decision", "action_item"}


def load_prompt_module() -> Any:
    """Load Week 2 prompt templates, whose filename contains hyphens."""

    spec = importlib.util.spec_from_file_location("week_02_initial_prompt_templates", PROMPT_MODULE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load prompt module: {PROMPT_MODULE_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def validate_summary(summary: Mapping[str, Any], valid_ids: set[str]) -> list[str]:
    errors: list[str] = []
    if not isinstance(summary.get("text"), str):
        errors.append("summary.text must be a string")
    ids = summary.get("covered_segment_ids")
    if not isinstance(ids, list) or not all(isinstance(value, str) for value in ids):
        errors.append("summary.covered_segment_ids must be a list of strings")
    else:
        if len(ids) != len(set(ids)):
            errors.append("summary.covered_segment_ids contains duplicate IDs")
        unknown = set(ids) - valid_ids
        if unknown:
            errors.append(f"summary cites unknown segment IDs: {sorted(unknown)}")
        if summary.get("text", "").strip() and not ids:
            errors.append("non-empty summary must cite at least one segment")
    return errors


def validate_extraction(extraction: Mapping[str, Any], valid_ids: set[str]) -> list[str]:
    errors: list[str] = []
    items = extraction.get("items")
    if not isinstance(items, list):
        return ["extraction.items must be a list"]

    item_ids: set[str] = set()
    for index, item in enumerate(items):
        prefix = f"extraction.items[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{prefix} must be an object")
            continue
        item_id = item.get("id")
        if not isinstance(item_id, str) or not item_id:
            errors.append(f"{prefix}.id must be a non-empty string")
        elif item_id in item_ids:
            errors.append(f"duplicate extraction item id: {item_id}")
        else:
            item_ids.add(item_id)

        if item.get("type") not in ALLOWED_TYPES:
            errors.append(f"{prefix}.type must be one of {sorted(ALLOWED_TYPES)}")
        if not isinstance(item.get("text"), str) or not item["text"].strip():
            errors.append(f"{prefix}.text must be a non-empty string")
        confidence = item.get("confidence")
        if not isinstance(confidence, (int, float)) or not 0.0 <= confidence <= 1.0:
            errors.append(f"{prefix}.confidence must be between 0.0 and 1.0")

        evidence_ids = item.get("evidence_segment_ids")
        if not isinstance(evidence_ids, list) or not evidence_ids:
            errors.append(f"{prefix}.evidence_segment_ids must be a non-empty list")
        elif not all(isinstance(value, str) for value in evidence_ids):
            errors.append(f"{prefix}.evidence_segment_ids must contain strings")
        else:
            unknown = set(evidence_ids) - valid_ids
            if unknown:
                errors.append(f"{prefix} cites unknown segment IDs: {sorted(unknown)}")
    return errors


def evaluate_fixture() -> list[str]:
    """Run deterministic prompt-rendering and reference-contract checks."""

    fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    prompt_module = load_prompt_module()
    failures: list[str] = []

    for case in fixture["cases"]:
        case_id = case["case_id"]
        segments = case["transcript_segments"]
        valid_ids = {segment["segment_id"] for segment in segments}

        for label, builder, required_phrase in (
            ("summary", prompt_module.build_summary_messages, "covered_segment_ids"),
            ("extraction", prompt_module.build_extraction_messages, "evidence_segment_ids"),
        ):
            messages = builder(segments)
            if [message["role"] for message in messages] != ["system", "user"]:
                failures.append(f"{case_id}: {label} messages must have system and user roles")
            if required_phrase not in messages[0]["content"]:
                failures.append(f"{case_id}: {label} system prompt omits {required_phrase}")
            serialized_input = messages[1]["content"]
            for segment in segments:
                if segment["segment_id"] not in serialized_input or segment["text"] not in serialized_input:
                    failures.append(f"{case_id}: {label} prompt omitted transcript data")
                    break
            if "untrusted source text" not in serialized_input:
                failures.append(f"{case_id}: user prompt omits source-text instruction boundary")

        for error in validate_summary(case["reference_summary"], valid_ids):
            failures.append(f"{case_id}: {error}")
        for error in validate_extraction(case["reference_extraction"], valid_ids):
            failures.append(f"{case_id}: {error}")

    return failures


if __name__ == "__main__":
    failures = evaluate_fixture()
    if failures:
        print(f"FAIL: {len(failures)} fixture check(s)")
        for failure in failures:
            print(f"- {failure}")
        raise SystemExit(1)
    print(f"PASS: prompt rendering and reference contracts valid for {len(json.loads(FIXTURE_PATH.read_text(encoding='utf-8'))['cases'])} sample transcripts")
    print("LIMITATION: no model provider was called; this does not score generated summary quality.")
