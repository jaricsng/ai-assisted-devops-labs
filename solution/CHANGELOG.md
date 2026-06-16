# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Added
- `docs/threat-model.md` — STRIDE threat register (16 threats), DFD Level 1, mitigation verification table
- `docs/adr/0008-token-storage-strategy.md` — JWT storage trade-off (localStorage vs. httpOnly cookie vs. in-memory + refresh token)
- `docs/runbooks/` — `runbook-database-unreachable.md`, `runbook-high-rejection-rate.md`, `on-call-guide.md`
- `docs/post-mortems/` — blameless post-mortem template with completed example from incident simulation
- `docs/operations/runbook-high-error-rate.md` — SLO burn-rate runbook with PromQL and rollback steps
- `infra/terraform/` — Terraform modules and environment configs for GCP Cloud Run + Cloud SQL (staging + production)
- `/.well-known/security.txt` endpoint — responsible vulnerability disclosure (Module 14)
- `.github/CODEOWNERS` — mandatory reviewer assignment for security-sensitive paths
- `.editorconfig` — consistent editor settings across Python, TypeScript, YAML, and Markdown
- `.dockerignore` for `backend/` and `frontend/` — excludes tests, `.venv`, `node_modules/`, secrets from build context
- `backend/app/business_metrics.py` — `tasks_created_total` and `projects_created_total` Prometheus counters

---

## [0.1.0] — 2026-06-15

### Added

#### Core Application
- Three-tier Task Manager: React 18 + TypeScript frontend, FastAPI backend, PostgreSQL 16
- Task status state machine: `TODO → IN_PROGRESS → IN_REVIEW → DONE`; `CANCELLED` from any non-terminal state
- Full CRUD for Projects, Tasks, Comments with owner-scoped access (IDOR protection)
- JWT HS256 authentication with 30-minute token expiry and JTI revocation on logout
- bcrypt password hashing (cost factor 12)
- GDPR right-to-erasure endpoint (`DELETE /auth/users/me`) with soft delete
- Soft deletes on all four domain tables (`users`, `projects`, `tasks`, `comments`)
- Password strength validation and input length constraints on all request schemas

#### Security
- `SecurityHeadersMiddleware` — 7 HTTP security headers (X-Content-Type-Options, X-Frame-Options, X-XSS-Protection, HSTS, Referrer-Policy, CSP, Cache-Control: no-store)
- `MaxBodySizeMiddleware` — rejects bodies > 1 MiB (HTTP 413)
- `RateLimitMiddleware` — sliding-window per-IP rate limiter on `POST /auth/login`
- Environment-aware CORS and global exception handler
- Pre-commit hooks: bandit, detect-secrets, black, isort, ruff, no-commit-to-main
- OWASP pen test script (22 checks covering A01–A07 + governance)
- `SECURITY.md` — vulnerability reporting policy with SLA tiers

#### Observability
- OpenTelemetry SDK: traces → Jaeger (OTLP gRPC), metrics → Prometheus
- `FastAPIInstrumentor` + `SQLAlchemyInstrumentor` auto-instrumentation
- Structured JSON logging via structlog with request-ID, user_id, trace_id correlation
- Grafana dashboard + 4 alert rules (HighErrorRate, HighLatency, DatabaseUnreachable, HighRejectionRate)
- SLI/SLO recording rules in Prometheus

#### Database
- Alembic migrations: `001_initial_schema`, `002_add_soft_deletes`
- `alembic upgrade head` wired as `release_command` in Fly.io deployment

#### CI/CD
- GitHub Actions CI: backend, frontend, security scan, Docker build, k6 smoke, Playwright E2E
- GitHub Actions CD: GHCR publish, Trivy scan (hard gate), CycloneDX SBOM, semantic release tagging
- Multi-cloud deploy targets (Fly.io, Azure, AWS, GCP) — gated by `if: false` until Module 16

#### Documentation
- 6 Architecture Decision Records (Module 1–14 scope)
- Pen test report, reflection document

---

[Unreleased]: https://github.com/YOUR_USERNAME/task-manager/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/YOUR_USERNAME/task-manager/releases/tag/v0.1.0
