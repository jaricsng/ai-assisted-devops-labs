# Operations Guide — Task Manager

Day-to-day reference for starting, stopping, restarting, and troubleshooting the application stack.

> **Preferred orchestration: .NET Aspire**
> This guide covers Docker Compose (the CI default and the fallback for any environment). For local development, `.NET Aspire` is preferred — it starts all services plus a developer dashboard at https://localhost:15888. See `CLAUDE.md → Running the App → Option A` for Aspire setup.

---

## Prerequisites

### macOS — fix the `docker` PATH

Docker Desktop ships its own CLI at a non-standard path. If `docker` resolves to a Multipass or Homebrew binary, compose commands will fail. Verify:

```bash
which docker
# should be /Applications/Docker.app/Contents/Resources/bin/docker
# NOT /usr/local/bin/docker or something under /multipass/
```

If it points elsewhere, add Docker Desktop to the front of your PATH (add to `~/.zshrc`):

```bash
export PATH="/Applications/Docker.app/Contents/Resources/bin:$PATH"
```

Then reload your shell: `source ~/.zshrc`

---

## Environment Variables

Copy `.env.example` to `.env` before the first `docker compose up`. The `.env` file is gitignored — never commit it.

```bash
cp .env.example .env
# Generate a strong SECRET_KEY:
python3 -c "import secrets; print(secrets.token_hex(32))"
# Paste the output as SECRET_KEY= in .env
```

| Variable | Default | Purpose |
|----------|---------|---------|
| `DATABASE_URL` | `postgresql+asyncpg://taskuser:taskpass@db:5432/taskmanager` | PostgreSQL connection string |
| `SECRET_KEY` | *(must be set)* | JWT signing key — generate with `openssl rand -hex 32` |
| `OTEL_ENABLED` | `"true"` | Set to `"false"` to disable OpenTelemetry (speeds up unit tests) |
| `OTLP_ENDPOINT` | `http://jaeger:4317` | OTLP gRPC endpoint for trace export |
| `VITE_API_URL` | `http://localhost:8000` | Frontend API base URL |
| `ENVIRONMENT` | `development` | Set to `test` in CI — switches DB engine to NullPool for test isolation |

> **Security:** The pre-commit `detect-secrets` hook will block any commit that contains a credential pattern. If you accidentally commit a secret, rotate it immediately and use `git filter-repo` to remove it from history.

---

## Core Stack (API · DB · Frontend)

### Start

```bash
# Foreground — logs stream to the terminal, Ctrl-C stops everything
docker compose up

# Background — returns the prompt immediately
docker compose up -d
```

### Stop

```bash
# Stop containers but keep data volumes (DB state is preserved)
docker compose down

# Stop AND wipe all data (full reset — DB is empty on next start)
docker compose down -v
```

### Restart

```bash
# Restart all services
docker compose restart

# Restart a single service without touching others
docker compose restart api
docker compose restart frontend
docker compose restart db
```

### Recreate (pick up docker-compose.yml changes)

A plain `restart` reuses the existing container — it does **not** apply changes to `command:`, `environment:`, or `image:` in `docker-compose.yml`. Use `--force-recreate` to apply those:

```bash
# Recreate one service (e.g. after editing its command or env vars)
docker compose up -d --force-recreate api

# Recreate all services
docker compose up -d --force-recreate
```

### Rebuild (pick up Dockerfile changes)

If you change the `Dockerfile` or `pyproject.toml`, you need to rebuild the image:

```bash
# Rebuild and restart the API
docker compose up -d --build api

# Rebuild everything
docker compose up -d --build
```

> **Note:** The API runs with `--reload` in development, so changes to Python source files under `backend/app/` are picked up automatically **without** a rebuild or restart.

---

## Running Tests

The test suite runs inside the Docker stack (backend) or from the host (frontend/E2E).

### Backend — unit + integration (Module 07)

The API container installs production dependencies only — it does **not** include `pytest` or the test toolchain. Use the Docker runner to get a clean Python 3.12 environment with dev deps:

```bash
# Recommended — Docker runner (requires `docker compose up -d` for the DB)
docker run --rm \
  --network task-manager_default \
  -e DATABASE_URL="postgresql+asyncpg://taskuser:taskpass@db:5432/taskmanager" \
  -e SECRET_KEY="test-secret-key-for-local-dev-only" \
  -e ENVIRONMENT=test \
  -e OTEL_ENABLED=false \
  -v "$(pwd)/backend:/app" \
  python:3.12-slim \
  bash -c "pip install -e '.[dev]' -q && pytest tests/ --cov=app --cov-report=term-missing -v"

# Alternative — if your system already runs Python 3.12
cd backend && pip install -e ".[dev]"
ENVIRONMENT=test OTEL_ENABLED=false pytest --cov=app --cov-report=term-missing

# Fail the run if coverage drops below 70%
# (add --cov-fail-under=70 to either command above)
```

