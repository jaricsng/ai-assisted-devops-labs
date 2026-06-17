# Solution — AI-Assisted DevOps Lab

This folder contains the **reference solution** for the Task Manager lab (Modules 00–14, plus 05b for observability and 07b for E2E testing). Modules 15–17 (SLOs, Multi-Environment, IaC) require live cloud infrastructure and GitHub repository configuration; they do not have a pre-built reference solution — the module guides in `docs/modules/` are the authoritative reference.

## How to use this folder

### As a student
- Complete each module first using only the lab guides in `docs/modules/`
- Use this folder to check your work or unblock yourself when stuck
- Pay attention to the ADRs and reflection — these are the parts that require the most original thought

### As an instructor
- Run `docker compose up` from the **project root** to verify the solution works end-to-end
- Use the pen test report and reflection as calibration samples for grading

## What's here vs the starter scaffold

| Item | Status |
|------|--------|
| Backend app (FastAPI) | Complete — all routers, services, repositories, models |
| Frontend (React) | Complete — all pages, components, API client |
| Tests | Complete — 133 backend tests (7 auth service, 13 task service, 29 governance, 11 auth endpoints, 9 auth integration, 9 security, 9 projects integration, 23 tasks integration, 23 observability); frontend: 48 component tests, 100% statement coverage; 7 E2E Playwright tests (3 auth + 4 task-flow) |
| Alembic migrations | Added — `001_initial_schema.py` and `002_add_soft_deletes.py` |
| Production Dockerfiles | Added — non-root `appuser`; production deps only (no `[dev]`) |
| Security headers middleware | Added — `app/middleware/security_headers.py` (8 headers: CSP, HSTS, X-Frame-Options, X-Content-Type-Options, X-XSS-Protection, Referrer-Policy, Cache-Control: no-store, Permissions-Policy) |
| Body size limit middleware | Added — `app/middleware/body_limit.py` (rejects requests > 1 MiB with 413) |
| Rate-limit middleware | Added — `app/middleware/rate_limit.py` (sliding-window per-IP; applied to `POST /auth/login` to block credential stuffing) |
| Token revocation | Added — JTI UUID claim in every JWT; `POST /auth/logout` revokes the session |
| GDPR deletion endpoint | Added — `DELETE /auth/users/me` soft-deletes the account |
| Soft deletes | Added — `deleted_at` column on all 4 model tables; all queries filter `IS NULL` |
| Structured audit logging | Added — every write operation emits `logger.info("audit", action=..., resource=..., resource_id=...)` |
| Input length constraints | Added — `StringConstraints` on all request schemas |
| CI workflow | Updated — bandit is a hard gate (no `--exit-zero`); `ENVIRONMENT=test` for NullPool DB isolation |
| CD workflow (publish.yml) | Updated — Trivy image scan (hard gate on CRITICAL/HIGH), CycloneDX SBOM upload, GitHub Actions pinned to commit SHAs; multi-cloud deploy jobs gated by `if: false` (remove the gate and configure secrets to activate a target) |
| Dependabot | Added — `.github/dependabot.yml` (weekly pip/npm/github-actions updates) |
| SECURITY.md | Added — vulnerability reporting policy and response SLAs |
| fly.toml | Added — Fly.io deployment config |
| ADRs | Added — 7 ADRs (architecture, API-first design with OpenAPI, security controls, soft-delete strategy & GDPR, deployment strategy with multi-cloud, observability stack, rate limiting) |
| Pen test report | Added — `docs/pen-test-report.md` |
| Reflection | Added — `docs/reflection.md` (example) |

## Running the solution

The solution shares the root-level `docker-compose.yml` and observability stack — start it from the project root:

```bash
# From the project root (not from solution/)
cp .env.example .env
# Set SECRET_KEY: python3 -c "import secrets; print(secrets.token_hex(32))"
docker compose up
```

API: http://localhost:8000  
Docs: http://localhost:8000/docs  
Frontend: http://localhost:5173

## Running backend tests

The solution backend is not mounted into the `api` Docker container — that container runs `backend/`, not `solution/backend/`. The backend requires **Python 3.12** — use the Docker runner to guarantee the right version:

```bash
# Recommended — Docker runner (guarantees Python 3.12; requires `docker compose up -d` first)
docker run --rm \
  --network task-manager_default \
  -e DATABASE_URL="postgresql+asyncpg://taskuser:taskpass@db:5432/taskmanager" \
  -e SECRET_KEY="test-secret-key-for-local-dev-only" \
  -e ENVIRONMENT=test \
  -e OTEL_ENABLED=false \
  -v "$(pwd)/solution/backend:/app" \
  -w /app \
  python:3.12-slim \
  bash -c "pip install -e '.[dev]' -q && pytest tests/ --cov=app --cov-report=term-missing -v"

# Alternative — if your system already runs Python 3.12
docker compose up db -d
cd solution/backend
pip install -e ".[dev]"
export DATABASE_URL=postgresql+asyncpg://taskuser:taskpass@localhost:5432/taskmanager
ENVIRONMENT=test OTEL_ENABLED=false pytest --cov=app --cov-report=term-missing
```

`ENVIRONMENT=test` switches the DB engine to `NullPool`, preventing asyncpg task-boundary errors from Starlette's `BaseHTTPMiddleware` stack in the ASGI test transport. `OTEL_ENABLED=false` skips OpenTelemetry setup so tests don't need a running Jaeger instance.

## Running frontend tests

```bash
cd solution/frontend
npm install
npm test          # component tests (vitest)
npm run e2e       # Playwright E2E tests (requires docker compose up first)
```
