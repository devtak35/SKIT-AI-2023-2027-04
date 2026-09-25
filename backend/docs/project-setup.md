# Week 01 (10-08-2026 - 16-08-2026)
Task: Set up the project repository and dev environment

Why this matters:
Every later service and weekly integration needs a shared repository layout and predictable local setup. This baseline gives backend, frontend, and ML work clear homes while keeping local secrets, generated media, and build output out of Git.

What this deliverable does:
Records the repository setup review, adds initial ignore rules, and defines the local development conventions for the backend and frontend. The backend and frontend instruction files specify the same Week 1 task and destination, so this one Dev artifact is the shared record for both.

## Repository setup review

The Git repository is already initialized at the project root. It contains separate `backend/`, `frontend/`, `ml/audio/`, `ml/nlp/`, `fixtures/`, and `weekly/` areas, but no application source, dependency manifests, or start commands yet. Week 1 establishes the working baseline; FastAPI code and database schema remain later-week work.

## Setup decisions

- Keep the existing single Git repository and the current ownership folders.
- Use a Python virtual environment for backend and ML dependencies; each lane should add only the dependencies it owns when implementation begins.
- Keep frontend dependencies and lockfile under `frontend/` when the React/Next.js scaffold is selected.
- Store credentials in ignored `.env` files and commit only sanitized `.env.example` templates.
- Keep sample audio, local datasets, generated artifacts, caches, and build output out of version control. Small, synthetic or consent-cleared fixtures may be checked in under `fixtures/` when they are suitable for sharing.
- The environment versions observed during setup are Python 3.12.1 and Node.js 22.22.0. Exact version pins and dependency lockfiles should be added with the first runnable backend/frontend scaffolds so they match chosen framework versions.

## Change made

Added a root `.gitignore` for Python environments/caches, frontend dependencies/build output, local secrets, editor files, and generated media/data. Existing tracked project files are not excluded by the new rules.

## Local workflow

1. Clone the repository and work on a member branch or the agreed team branch.
2. Create a Python virtual environment for backend/ML work; install dependencies from the lane-specific manifest once it exists.
3. Install frontend dependencies from `frontend/` once its package manifest is added.
4. Copy `.env.example` to a local `.env` when a service needs credentials; never commit `.env`.
5. Put shareable test fixtures in `fixtures/`, and keep personal or large recordings in ignored local data folders.

## Week output contract

**Input:** The existing repository, team ownership described in `AGENTS.md`, and the backend/frontend setup requirements.

**Output:** A single shared repository layout and ignore policy. Both `backend/AGENTS.md` and `frontend/AGENTS.md` point to `weekly/dev/` and assign the same Week 1 task, so this artifact is the contract for both lanes.

## Verification

The repository root resolves as a Git worktree. The new ignore policy covers local virtual environments, Node dependencies/build output, environment files, and generated recordings. No application run command can be verified yet because the backend and frontend manifests/source are not present.
