Week 08 (28-09-2026 - 04-10-2026)
Task: Review summary quality, note gaps

Why this matters:
The Week 6 summarization pipeline validates response structure and evidence IDs, while Week 7 provides a runner for applying it to transcript input. Reviewing the available fixture output makes quality concerns explicit before Week 9 changes the prompts or pipeline. Dhruv's current audio handoff is fixture-backed and does not yet provide a real transcript for quality evaluation.

What this report does:
Reviews the Week 7 fixture-backed summary and extraction against its transcript, notes what the current checks do and do not establish, and records prioritized gaps for follow-up.

# Week 08 Summary Quality Review

## Evidence reviewed

- `weekly/garvit/week_07_real-transcript-run.py` and its default run data.
- `fixtures/week_02_transcript.json`, the two-segment transcript used by that runner.
- `ml/nlp/week6_summarization_pipeline.py`, which validates response shape and evidence references.
- Dhruv's `ml/audio/week8_transcript_pipeline.py`, whose current adapters provide fixture segments rather than a real captured transcript.

This is a **mock-based review**, not a real-transcript or generated-LLM quality evaluation. The Week 7 runner uses a hard-coded summary and extraction response by default. Its optional input path also accepts supplied responses; it does not call a model provider.

## Available fixture result

The transcript says:

1. “Let's review the capture prototype next week.”
2. “I can review it by Friday and send notes.”

The runner's sample summary is: “The team will review the capture prototype next week; a speaker will review it by Friday and send notes.” Its action item is: “Review the capture prototype by Friday and send notes.” The action cites the second transcript segment.

### Quality observations

- **Main point and action are present.** The summary includes the planned review and the action item retains its deadline and deliverable.
- **Attribution is cautious.** The fixture identifies the owner only as a speaker, avoiding an invented personal name. The action item's evidence points to the segment containing the commitment.
- **Wording can be tightened.** “The team will review” is less precise than the first speaker's invitation and the second speaker's commitment. “A speaker will review” is accurate but awkward; the output could preserve that the owner is unresolved without presenting it as a named person.
- **The summary and action item repeat information.** That may be acceptable for separate overview and action-item sections, but the output should keep the distinction clear in the UI.
- **Coverage is only structurally checked.** The pipeline checks that cited segment IDs exist, but does not establish that the summary faithfully represents every cited segment or that important content was not omitted.
- **Confidence is not quality evidence.** The fixture's `0.94` action confidence is supplied by hand; it is not calibrated or measured against correctness.

## Gaps to carry forward

1. **No real transcript was available.** Dhruv's Week 8 pipeline combines ASR and diarization through fixture adapters in this checkout. Real ASR wording, speaker attribution, and their impact on summary quality remain unreviewed.
2. **The Week 7 contract does not yet match Dhruv's current output directly.** Dhruv emits `turn_id`, `speaker`, and optional `confidence`, while the Week 7 normalizer requires `segment_id`, `speaker_label`/`speaker_id`, and numeric `asr_confidence`; it also requires `revision` and `is_final` for non-fixture input. A shared mapping and a decision on batch finality/revision are needed before calling this an integrated real-transcript run.
3. **Responses are supplied, not generated.** The runner validates given JSON but cannot expose prompt behavior, provider formatting issues, or variation across runs.
4. **There is no scored quality rubric yet.** Current checks cover schema and evidence-ID validity, not factual consistency, omission, decision-versus-suggestion handling, action-item completeness, or readability.

## Suggested Week 09 follow-up

- Agree on a small adapter between Dhruv's transcript-turn fields and the NLP segment contract, including how absent confidence and batch finality are represented.
- Once a real transcript is available, run the summarizer on it and retain the source transcript, supplied/generated response, and output together for review.
- Add a small review checklist covering factual support, coverage, action owner/deadline, decision certainty, speaker attribution, readability, and unsupported claims. Keep confidence values separate from measured quality until calibrated.
- Keep fixture-based findings labeled as provisional; do not tune production prompts based only on these observations.

## Review status

**PARTIAL — fixture review completed; real transcript quality remains unevaluated.** No prompt, pipeline, or transcript contract files were changed as part of this review.
