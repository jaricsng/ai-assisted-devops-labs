# Task Manager — Claude Code Lab

## Project Overview

A three-tier Task Manager application built as a learning lab for AI-assisted DevOps with Claude Code.

- **Frontend:** React 18 + TypeScript (Vite) on port 5173
- **Business Logic:** FastAPI (Python 3.12) on port 8000
- **Database:** PostgreSQL 16 on port 5432
- **Infra:** Docker Compose (legacy) / .NET Aspire (preferred)

## Running the App

### Option A — .NET Aspire (preferred, replaces Docker Compose)

```bash
# One-time setup
dotnet workload install aspire

# Start all services (API, frontend, PostgreSQL) + Aspire Dashboard
dotnet run --project aspire/TaskManager.AppHost

# Aspire Developer Dashboard  → https://localhost:15888  (traces, logs, health)
# React frontend              → http://localhost:5173
# FastAPI backend             → http://localhost:8000
```

Credentials for local dev are pre-configured in `aspire/TaskManager.AppHost/appsettings.Development.json`.
Override via env vars (`Parameters__secret-key=...`) or `dotnet user-secrets` for production.

Generate a cloud deployment manifest:
```bash
dotnet run --project aspire/TaskManager.AppHost -- \
  --publisher manifest --output-path aspire-manifest.json
```

### Option B — Docker Compose (legacy, kept for CI)

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
# Backend — Docker runner (guarantees Python 3.12; run `docker compose up -d` first)
docker run --rm \
  --network task-manager_default \
  -e DATABASE_URL="postgresql+asyncpg://taskuser:taskpass@db:5432/taskmanager" \
  -e SECRET_KEY="test-secret-key-for-local-dev-only" \
  -e ENVIRONMENT=test \
  -e OTEL_ENABLED=false \
  -v "$(pwd)/backend:/app" \
  -w /app \
  python:3.12-slim \
  bash -c "pip install -e '.[dev]' -q && pytest tests/ --cov=app --cov-report=term-missing -v"

# Backend — alternative if system Python is already 3.12
# cd backend && ENVIRONMENT=test pytest --cov=app --cov-report=term-missing

# Frontend
cd frontend && npm test

# E2E (requires running stack; restart api after pen test to clear rate limit state)
cd frontend && npm run e2e

# Load tests — k6 (requires `docker compose up -d`)
k6 run load-tests/k6/smoke.js   # 1 VU, 60 s — smoke gate before load/spike
k6 run load-tests/k6/load.js    # 50 VUs, 9 min — SLO gate: p95 < 500 ms
k6 run load-tests/k6/spike.js   # 100 VUs burst — verify recovery

# Load tests — Locust web UI
locust -f load-tests/locustfile.py --host http://localhost:8000   # open http://localhost:8089

# Pen test (requires `docker compose up -d`)
./pen-tests/manual-checks.sh http://localhost:8000   # 38 OWASP + governance checks
./pen-tests/zap-scan.sh http://localhost:8000        # ZAP baseline scan → pen-tests/reports/
```

> **Rate-limiter note:** The pen test fires 20 rapid login attempts. Run `docker compose restart api` between pen test and E2E tests to reset in-memory rate limit state.

## Security Scanning

```bash
# Run before opening any PR to main:
/security-scan        # bandit + pip-audit + npm audit + secret patterns
/check-secrets        # scan git history and tracked files for credentials
```

## Deploying to Cloud

```bash
# Azure Container Apps (most mature Aspire path)
az login && azd auth login
azd up                          # provisions infra + deploys via Aspire manifest

# AWS ECS Fargate
aws configure
REGION=ap-southeast-1 ACCOUNT_ID=123456789 GITHUB_USERNAME=youruser bash aws/deploy.sh

# GCP Cloud Run
gcloud auth login
PROJECT_ID=my-project REGION=asia-southeast1 GITHUB_USERNAME=youruser bash infra/gcp/deploy.sh
```

Each CI deploy job in `.github/workflows/publish.yml` is gated by `if: false` — remove that line
and configure the matching GitHub Environment + secrets to activate the target.

## Key Directories

- `backend/app/services/` — business logic (status transitions, validation rules, auth)
- `backend/app/routers/` — FastAPI route handlers (HTTP in/out only — no business logic here)
- `backend/app/models/` — SQLAlchemy ORM models (Mapped[] annotations, 2.0 style)
- `backend/app/repositories/` — SQL queries only (no business logic, no HTTPException)
- `backend/app/middleware/` — SecurityHeadersMiddleware, MaxBodySizeMiddleware, RequestLoggingMiddleware, MetricsMiddleware
- `backend/app/telemetry.py` — OTel SDK setup: traces → Jaeger, metrics → Prometheus
- `frontend/src/components/` — React UI components
- `frontend/src/api/` — typed API client + OpenAPI-generated types
- `aspire/TaskManager.AppHost/` — Aspire orchestration (local dev, cloud manifest generation)
- `aspire/TaskManager.ServiceDefaults/` — shared .NET OTel/health defaults (for future .NET services)
- `aws/ecs/` — ECS Fargate task definitions
- `infra/gcp/` — Cloud Run service manifests
- `docs/adr/` — Architecture Decision Records
- `docs/api/openapi.yaml` — API contract (source of truth for all endpoints)
- `observability/` — Prometheus scrape config and Grafana provisioning
- `.claude/commands/` — project skills (19 skills covering standards, compliance, security, performance testing, and cloud deployment)

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

### Compliance
```
/compliance-check [domain]   — full best-practice compliance gate: 12 domains (code, security, architecture,
                               governance, observability, docs, containers, CI/CD). Pass a domain name to
                               run a single domain. No arg = all domains + scorecard.
```

### Performance & Security Testing
```
/load-test [smoke|load|spike|locust]  — run k6 or Locust scenario, parse results, identify bottlenecks
/pen-test [authentication|access-control|injection|design]  — structured pen test with OWASP findings
```

### Deployment & Cloud
```
/check-aspire [file]     — review Aspire AppHost wiring, secret hygiene, manifest readiness
/check-azure [file]      — review Azure Container Apps config, OIDC auth, Key Vault, scaling
/check-aws [file]        — review ECS Fargate task defs, IAM least-privilege, Secrets Manager, OIDC
/check-gcp [file]        — review Cloud Run YAMLs, WIF auth, Secret Manager, Cloud SQL proxy
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
- PRs: always from a feature branch, must pass all 5 CI jobs before merge
- Security: no secrets in code, bcrypt for passwords, SQLAlchemy ORM for all SQL, soft deletes only (no hard DELETE), JTI revocation on logout
- Audit: every write operation emits a structlog audit event with action/resource/resource_id
