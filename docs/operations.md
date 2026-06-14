# Operations Guide — Task Manager

Day-to-day reference for starting, stopping, restarting, and troubleshooting the application stack.

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

## Observability Stack (Jaeger · Prometheus · Grafana)

The observability services are opt-in. They run under the `observability` Docker Compose profile.

### Start (with core stack)

```bash
docker compose --profile observability up -d
```

### Start (observability only, core already running)

```bash
docker compose --profile observability up -d jaeger prometheus grafana
```

### Stop (observability only, leave core running)

```bash
docker compose --profile observability stop jaeger prometheus grafana
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
NAME                        STATUS            PORTS
task-manager-api-1          Up 3 minutes      0.0.0.0:8000->8000/tcp
task-manager-db-1           Up 3 minutes      0.0.0.0:5432->5432/tcp
task-manager-frontend-1     Up 3 minutes      0.0.0.0:5173->5173/tcp
task-manager-grafana-1      Up 26 seconds     0.0.0.0:3000->3000/tcp
task-manager-jaeger-1       Up 26 seconds     0.0.0.0:4317->4317/tcp, 0.0.0.0:16686->16686/tcp
task-manager-prometheus-1   Up 26 seconds     0.0.0.0:9090->9090/tcp
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

---

## Full Reset

Wipes all containers, volumes, and locally-built images:

```bash
docker compose --profile observability down -v --rmi local
docker compose --profile observability up -d --build
```