`ENVIRONMENT=test` switches the SQLAlchemy engine to `NullPool`, preventing asyncpg connection-boundary errors in the ASGI test transport. `OTEL_ENABLED=false` skips OTel setup so tests do not require a running Jaeger instance.

### Frontend — component tests (Module 07)

```bash
cd frontend && npm test            # watch mode (interactive)
cd frontend && npm test -- --run   # single run (CI mode)
cd frontend && npm test -- --coverage
```

### E2E — Playwright (Module 07b)

Requires the full stack running (`docker compose up -d`):

```bash
cd frontend && npm run e2e
```

Playwright test results land in `frontend/test-results/` and reports in `frontend/playwright-report/` (both gitignored).

### Load tests — k6 (Module 11)

Requires `docker compose up -d`. The Docker runner uses `--network task-manager_default` so it can reach the API container at `http://api:8000` (plain `--network host` is unreliable on macOS Docker Desktop).

```bash
# Smoke (1 VU, 60 s — sanity check before any load run)
docker run --rm --network task-manager_default \
  -e BASE_URL=http://api:8000 \
  -v "$(pwd)/load-tests/k6:/scripts" \
  grafana/k6 run /scripts/smoke.js

# Load (ramp to 50 VUs, 9 min — SLO gates: p95 < 500 ms, errors < 1%)
docker run --rm --network task-manager_default \
  -e BASE_URL=http://api:8000 \
  -v "$(pwd)/load-tests/k6:/scripts" \
  grafana/k6 run /scripts/load.js

# Spike (burst to 100 VUs — verify recovery after sudden traffic event)
docker run --rm --network task-manager_default \
  -e BASE_URL=http://api:8000 \
  -v "$(pwd)/load-tests/k6:/scripts" \
  grafana/k6 run /scripts/spike.js
```

If k6 is installed locally, skip Docker: `k6 run load-tests/k6/smoke.js` (the script defaults `BASE_URL` to `http://localhost:8000`).

> **k6 tip:** Use the `/load-test` Claude Code skill to run scenarios, parse results, and correlate with Prometheus + Jaeger automatically.

### Pen tests (Module 12)

```bash
# Automated OWASP A01–A07 + Module 14 governance checks
./pen-tests/manual-checks.sh http://localhost:8000

# OWASP ZAP baseline scan (pulls Docker image on first run — ~1.5 GB)
./pen-tests/zap-scan.sh http://localhost:8000
```

> **CI DAST gate:** The ZAP baseline scan also runs automatically as a `zap-baseline-scan` job in `publish.yml` after each staging deployment (gated by `if: false`; enable alongside `deploy-fly-staging`). See Module 13 for the CI DAST gate configuration.

---

## Observability Stack (Jaeger · Prometheus · Grafana)

The observability services are opt-in. They run under the `observability` Docker Compose profile.

### Start (with core stack)

```bash
docker compose --profile observability up -d
```

### Start (observability only, core already running)

```bash
docker compose --profile observability up -d jaeger prometheus grafana blackbox-exporter
```

### Stop (observability only, leave core running)

```bash
docker compose --profile observability stop jaeger prometheus grafana blackbox-exporter
```

### Stop everything (core + observability)

```bash
docker compose --profile observability down
```

### Service URLs

| Service | URL | Credentials |
|---------|-----|-------------|
| Frontend | http://localhost:5173 | — |
| API | http://localhost:8000 | — |
| API docs (Swagger) | http://localhost:8000/docs | — |
| API metrics | http://localhost:8000/metrics | — |
| Jaeger (traces) | http://localhost:16686 | — |
| Prometheus | http://localhost:9090 | — |
| Grafana | http://localhost:3000 | admin / admin |
| Blackbox Exporter | http://localhost:9115 | — |

---

## Logs

### Tail logs for a single service

```bash
docker compose logs -f api
docker compose logs -f frontend
docker compose logs -f db
```

### Tail all services at once

```bash
docker compose --profile observability logs -f
```

### Show last N lines without following

```bash
docker compose logs --tail=100 api
```

### Filter API logs by level or event

The API emits structured JSON logs via `structlog`. Pipe through `jq` to filter:

