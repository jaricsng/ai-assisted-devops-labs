Review the current branch's changes (or a specified file/directory) against the project's architectural and style conventions. This goes beyond what linters can catch — it checks layer boundaries, naming patterns, security hygiene, and the conventions defined in CLAUDE.md and CONTRIBUTING.md.

If an argument is provided (`$ARGUMENTS`), review that specific file or directory.
If no argument is provided, review all files changed since the branch diverged from `main` (`git diff main...HEAD --name-only`).

## Conventions to Check

### Python — Service Layer Boundaries

The architecture is: **Router → Service → Repository**. Each layer has strict rules:

- **Routers** (`app/routers/`) — only validate input, call one service method, return a response. No SQL, no business logic.
- **Services** (`app/services/`) — contain all business logic (status transitions, validation rules, permission checks). May call repositories. Must NOT import SQLAlchemy models directly for queries.
- **Repositories** (`app/repositories/`) — only contain SQL (SQLAlchemy queries). No business logic, no HTTP concerns.

Flag any violation:
- A router that contains an `if` statement about business state (e.g., checking task status)
- A service that calls `db.execute()` directly with raw SQL
- A repository that raises `HTTPException` (that belongs in the router)
- A repository that contains non-SQL logic

### Python — Type Safety

- Every function must have type annotations on all parameters and the return type
- No bare `except:` — always catch a specific exception type
- No `type: ignore` comments unless accompanied by an explanation of why it's unavoidable
- Pydantic models must use `model_config = ConfigDict(...)` (Pydantic v2 style), not `class Config`

### Python — Security

- No hardcoded secrets, passwords, or API keys (even in tests — use `pytest.ini` or env vars)
- Passwords must be hashed with `bcrypt` (`bcrypt.hashpw` / `bcrypt.checkpw` in `auth_service.py`) — never `hashlib` or plain storage
- JWT tokens must be validated with `python-jose` — never decoded without signature verification
- No `eval()`, `exec()`, or `subprocess` calls that include user-supplied input
- SQL queries must use SQLAlchemy ORM or parameterised statements — never f-strings in SQL

### Python — Async Patterns

- All database calls must use `await` — flag any synchronous `session.execute()` call
- No `asyncio.sleep()` in production code (only in tests)
- No blocking I/O in async functions (no `open()`, `requests.get()`, etc. — use `aiofiles` or `httpx` async)

### TypeScript — Type Safety

- No `any` type — if something is genuinely unknown, use `unknown` and narrow it
- No type assertions (`as SomeType`) unless the value has just been validated
- All component props must be typed with an explicit interface (`interface XxxProps { ... }`)
- API response types must come from the generated `src/api/types.ts` (generated from OpenAPI) — no hand-rolled duplicates

### TypeScript — Component Conventions

- All data-fetching components must handle three states: loading, error, and success
- No inline `fetch()` or `axios()` calls inside components — all API calls go through `src/api/` functions
- No hardcoded API base URLs — always use `import.meta.env.VITE_API_URL`
- React Query mutations must call `queryClient.invalidateQueries()` after success so the UI stays consistent

### TypeScript — Security

- No secrets or tokens stored in `localStorage` beyond the JWT (and even that should be noted as a trade-off)
- No `dangerouslySetInnerHTML` unless the content is provably not user-supplied
- API error messages must not be displayed raw to the user — extract a safe message first

### General — Git Hygiene

- Commit messages must follow Conventional Commits (`feat:`, `fix:`, `test:`, `docs:`, `chore:`, `refactor:`)
  Check: `git log main...HEAD --oneline`
- No `.env` files committed (check `git diff main...HEAD --name-only` for `.env`)
- No commented-out code blocks — if code is disabled, it should be deleted (git history preserves it)
- No TODO/FIXME comments in files on the changed lines — these belong in GitHub Issues

### Database — Migration Hygiene

- Any change to `app/models/` must have a corresponding new file in `alembic/versions/`
- Alembic migration files must not be edited after creation — create a new migration to correct mistakes
- No `Base.metadata.create_all()` calls in production code; acceptable in `tests/conftest.py` and in `app/main.py` under a `settings.environment == "development"` guard (the dev scaffold uses this in place of Alembic)

## Output Format

For each file reviewed, produce a section:

```
── app/services/task_service.py ──────────────────
✅ Layer boundaries: service does not call db directly
✅ Type annotations: all functions fully annotated
⚠️  Line 47: bare `except Exception` — catch the specific SQLAlchemy exception type
❌ Line 83: `raise HTTPException` — HTTP exceptions belong in the router, not the service layer
```

End with a summary:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Convention Review
  Files reviewed: N
  ✅ Passed:   N
  ⚠️  Warnings: N  (should fix before merge)
  ❌ Errors:   N  (must fix before merge)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

For every ⚠️ and ❌ item: explain the rule, show the violating code, and provide the corrected version.
