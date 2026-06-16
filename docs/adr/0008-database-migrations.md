# ADR 0008 — Database Migration Strategy: Alembic

**Date:** 2026-06-16
**Status:** Accepted

## Context

The Task Manager schema evolves across modules: initial tables are created in Module 02, soft-delete columns are added in Module 14. We need a strategy for applying schema changes in a controlled, reversible way across development, CI, staging, and production environments.

The application uses SQLAlchemy's async ORM. Two approaches were evaluated:

1. **`Base.metadata.create_all()`** — SQLAlchemy creates all tables at startup from current model definitions (additive only; never alters or drops)
2. **Alembic** — explicit, versioned migration scripts with `upgrade()` and `downgrade()` functions checked into git

## Decision

**Alembic** is used for all schema management in CI, staging, and production. A single dev-only exception applies: `Base.metadata.create_all()` is called at startup when `ENVIRONMENT=development` as a convenience for new developer environments that have no persistent data.

```python
# main.py — lifespan context manager
if settings.environment == "development":
    # Dev-only convenience: create tables without running migrations.
    # Production deployments must run: alembic upgrade head
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
```

In `test`, `staging`, and `production` environments, schema management is done exclusively via `alembic upgrade head`.

### Production deploy command

Every cloud deployment config runs migrations before traffic switches to the new version:
- **Fly.io:** `release_command = "alembic upgrade head"` in `fly.toml`
- **AWS ECS / GCP Cloud Run / Azure Container Apps:** equivalent pre-start migration step in `deploy.sh`

This guarantees new code always runs against the expected schema, even if migration takes longer than expected.

### Migration workflow

```bash
# After modifying a SQLAlchemy model:
alembic revision --autogenerate -m "describe the change"
# Review the generated file in backend/alembic/versions/
alembic upgrade head
```

Migrations are checked into git. PRs that add a migration file are reviewed for correctness (column types, index names, working `downgrade()` function) before merge.

## Rationale

### Why not `create_all()` in production?

`create_all()` is additive-only. Once data exists in the database, SQLAlchemy cannot safely evolve the schema via `create_all()`:

| Change | `create_all()` | Alembic |
|--------|---------------|---------|
| Add table | ✅ Creates it | ✅ `CREATE TABLE` |
| Add column | ❌ Ignored (table already exists) | ✅ `ALTER TABLE ADD COLUMN` |
| Rename column | ❌ Ignored | ✅ `ALTER TABLE RENAME COLUMN` |
| Add index | ❌ Ignored | ✅ `CREATE INDEX` |
| Drop column | ❌ Impossible | ✅ `ALTER TABLE DROP COLUMN` |

### Why `create_all()` in dev?

Developer environments typically start with a fresh database (no persistent data). `create_all()` bootstraps all tables in one shot without requiring `alembic upgrade head` on first run — removing one friction point from the new-developer onboarding flow.

The risk of schema drift between ORM models and migration history is acceptable in disposable dev environments. Developers are expected to run `alembic upgrade head` periodically to verify parity with CI.

### Expand/contract for backward-incompatible changes

A migration that drops a column still read by the currently deployed code version must follow the expand/contract pattern across two deployments:

1. **Expand:** Add the new column; deploy code that writes to both old and new columns
2. **Contract:** Drop the old column after all instances are running the new code

Skipping this pattern during a rolling deployment leaves the old code reading a column that the new migration has dropped, causing 500 errors during the transition window.

### Test environment

Test fixtures call `Base.metadata.create_all()` (not Alembic) against a real PostgreSQL instance with `NullPool`. This avoids the overhead of running all migration files in tests while still using the actual ORM models as the schema source of truth. The `ENVIRONMENT=test` flag suppresses the dev-mode `create_all()` in `main.py` so the two code paths do not conflict.

## Consequences

- Every model change requires a corresponding migration file; both `upgrade()` and `downgrade()` must be implemented — PRs without a working `downgrade()` are rejected in code review
- `alembic --autogenerate` detects most changes but misses check constraints and some dialect-specific defaults — generated files must always be reviewed before committing
- Production deploys including a non-trivial migration (e.g., backfill or index on a large table) require a maintenance window or online migration tooling
- The dev convenience shortcut (`create_all()` in dev mode) means schema drift between models and migration history is possible; run `alembic upgrade head` in dev after each migration PR to verify
- Two migration files exist in the solution branch: `001_initial_schema.py` (full schema) and `002_add_soft_deletes.py` (adds `deleted_at TIMESTAMPTZ` + index to all four domain tables)
- The starter scaffold uses `create_all()` in all environments to avoid requiring Alembic knowledge before Module 04; the solution branch replaces this with Alembic