```bash
# Show only errors
docker compose logs -f api | grep '"level":"error"'

# Pretty-print all log lines
docker compose logs -f api | jq '.'

# Show only slow requests (duration_ms > 500)
docker compose logs -f api | jq 'select(.duration_ms > 500)'
```

### Filter audit logs by action

Every write operation emits a structured audit log line with `"event":"audit"`. The authenticated user's `user_id` is bound to the log context automatically.

```bash
# See all audit events with who performed them
docker compose logs -f api | jq 'select(.event=="audit")'

# Track a specific user's write actions
docker compose logs -f api | jq 'select(.event=="audit" and .user_id==42)'

# See only project-level events
docker compose logs -f api | jq 'select(.event=="audit" and .resource=="project")'

# See only authentication events (logins, logouts, registrations)
docker compose logs -f api | jq 'select(.event=="audit" and .resource=="user" or .resource=="session")'
```

**Audit actions emitted:** `REGISTER`, `LOGIN_SUCCESS`, `LOGIN_FAILED`, `LOGOUT`, `USER_DELETED`, `PROJECT_CREATED`, `PROJECT_DELETED`, `TASK_CREATED`, `TASK_UPDATED`, `TASK_DELETED`, `COMMENT_CREATED`.

---

## Database

### Open a psql shell

```bash
docker compose exec db psql -U taskuser -d taskmanager
```

### Reset the database (wipe all data)

```bash
docker compose down -v          # removes the postgres_data volume
docker compose up -d            # starts fresh — tables are recreated on first API startup
```

### Inspect tables

```sql
-- Inside psql:
\dt                             -- list tables
SELECT * FROM users LIMIT 5;
SELECT * FROM projects LIMIT 5;
SELECT id, title, status FROM tasks ORDER BY created_at DESC LIMIT 10;
```

### Soft-deleted records

Records are never hard-deleted; `deleted_at` is set to the UTC timestamp instead. All application queries filter `WHERE deleted_at IS NULL`, so soft-deleted records are invisible to the API but retained in the database for audit compliance.

```sql
-- View soft-deleted users (GDPR-deleted accounts)
SELECT id, email, deleted_at FROM users WHERE deleted_at IS NOT NULL;

-- View all tasks including soft-deleted ones
SELECT id, title, status, deleted_at FROM tasks ORDER BY created_at DESC LIMIT 20;

-- Count soft-deleted vs active records per table
SELECT
  (SELECT COUNT(*) FROM users    WHERE deleted_at IS NOT NULL) AS deleted_users,
  (SELECT COUNT(*) FROM projects WHERE deleted_at IS NOT NULL) AS deleted_projects,
  (SELECT COUNT(*) FROM tasks    WHERE deleted_at IS NOT NULL) AS deleted_tasks,
  (SELECT COUNT(*) FROM comments WHERE deleted_at IS NOT NULL) AS deleted_comments;
```

To permanently purge soft-deleted records (e.g., after a legal retention window expires):
```sql
-- Hard-delete users that were soft-deleted more than 90 days ago
DELETE FROM users WHERE deleted_at < NOW() - INTERVAL '90 days';
```

### Database Migrations (Alembic) — Module 04

Alembic manages the schema. In development, the API auto-creates tables on startup (`metadata.create_all`). For production or after schema changes, run migrations explicitly:

```bash
# Apply all pending migrations to the running DB
docker compose exec api alembic upgrade head

# Check current migration version
docker compose exec api alembic current

# Generate a new migration from ORM model changes
docker compose exec api alembic revision --autogenerate -m "add_due_date_column"

# Rollback one migration
docker compose exec api alembic downgrade -1
```

> **Naming convention:** Migration files follow `NNNN_description.py` (e.g., `0001_initial_schema.py`, `0002_add_soft_deletes.py`). Always review autogenerated migrations before applying — Alembic cannot detect column renames or data migrations.

---

## Seed Demo Data

Load a demo account and sample projects/tasks for quick exploration:

```bash
docker compose exec api python seed.py
```

This creates (idempotently — safe to run multiple times):

| | |
|-|-|
| **Email** | `demo@example.com` |
| **Password** | `Demo1234!` |
| **Projects** | Website Redesign · Payment & Notifications Integration |
| **Tasks** | 12 tasks spread across TODO / IN_PROGRESS / IN_REVIEW / DONE |

If the demo user already exists the script skips silently. To reseed from scratch, reset the database first:

```bash
docker compose down -v && docker compose up -d
docker compose exec api python seed.py
```

---

## Health Checks

