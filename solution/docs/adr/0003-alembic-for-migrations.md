# ADR 0003 — Alembic for Database Migrations

**Date:** 2026-06-14  
**Status:** Accepted

## Context

The database schema will evolve as the application grows. We need a strategy for applying schema changes in a controlled, reversible way across development, CI, and production environments.

Options considered:

1. **Manual SQL scripts** — hand-write SQL files and apply them in sequence
2. **SQLAlchemy `create_all()`** — let SQLAlchemy create all tables at startup based on current models
3. **Alembic** — migration tool for SQLAlchemy with versioned, reversible migration scripts

## Decision

We use **Alembic** with autogenerate support. Every schema change follows this workflow:

```bash
# After modifying a SQLAlchemy model:
alembic revision --autogenerate -m "describe the change"
# Review the generated file in alembic/versions/
alembic upgrade head
```

Migrations are checked into git. In production, the `release_command = "alembic upgrade head"` in `fly.toml` runs migrations before traffic switches to the new version.

## Consequences

**Positive:**
- Schema changes are versioned, reviewed in PRs, and applied consistently across all environments
- `downgrade()` in every migration enables rollback to any previous schema version
- Autogenerate detects column additions, renames, and index changes — developers rarely write migration SQL by hand
- The production deploy pipeline runs migrations atomically before traffic switches, so the new code always runs against the expected schema

**Negative:**
- Each schema change requires two steps: edit the model AND generate/review the migration
- `alembic --autogenerate` does not detect all changes (e.g., check constraints, column-level defaults in some dialects) — always review the generated file before committing
- Backward-incompatible migrations (dropping a column used by the previous version) require the expand/contract pattern across two deployments

**Convention adopted:**
- Never edit `Base.metadata.create_all()` to apply schema changes in non-test code
- `create_all()` is only used in the test `conftest.py` for the in-memory SQLite test DB
- Every migration file must have a working `downgrade()` function — PRs that add a migration without a downgrade are rejected in code review
