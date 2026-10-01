"""
Week 03 (24-08-2026 - 30-08-2026)
Task: Draft architecture docs and component diagrams

Why this matters:
The Week 2 boundaries need a single visual representation that the team and
faculty can use to check data ownership and evidence flow. These diagrams
become the reference for API alignment in Week 4 and architecture sign-off in
Week 5.

What this script does:
This design note documents the logical components, first deployment shape,
live-update and historical-query flows, and evidence lineage that later API
contracts must preserve. The diagrams are source text for team review and a
thesis appendix.
"""

# Week 3 — architecture documentation and diagrams

## Architecture documentation scope

The diagrams describe logical boundaries, not six independently deployed
microservices. For the first implementation, Dev's FastAPI process may host
the API and background workers while the contracts remain transport-neutral.
This keeps the system explainable for a faculty review and leaves room to
split out a slow provider later without changing payload ownership.

## Component diagram

```mermaid
flowchart LR
    C[Capture adapter] --> A[ASR + diarization adapter]
    A --> N[Summarization + extraction adapter]
    A --> S[(PostgreSQL source of truth)]
    N --> S
    S --> E[Embedding/index worker]
    E --> V[(Vector index)]
    S --> G[Knowledge-graph linker]
    G --> K[(Graph relationships)]
    F[Next.js frontend] --> B[FastAPI API]
    B --> R[RAG query service]
    R --> S
    R --> V
    R --> K
    R --> B
    B --> F

    subgraph First deployment
      B
      N
      E
      G
      R
    end
```

The first-deployment box is an implementation choice, not a data contract:
each logical component still accepts and emits the versioned envelope from
Week 2.

## Live meeting update flow

```mermaid
sequenceDiagram
    participant Capture
    participant ASR as ASR/Diarization
    participant NLP as Summary/Extraction
    participant Store as Storage
    participant UI as Frontend

    Capture->>ASR: audio.chunk (ordered)
    ASR->>Store: transcript.segment (revision 1, provisional)
    ASR->>NLP: transcript.segment (stable revision)
    NLP->>Store: summary.update + extraction.update
    Store-->>UI: update event with event_id
    ASR->>Store: transcript.segment (higher revision, final)
    Store-->>UI: replacement for same segment_id
    Note over Store: Derived records retain source/evidence segment IDs
```

## Historical question flow

```mermaid
sequenceDiagram
    participant User
    participant API as Backend API
    participant RAG
    participant DB as Postgres + Vector Index + Graph

    User->>API: question and optional session filters
    API->>RAG: validated query
    RAG->>DB: hybrid retrieval and graph expansion
    DB-->>RAG: ranked evidence with source IDs
    RAG-->>API: answer, citations, confidence/status
    API-->>User: cited answer or insufficient-evidence response
```

## Deployment view

```mermaid
flowchart TB
    Client[Browser] -->|HTTPS + SSE| API[FastAPI API process]
    API --> Queue[In-process/background job hand-off]
    Queue --> Providers[Capture / ASR / NLP adapters]
    API --> PG[(PostgreSQL)]
    Queue --> PG
    PG --> Index[Embedding worker]
    Index --> Vector[(pgvector or replaceable vector index)]
    PG --> Graph[Graph linker module]
    Graph --> GraphStore[(Graph tables / future Neo4j)]
```

This deployment is intentionally modest. A queue, separate workers, or a
managed vector service can replace the in-process hand-off later because the
event envelope and IDs are stable. No diagram implies that the graph is the
canonical store for transcript text.

## Storage model at this stage

PostgreSQL stores sessions, transcript segments, summary versions, extracted
records, and citation provenance. The vector index stores embeddings for
searchable records and references their canonical IDs. The graph stores
relationships such as `PERSON MENTIONED_IN SESSION`, `ACTION_ITEM OWNED_BY
PERSON`, and `DECISION SUPPORTED_BY SEGMENT`. It does not become an alternate
copy of raw transcript data.

## Evidence lineage

| Stage | Durable identifier | Must point back to |
| --- | --- | --- |
| Audio chunk | `chunk_id` | `session_id`, capture time, and audio reference |
| Transcript segment | `segment_id` + `revision` | `session_id`, timing, speaker label |
| Summary version | `summary_id` + `version` | `source_segment_ids` |
| Extracted item | `item_id` | `evidence_segment_ids` |
| Graph relationship | `relationship_id` | source/target records and evidence IDs |
| RAG citation | record ID plus segment timing | the stored evidence record |

An update may replace the text for a `segment_id`, but it never silently
creates a second identity for the same logical segment. This lets live
corrections remain traceable in historical answers.

## Assumptions for early fixtures

- Audio, ASR, and LLM providers are swappable adapters, not architecture
  dependencies.
- Speaker labels may be anonymous (for example, `SPEAKER_00`) until identity
  resolution is available.
- Search and answer generation must return an explicit insufficient-evidence
  result instead of inventing a response.

## Open decisions carried into Week 4

1. Confirm whether the external frontend receives updates through SSE first;
   WebSockets remain an option if bidirectional controls become necessary.
2. Confirm the canonical persisted summary field name. This architecture uses
   `source_segment_ids`; provider-native `covered_segment_ids` can be mapped by
   the NLP adapter without changing storage.
3. Confirm whether Dev stores graph relationships in PostgreSQL initially or
   provisions Neo4j. RAG must call a graph interface either way.

## WEEK OUTPUT CONTRACT

**Input:** Week 2 service and payload boundaries.

**Output:** Reusable component and sequence diagrams plus a storage-role
statement. The diagrams describe the expected chain for the eventual weekly
integration demo.