```bash
# Liveness — is the API process running?
curl http://localhost:8000/health
# {"status":"ok"}

# Readiness — can the API reach the database?
curl http://localhost:8000/ready
# {"status":"ready","db":"ok"}
```

If `/ready` returns 503, the API started but cannot connect to the database. Check:

```bash
docker compose ps db            # is it healthy?
docker compose logs db          # any startup errors?
```

---

## Status Check

See all running containers and their ports at a glance:

```bash
docker compose --profile observability ps
```

Example output:

```
NAME                                 STATUS            PORTS
task-manager-api-1                   Up 3 minutes      0.0.0.0:8000->8000/tcp
task-manager-db-1                    Up 3 minutes      0.0.0.0:5432->5432/tcp
task-manager-frontend-1              Up 3 minutes      0.0.0.0:5173->5173/tcp
task-manager-blackbox-exporter-1     Up 26 seconds     0.0.0.0:9115->9115/tcp
task-manager-grafana-1               Up 26 seconds     0.0.0.0:3000->3000/tcp
task-manager-jaeger-1                Up 26 seconds     0.0.0.0:4317->4317/tcp, 0.0.0.0:16686->16686/tcp
task-manager-prometheus-1            Up 26 seconds     0.0.0.0:9090->9090/tcp
```

---

## Common Problems

### Port already in use

```bash
# Find what's holding port 8000
lsof -nP -i :8000

# Kill it (replace PID)
kill -9 <PID>
```

### API not picking up code changes

The API uses `uvicorn --reload`. Check that the reload worker is running:

```bash
docker compose logs api | tail -5
# Should see: "Detected change ... reloading"
```

If reload is stuck, restart the container:

```bash
docker compose restart api
```

### `docker` resolves to the wrong binary (macOS)

