# Module 4 — Database Tier (PostgreSQL + SQLAlchemy)

## Learning Objectives

- Understand the SQLAlchemy ORM models and how they map to database tables
- Create and run Alembic migrations to evolve the schema safely
- Write a seed script so every developer starts with useful data
- Never modify the database schema by hand

## Background

The database tier owns only one thing: **durable storage**. It does not enforce business rules (those live in Module 5). It does enforce data integrity through constraints, foreign keys, and indexes.

The schema:

```
users(id, email, full_name, hashed_password, created_at)
  └── projects(id, name, description, owner_id→users, created_at)
        └── tasks(id, project_id→projects, title, description,
                  status ENUM, priority ENUM,
                  assignee_id→users, due_date, created_at)
              └── comments(id, task_id→tasks, author_id→users, body, created_at)
```

## Activities

### 1. Read the existing models

Open `backend/app/models/` and read each file. Answer these questions:

- Which columns have `index=True`? Why those ones?
- What does `cascade="all, delete-orphan"` mean on `Project.tasks`?
- Why is `TaskStatus` defined as a Python `enum.Enum` *and* a SQLAlchemy `Enum` column?

Ask Claude Code to check your understanding:
> "Explain why the Task model uses `mapped_column(Enum(TaskStatus))` instead of just `String`. What does SQLAlchemy enforce at the database level?"

### 2. Set up Alembic

Alembic manages schema changes as numbered migration scripts — the git history for your database.

```bash
cd backend
pip install -e ".[dev]"

# Initialize Alembic (already done in starter — review the files)
# alembic init alembic

# Edit alembic/env.py to connect to your DATABASE_URL
```

Open `alembic/env.py`. It needs two changes to work with our async setup. Ask Claude Code:
> "Update alembic/env.py to use the async SQLAlchemy engine from app.database and auto-detect our models from app.models. Show me the complete file."

Apply the changes, then generate the initial migration:

```bash
alembic revision --autogenerate -m "initial schema"
alembic upgrade head
```

Connect to the database to verify:
```bash
docker compose exec db psql -U taskuser -d taskmanager -c "\dt"
```

You should see `users`, `projects`, `tasks`, `comments` tables.

### 3. Make a schema change via migration

Add an `updated_at` column to the `tasks` table:

1. First, update the model in `backend/app/models/task.py`:
```python
updated_at: Mapped[datetime] = mapped_column(
    DateTime(timezone=True),
    server_default=func.now(),
    onupdate=func.now(),
)
```

2. Generate a migration:
```bash
alembic revision --autogenerate -m "add tasks.updated_at"
```

3. Review the generated migration file in `alembic/versions/`. Ask Claude Code:
> "Review this Alembic migration. Is it safe to run on a table with existing data? What could go wrong?"

4. Apply it:
```bash
alembic upgrade head
```

**Key rule:** Never `ALTER TABLE` directly in psql. Always go through Alembic.

### 4. Write a seed script

Create `backend/scripts/seed.py` that inserts demo data. Ask Claude Code:
> "Write a seed script using SQLAlchemy async that creates 2 users, 2 projects (one per user), and 5 tasks spread across both projects with varied statuses and priorities. Use asyncio.run() as the entry point."

Run it:
```bash
python -m scripts.seed
```

Then visit [http://localhost:8000/docs](http://localhost:8000/docs), log in with a seeded user, and verify the data appears.

## Index Strategy

Ask Claude Code:
> "Given our query patterns — listing tasks by project, filtering by status and assignee — what indexes should we add beyond the foreign key indexes already defined? Show the SQLAlchemy `Index` definitions."

Add any missing indexes to the relevant model file and create a migration for them.

## Checkpoint

- [ ] `alembic upgrade head` runs without errors
- [ ] `\dt` in psql shows all 4 tables with correct column types
- [ ] The `updated_at` migration is applied
- [ ] Seed script runs and populates the DB with usable data
- [ ] You can explain why we never edit the schema by hand
- [ ] Commit message: `feat(db): add tasks.updated_at and seed script`
