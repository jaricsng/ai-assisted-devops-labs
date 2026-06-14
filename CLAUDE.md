# Task Manager — Claude Code Lab

## Project Overview

A three-tier Task Manager application built as a learning lab for AI-assisted DevOps with Claude Code.

- **Frontend:** React 18 + TypeScript (Vite) on port 5173
- **Business Logic:** FastAPI (Python 3.12) on port 8000
- **Database:** PostgreSQL 16 on port 5432
- **Infra:** Docker Compose

## Running the App

```bash
docker compose up                              # start core services (api, db, frontend)
docker compose --profile observability up      # also start Jaeger, Prometheus, Grafana
docker compose up -d                           # start in background
docker compose logs -f api                     # tail API logs
docker compose down -v                         # stop and wipe volumes (reset DB)
```

## Observability Stack

| Service | URL | Purpose |
|---------|-----|---------|
| Jaeger | http://localhost:16686 | Distributed trace UI (traces from API via OTLP gRPC) |
| Prometheus | http://localhost:9090 | Metrics scraping and query UI |
| Grafana | http://localhost:3000 | Unified dashboards (admin/admin) |

`OTEL_ENABLED=true` in docker-compose wires the API to export traces to Jaeger and serve Prometheus metrics at `/metrics`. Set `OTEL_ENABLED=false` to disable (e.g. unit tests).

## Running Tests

```bash
# Backend
cd backend && pytest --cov=app --cov-report=term-missing

# Frontend
cd frontend && npm test

# E2E
cd frontend && npm run e2e
```

## Security Scanning

```bash
# Run before opening any PR to main:
/security-scan        # bandit + pip-audit + npm audit + secret patterns
/check-secrets        # scan git history and tracked files for credentials
```

## Key Directories

- `backend/app/services/` — business logic (status transitions, validation rules, auth)
- `backend/app/routers/` — FastAPI route handlers (HTTP in/out only — no business logic here)
- `backend/app/models/` — SQLAlchemy ORM models (Mapped[] annotations, 2.0 style)
- `backend/app/repositories/` — SQL queries only (no business logic, no HTTPException)
- `backend/app/telemetry.py` — OTel SDK setup: traces → Jaeger, metrics → Prometheus
- `frontend/src/components/` — React UI components
- `frontend/src/api/` — typed API client + OpenAPI-generated types
- `docs/adr/` — Architecture Decision Records
- `docs/api/openapi.yaml` — API contract (source of truth for all endpoints)
- `observability/` — Prometheus scrape config and Grafana provisioning
- `.claude/commands/` — project skills (12 skills covering standards + security)

## Domain Model

```
User → owns → Projects
Project → contains → Tasks
Task → has → Comments

Task status state machine (enforced in task_service.py, NOT in the router or DB):
  TODO → IN_PROGRESS → IN_REVIEW → DONE
  Any non-terminal state → CANCELLED
  DONE and CANCELLED are terminal — no transitions out
```

## Layered Architecture

```
Router      (app/routers/)       — validates HTTP input, calls service, returns response
  ↓
Service     (app/services/)      — business rules, raises HTTPException on violations
  ↓
Repository  (app/repositories/)  — SQL queries only, returns ORM models
  ↓
Database    (PostgreSQL via SQLAlchemy async)
```

Breaking this boundary is a convention violation. Use `/review-conventions` to check.

## Available Claude Code Skills

### Coding Standards
```
/check-python [file]     — black/isort/ruff report (read-only)
/fix-python [file]       — auto-fix formatting
/check-frontend [file]   — tsc + ESLint report (read-only)
/fix-frontend [file]     — auto-fix ESLint issues
/check-standards         — full pre-merge gate (all tiers + tests + Docker build)
/review-conventions      — AI review: layer boundaries, naming, git hygiene
/check-db                — SQLAlchemy models, Alembic migrations, repository patterns
```

### Security
```
/security-scan           — bandit SAST + pip-audit + npm audit + secret grep
/security-review         — OWASP Top 10 AI review
/check-secrets           — credential scan in tracked files and git history
/check-dependencies      — CVE audit for Python + JS packages
/threat-model [feature]  — STRIDE threat model with prioritised mitigation backlog
```

## Environment Variables

Copy `.env.example` to `.env` — never commit `.env`. The `detect-secrets` pre-commit hook will block any commit that contains credential patterns.

- `DATABASE_URL` — PostgreSQL connection string
- `SECRET_KEY` — JWT signing key (generate: `openssl rand -hex 32`)
- `OTLP_ENDPOINT` — OTLP gRPC endpoint for Jaeger (default: `http://jaeger:4317`)
- `OTEL_ENABLED` — Set to `"false"` to disable OTel (default: `"true"`)
- `VITE_API_URL` — Frontend API base URL (default: `http://localhost:8000`)

## Conventions

- Python: type hints everywhere, docstrings on public functions, no bare `except:`
- TypeScript: strict mode, no `any`, interfaces for object shapes
- Git: Conventional Commits (`feat:`, `fix:`, `test:`, `docs:`, `chore:`, `ci:`)
- PRs: always from a feature branch, must pass all 4 CI jobs before merge
- Security: no secrets in code, bcrypt for passwords, SQLAlchemy ORM for all SQL
