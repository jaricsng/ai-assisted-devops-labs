# Disaster Recovery Runbook

**Service:** Task Manager API  
**Last reviewed:** 2026-06-15  
**Owner:** Platform / DevOps team  

---

## Recovery Targets

| Target | Value | Rationale |
|--------|-------|-----------|
| **RTO** (Recovery Time Objective) | 1 hour | Time to restore service to a functional state |
| **RPO** (Recovery Point Objective) | 24 hours | Maximum acceptable data loss (daily backup cadence) |

Tighten these targets by enabling continuous WAL archiving (see §5) once a managed DB service is in use.

---

## 1. Severity Classification

| Severity | Description | Example |
|----------|-------------|---------|
| **P1 — Critical** | Full service outage; no requests served | DB unreachable, API crash-loop |
| **P2 — High** | Partial degradation; core features unavailable | Login broken, all task writes failing |
| **P3 — Medium** | Single feature broken; workaround available | Comments unavailable, slow queries |
| **P4 — Low** | Cosmetic or non-blocking | Stale cache, minor UI glitch |

---

## 2. Health Checks

```bash
# Liveness — API process up
curl -sf http://localhost:8000/health && echo "OK" || echo "DOWN"

# Readiness — API can reach DB
curl -sf http://localhost:8000/ready && echo "DB OK" || echo "DB UNREACHABLE"

# Check container status
docker compose ps

# Tail recent API logs (last 50 lines)
docker compose logs --tail=50 api
```

---

## 3. Incident Response

### Step 1 — Detect

Grafana alert or manual check:

```bash
curl -sf http://localhost:8000/ready
# HTTP 503 → DB unreachable
# Connection refused → API process down
# HTTP 200 → service healthy
```

### Step 2 — Communicate

1. Post to the team incident channel: `#incidents`
2. Include: what is broken, when it started, who is investigating
3. Update every 15 minutes until resolved

### Step 3 — Diagnose

```bash
# API container logs
docker compose logs --tail=100 api 2>&1 | grep -E "ERROR|CRITICAL|exception"

# DB connection test
docker compose exec db psql -U taskuser -d taskmanager -c "SELECT 1"

# DB disk usage
docker compose exec db psql -U taskuser -d taskmanager -c "\l+"

# Check alembic_version (confirms migrations ran)
docker compose exec db psql -U taskuser -d taskmanager \
  -c "SELECT version_num FROM alembic_version;"
```

### Step 4 — Remediate (by cause)

#### API crash-loop

```bash
docker compose restart api
# If still crashing after 2 restarts, check logs for root cause before continuing
docker compose logs api | tail -50
```

#### DB unreachable (container down)

```bash
docker compose up -d db
# Wait for healthy
docker compose exec db pg_isready -U taskuser -d taskmanager
# Restart API once DB is healthy
docker compose restart api
```

#### DB disk full

```bash
# Check disk usage
df -h $(docker volume inspect task-manager_postgres_data --format '{{.Mountpoint}}')
# Free space — see §4 for PITR restore if data is corrupt
docker compose exec db psql -U taskuser -d taskmanager \
  -c "SELECT pg_size_pretty(pg_database_size('taskmanager'));"
```

#### Bad deploy (API regression after upgrade)

```bash
# Roll back to the previous image
docker compose pull api   # pull if using remote image
# OR restart from the last known-good tag:
# docker compose stop api
# docker run ... ghcr.io/org/task-manager-api:sha-<prev-commit> ...

# Roll back schema if a migration caused the regression
docker compose exec api alembic downgrade -1
```

### Step 5 — Verify recovery

```bash
curl -sf http://localhost:8000/health && echo "Liveness OK"
curl -sf http://localhost:8000/ready  && echo "Readiness OK"
# Smoke test: register + login
TOKEN=$(curl -s -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=<test-user>&password=<test-pass>" | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
curl -sf -H "Authorization: Bearer $TOKEN" http://localhost:8000/projects && echo "Projects OK"
```

### Step 6 — Post-mortem

Within 48 hours of a P1/P2 incident, file a post-mortem using the template in §7.

---

## 4. Backup and Restore

### 4a. Manual backup (local / Docker Compose)

```bash
# Dump to a timestamped file
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
docker compose exec db pg_dump \
  -U taskuser \
  -d taskmanager \
  --format=custom \
  --file=/tmp/taskmanager-${TIMESTAMP}.dump

# Copy dump out of the container
docker cp task-manager-db-1:/tmp/taskmanager-${TIMESTAMP}.dump \
  ./backups/taskmanager-${TIMESTAMP}.dump
```

### 4b. Restore from a dump

```bash
# Stop the API first to prevent writes during restore
docker compose stop api

# Drop and recreate the database
docker compose exec db psql -U taskuser -d postgres \
  -c "DROP DATABASE IF EXISTS taskmanager; CREATE DATABASE taskmanager OWNER taskuser;"

# Restore
docker compose exec db pg_restore \
  -U taskuser \
  -d taskmanager \
  /tmp/taskmanager-<TIMESTAMP>.dump

# Re-run migrations to ensure schema is current
docker run --rm \
  --network task-manager_default \
  -e DATABASE_URL="postgresql+asyncpg://taskuser:taskpass@db:5432/taskmanager" \
  -e SECRET_KEY="${SECRET_KEY}" \
  -e ENVIRONMENT=production \
  -e OTEL_ENABLED=false \
  -v "$(pwd)/backend:/app" \
  -w /app \
  python:3.12-slim \
  bash -c "pip install -e '.' -q && alembic upgrade head"

# Restart API
docker compose start api
```

