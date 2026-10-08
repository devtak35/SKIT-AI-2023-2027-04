"""
Week 07 (21-09-2026 - 27-09-2026)
Task: Spot design gaps based on real transcript quality

Why this matters:
The Week 6 contract review identified fields that raw transcript data must
preserve. This week converts likely ASR and diarization quality issues into
explicit design gaps before the data model is revised in Week 8.

What this script does:
This design note records quality-driven failure modes, their effects on
summaries and RAG citations, and the design response required for each.
"""

# Week 7 — transcript quality design gaps

## Evidence limitation

No real ASR fixture from Dhruv is present in this checkout. The findings below
are therefore quality scenarios to validate against the pending handoff, not
measured claims about the current ASR implementation. They are derived from
the revision-aware, anonymous-speaker contract established in Week 6.

| Quality scenario | Design gap if ignored | Pipeline impact | Required response |
| --- | --- | --- | --- |
| ASR corrects earlier words | A derived decision may cite obsolete text | Incorrect summary/RAG answer | Track transcript revision and invalidate/recompute derived records when needed |
| Speaker is uncertain | An action item may be assigned to the wrong person | Harmful ownership claim | Store speaker confidence and distinguish label from resolved identity |
| Speakers overlap | One speaker's words can be lost or falsely combined | Missed decisions and misleading attribution | Support overlapping segments or interval links |
| Names/terms are misheard | Entity links merge or fragment incorrectly | Poor cross-session retrieval | Keep raw text, normalized candidate, confidence, and evidence separate |
| Mixed language or jargon | Extraction confidence is overstated | Weak action/decision detection | Retain language metadata and allow low-confidence review state |
| Missing/late chunks | Summary appears complete when transcript has a gap | False confidence in answer | Record ingest sequence and explicit missing/processing status |

## Design principles confirmed

1. Transcript data is evidence, not a final fact. Every derived record must
   retain the source segment revision(s) used to create it.
2. A diarization label is not a person identity. Identity resolution is a
   separate, reviewable graph operation.
3. Uncertainty must survive storage. The system should expose confidence and
   provenance rather than hide uncertainty behind fluent generated text.
4. A current rolling summary can change. Historical final summaries must be
   versioned, not overwritten without trace.

## Required validation scenarios for real data

- A segment revision replaces a phrase that would alter an extracted action
  item; verify the action item is superseded or re-evaluated.
- A two-speaker overlap contains a decision; verify both source intervals can
  be cited.
- A speaker changes label mid-session; verify no cross-session identity link
  is inferred merely from label text.
- A low-confidence named entity occurs in two sessions; verify the graph does
  not auto-merge it without supporting evidence.

## WEEK OUTPUT CONTRACT

**Input:** Real or representative transcript segments with timing, revision,
speaker labels, and confidence fields.

**Output:** The quality-gap matrix and four validation scenarios. Week 8 uses
these responses to revise the canonical transcript and provenance model.

## Integration status

The Week 7 integration runner exercises representative revision, uncertain
speaker, and overlap cases through the current transcript upload boundary. It
reports a partial result because real ASR quality measurements and durable
quality metadata are not yet available.
