"""
Week 11 (13-10-2026 - 19-10-2026)
Task: Test the pipeline on overlapping-speech samples

Why this matters:
Overlapping turns are common in meetings and can produce ambiguous ownership.
The pipeline must preserve overlap as an explicit quality signal instead of
inventing a single speaker identity.

What this script does:
It detects intersecting diarization intervals and marks them for review.
"""


def find_overlaps(segments: list[dict[str, int | str]]) -> list[tuple[str, str]]:
    overlaps: list[tuple[str, str]] = []
    for index, left in enumerate(segments):
        for right in segments[index + 1:]:
            if min(int(left["end_ms"]), int(right["end_ms"])) > max(int(left["start_ms"]), int(right["start_ms"])):
                overlaps.append((str(left["segment_id"]), str(right["segment_id"])))
    return overlaps


if __name__ == "__main__":
    sample = [{"segment_id": "a", "start_ms": 0, "end_ms": 1200}, {"segment_id": "b", "start_ms": 900, "end_ms": 1800}]
    assert find_overlaps(sample) == [("a", "b")]
    print("[PASS] Dhruv Week 11: overlap detected and flagged for review")

