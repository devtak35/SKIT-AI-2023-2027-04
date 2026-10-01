"""
Week 04 (31-08-2026 - 06-09-2026)
Task: Set up basic CI for the backend

Why this matters:
The schema and FastAPI scaffold are shared contracts, so regressions must be
caught before later teammates build against them. A small pull-request check
keeps the backend reproducible without requiring PostgreSQL, cloud services, or
provider credentials during early development.

What this script does:
Adds GitHub Actions workflow configuration that installs the backend and test
dependencies, compiles the backend, and runs the health and schema tests on
pushes and pull requests that affect backend work.
"""

# CI implementation: .github/workflows/backend-ci.yml
# Local equivalent: python -m compileall -q backend && python -m pytest backend/tests -q

## Week output contract

**Input:** Backend source, requirements, and Week 03 schema.

**Output:** A repeatable backend CI job that reports dependency, syntax, health
endpoint, and schema-constraint failures before a change is merged.

## Verification

```bash
python -m compileall -q backend
python -m pytest backend/tests -q
```
