"""
Week 09 (05-10-2026 - 11-10-2026)
Task: Adjust prompts/logic based on findings

Why this matters:
Week 8 identified that tentative plans and ownership must remain evidence-backed.
These prompt rules make uncertainty explicit before the first version is frozen.

What this script does:
It exposes deterministic validation rules for grounded summaries and action items.
"""


def grounding_rules() -> dict[str, object]:
    return {
        "summary_requires_citations": True,
        "action_item_requires_evidence": True,
        "unknown_owner_is_null": True,
        "tentative_decision_status": "proposed",
    }


if __name__ == "__main__":
    rules = grounding_rules()
    assert all(rules.values())
    print(f"[PASS] Garvit Week 9: {rules}")