See [macOS — fix the `docker` PATH](#macos--fix-the-docker-path) at the top of this guide. The symptom is an error like:

```
instance "htx-edge1" does not exist
exec failed: The following errors occurred:
```

### Grafana shows "No data"

1. Confirm Prometheus is scraping the API: open http://localhost:9090/targets — `api:8000/metrics` should show **UP**.
2. Generate some traffic first: `curl http://localhost:8000/health` a few times.
3. In Grafana, check the time range in the top-right — widen it to **Last 15 minutes**.
4. If `OTEL_ENABLED` is `"false"` in `docker-compose.yml`, the `/metrics` endpoint is not mounted. Set it to `"true"` and recreate the API container.

### Database connection refused

The API waits for a `healthy` db before starting (see `depends_on` in `docker-compose.yml`). If the db takes longer than usual:

```bash
docker compose logs db | tail -20
docker compose restart db
```

### API returns 429 Too Many Requests on `/auth/login`

The rate limiter allows 10 requests per 60-second window per IP address. During development, running scripts or curl loops can exhaust the window.

**Wait 60 seconds**, or restart the API container to reset the in-memory bucket:

```bash
docker compose restart api
```

> **Why restart works:** The rate-limit bucket is stored in process memory. A container restart starts a fresh process with an empty bucket.

### Unit tests return 429 after ~10 login calls

All ASGI test requests share the client IP `"unknown"` (no real TCP socket in the test transport). After ~10 login calls across tests, the shared bucket fills and subsequent tests get 429 instead of the expected 200/401.

Fix: add an `autouse` fixture in `backend/tests/conftest.py` that calls `reset_for_testing()` from `app.middleware.rate_limit` before each test:

```python
from app.middleware.rate_limit import reset_for_testing

@pytest.fixture(autouse=True)
def clear_rate_limit_buckets():
    reset_for_testing()
```

### Revoked tokens work again after API restart

The JTI (JWT ID) revocation set is stored in process memory (`_revoked_jtis` in `auth_service.py`). When the API container restarts, the set is cleared — any tokens that were revoked via `POST /auth/logout` become valid again until their natural expiry time.

**In development:** this is acceptable. Log back in to get a fresh token.

**In production:** deploy Redis and replace the in-memory set with a Redis-backed store with TTL equal to the token lifetime. See `docs/adr/0003-security-controls.md` for the architectural trade-off.

### `DatabaseUnreachable` Grafana alert never fires

This alert depends on the **Blackbox Exporter** probing `http://api:8000/ready` and exposing the result as `probe_success{job="readiness"}`. If the Blackbox Exporter is not running, Prometheus has no data for this metric and the alert stays in `Normal` state regardless of DB health.

**Fix:** start the full observability profile:

```bash
docker compose --profile observability up -d
```

Verify the exporter is running and the probe succeeds:

```bash
curl "http://localhost:9115/probe?target=http://localhost:8000/ready&module=http_2xx"
# Should return probe_success 1 when the DB is healthy
```

### k6 spike or load test exits code 100 during setup

k6's default `setupTimeout` is 60 seconds. The token pool pattern pre-creates 10 users with a 7-second sleep between logins (to stay within the 10 req/60 s rate limit) — that takes 63 seconds and exceeds the default.

Both `load.js` and `spike.js` already include `setupTimeout: "120s"` in their `options` object to account for this. If you see a code 100 exit, verify the option is present:

```javascript
export const options = {
  setupTimeout: "120s",   // 10 users × 7 s = 70 s; 50 s headroom
  // ... rest of options
};
```

If the option is present and you still see a timeout, the rate limiter may have been pre-filled by a previous run. Restart the API to clear it (`docker compose restart api`) and re-run.

---

## Full Reset

Wipes all containers, volumes, and locally-built images:

```bash
docker compose --profile observability down -v --rmi local
docker compose --profile observability up -d --build
```

---

## Incident Runbooks

Quick reference for the most common operational failures. For full disaster-recovery procedures (backup, restore, GDPR purge, post-mortem template) see [`docs/runbooks/disaster-recovery.md`](runbooks/disaster-recovery.md).

### API not starting / crash-loop

```bash
docker compose logs --tail=50 api | grep -E "ERROR|exception|Traceback"
```

Common causes:
- **Missing `SECRET_KEY`** — ensure `.env` has `SECRET_KEY=<value>` and is sourced
- **DB not ready** — API respects `depends_on: db: condition: service_healthy`; if DB is slow, run `docker compose up -d db` first and wait for the healthy check
- **Port conflict** — `lsof -i :8000`; kill the occupying process

```bash
docker compose restart api
curl -sf http://localhost:8000/health && echo "recovered"
```

### Database unreachable (`/ready` returns 503)

```bash
docker compose ps db                                       # is it running?
docker compose exec db pg_isready -U taskuser -d taskmanager
docker compose logs --tail=20 db
```

If the container is stopped:
```bash
docker compose up -d db
docker compose restart api   # force API to reconnect
```

### Alembic migration failed during deploy

```bash
# Check current revision
docker compose exec api alembic current

# See what failed
docker compose logs api | grep -i alembic

# Roll back one revision and diagnose
docker compose exec api alembic downgrade -1
# Fix the migration file, then re-apply
docker compose exec api alembic upgrade head
```

Note: the API container mounts `./backend:/app` in development mode, so `alembic` commands run directly against your local files.

### Rate limiter blocking E2E / smoke tests

The pen test fires 20 rapid login attempts. If tests run immediately after, the in-memory rate-limit bucket may be pre-filled:

```bash
docker compose restart api   # clears the in-memory bucket
```

Then re-run the affected tests.

### Observability stack not showing data

If Prometheus is up but graphs are empty:

```bash
# Confirm API metrics endpoint is reachable from Prometheus
docker compose exec prometheus wget -qO- http://api:8000/metrics/ | head -5

# Check Prometheus targets
curl -s http://localhost:9090/api/v1/targets | python3 -m json.tool | grep -A3 '"health"'
```

If Jaeger shows no traces:

```bash
# Confirm OTLP endpoint is reachable from the API
docker compose logs api | grep -i "otlp\|jaeger\|telemetry"
```

The API logs `telemetry_configured` on startup if OTel is enabled, or `Failed to export` warnings if Jaeger is unreachable (the API continues — traces are dropped, not buffered).

### High latency or error rate alert firing

1. Check Jaeger for slow traces: http://localhost:16686 → select `task-manager-api`
2. Identify the slow span — look for SQLAlchemy child spans > 300 ms
3. Check DB connection pool: `GET /metrics/` → `db_client_connections_usage_connections`
4. Restart the API to reset the connection pool if exhausted:

```bash
docker compose restart api
```

### Security header missing from responses

```bash
curl -sI http://localhost:8000/health | grep -icE \
  "x-frame-options|x-content-type-options|x-xss-protection|strict-transport-security|referrer-policy|content-security-policy|cache-control|permissions-policy"
# → should output 8
```

All 8 security headers should appear: `X-Frame-Options`, `X-Content-Type-Options`, `X-XSS-Protection`, `Strict-Transport-Security`, `Referrer-Policy`, `Content-Security-Policy`, `Cache-Control`, `Permissions-Policy`. If the count is less than 8, `SecurityHeadersMiddleware` may not be registered or may be missing a header. Check `backend/app/main.py` middleware stack order and `backend/app/middleware/security_headers.py`.
