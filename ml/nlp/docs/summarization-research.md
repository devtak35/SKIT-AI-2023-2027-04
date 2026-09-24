"""
Week 01 (10-08-2026 - 16-08-2026)
Task: Research summarization approaches: extractive vs abstractive

Why this matters:
The project needs concise meeting summaries that preserve decisions and assigned work from noisy, speaker-labeled transcripts. Choosing an approach now informs the prompt templates and sample-transcript evaluation in Weeks 2-5, while keeping source evidence available for the downstream storage and RAG layers.

What this script does:
This note compares extractive and abstractive summarization for meeting transcripts and recommends an evidence-grounded hybrid for initial experiments.
"""

# Week 1 — extractive vs. abstractive summarization

## Scope

This is a design review for Garvit's summarization lane. It does not select a model or claim measured performance on this project's data. No transcript fixture or summarizer implementation is present in this checkout, so the recommendation should be checked against mock transcripts in Weeks 2-5 and real ASR output when available. The IBM explainer and the user-provided JETIR review are used for introductory framing; empirical claims are cross-checked against the cited ACL research where possible.

## The two approaches

**Extractive summarization** ranks and selects source sentences or spans, then assembles them into a shorter output. The selected wording can be traced directly to the transcript, which helps evidence review. However, speech transcripts contain repetitions, fragments, ASR errors, and conversational dependencies; copied sentences can be awkward, redundant, or unclear when removed from context. Extraction can also miss a commitment expressed across several turns. Extractive output is not automatically grammatical or coherent: that depends on the quality of the selected spans and how they are ordered.

**Abstractive summarization** generates new wording intended to express the source's meaning. It can combine turns, remove repetition, and produce readable sections such as an overview, decisions, and action items. It can also introduce unsupported details, misstate who said or owns something, or turn tentative discussion into a firm decision. Generation does not guarantee grammar, coherence, or factuality. Generated claims therefore need source evidence and explicit uncertainty handling.

These are not mutually exclusive system designs: a pipeline can first identify evidence-bearing transcript spans and then generate a concise statement constrained to those spans.

## Comparison for this project

| Criterion | Extractive | Abstractive | Meeting-project implication |
| --- | --- | --- | --- |
| Fidelity to wording | Copies selected source wording, which is easy to inspect but can preserve ASR mistakes | Paraphrases; meaning must be checked against evidence | Keep source segment IDs and transcript revisions with every claim |
| Readability | Can retain fragments/repetition and can lose context between selected sentences | Can consolidate turns, though fluent output is not necessarily accurate | Compare coherence and factual support as separate qualities |
| Decisions and action items | May miss a commitment spread over several turns | Can combine context, but may infer a commitment or owner | Require explicit evidence spans and represent unknown owner/due date as unknown |
| Auditability | Selected text itself is a direct source excerpt | Claim must be checked against the transcript | Show citations to segment IDs and timestamps, including for paraphrases |
| Transcript noise | May copy transcription errors verbatim | May smooth errors into plausible but wrong text | Preserve transcript evidence and uncertainty; do not treat fluent output as proof |
| Implementation burden | Can use ranking/selection methods; neural extractors also exist | Needs a generation model or LLM prompt and quality checks | Start with provider-independent interfaces and fixture-based comparison |

## What the supplied references add

IBM's overview describes extraction in terms of sentence representation, scoring, selection, and redundancy reduction; it describes abstraction through compression, information fusion, and reordering. These are useful process distinctions. It also summarizes a human evaluation finding where abstractive summaries were judged more coherent while extractive summaries were judged more informative/relevant, and cautions that comparative results depend on evaluation context ([IBM, “What is text summarization?”](https://www.ibm.com/think/topics/text-summarization)).

The attached article, Anil Kumar and V. K. Sharma, “A Review on Extractive and Abstractive Text Summarization Approaches,” *JETIR*, April 2025, Vol. 12, Issue 4, article JETIR2504858, pages i433-i439, provides a broad taxonomy and introductory descriptions of methods such as TF-IDF, TextRank, LexRank, encoder-decoder models, attention, and transformers. It also distinguishes summary intent (indicative/informative), query focus (generic/query-based), language relation, and number of input documents. These are separate design axes; they should not be conflated with extractive versus abstractive generation. The article is a secondary review, and its broad comparison table makes categorical claims about grammar that are too strong to treat as general guarantees. I use it for taxonomy and terminology, not as evidence that either approach is always more grammatical or accurate.

