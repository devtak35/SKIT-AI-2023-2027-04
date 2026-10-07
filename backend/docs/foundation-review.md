"""
Week 05 (07-09-2026 - 13-09-2026)
Task: Review and finalize the foundation setup

Why this matters:
The transcript APIs planned for Weeks 6-10 need a known-good FastAPI entry
point, repeatable CI, and a schema that already represents transcript
revisions. This review confirms those foundations before public ingestion
endpoints add behavioural complexity.

What this script does:
This design note records the completed foundation review, the agreed API
boundary, and the intentionally deferred database wiring.
"""

# Week 5 — foundation review

## Reviewed foundation

- `backend/app/main.py` provides the FastAPI application and `/health` route.
- `backend/app/schema.sql` defines sessions, revision-aware transcript
  segments, summaries, extracted items, and idempotent domain events.
- `backend/tests` covers the health route and critical schema constraints.
- `.github/workflows/backend-ci.yml` installs dependencies, compiles backend
  code, and runs the backend tests for relevant pushes and pull requests.

## Decisions confirmed for the next API slice

1. Public routes remain under `/v1`; the existing health route remains
   unversioned for operational checks.
2. Transcript uploads use the Week 4 `transcript.segment` envelope and the
   canonical `speaker_id` field.
3. The endpoint validates a revision-aware payload now. Database persistence
   remains Week 8 work, so the initial implementation uses an isolated
   in-memory store rather than prematurely wiring SQLite as production state.
4. Duplicate event delivery is acknowledged idempotently; a new event cannot
   replace an equal or newer segment revision.

## Review result

The foundation is ready for Week 6 transcript ingestion. The Week 4 API
contract still records team confirmation as pending, so this implementation
does not expand the agreed payload surface.

## WEEK OUTPUT CONTRACT

**Input:** The FastAPI scaffold, Week 3 schema, Week 4 CI workflow, and the
Week 4 team API proposal.

**Output:** A confirmed backend baseline and the implementation rules used by
the Week 6 transcript-upload endpoint.
