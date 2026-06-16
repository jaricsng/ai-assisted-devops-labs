# Solution Notes — What Each File Demonstrates

This document maps each solution file to the lab module that produces it.

## Files present only in solution/ (not in starter scaffold)

| File | Module | What it teaches |
|------|--------|----------------|
| `backend/Dockerfile` (non-root, prod-only deps) | 13, 14 | Production image: non-root `appuser`, no dev/test dependencies |
| `frontend/Dockerfile` (non-root) | 13, 14 | React build → nginx static serving; non-root user |
| `frontend/nginx.conf` | 13 | SPA routing (all 404s → index.html), static asset caching |
| `backend/alembic.ini` | 4 | Alembic configuration, `DATABASE_URL` read from env not ini file |
| `backend/alembic/env.py` | 4 | Async SQLAlchemy + Alembic wiring; converts asyncpg URL for sync Alembic |
| `backend/alembic/versions/001_initial_schema.py` | 4 | Full schema in one migration; named PostgreSQL enum types; working `downgrade()` |
| `backend/alembic/versions/002_add_soft_deletes.py` | 14 | Adds `deleted_at TIMESTAMPTZ` + index to users, projects, tasks, comments; reversible `downgrade()` |
| `backend/app/middleware/security_headers.py` | 14 | HTTP security headers middleware — all 8 headers: X-Content-Type-Options, X-Frame-Options, X-XSS-Protection, Strict-Transport-Security, Referrer-Policy, Content-Security-Policy, Cache-Control: no-store, Permissions-Policy |
| `backend/app/middleware/body_limit.py` | 14 | MaxBodySizeMiddleware — rejects requests with Content-Length > 1 MiB (HTTP 413) |
| `backend/app/schemas/user.py` | 5, 12 | `@field_validator` for password strength (A07 pen test fix) |
| `backend/tests/test_auth_integration.py` | 7 | 9 tests: TestRegister (weak/empty/invalid password → 422, no hashed_password in response), TestLogin (user enumeration identical errors), TestProtectedEndpoints (invalid token, alg:none, expired JWT, missing sub claim) |
| `backend/tests/test_auth_endpoints.py` | 7, 14 | 11 tests: logout revocation, GDPR deletion, security headers, soft-delete flows |
| `backend/tests/test_auth_service.py` | 5, 14 | 7 tests: bcrypt hash/verify round-trip, JWT create/decode, JTI uniqueness per token, and revoke/check cycle — no database required |
| `backend/tests/test_governance.py` | 14 | 29 tests: transport security (security headers, body limit, input constraints), weak password (3 parametrize cases), rate limiting (429 after 11th attempt), X-Forwarded-For IP extraction, sliding-window expiry, security.txt RFC 9116, SECRET_KEY validator (5 cases), audit log emission for 10 event types (REGISTER, LOGIN_SUCCESS, LOGIN_FAILED, LOGOUT, USER_DELETED, PROJECT_CREATED, PROJECT_DELETED, TASK_CREATED, TASK_UPDATED, TASK_DELETED) |
| `backend/tests/test_security.py` | 7, 12 | 9 tests: TestPasswordValidator (3: min-length, uppercase, digit), TestCORS (4: allowed origin, disallowed origin, preflight OPTIONS, no origin), TestResponseHeaders (2: server header fingerprinting, security headers present) |
| `backend/tests/test_projects_integration.py` | 7 | 9 tests: project CRUD, IDOR isolation (User B cannot access User A's projects, 2 cases) |
| `backend/tests/test_tasks_integration.py` | 7, 12, 14 | 23 tests: task lifecycle (create/read/update/delete), status transitions (happy path, invalid, terminal CANCELLED), IDOR at task + comment level (4 cases), comments, CANCEL transition, field updates (priority + description), task filtering by status/priority/both/no-match, COMMENT_CREATED audit log |
| `fly.toml` | 13 | Fly.io app config: `release_command` for migrations, health checks, concurrency |
| `docs/adr/0001-three-tier-architecture.md` | 1 | Architecture decision with trade-offs documented |
| `docs/adr/0002-jwt-authentication.md` | 2, 5 | JWT vs session cookies; alg:none protection rationale |
| `docs/adr/0003-alembic-for-migrations.md` | 4 | Why Alembic; expand/contract convention; no `create_all()` in prod |
| `docs/adr/0004-security-controls.md` | 14 | JWT HS256, bcrypt cost factor 12, JTI revocation trade-offs (in-memory vs Redis), environment-aware CORS |
| `docs/adr/0005-soft-delete-strategy.md` | 14 | Soft delete rationale, GDPR Article 17 right to erasure, 90-day retention window, hard-purge schedule |
| `docs/adr/0006-rate-limiting.md` | 5, 14 | Sliding-window in-memory middleware vs. slowapi vs. Redis; why middleware layer, not router; operational note on pen-test bucket reset |
| `backend/app/business_metrics.py` | 05b | `prometheus_client.Counter` for domain-level metrics — `tasks_created_total`, `projects_created_total`; demonstrates custom (non-OTel) Prometheus instrumentation alongside auto-instrumented OTel metrics |
| `docs/adr/0007-infrastructure-as-code.md` | 17 | IaC tool selection: Terraform (HCL + GCS state) over Pulumi, Deployment Manager, CDKTF; covers module/environment structure, GCS remote state, secret handling via Secret Manager, OpenTofu as open-source alternative |
| `docs/adr/0008-token-storage-strategy.md` | 19 | JWT storage trade-off: localStorage (current, CSP-mitigated) vs. httpOnly cookie vs. in-memory + refresh token; documents T-02 from threat model as the accepted risk |
| `docs/operations/runbook-high-error-rate.md` | 15 | SLO burn-rate runbook: triage → endpoint identification → DB/app diagnosis → rollback → escalation; includes PromQL queries referencing the recording rules from Module 15 |
| `docs/runbooks/runbook-database-unreachable.md` | 18 | P1 runbook with four remediation paths: container stopped, pool exhaustion, disk full, migration lock; includes verify-resolution step and SLO impact calculation |
| `docs/runbooks/runbook-high-rejection-rate.md` | 18 | P3/P2 runbook for credential stuffing detection; distinguishes pen-test false-positive from real attack; includes account-compromise check via audit log |
| `docs/runbooks/on-call-guide.md` | 18 | Alert → runbook mapping table, first-5-minutes checklist, escalation contacts, post-incident checklist, handoff protocol |
| `docs/post-mortems/2026-06-15-db-container-stop.md` | 18 | Completed post-mortem from the Module 18 incident simulation: full timeline, systemic root cause, contributing factors, what went well, action items with owners |
| `docs/threat-model.md` | 19 | Complete STRIDE threat model: Level-1 DFD, 16-threat register with Likelihood/Impact/Risk scoring, mitigation verification table (each threat traced to file:function), accepted risks with rationale and monitoring |
| `infra/terraform/modules/cloud-run/variables.tf` | 17 | Terraform module input declarations: project_id, region, environment (validated), image_tag, secret_key (sensitive), db_tier, min/max_instances |
| `infra/terraform/modules/cloud-run/main.tf` | 17 | Complete GCP module: Cloud SQL (PostgreSQL 16) with backup + PITR, random password, Secret Manager for DATABASE_URL + SECRET_KEY, service account with minimal IAM, Cloud Run v2 service with health probes + Cloud SQL socket |
| `infra/terraform/modules/cloud-run/outputs.tf` | 17 | Module outputs: api_url, db_connection_name, service_account_email |
| `infra/terraform/environments/staging/backend.tf` | 17 | GCS remote state backend, prefix `task-manager/staging`; provider version lock |
| `infra/terraform/environments/staging/variables.tf` | 17 | Environment-level variable declarations (project_id, region, image_tag, github_repository, secret_key) |
| `infra/terraform/environments/staging/main.tf` | 17 | Staging environment: calls cloud-run module with `min_instances=0` (scale-to-zero) and `db-f1-micro` |
| `infra/terraform/environments/production/backend.tf` | 17 | GCS remote state backend, prefix `task-manager/production` (separate from staging) |
| `infra/terraform/environments/production/variables.tf` | 17 | Same variable declarations as staging — separate file so plans are independent |
| `infra/terraform/environments/production/main.tf` | 17 | Production environment: `min_instances=1` (always-on), `db-n1-standard-1`, `max_instances=20` |
| `.editorconfig` | 03 | Consistent editor settings across Python (indent=4), TypeScript/JS (indent=2), YAML (indent=2), and Markdown; respected by VS Code, JetBrains, vim out of the box |
| `.github/CODEOWNERS` | 03, 14 | Mandatory reviewer assignment for security-sensitive paths (`middleware/`, `routers/auth.py`, `alembic/`, `.github/workflows/`); uses `@YOUR_GITHUB_USERNAME` placeholder |
| `CHANGELOG.md` | 09 | Keep a Changelog format with `[Unreleased]` and `[0.1.0]` sections; student-perspective release history covering the complete lab build |
| `backend/.dockerignore` | 13 | Excludes `.venv`, `tests/`, `.env`, `.git`, `node_modules/` from Docker build context; keeps `alembic/` (needed for `release_command`) |
| `frontend/.dockerignore` | 13 | Excludes `e2e/`, `playwright-report/`, `node_modules/`, `.env` files from frontend build context; reduces image build time and attack surface |
| `backend/app/well_known.py` | 14 | RFC 9116 responsible disclosure endpoint at `/.well-known/security.txt`; `PlainTextResponse`; `include_in_schema=False` keeps it out of OpenAPI docs; registered in `main.py` |
| `docs/pen-test-report.md` | 12 | CVSS scoring, PASS/FAIL evidence, remediation tracking |
| `docs/reflection.md` | 10 | 8 sections: what was built, 3 Claude Code prompt examples, 1 disagreement, 1 security finding, observability insight, load testing insight (what k6 numbers revealed), best practice carried forward, and one architectural decision cross-referenced to an ADR |

## Files copied verbatim from the scaffold

These files exist in solution/ and are **identical** to the parent project. They are included so students can run `pytest` and frontend tests from the solution directory without needing to reference the parent tree:

**Backend (copied from `backend/`):**
- `backend/app/telemetry.py` — OTel SDK setup: traces → Jaeger, metrics → Prometheus (Module 05b)
- `backend/app/middleware/metrics.py` — in-process request counter + slow-request logger (Module 05b)
- `backend/app/middleware/rate_limit.py` — sliding-window rate limiter on `/auth/login` (Module 05)
- `backend/app/services/task_service.py` — task status state machine and validation (Module 05)
- `backend/tests/test_health.py` — health + readiness endpoint tests (Module 07)
- `backend/tests/test_observability.py` — metrics mount, request-ID header tests (Module 07)
- `backend/tests/test_task_service.py` — unit tests for the task service state machine (Module 07)
- `backend/pyproject.toml` — package metadata and tool configuration (Module 03)

**Frontend (copied from `frontend/`):**
- `frontend/src/` — all React source files (App.tsx, pages/, components/, api/, hooks/) (Module 06)
- `frontend/e2e/` — Playwright E2E tests (auth.spec.ts, task-flow.spec.ts, pages/) (Module 07b)
- `frontend/playwright.config.ts` — Playwright configuration (Module 07b)
- `frontend/package.json`, `vite.config.ts`, `tsconfig*.json`, `eslint.config.js`, `index.html`

**Shared resources (not duplicated — use from project root):**
- `docker-compose.yml` — start services with `docker compose up` from the project root
- `.github/workflows/ci.yml` and `publish.yml` — CI/CD pipelines
- `.github/dependabot.yml` — weekly pip/npm/GitHub Actions updates
- `SECURITY.md` — vulnerability reporting policy
- `observability/`, `load-tests/`, `pen-tests/`, `.pre-commit-config.yaml`, `CLAUDE.md`, `CONTRIBUTING.md`

## Files that differ from the original scaffold design

| File | Change | Why |
|------|--------|-----|
| `backend/app/services/auth_service.py` | Uses `bcrypt.hashpw` / `bcrypt.checkpw` directly; adds `jti` UUID claim, `get_token_payload`, `revoke_token`, `is_revoked` | Direct bcrypt avoids `passlib` 1.7.4 / `bcrypt` 4+ incompatibility. JTI revocation is the enterprise governance addition from Module 14. |
| `backend/app/routers/auth.py` | Added `POST /auth/logout` (JTI revocation) and `DELETE /auth/users/me` (GDPR soft-delete); structured audit logs on register/login | Module 14 enterprise governance — session management and right-to-erasure |
| `backend/app/routers/deps.py` | `current_user` now checks `is_revoked(jti)`; sets `request.state.user_id` and `request.state.jti` | Required for token revocation and user_id audit log binding |
| `backend/app/routers/projects.py` | Audit log calls on create/delete; `projects_created_total.inc()` after creation | Module 14 audit logging; Module 05b business metrics |
| `backend/app/routers/tasks.py` | Audit log calls on create/update/delete; `tasks_created_total.inc()` after creation | Module 14 audit logging; Module 05b business metrics |
| `backend/app/models/*.py` | `deleted_at: Mapped[datetime \| None]` added to all 4 models | Module 14 — soft deletes replace hard deletes across the entire domain |
| `backend/app/repositories/*.py` | All queries filter `deleted_at IS NULL`; deletes set `deleted_at` instead of `db.delete()` | Enforces soft-delete contract at the repository boundary |
| `backend/app/schemas/*.py` | `StringConstraints(min_length=1, max_length=...)` on all request bodies | Module 14 — input length limits prevent memory exhaustion and over-large payloads |
| `backend/app/database.py` | `NullPool` when `ENVIRONMENT=test`; explicit `pool_size/max_overflow/pool_pre_ping/pool_recycle` in production | `NullPool` prevents asyncpg "Future attached to different loop" errors with Starlette's `BaseHTTPMiddleware` in tests |
| `backend/app/config.py` | `cors_origins: list[str]` field | Environment-driven CORS — no hardcoded origins |
| `backend/app/main.py` | Middleware stack (SecurityHeaders → CORS → MaxBodySize → RateLimit → Logging → Metrics); global exception handler; `create_all()` in dev startup | SecurityHeaders and MaxBodySize are Module 14 additions |
| `backend/app/middleware/logging.py` | Binds `user_id` to structlog context after `call_next` | Makes every `request_finished` log line carry the authenticated user ID |
| `backend/tests/conftest.py` | `NullPool` / `ENVIRONMENT=test` isolation; `autouse` fixture calls `reset_for_testing()` to clear the in-memory rate-limit bucket before each test | `BaseHTTPMiddleware` requires `NullPool`; all ASGI tests share `"unknown"` IP so bucket must reset between tests |
| `.github/workflows/ci.yml` | Bandit hard gate (no `--exit-zero`); `ENVIRONMENT=test` env var in pytest step | Module 14 supply chain hardening |
| `frontend/src/App.tsx` | Auth state uses `useState` instead of a bare `localStorage.getItem` call | React 18 batching caused the inline function to return `false` during the re-render triggered by `navigate("/projects")`, immediately redirecting back to `/login`; reactive state is correct regardless |
| `frontend/src/pages/LoginPage.tsx` | Accepts an `onLogin?: () => void` prop | Required for the `App.tsx` reactive auth state — `onLogin()` batches `setIsAuthed(true)` with the `navigate("/projects")` call so both apply in the same React render |

## Key differences to discuss in class

### 1. Password validation (Modules 5 + 12 interaction)
The starter scaffold's `UserCreate` schema has no password validation. The pen test (Module 12) flags weak passwords as a Medium finding (A07). The fix is in `backend/app/schemas/user.py` — a `@field_validator` that gives specific error messages per violation. This is a good example of how security testing drives code quality improvements.

### 2. Integration tests include security assertions (Module 7 + 12 interaction)
`test_auth_integration.py` includes a test for the `alg:none` JWT attack. `test_projects_integration.py` includes IDOR tests. These tests would have caught the security issues the pen test found — demonstrating that a good test suite is also a security control.

### 3. Production Dockerfile vs dev Dockerfile (Module 13 + 14)
The solution `backend/Dockerfile` runs as non-root `appuser` and installs only production dependencies (no `.[dev]`). The diff is small but the security implications are significant: test tools, linters, and bandit are not present in the production image.

### 4. Alembic env.py reads DATABASE_URL from environment (Module 4)
The `env.py` calls `os.environ["DATABASE_URL"]` at migration time rather than using the `sqlalchemy.url` placeholder in `alembic.ini`. This is the correct pattern: secrets in environment, not in committed config files.

### 5. JTI revocation trade-off (Module 14)
`auth_service.py` uses an in-memory `set[str]` for revoked JTIs. This works for a single-process deployment but loses all revocations on restart and does not share across replicas. ADR 0004 documents the trade-off. The discussion question: "What changes if we deploy two API replicas? What would a Redis-backed implementation look like?"

### 6. NullPool for test isolation (Modules 7 + 14)
Adding `SecurityHeadersMiddleware` and `MaxBodySizeMiddleware` (both `BaseHTTPMiddleware` subclasses) caused asyncpg to raise `RuntimeError: Future attached to a different loop` in tests. The fix is `NullPool` when `ENVIRONMENT=test`. This teaches students that middleware stack changes can have non-obvious test infrastructure effects — and that the root cause is always worth understanding rather than just suppressing.

### 7. Soft deletes across all four tables (Module 14)
Every repository's `delete()` method sets `deleted_at` instead of calling `db.delete()`. Every `SELECT` query filters `deleted_at IS NULL`. The consequence: test isolation requires unique emails per test (`uuid.uuid4()`) because soft-deleted users remain in the database between test runs and `get_by_email` correctly ignores them — but uniqueness constraints still apply.

---

## Modules 15–19 — Partial solution (templates + examples)

Some later modules require live cloud infrastructure or team-specific decisions. The solution
provides completed example files that students can compare against — but the values
(project IDs, alert thresholds, threat IDs) will differ for each student.

| Module | What the solution provides | What students must customise |
|--------|---------------------------|------------------------------|
| 15 — SLOs & Error Budgets | `docs/operations/runbook-high-error-rate.md` — completed SLO runbook with PromQL | Prometheus recording rules load against *your* live metric names; Grafana SLO dashboard panels reference *your* datasource |
| 16 — Multi-Environment | No pre-built file — GitHub Environments and Fly.io apps are per-account | Follow the module guide; the publish.yml job structure in the parent project is the reference |
| 17 — Infrastructure as Code | `infra/terraform/modules/cloud-run/` + `environments/staging/` + `environments/production/` — complete GCP Terraform | Replace `YOUR_PROJECT_ID` in `backend.tf`; set `project_id`, `github_repository` in `terraform.tfvars`; the `secret_key` must be injected via CI secrets — never committed |
| 18 — Incident Response | `docs/runbooks/` (3 runbooks) + `docs/post-mortems/` (1 completed post-mortem) | Escalation contacts, incident tool links, and post-mortem timestamps are fictional — replace with real values |
| 19 — Threat Modeling | `docs/threat-model.md` (16-threat STRIDE register) + `docs/adr/0008-token-storage-strategy.md` | Threat IDs and mitigation file paths reference *this* codebase exactly — your threat model may diverge if you changed architecture |

The **authoritative reference for the learning content** is the module guide in `docs/modules/`:
- [`docs/modules/15-slos-and-error-budgets.md`](../../docs/modules/15-slos-and-error-budgets.md)
- [`docs/modules/16-multi-environment.md`](../../docs/modules/16-multi-environment.md)
- [`docs/modules/17-infrastructure-as-code.md`](../../docs/modules/17-infrastructure-as-code.md)
- [`docs/modules/18-incident-response.md`](../../docs/modules/18-incident-response.md)
- [`docs/modules/19-threat-modeling.md`](../../docs/modules/19-threat-modeling.md)

---

## Note on solution/docs/adr vs docs/adr

The `solution/docs/adr/` files are **student-written example ADRs** — they show what a well-written student submission looks like across the modules that require ADRs (Modules 1, 2/5, 4, 5, 14, 17, 19). They use a student's perspective ("we chose X because…") and are scoped to decisions visible at the time each module was completed. The solution has **8 example ADRs** (0001–0008):

| Solution ADR | Topic | Module |
|-------------|-------|--------|
| 0001 | Three-tier architecture | 1 |
| 0002 | JWT authentication | 2, 5 |
| 0003 | Alembic for migrations | 4 |
| 0004 | Security controls (JWT, bcrypt, JTI, CORS, 8 headers, security.txt) | 14 |
| 0005 | Soft delete strategy and GDPR compliance | 14 |
| 0006 | Rate limiting (sliding-window middleware vs. slowapi vs. Redis) | 5, 14 |
| 0007 | Infrastructure as Code: Terraform for GCP Cloud Run (vs. Pulumi, Deployment Manager, CDKTF) | 17 |
| 0008 | JWT token storage: localStorage vs. httpOnly cookie vs. in-memory (threat T-02 from Module 19) | 19 |

The **canonical project ADRs** live at `docs/adr/` in the project root. These are instructor-maintained, cover the full system, and reflect the final implementation including all modules through 19. The project root currently has **9 ADRs** (0001–0009):

| ADR | Topic |
|-----|-------|
| 0001 | Three-tier architecture |
| 0002 | API-first design with OpenAPI |
| 0003 | Security controls (JWT, bcrypt, JTI, CORS, 8 headers, security.txt) |
| 0004 | Soft-delete strategy and GDPR compliance |
| 0005 | Deployment strategy (multi-cloud via .NET Aspire) |
| 0006 | Observability stack (structlog + OTel + Prometheus + Jaeger) |
| 0007 | Rate limiting (sliding-window in-memory middleware) |
| 0008 | Database migration strategy (Alembic vs. create_all(), expand/contract) |
| 0009 | JWT token storage: localStorage (lab) vs. httpOnly cookie + refresh token (production) |

When a student ADR and a project ADR cover the same topic (e.g., security controls or rate limiting), the project-root ADR is the authoritative reference; the solution ADR is an example of how to express the same decision in a student's voice. Note that the solution ADR numbering differs from the project-root ADR numbering — they are parallel documents, not the same files.
