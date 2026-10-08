"""
Week 05 (07-09-2026 - 13-09-2026)
Task: Lock the architecture plan before Sprint 2 begins

Why this matters:
Sprint 2 implementation needs a stable baseline so that independent work does
not create incompatible assumptions. This sign-off freezes the architectural
decisions from Weeks 1-4 while explicitly identifying the choices that remain
implementation details.

What this script does:
This design note records the approved baseline, non-goals, change-control
rules, and Sprint 2 acceptance criteria.
"""

# Week 5 — architecture sign-off

## Approved baseline

The project will use a modular, asynchronous pipeline:

1. Capture emits ordered audio chunks or media references.
2. ASR/diarization emits revision-aware transcript segments.
3. NLP creates rolling summaries and evidence-linked extracted records.
4. PostgreSQL persists canonical records; vector search is a derived index.
5. A lightweight graph links durable entities, decisions, and action items
   across sessions.
6. RAG performs evidence-grounded hybrid retrieval and returns citations.
7. The frontend accesses all state through versioned FastAPI endpoints.

The logical modules may initially share one deployment. Separating them into
workers or services later must preserve the Week 2 event contracts.

## Decisions frozen for Sprint 2

| Area | Decision | Rationale |
| --- | --- | --- |
| Canonical storage | PostgreSQL | Clear, transactional, easy to explain and test |
| Semantic retrieval | pgvector/vector abstraction | Supports similarity search without coupling application code to one vendor |
| Graph scope | Lightweight evidence-backed relationships | Adds cross-session context without duplicating documents |
| Provenance | Mandatory source segment IDs | Enables auditable citations and safer generated answers |
| Live model | Revision-aware events and current state | Handles provisional ASR output correctly |
| Public API | Versioned `/v1` backend routes | Protects the frontend from internal changes |
| Early deployment | Modular monolith/background tasks | Appropriate operational complexity for the team and thesis timeline |

## Explicit non-goals for Sprint 2

- No requirement to deploy a separate microservice, message broker, or Neo4j
  before the interfaces and fixtures demonstrate the need.
- No attempt to resolve anonymous speaker labels to real identities without
  reliable source data and consent.
- No answer without evidence; RAG must signal insufficient evidence.
- No direct frontend access to databases, vector indexes, or graph storage.

## Change-control rule

Any change to a required event field, identifier semantics, timing unit,
confidence scale, or citation structure requires: (1) a schema-version change
or documented backward-compatible extension, (2) an updated fixture, and (3)
an entry in the weekly integration script's known-issues/status output. This
keeps contract changes visible rather than silently breaking other modules.

## Sprint 2 acceptance criteria

- Each owner can produce/consume their contract with mock JSON fixtures.
- A session, transcript segment, summary update, and extracted item can be
  persisted with full provenance.
- A minimal cross-session retrieval demonstration can return source references
  even before live capture is available.
- The team can identify processing status and a failed stage for any session.

## Integration status

Architecture sign-off is complete as a repository baseline. The executable
integration check uses the latest available teammate artifacts and marks the
missing Week 5 artifacts and production stages as limitations rather than
claiming a full multi-owner Sprint 2 implementation.

## WEEK OUTPUT CONTRACT

**Input:** The Week 1 architecture review, Week 2 boundaries, Week 3 diagrams,
and Week 4 API proposal.

**Output:** The frozen Sprint 2 architecture baseline and change-control
criteria above. Future work may evolve implementation details without breaking
the documented service and provenance contracts.
