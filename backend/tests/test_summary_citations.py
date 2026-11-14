from ml.nlp.summarization_pipeline import remove_inline_segment_references


def test_summary_strips_known_short_segment_lists_but_preserves_other_numbers() -> None:
    source_ids = {"audio-batch-asr-0000", "audio-batch-asr-0001", "audio-batch-asr-0002"}

    text = remove_inline_segment_references(
        "The worker arrived at 11:47 PM (0000,0001,0002). The bag was labeled batch 0417.",
        source_ids,
    )

    assert text == "The worker arrived at 11:47 PM. The bag was labeled batch 0417."


def test_summary_keeps_parenthetical_lists_that_are_not_source_ids() -> None:
    source_ids = {"audio-batch-asr-0000", "audio-batch-asr-0001"}

    text = remove_inline_segment_references("Batches were 0417 and 0418 (0417,0418).", source_ids)

    assert text == "Batches were 0417 and 0418 (0417,0418)."
