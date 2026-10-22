"""
Week 11 (13-10-2026 - 19-10-2026)
Task: Build action-item extraction logic

Why this matters:
Action items are the first NLP records that need an owner, due date, status,
and evidence link in Harsh's graph schema. This small normalizer keeps unknown
values explicit and preserves the source segment IDs.

What this script does:
It converts validated extraction records into the Week 12-compatible action
item shape without guessing missing owners or dates.
"""


def normalize_action_item(item: dict[str, object]) -> dict[str, object]:
    if item.get("type") != "action_item":
        raise ValueError("item must have type action_item")
    evidence = item.get("evidence_segment_ids")
    if not isinstance(evidence, list) or not evidence:
        raise ValueError("action item requires evidence")
    return {
        "action_item_id": str(item["id"]),
        "description": str(item["text"]),
        "owner": item.get("owner"),
        "due_date": item.get("due_date"),
        "status": "open",
        "confidence": float(item["confidence"]),
        "evidence_segment_ids": [str(value) for value in evidence],
    }


if __name__ == "__main__":
    result = normalize_action_item({"id": "action-1", "type": "action_item", "text": "Ship Friday", "confidence": 0.9, "evidence_segment_ids": ["turn-0000"]})
    assert result["status"] == "open" and result["owner"] is None
    print(f"[PASS] Garvit Week 11: {result}")

