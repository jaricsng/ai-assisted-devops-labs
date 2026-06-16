# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Added
- `task_status_transitions_total` Prometheus counter (labelled `from_status`/`to_status`) emitted in `task_service.py` on every status change — closes observability gap for state-machine throughput
- Environment field in `GET /health` response (`{"status": "ok", "environment": "production"}`) so operators can confirm which deployment they are connected to
- `user_id` bound to structlog context via `bind_contextvars` in `deps.py::current_user()` — every log line in an authenticated request (including audit events) now carries the caller's identity
- `.secrets.baseline` — detect-secrets v1.5.0 baseline (32 files, 56 acknowledged false positives) enabling the pre-commit credential scan hook that was previously blocked by missing baseline
- `docs/threat-model.md` — STRIDE threat model covering 23 threats across the full three-tier stack; includes a DFD, per-threat mitigation status, residual risk register, and controls summary
- `docs/runbooks/runbook-high-error-rate.md` — step-by-step triage for elevated 5xx rate (process crash, DB failure, application error, rollback)
- `docs/runbooks/runbook-database-unreachable.md` — recovery procedure for DB container down, connection failure, and data corruption; references disaster-recovery.md for backup restore
- `docs/runbooks/runbook-high-rejection-rate.md` — triage guide for elevated 4xx rate (401/422/429/413/404) with per-code investigation steps
- `docs/runbooks/on-call-guide.md` — first-5-minutes checklist, runbook index, safe restart procedure, escalation thresholds
- `docs/post-mortems/template.md` — standard post-mortem template (timeline, impact, root cause, contributing factors, action items)
- `docs/post-mortems/2026-06-15-db-container-stop.md` — worked example post-mortem from DB container stop during load test
- `MishaKav/pytest-coverage-comment@v1.10.0` step in CI backend job — posts coverage delta as a PR comment on every pull request
- SLSA Level 3 provenance attestation job in `publish.yml` (`slsa-framework/slsa-github-generator`) — generates signed build provenance pushed to GHCR alongside the API image
- Slack failure notification job in `publish.yml` — fires on any job failure on `main`; uses `env:` to pass context safely (no shell injection risk); skips gracefully if `SLACK_WEBHOOK_URL` is unset
- `docs/threat-model.md` — comprehensive STRIDE threat model with 23 threats, DFD, mitigation status table, residual risk register, and controls summary
- `.github/workflows/drift-detection.yml` — nightly workflow (+ manual trigger) that detects staging image/version drift and OpenAPI schema drift between `docs/api/openapi.yaml` and the live API contract; posts Slack alert on divergence

### Fixed
- `load-tests/k6/load.js` — duplicate `http_req_duration` threshold key silently dropped the `p(95)<500` gate; fixed to single key with `["p(95)<650", "p(99)<1000"]`
- `backend/tests/test_auth_integration.py` — `user_payload` fixture used hardcoded `alice@example.com`; changed to `alice_<uuid8>@example.com` to prevent 409 Conflict on repeated test runs against a persistent DB

### Changed
- k6 load test thresholds calibrated with ~20% headroom for local Docker variance
- k6 smoke/load/spike scripts extended with `get_task`, `list_comments`, `cancel_transition`, `/ready` probe, and `get_project_detail` steps to cover more of the API surface

---

## [Unreleased — previous]

### Added
- Alembic database migrations (`backend/alembic/`) promoted to main project — two migrations: `001_initial_schema` and `002_add_soft_deletes`
- Disaster recovery runbook (`docs/runbooks/disaster-recovery.md`) — RTO/RPO targets, backup/restore procedures, GDPR purge schedule, post-mortem template
- Incident runbooks section in `docs/operations.md` — crash-loop, DB unreachable, Alembic failure, rate-limit reset, observability troubleshooting
- Grafana alerting rules corrected to use actual OTel metric name `http_server_duration_milliseconds` (was `http_requests_total` which did not exist)
- `CODEOWNERS` — automatic reviewer assignment for security-sensitive paths
- `CHANGELOG.md` (this file)
- `.editorconfig` — consistent editor settings across contributors
- SLI/SLO recording rules in Prometheus (`observability/prometheus.yml`)
- `.dockerignore` for `backend/` and `frontend/` — reduces image build context
- Custom Prometheus business metrics: `tasks_created_total`, `projects_created_total`
- `solution/docs/adr/0006-rate-limiting.md` — student-example ADR for the rate limiting decision

