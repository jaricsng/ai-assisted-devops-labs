Review the database tier for standards compliance: SQLAlchemy model conventions, Alembic migration hygiene, index coverage, and async usage patterns.

## Steps

### 1. Verify all model changes have a migration

```bash
git diff main...HEAD --name-only | grep "app/models/"
```

For every changed model file found, check that a new file exists in `alembic/versions/` that was also added in this branch:

```bash
git diff main...HEAD --name-only | grep "alembic/versions/"
```

Flag any model change that has no corresponding migration.

### 2. Read every file in `backend/app/models/` and check:

**Naming conventions:**
- Table names must be plural snake_case (e.g., `tasks`, `projects`, `users`)
- Column names must be snake_case
- Relationship names must be descriptive (not `rel1`, `data`, `obj`)
- All models must inherit from `Base` (the `DeclarativeBase` subclass in `database.py`)

**Required columns:**
- Every model must have `id` as the primary key (UUID or Integer)
- Every model must have `created_at = mapped_column(DateTime, server_default=func.now())`
- Models that support soft-delete (if any) must have `deleted_at` as nullable

**Indexes:**
- Every foreign key column must have an index (`index=True` on the column or an explicit `Index(...)`)
- Columns used in common filter queries (e.g., `status`, `priority`, `email`) should have indexes
- Report any FK column without an index as a ⚠️ warning

**Type annotations:**
- All columns must use `mapped_column()` with `Mapped[type]` annotations (SQLAlchemy 2.0 style)
- No legacy `Column(...)` without `Mapped` (SQLAlchemy 1.x style)
- Nullable columns must be typed `Mapped[Optional[type]]`

**Relationships:**
- All `relationship()` calls must specify `back_populates` (not `backref`) for explicit bidirectionality
- Cascade rules must be explicit on the owning side (e.g., `cascade="all, delete-orphan"` for child tables)

### 3. Read every file in `alembic/versions/` added/modified in this branch and check:

- `upgrade()` and `downgrade()` are both implemented (not `pass`)
- No raw SQL strings in migrations — use `op.create_table()`, `op.add_column()`, etc.
- Each migration has a descriptive `revision` message (not "auto-generated" with no description)
- `create_index()` is called for every FK column added in `op.create_table()` or `op.add_column()`

### 4. Read every file in `backend/app/repositories/` and check:

**Async patterns:**
- All `session.execute()` calls must be `await`ed
- No `session.commit()` inside repositories — commit belongs in the service or as a dependency
- All functions must be `async def`

**Query patterns:**
- No string-format SQL (`f"SELECT ... WHERE id = {task_id}"`) — always use SQLAlchemy ORM or `text()` with bound parameters
- N+1 query risk: if a query returns a list and each item needs a related object, check for `selectinload()` or `joinedload()`

**Repository scope:**
- Repositories must only contain database operations — no business logic, no `HTTPException`, no logging of business events (only debug-level DB logs are acceptable)

## Output Format

```
── models/task.py ────────────────────────────────
✅ Inherits from Base
✅ Primary key defined
✅ created_at with server_default
⚠️  Column `assignee_id` (FK) has no index — add index=True to avoid slow lookups
❌ Uses legacy Column() without Mapped[] annotation (line 23)

── alembic/versions/0002_add_priority.py ─────────
✅ upgrade() implemented
✅ downgrade() implemented
⚠️  downgrade() drops the column but does not drop the index created in upgrade()

── repositories/task_repository.py ──────────────
✅ All queries use SQLAlchemy ORM
✅ All functions are async
❌ Line 67: session.commit() called inside repository — move to service layer
```

Final summary:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Database Standards Review
  Models reviewed:       N
  Migrations reviewed:   N
  Repositories reviewed: N
  ✅ Passed:   N checks
  ⚠️  Warnings: N
  ❌ Errors:   N
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

For every ❌ error, show the violating code and the corrected version.
