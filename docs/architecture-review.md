"""
Week 01 (10-08-2026 - 16-08-2026)
Task: Review existing meeting-tool architectures, sketch the high-level design

Why this matters:
The project needs a stable end-to-end direction before individual modules are
implemented. This review identifies the pipeline boundaries that later weeks
will formalize as service contracts, schemas, knowledge-graph relationships,
and RAG interfaces.

What this script does:
This design note compares suitable architecture patterns for a real-time
meeting summarizer and records the selected high-level design and its initial
data-flow contract.
"""

# Week 1 architecture review

## Problem and constraints

The system must turn a live or uploaded recording into timestamped,
speaker-attributed transcript segments, continuously updated summaries,
action items, and searchable cross-session memory. It must support an
eventual bot-free capture path and remain usable while upstream ASR and NLP
formats are still evolving.

The most important design constraints are:

- Live output should arrive incrementally; the user must not wait for the
  recording to finish.
- Every generated claim must retain links to its transcript evidence so later
  RAG answers can provide citations.
- The knowledge graph should enrich retrieval, not replace reliable document
  storage and semantic search.
- Components owned by different team members must be independently testable
  with fixtures.

## Architecture patterns reviewed

| Pattern | Strength | Limitation | Decision |
| --- | --- | --- | --- |
| Single synchronous application | Simple initial setup | One slow ASR/LLM call blocks the whole pipeline and makes live updates difficult | Not selected |
| Fully event-driven microservices | Scales and isolates workloads | Operationally heavy for a four-person academic project | Not selected initially |
| Modular pipeline with asynchronous hand-offs | Keeps clear ownership, allows incremental results, and can run in one FastAPI deployment at first | Requires stable payload contracts | Selected |
| Graph-only session memory | Makes entity relationships explicit | Poor fit for raw transcripts, semantic similarity, and citation provenance alone | Use as a complement to relational/vector storage |

## Chosen high-level design

The initial implementation will be a **modular pipeline with asynchronous
stage hand-offs**. Modules can first run in one backend deployment or through
simple background jobs; their interfaces must not depend on that deployment
choice. This avoids premature distributed-systems complexity while preserving
a clean future path to queues and separately deployed workers.

```text
Capture source (live system audio / uploaded recording)
        |
        v
ASR + diarization
        |  transcript segments: text, timestamps, speaker, confidence
        v
Summarization + extraction
        |  rolling summary, decisions, action items, entities, provenance
        v
Storage and indexing
        |-- PostgreSQL: sessions, segments, summaries, extracted records
        |-- pgvector/vector DB: searchable embeddings
        `-- Knowledge graph: cross-session entity/action/decision links
        v
RAG query service
        |  hybrid retrieval + evidence-grounded answer + citations
        v
React/Next.js frontend
        |-- live transcript and rolling summary
        `-- historical search and cited answers
```

## Data-flow decisions

1. A `session_id` is created before capture begins and is carried by every
   downstream payload. A `segment_id` uniquely identifies each transcript
   segment.
2. ASR emits small ordered transcript segments. A segment may be revised while
   live transcription is still provisional; consumers should therefore retain
   a revision number and finality flag rather than treating every update as
   immutable.
3. Summaries are generated from batches of finalized or sufficiently stable
   segments. Each extracted decision, action item, or entity stores the source
   `segment_id` values that support it.
4. PostgreSQL is the source of truth for structured records and provenance.
   The vector index is a derived search index. The graph stores only durable,
   explainable relationships rather than duplicating full transcript text.
5. RAG retrieves relevant transcript/summary evidence through vector and
   metadata filtering, optionally expands related graph records, then returns
   an answer only with citations back to stored segment or summary identifiers.

## Initial module responsibilities

| Module | Owner | Responsibility | Does not own |
| --- | --- | --- | --- |
| Capture and ASR | Dhruv | Audio acquisition, transcription, speaker labels | Summaries and persistence policy |
| NLP extraction | Garvit | Rolling summaries, action items, entities, confidence | Cross-session retrieval |
| Backend/platform | Dev | FastAPI, persistence, embeddings pipeline, frontend integration | Knowledge-linking policy |
| Knowledge graph and RAG | Harsh | Entity/action/decision links, retrieval, cited answer generation, integration | Audio/ASR and core UI implementation |

## Decisions to carry into Week 2

- Use a canonical JSON envelope for all inter-module payloads, beginning with
  `session_id`, `event_id`, `created_at`, `schema_version`, and `payload`.
- Treat transcript evidence and provenance as mandatory fields, not optional
  metadata added later.
- Start with PostgreSQL plus pgvector where practical; keep vector-store access
  behind an interface so Pinecone can be substituted if deployment needs
  change.
- Model the knowledge graph as lightweight, explainable records first. Neo4j
  is a future option only if relationship queries outgrow PostgreSQL.
- Defer real-time transport selection (polling, SSE, or WebSocket) until the
  frontend API boundary is defined; internal stages should be transport
  agnostic.

## Risks and mitigation

| Risk | Mitigation |
| --- | --- |
| Speaker labels or text change after an early ASR result | Preserve segment revisions and only promote stable data to durable extractions |
| LLM extraction is inaccurate | Store confidence and source segments; make reviewable records instead of opaque text |
| Cross-session entities are incorrectly merged | Begin with conservative links, aliases, and human-auditable evidence |
| Team contracts change during early sprints | Version every payload and validate fixtures at each weekly integration |

## WEEK OUTPUT CONTRACT

**Input:** Project goals, planned technology stack, and the responsibilities
of the four team members.

**Output:** This approved architecture baseline: a modular pipeline with
provenance-preserving transcript storage, vector retrieval, and a lightweight
knowledge graph used to improve cited RAG answers.

## Week-end integration status

The four team Week 1 deliverables are now present in this checkout. The
documentation integration confirms that their handoffs fit the architecture
baseline. An executable audio-to-summary-to-storage-to-RAG runtime is not yet
implemented; see `weekly/integration/week_01_summary.md` for the partial status,
handoffs, and open dependencies.
