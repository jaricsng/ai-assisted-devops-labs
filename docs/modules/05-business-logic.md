# Module 5 — Business Logic Tier (FastAPI)

## Learning Objectives

- Understand the layered architecture: router → service → repository
- See why business rules live in the service layer, not the router or the DB
- Implement a new feature end-to-end through all three layers
- Run automated and AI-powered security reviews
- Understand what OWASP Top 10 means in practice for a FastAPI service

## Background

The FastAPI tier is the brain of the application. It:
- Validates all input with Pydantic (bad data never reaches the DB)
- Enforces business rules in the service layer (e.g., status transitions)
- Authenticates requests with JWT before touching any data
- Returns consistent error envelopes the frontend can handle

**Layer responsibilities:**

| Layer | File location | Does |
|-------|--------------|------|
| Router | `app/routers/` | HTTP in/out, calls service or repository |
| Service | `app/services/` | Business rules, raises HTTP exceptions |
| Repository | `app/repositories/` | SQL queries only, no business logic |

## Activities

### 1. Trace a request end-to-end

Pick `PATCH /projects/{project_id}/tasks/{task_id}` — the status transition endpoint.

Trace the request through the code:
1. `app/routers/tasks.py` → `update_task()`
2. → `app/services/task_service.py` → `apply_task_update()`
3. → `app/services/task_service.py` → `validate_status_transition()`
4. → `app/repositories/task_repository.py` → `save()`

Ask Claude Code:
> "Why does validate_status_transition raise an HTTPException directly instead of returning a boolean? What are the trade-offs of each approach?"

### 2. Add task filtering (implement the spec from Module 2)

In Module 2 you added `?status=TODO&priority=HIGH` query params to the OpenAPI spec. Now implement it.

**Step 1 — Repository layer** (`backend/app/repositories/task_repository.py`)

Ask Claude Code:
> "Add a get_filtered function to task_repository.py that accepts optional status and priority parameters and returns matching tasks. Use SQLAlchemy's select() with conditional where() clauses — do not use string interpolation."

**Step 2 — Router layer** (`backend/app/routers/tasks.py`)

Add query params to `list_tasks`:
```python
@router.get("/projects/{project_id}/tasks", response_model=list[TaskRead])
async def list_tasks(
    project_id: int,
    status: TaskStatus | None = None,
    priority: TaskPriority | None = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(current_user),
):
```

Ask Claude Code:
> "Update the list_tasks router function to pass the optional status and priority query params to the repository. Keep the existing project ownership check."

**Step 3 — Verify in Swagger UI**

Open [http://localhost:8000/docs](http://localhost:8000/docs) → `GET /projects/{project_id}/tasks` → try it with `?status=TODO`.

### 3. Add a health check with DB connectivity

The existing `/health` endpoint only checks that the process is running. Improve it to verify the database is reachable:

Ask Claude Code:
> "Update the /health endpoint in app/main.py to also execute a SELECT 1 against the database. Return {status: ok, db: ok} on success or {status: degraded, db: error} with HTTP 503 on DB failure. Use a try/except and inject the db session via Depends."

### 4. Run the automated security scan

Now that auth is implemented, run the security scanner:

```
/security-scan
```

This runs:
- **bandit** — Python SAST scanning for issues like hardcoded passwords, SQL injection patterns, use of `eval()`
- **pip-audit** — checks all Python dependencies against the CVE database
- **npm audit** — checks frontend dependencies for known vulnerabilities
- Secret pattern grep — scans tracked files for credential patterns

Examine the bandit output. Each finding shows a severity (LOW/MEDIUM/HIGH), a CWE ID, and the exact line. Ask Claude Code:
> "Explain CWE-259 (hardcoded password) and CWE-78 (OS command injection). Which of these is more likely to appear in a FastAPI application, and why?"

### 5. Run an OWASP Top 10 review

```
/security-review
```

This AI review goes through all 10 OWASP categories against the actual code. Pay close attention to:

- **A01 (Broken Access Control)** — does every route check that the resource belongs to the current user? An IDOR vulnerability would let User A read User B's tasks.
- **A04 (Insecure Design)** — is there rate limiting on `POST /auth/login`? Without it, an attacker can try unlimited passwords.
- **A07 (Auth Failures)** — does a failed login return `"email not found"` vs `"wrong password"` separately? That leaks information about which emails are registered.

Fix at least one finding. For findings you won't fix now, add an ADR entry or a code comment explaining the trade-off and accepted risk.

### 6. Check for layer boundary violations

```
/review-conventions
```

This checks that the router → service → repository boundary is respected. Common violations:
- A router that contains `if task.status ==` (business logic in the wrong layer)
- A repository that raises `HTTPException` (HTTP concerns in the data layer)
- A service that runs `await db.execute(text(...))` directly (bypassing the repository)

Fix any flagged violations.

### 7. Environment configuration audit

Open `app/config.py`. The `Settings` class uses `pydantic-settings` to read from `.env`.

Ask Claude Code:
> "Are there any fields in our Settings class that should have validators? For example, what happens if SECRET_KEY is set to 'change-me'? Add a validator that raises an error in production if the key is too short or matches the example value."

### 8. Generate a threat model

```
/threat-model authentication
```

This produces a STRIDE analysis of the authentication flow, identifying threats like:
- **S** (Spoofing) — stolen JWT impersonation
- **D** (Denial of Service) — login endpoint brute force without rate limiting
- **E** (Elevation of Privilege) — JWT `role` claim manipulation

Read the output and identify which mitigations are already in place and which are gaps. Document two gaps in `docs/adr/0003-security-trade-offs.md`.

## Best Practices Applied in This Module

- **Input validation at the boundary** — Pydantic rejects bad data before any code runs
- **Business logic isolated** — `task_service.py` has no SQLAlchemy imports; it works on plain Python objects
- **No raw SQL strings** — all queries use SQLAlchemy's query builder
- **Secrets from environment** — nothing hardcoded; `pydantic-settings` raises on missing required vars
- **Shift-left security** — security scanned with tools (bandit) and AI (OWASP review) during development, not after deployment

## Checkpoint

- [ ] `GET /projects/{id}/tasks?status=TODO` returns only TODO tasks
- [ ] `PATCH` with an invalid status transition returns 422 with a clear message
- [ ] `/ready` returns 503 when the DB is down (`docker compose stop db`)
- [ ] `/security-scan` passes with no HIGH or CRITICAL findings
- [ ] You've read the `/security-review` output and fixed or documented at least one finding
- [ ] `/review-conventions` shows no layer boundary violations
- [ ] `pytest` still passes after your changes
- [ ] Commit: `feat(api): add task filtering, security review, layer boundary audit`
