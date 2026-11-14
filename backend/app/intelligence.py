"""Generate and persist evidence-linked summaries and extracted meeting records."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from backend.app.graph_repository import GraphRepository
from backend.app.llm import GroqJsonGenerator
from backend.app.transcript_repository import TranscriptRepository
from ml.nlp.summarization_pipeline import SummarizationPipeline


def refresh_session_intelligence(
    session_id: str, transcripts: TranscriptRepository, graph: GraphRepository
) -> dict[str, object]:
    """Run a configured LLM over final transcript evidence and persist its output."""
    segments = [segment for segment in transcripts.list_segments(session_id, include_revisions=False) if segment.is_final]
    if not segments:
        raise ValueError("At least one final transcript segment is required before generating intelligence.")
    nlp_segments = [{
        "segment_id": segment.segment_id,
        "revision": segment.revision,
        "is_final": segment.is_final,
        "start_ms": segment.start_ms,
        "end_ms": segment.end_ms,
        "speaker_label": segment.speaker_id,
        "text": segment.text,
        "asr_confidence": segment.asr_confidence,
    } for segment in segments]
    output = SummarizationPipeline(GroqJsonGenerator.from_environment()).process(nlp_segments)
    now = datetime.now(timezone.utc).isoformat()
    previous = transcripts.latest_summary(session_id)
    summary = transcripts.save_summary(
        summary_id=previous.summary_id if previous else f"summary-{uuid4()}",
        session_id=session_id,
        version=(previous.version + 1) if previous else 1,
        text=output["summary"]["text"],
        source_segment_ids=output["summary"]["covered_segment_ids"],
        is_final=False,
        created_at=now,
    )
    items = output["extraction"]["items"]
    graph_result = graph.ingest(
        session_id=session_id,
        producer="groq",
        producer_version="1",
        entities=[item for item in items if item["type"] != "action_item"],
        action_items=[item for item in items if item["type"] == "action_item"],
        relationships=[],
    )
    return {
        "summary": summary.__dict__,
        "entities_created": len(graph_result["entities"]),
        "action_items_created": len(graph_result["action_items"]),
        "provider": "groq",
    }