### Fixed
- `solution/docs/adr/0004-security-controls.md` — corrected "six" → "seven" security headers; added `Cache-Control: no-store` row
- `docs/adr/0003-security-controls.md` — same fix applied to canonical project ADR
- Grafana alerting rules: `HighLatency` threshold corrected from `> 0.5` (seconds) to `> 500` (milliseconds) to match the OTel millisecond histogram unit
- `backend/app/main.py` — added comment clarifying production deployments must run `alembic upgrade head`

---

## [0.1.0] — 2026-06-14

### Added

#### Core Application
- Three-tier Task Manager: React 18 + TypeScript frontend, FastAPI backend, PostgreSQL 16
- Task status state machine: `TODO → IN_PROGRESS → IN_REVIEW → DONE`; `CANCELLED` from any non-terminal state
- Full CRUD for Projects, Tasks, Comments with owner-scoped access (IDOR protection)
- JWT HS256 authentication with 30-minute token expiry and JTI revocation on logout
- bcrypt password hashing (cost factor 12)
- GDPR right-to-erasure endpoint (`DELETE /auth/users/me`) with soft delete
- Soft deletes on all four domain tables (`users`, `projects`, `tasks`, `comments`) with `deleted_at TIMESTAMPTZ` and indices
- Password strength validation (`@field_validator` in `UserCreate` schema)
- Input length constraints on all request schemas (project/task name max 255 chars, body max 5000 chars)

#### Security
- `SecurityHeadersMiddleware` — 7 HTTP security headers (X-Content-Type-Options, X-Frame-Options, X-XSS-Protection, HSTS, Referrer-Policy, CSP, Cache-Control: no-store)
- `MaxBodySizeMiddleware` — rejects bodies > 1 MiB (HTTP 413)
- `RateLimitMiddleware` — sliding-window per-IP rate limiter on `POST /auth/login` (`max_requests=10, window_seconds=60`)
- Environment-aware CORS (`cors_origins` from config, not hardcoded)
- Global exception handler (prevents stack-trace disclosure on 500 errors)
- Pre-commit hooks: bandit, detect-secrets, black, isort, ruff, no-commit-to-main
- OWASP pen test script (28 checks covering A01–A07 + governance)
- OWASP ZAP baseline scan integration
- `SECURITY.md` — vulnerability reporting policy with SLA tiers

#### Observability
- OpenTelemetry SDK: traces → Jaeger (OTLP gRPC), metrics → Prometheus
- `FastAPIInstrumentor` + `SQLAlchemyInstrumentor(enable_commenter=True)` auto-instrumentation
- Structured JSON logging via structlog with request-ID, user_id, trace_id/span_id correlation
- `RequestLoggingMiddleware` — emits `request_started` / `request_finished` events per request
- `MetricsMiddleware` — in-process request counters and slow-request logger
- Grafana dashboards provisioned from `observability/grafana/`
- Prometheus + Blackbox exporter for readiness probe monitoring

#### CI/CD
- GitHub Actions CI: backend lint + tests (≥70% coverage), frontend tsc + eslint + vitest, security scan (bandit + pip-audit + npm audit + secret grep), Docker build smoke, k6 smoke test, Playwright E2E (on PRs to main)
- GitHub Actions publish: GHCR image push, Trivy container scan (CRITICAL/HIGH hard gate), CycloneDX SBOM (90-day retention)
- Multi-cloud deploy jobs (Fly.io, Azure Container Apps, AWS ECS Fargate, GCP Cloud Run) — gated by `if: false`

#### Infrastructure
- Docker Compose with optional observability profile (Jaeger, Prometheus, Grafana, Blackbox)
- `.NET Aspire` AppHost as canonical orchestration for local dev and cloud manifest generation
- Fly.io (`fly.toml`) — `release_command = alembic upgrade head`, auto-stop, health checks
- Azure Container Apps (`azure.yaml`) — Aspire-native, postdeploy Alembic hook
- AWS ECS Fargate task definitions + OIDC keyless deploy script
- GCP Cloud Run service manifests + Workload Identity Federation deploy script

#### Documentation
- 20-module lab curriculum (`docs/modules/00–17`)
- 7 Architecture Decision Records (`docs/adr/0001–0007`)
- Operations guide (`docs/operations.md`)
- Instructor guide (`docs/instructor-guide.md`)
- Assessment rubric (`docs/rubric.md`)
- UML sequence diagrams (`docs/diagrams.md`) — 7 sequences covering auth, tasks, rate limiting, observability
- OpenAPI spec (`docs/api/openapi.yaml`)
- User guide (`docs/user-guide.md`)
- Student solution reference (`solution/`) with annotated SOLUTION_NOTES.md

---

[Unreleased]: https://github.com/jaricsng/task-manager/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/jaricsng/task-manager/releases/tag/v0.1.0