### 4c. Cloud-managed backups (production)

| Platform | Feature | Retention | PITR |
|----------|---------|-----------|------|
| **Fly.io + Supabase** | Automated daily snapshots | 7 days | Yes (WAL) |
| **Azure Database for PostgreSQL** | Automated backups | 7–35 days | Yes (WAL, 5-min granularity) |
| **AWS RDS for PostgreSQL** | Automated backups | 1–35 days | Yes (WAL, 5-min granularity) |
| **GCP Cloud SQL** | Automated backups | 7 days | Yes (WAL) |

For production deployments, enable automated backups and point-in-time recovery on the managed DB service. The `DATABASE_URL` must include `?sslmode=require` for all cloud deployments.

### 4d. Scheduled backup (cron example)

```bash
# Add to server crontab for daily 02:00 backup + S3 upload
0 2 * * * /opt/scripts/backup-taskmanager.sh >> /var/log/taskmanager-backup.log 2>&1
```

`/opt/scripts/backup-taskmanager.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
DUMP_FILE="/tmp/taskmanager-${TIMESTAMP}.dump"
pg_dump "$DATABASE_URL" --format=custom --file="$DUMP_FILE"
# Upload to object storage (example: AWS S3)
aws s3 cp "$DUMP_FILE" "s3://${BACKUP_BUCKET}/postgres/${TIMESTAMP}.dump"
rm "$DUMP_FILE"
# Prune local copies older than 7 days
find /tmp -name "taskmanager-*.dump" -mtime +7 -delete
```

---

## 5. Schema Migrations

All schema changes use Alembic. The migration history is in `backend/alembic/versions/`.

```bash
# Show current revision
alembic current

# Show migration history
alembic history --verbose

# Apply all pending migrations
alembic upgrade head

# Roll back one revision
alembic downgrade -1

# Roll back to a specific revision
alembic downgrade 001
```

**Production convention:** Migrations run automatically before traffic switches in all deploy targets:
- **Fly.io:** `release_command = "alembic upgrade head"` in `fly.toml`
- **Azure Container Apps:** `postdeploy` hook in `azure.yaml`
- **AWS ECS / GCP Cloud Run:** Run as a one-off container before updating the service

**Backward-incompatible migrations** (e.g., dropping a column still used by the previous version) require the expand/contract pattern:
1. Deploy migration that adds the new column (expand)
2. Deploy application code using the new column
3. Deploy migration that removes the old column (contract)

---

## 5b. Secret Rotation

Rotating `SECRET_KEY` or the PostgreSQL password without downtime requires care:

- **`SECRET_KEY` (JWT signing key):** Use a dual-key window — deploy the API accepting both old and new key simultaneously, wait for all old tokens to expire (default TTL = 30 min), then remove the old key. See [`docs/runbooks/runbook-secret-rotation.md`](runbook-secret-rotation.md) §2 for the full procedure.
- **PostgreSQL password:** `ALTER USER taskuser PASSWORD '...'` → update `DATABASE_URL` in secret store → redeploy API → verify `/ready` returns 200.
- **Emergency rotation** (suspected leak): skip the dual-key window; accept user disruption; restart API immediately to clear the in-memory JTI revocation set.

**Rotation schedule:** `SECRET_KEY` quarterly; `DATABASE_URL` annually; immediately after any suspected credential exposure or engineer offboarding.

---

## 6. Data Retention and GDPR

- Soft deletes: `deleted_at` is set on all domain tables — records are invisible to the API but retained in the DB
- **GDPR erasure requests:** `DELETE /auth/users/me` soft-deletes the user; a hard purge must be scheduled after the 90-day legal hold window:

```sql
-- Purge GDPR-erased users after 90-day hold (run as a scheduled job)
DELETE FROM users WHERE deleted_at < NOW() - INTERVAL '90 days';
```

- Run this as a scheduled job (cron, Cloud Scheduler, EventBridge) in production — not in application code

---

## 7. Post-Mortem Template

```markdown
# Post-Mortem: [Brief title] — [Date]

## Summary
One-paragraph description of what happened and the impact.

## Timeline (UTC)
- HH:MM — Alert fired / incident detected
- HH:MM — Investigation started
- HH:MM — Root cause identified
- HH:MM — Mitigation applied
- HH:MM — Service restored
- HH:MM — Incident closed

## Root Cause
What caused the failure?

## Impact
- Duration: X minutes
- Users affected: estimated N
- Requests lost / errored: N

## What Went Well
- …

## What Went Wrong
- …

## Action Items
| Action | Owner | Due |
|--------|-------|-----|
| … | … | … |
```

---

## 8. Escalation

| Severity | Initial responder | Escalate to | Escalate after |
|----------|-------------------|-------------|----------------|
| P1 | On-call engineer | Engineering lead | 15 min |
| P2 | On-call engineer | Engineering lead | 30 min |
| P3 | Team channel | On-call engineer | Next business day |
| P4 | Team channel | — | Next sprint |
