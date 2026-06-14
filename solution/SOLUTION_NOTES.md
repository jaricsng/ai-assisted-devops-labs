# Solution Notes — What Each File Demonstrates

This document maps each solution file to the lab module that produces it.

## Files present only in solution/ (not in starter scaffold)

| File | Module | What it teaches |
|------|--------|----------------|
| `backend/Dockerfile` (multi-stage) | 13 | Production image: non-root user, no dev deps, separate build/run stages |
| `frontend/Dockerfile` (multi-stage) | 13 | React build → nginx static serving; `try_files` for SPA routing |
| `frontend/nginx.conf` | 13 | SPA routing (all 404s → index.html), static asset caching |
| `backend/alembic.ini` | 4 | Alembic configuration, `DATABASE_URL` read from env not ini file |
| `backend/alembic/env.py` | 4 | Async SQLAlchemy + Alembic wiring; converts asyncpg URL for sync Alembic |
| `backend/alembic/versions/001_initial_schema.py` | 4 | Full schema in one migration; named PostgreSQL enum types; working `downgrade()` |
| `backend/app/schemas/user.py` | 5, 12 | `@field_validator` for password strength (A07 pen test fix) |
| `backend/tests/test_auth_integration.py` | 7 | API-level auth tests: register, login, token validation, alg:none rejection |
| `backend/tests/test_projects_integration.py` | 7 | IDOR protection tests: User B cannot access User A's resources |
| `backend/tests/test_tasks_integration.py` | 7 | Status transition matrix, full TODO→DONE path, terminal state enforcement |
| `fly.toml` | 13 | Fly.io app config: `release_command` for migrations, health checks, concurrency |
| `docs/adr/0001-three-tier-architecture.md` | 1 | Architecture decision with trade-offs documented |
| `docs/adr/0002-jwt-authentication.md` | 2, 5 | JWT vs session cookies; alg:none protection rationale |
| `docs/adr/0003-alembic-for-migrations.md` | 4 | Why Alembic; expand/contract convention; no `create_all()` in prod |
| `docs/pen-test-report.md` | 12 | CVSS scoring, PASS/FAIL evidence, remediation tracking |
| `docs/reflection.md` | 10 | Specific prompts used, one disagreement with Claude Code, one best practice |

## Files identical to scaffold (shared resources)

These files are **the same** in solution/ and the parent scaffold. The solution uses them as-is:

- Backend `app/` files **except** the two noted below
- Frontend `src/` files **except** the two noted below
- `docker-compose.yml`
- `.github/workflows/ci.yml` and `publish.yml`
- `observability/` directory
- `load-tests/` directory
- `pen-tests/` directory
- `.pre-commit-config.yaml`
- `CLAUDE.md`, `CONTRIBUTING.md`

## Files that differ from the original scaffold design

| File | Change | Why |
|------|--------|-----|
| `backend/app/services/auth_service.py` | Uses `bcrypt.hashpw` / `bcrypt.checkpw` directly instead of `passlib` | `passlib` 1.7.4 is incompatible with `bcrypt` 4+ (raises `ValueError: password cannot be longer than 72 bytes`); the direct bcrypt API is stable and avoids the dependency |
| `backend/app/main.py` | Added dev-mode `create_all()` in `on_startup` | The starter scaffold uses `create_all()` in place of Alembic migrations for dev convenience (Module 4 replaces it with real Alembic migrations in production) |
| `frontend/src/App.tsx` | Auth state uses `useState` instead of a bare `localStorage.getItem` call | React 18 batching caused the inline function to return `false` during the re-render triggered by `navigate("/projects")`, immediately redirecting back to `/login`; reactive state is correct regardless |
| `frontend/src/pages/LoginPage.tsx` | Accepts an `onLogin?: () => void` prop | Required for the `App.tsx` reactive auth state — `onLogin()` batches `setIsAuthed(true)` with the `navigate("/projects")` call so both apply in the same React render |

## Key differences to discuss in class

### 1. Password validation (Modules 5 + 12 interaction)
The starter scaffold's `UserCreate` schema has no password validation. The pen test (Module 12) flags weak passwords as a Medium finding (A07). The fix is in `backend/app/schemas/user.py` — a `@field_validator` that gives specific error messages per violation. This is a good example of how security testing drives code quality improvements.

### 2. Integration tests include security assertions (Module 7 + 12 interaction)
`test_auth_integration.py` includes a test for the `alg:none` JWT attack. `test_projects_integration.py` includes IDOR tests. These tests would have caught the security issues the pen test found — demonstrating that a good test suite is also a security control.

### 3. Production Dockerfile vs dev Dockerfile (Module 13)
Compare the starter `backend/Dockerfile` (single-stage, includes dev deps, runs as root) with the solution `backend/Dockerfile` (two-stage, prod-only deps, `appuser` non-root). The diff is small but the security and size implications are significant.

### 4. Alembic env.py reads DATABASE_URL from environment (Module 4)
The `env.py` calls `os.environ["DATABASE_URL"]` at migration time rather than using the `sqlalchemy.url` placeholder in `alembic.ini`. This is the correct pattern: secrets in environment, not in committed config files.
