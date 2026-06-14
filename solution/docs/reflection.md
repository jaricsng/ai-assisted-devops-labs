# Reflection — AI-Assisted DevOps Lab

> **Note:** This is an example reflection written to the standard of a Distinction.
> Your own reflection should draw on your specific experience with the lab.

---

## What I Built

I built a three-tier Task Manager application: a React 18 frontend, a FastAPI backend, and a PostgreSQL database, all orchestrated with Docker Compose. The application supports user registration and login with JWT authentication, project creation, task management with a Kanban-style status flow (TODO → IN_PROGRESS → IN_REVIEW → DONE), and comments on tasks. The status transition rules are enforced server-side in `task_service.py` — not just in the frontend — so a user cannot skip from TODO to DONE by crafting a direct API request. By the end of the lab I had a full CI/CD pipeline: GitHub Actions running lint, tests, and security scans on every push, publishing Docker images to GHCR on merges to `main`, and deploying to Fly.io with Alembic running database migrations as a release command before traffic switches.

---

## Where Claude Code Helped

**1. Designing the status transition guard (Module 5)**

I described the business rule to Claude Code: "Tasks must follow a specific sequence and terminal states cannot be left." Claude Code produced the `VALID_TRANSITIONS` dictionary and the `validate_status_transition` function in one shot. The prompt I used was:

> "In Python, implement a function `validate_status_transition(current: TaskStatus, next_status: TaskStatus) -> None` that raises HTTP 422 if the transition is not in the VALID_TRANSITIONS map. TaskStatus values are: TODO, IN_PROGRESS, IN_REVIEW, DONE, CANCELLED. Terminal states are DONE and CANCELLED."

The result matched my mental model exactly, and it included structured logging via `structlog` that I hadn't thought to add. I kept that addition.

**2. Writing the Alembic migration (Module 4)**

I had never used Alembic before. I asked:

> "Generate an Alembic migration file that creates four tables: users, projects, tasks (with a TaskStatus enum and TaskPriority enum), and comments. Include foreign keys with ON DELETE CASCADE where appropriate and add indexes on all foreign key columns."

Claude Code produced a complete, correct migration with both `upgrade()` and `downgrade()` functions. I reviewed it carefully and caught one issue: it used `sa.Enum("TODO", "IN_PROGRESS", ...)` with positional strings rather than the `name=` parameter, which would have caused the enum type to be created without a name in PostgreSQL. I fixed that before committing.

**3. Setting up the GitHub Actions security job (Module 9)**

I asked Claude Code to add a `security` job to `ci.yml` that runs bandit SAST, pip-audit, and npm audit. The prompt:

> "Add a `security` job to .github/workflows/ci.yml that runs: bandit -r app/ -c pyproject.toml -ll --exit-zero, pip-audit, and npm audit --audit-level=high. It should run on every push, not just PRs."

The output was immediately usable. More valuably, Claude Code explained why `--exit-zero` should be used initially (to establish a baseline before making bandit a hard gate), which I then turned into Activity 5 of my lab notes.

---

## Where I Disagreed with Claude Code

**Password validation approach**

When I asked Claude Code to add password validation to `UserCreate`, it initially suggested a regex-based approach using a single complex pattern: `^(?=.*[A-Z])(?=.*\d).{8,}$`. I overrode this with a `@field_validator` that checks each condition separately and gives a specific error message for each failure ("Password must contain at least one uppercase letter"). 

My reasoning: the regex approach gives the user a single opaque error message ("Password does not meet requirements") with no guidance on what the requirements are. Separate checks allow the API to return distinct, user-actionable messages. The Pydantic docs also recommend `field_validator` over regex for business rules because it produces better error detail in the 422 response body.

---

## Best Practice I'll Carry Forward

**The layered architecture boundary is worth defending.**

Early in Module 5 I instinctively put an `HTTPException` inside `project_repository.py` when a project wasn't found. Claude Code's `/review-conventions` skill flagged it: "HTTPException belongs in the router layer, not in the repository. The repository should return `None`; the router decides what HTTP status to return."

I initially thought it was a stylistic preference. By Module 7 I understood why it matters: unit tests for the repository can now test the `None` return without importing FastAPI or dealing with exception handling. The router tests can verify the 404 response without touching the database. The boundary isn't bureaucracy — it's what makes each layer independently testable.

I'll apply this in any future service I build: database layer returns None or raises database-specific exceptions; HTTP layer translates those into HTTP responses. Never mix the two.

---

## What I'd Improve

I would implement proper token refresh from the start. The current implementation uses a 30-minute access token with no refresh mechanism, so users are logged out after 30 minutes of inactivity. In a real application this would need a refresh token flow: a long-lived `refresh_token` stored in an `httpOnly` cookie (not localStorage) that the frontend uses to request a new `access_token` silently. I didn't do this because it adds significant frontend state management complexity, but I now understand why it's necessary for production — and why the pen test report flagged `localStorage` storage as an XSS risk.
