# Reflection — AI-Assisted DevOps Lab

> **Note:** This is an example reflection written to the standard of a Distinction.
> Your own reflection should draw on your specific experience with the lab.

---

## What I Built

I built a three-tier Task Manager application: a React 18 frontend, a FastAPI backend, and a PostgreSQL database, orchestrated with Docker Compose. The application supports user registration and login with JWT authentication, project creation, task management with a Kanban-style status flow (TODO → IN_PROGRESS → IN_REVIEW → DONE), and comments on tasks. Status transition rules are enforced server-side in `task_service.py` — not just in the frontend — so a user cannot skip from TODO to DONE by crafting a direct API request.

By Module 14 the project had grown considerably beyond the initial CRUD application. The security layer includes five HTTP security headers applied as middleware to every response, a JTI-based token revocation system (`POST /auth/logout`), a GDPR-compliant soft-delete endpoint (`DELETE /auth/users/me`), and an input size middleware that rejects bodies over 1 MiB. All four domain tables have a `deleted_at` column; no data is ever hard-deleted.

The observability stack (Module 05b) runs as an optional Docker Compose profile — Jaeger for distributed traces, Prometheus for metrics, Grafana with four pre-configured alert rules, and a Blackbox Exporter probing `/ready` to power the `DatabaseUnreachable` alert. Every API request produces an OpenTelemetry trace that shows the full middleware chain and each SQLAlchemy query as child spans.

On the delivery side: load tests with k6 (smoke, load, spike scenarios) and Locust (three user classes covering read-heavy, write-heavy, and auth-stress patterns), a penetration test including a ZAP baseline scan, E2E tests with Playwright, and a CI/CD pipeline that builds to GHCR, scans images with Trivy, generates a CycloneDX SBOM, and deploys via a GitHub Environment with a named approval gate.

---

## Where Claude Code Helped

**1. Designing the status transition guard (Module 5)**

I described the business rule to Claude Code and used the prompt:

> "In Python, implement a function `validate_status_transition(current: TaskStatus, next_status: TaskStatus) -> None` that raises HTTP 422 if the transition is not in the VALID_TRANSITIONS map. TaskStatus values are: TODO, IN_PROGRESS, IN_REVIEW, DONE, CANCELLED. Terminal states are DONE and CANCELLED."

The result matched my mental model exactly, and it included `structlog` logging that I hadn't thought to add. I kept that addition.

**2. Writing the Alembic migration (Module 4)**

I had never used Alembic before. I asked:

> "Generate an Alembic migration file that creates four tables: users, projects, tasks (with a TaskStatus enum and TaskPriority enum), and comments. Include foreign keys with ON DELETE CASCADE where appropriate and add indexes on all foreign key columns."

Claude Code produced a complete migration with both `upgrade()` and `downgrade()` functions. I reviewed it and caught one issue: it used `sa.Enum("TODO", "IN_PROGRESS", ...)` with positional strings rather than the `name=` parameter, which would have created an unnamed PostgreSQL enum type that is difficult to drop in `downgrade()`. I added the `name=` parameter before committing.

**3. Implementing the security headers middleware (Module 14)**

When adding the HTTP security headers, I prompted:

> "Write a Starlette `BaseHTTPMiddleware` subclass called `SecurityHeadersMiddleware` that adds X-Content-Type-Options, X-Frame-Options, X-XSS-Protection, Strict-Transport-Security, Referrer-Policy, and Content-Security-Policy to every response."

Claude Code produced the correct middleware in one shot. More importantly, it warned me that the `Content-Security-Policy` value of `default-src 'none'` would block the Swagger UI's inline scripts and suggested I either relax it for the `/docs` path or accept that Swagger would not render. I chose to keep the strict policy and noted it in the pen test report — a deliberate trade-off rather than an oversight.

---

## Where I Disagreed with Claude Code

**Password validation approach**

When I asked Claude Code to add password validation to `UserCreate`, it initially suggested a regex: `^(?=.*[A-Z])(?=.*\d).{8,}$`. I overrode this with a `@field_validator` that checks each condition separately and gives a specific error message per failure ("Password must contain at least one uppercase letter").

My reasoning: the regex gives the user a single opaque error. Separate checks let the API return distinct, actionable messages in the 422 body. The pen test (Module 12) would have flagged opaque error messages as an A07 weakness — separate validators prevent that.

**Where to apply security headers**

When I first asked Claude Code to add security headers, it added them to individual route handlers, returning `Response` objects with the headers set manually. I moved the logic into `SecurityHeadersMiddleware` instead. The router approach would have required every future endpoint to remember to add the headers — a maintenance burden and a missing-header risk whenever a new route was added. Middleware applies them once, to every response, unconditionally. The `/review-conventions` skill later confirmed the router-level approach as a convention violation.

---

## Best Practice I'll Carry Forward

**The layered architecture boundary is worth defending.**

Early in Module 5 I put an `HTTPException` inside `project_repository.py` when a project wasn't found. Claude Code's `/review-conventions` skill flagged it: "HTTPException belongs in the router layer, not in the repository. The repository should return `None`; the router decides what HTTP status to return."

By Module 7 I understood why: unit tests for the repository can now check the `None` return without importing FastAPI. Router tests can verify the 404 response without touching the database. I'll apply this boundary in any future service: database layer returns `None` or raises storage-specific exceptions; HTTP layer translates into HTTP status codes. Never mix the two.

---

## What I'd Improve

Two things I would change from the start:

First, I would use **Redis-backed JTI revocation** instead of the in-memory `set[str]`. The current implementation loses all revocations on API restart and does not work across multiple replicas. A production deployment with two API containers would have revoked tokens silently become valid again on whichever replica hadn't seen the logout. I documented this trade-off in ADR 0004, but I'd make the Redis version the default rather than the extension exercise.

Second, I would configure **environment-aware CORS** before writing any frontend code. I set `allow_origins=["http://localhost:5173"]` in Module 5 and had to refactor it in Module 14 to read from `settings.cors_origins`. If I had introduced the `cors_origins` config field at the start, every subsequent module would have been pointing at a production-ready pattern from day one rather than a hardcoded development URL.