For direct comparison, Pilault et al. evaluated extractive, abstractive, and combined transformer approaches on four document datasets. Their reported human evaluation favored transformer systems for coherence and fluency, while purely extractive systems scored higher for informativeness and relevance. This result supports a trade-off framing, but it is not a result on meeting transcripts and should not be generalized as a guaranteed outcome for this project ([Pilault et al., EMNLP 2020](https://aclanthology.org/2020.emnlp-main.748/)). Zhang et al. further report that an extract-then-generate approach improved faithfulness over abstractive baselines in their benchmark experiments ([Zhang et al., Findings of EMNLP 2023](https://aclanthology.org/2023.findings-emnlp.214/)).

## Research basis

Neural generation work such as BART demonstrates that sequence-to-sequence models can be effective on abstractive summarization benchmarks, but benchmark capability alone does not establish reliability for meeting decisions or action ownership ([Lewis et al., ACL 2020](https://aclanthology.org/2020.acl-main.703/)).

Factual consistency is a distinct concern: Kryscinski et al. propose checking summary sentences against their source and identifying supporting or conflicting spans, while Wang et al.'s QAGS work reports that common automatic metrics can miss factual inconsistencies ([Kryscinski et al., EMNLP 2020](https://aclanthology.org/2020.emnlp-main.750/); [Wang et al., ACL 2020](https://aclanthology.org/2020.acl-main.450/)). This supports evaluating factual support separately from fluency or lexical overlap. These papers motivate the design safeguards below; they do not prove that one approach will outperform the other on our transcripts.

## Recommendation

Use an **evidence-grounded hybrid** for the first experiments. This is a testable design hypothesis for this project, not a conclusion that the literature proves universally best:

1. Keep the transcript as the immutable source, with segment IDs, timestamps, and speaker labels supplied by the ASR contract.
2. Identify candidate source spans for key points, decisions, and action items. Treat these as evidence candidates, not necessarily the final summary text.
3. Generate a concise overview and structured records from those spans, instructing the generator not to add names, dates, decisions, or commitments absent from the cited evidence.
4. Store the exact evidence segment IDs on every generated item. Keep confidence/uncertainty separate from the generated prose; do not invent an owner or due date when the transcript does not establish one.
5. Compare extractive-only, abstractive-only, and hybrid outputs on the same small mock transcripts. Review coverage, factual support, attribution, readability, and citation correctness separately. ROUGE or other overlap metrics can be included as limited diagnostics, but they should not be the sole quality measure because paraphrases and factual errors are not fully captured by word overlap.

This is a practical starting point, not a final model choice. If the abstractive version cannot reliably preserve evidence and attribution, use extracted sentences as the displayed fallback for the affected item while retaining the same structured output contract.

## Risks and mitigations

- **Unsupported paraphrase or hallucinated commitment:** require evidence references and review each claim against its source spans.
- **Wrong speaker or action owner:** keep diarization labels distinct from resolved person identities; leave ownership unknown unless the transcript supports it.
- **Overcompression:** evaluate whether decisions, rationale, and action details survive, not just whether the output is short.
- **ASR correction after a summary is generated:** retain transcript revisions and re-evaluate derived claims when cited evidence changes, following the project architecture notes.
- **Metrics hide important errors:** use human review on a small fixed fixture set and record coverage, factual support, attribution, readability, and citation accuracy separately.

## Week 1 output contract

**Input:** A transcript with text and, when available, segment IDs, timestamps, and speaker labels.

**Output:** A concise overview plus evidence-linked key points, decisions, and action-item candidates. Each item should retain source segment IDs; uncertain owners, dates, and claims remain explicitly unknown or flagged.

## Handoff to Week 2

Draft prompts should request a structured overview and separate evidence-linked items, prohibit unsupported additions, and return a parseable format. Week 3 should test the prompts on the same mock transcripts using the comparison criteria above.

## References

1. IBM Think, Jacob Murel and Eda Kavlakoglu, [“What is text summarization?”](https://www.ibm.com/think/topics/text-summarization), published 6 May 2024; accessed 24 September 2026.
2. Anil Kumar and V. K. Sharma, “A Review on Extractive and Abstractive Text Summarization Approaches,” *Journal of Emerging Technologies and Innovative Research (JETIR)*, Vol. 12, Issue 4, April 2025, JETIR2504858, pp. i433-i439. Local reference supplied by the user: `C:\Users\garvi\Downloads\JETIR2504858.pdf`.
3. Jonathan Pilault, Raymond Li, Sandeep Subramanian, and Chris Pal. 2020. [“On Extractive and Abstractive Neural Document Summarization with Transformer Language Models.”](https://aclanthology.org/2020.emnlp-main.748/) EMNLP 2020.
4. Haopeng Zhang, Xiao Liu, and Jiawei Zhang. 2023. [“Extractive Summarization via ChatGPT for Faithful Summary Generation.”](https://aclanthology.org/2023.findings-emnlp.214/) Findings of EMNLP 2023.
5. Mike Lewis et al. 2020. [“BART: Denoising Sequence-to-Sequence Pre-training for Natural Language Generation, Translation, and Comprehension.”](https://aclanthology.org/2020.acl-main.703/) ACL 2020.
6. Wojciech Kryscinski et al. 2020. [“Evaluating the Factual Consistency of Abstractive Text Summarization.”](https://aclanthology.org/2020.emnlp-main.750/) EMNLP 2020.
7. Alex Wang, Kyunghyun Cho, and Mike Lewis. 2020. [“Asking and Answering Questions to Evaluate the Factual Consistency of Summaries.”](https://aclanthology.org/2020.acl-main.450/) ACL 2020.
