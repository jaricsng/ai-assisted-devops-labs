# Runbook — DatabaseUnreachable

**Alert:** DatabaseUnreachable  
**Service:** Task Manager API → PostgreSQL 16  
**Severity:** Critical (P1) — total service outage; all write and most read operations fail  
**SLO impact:** Service fully unavailable — readiness probe failing  
**Trigger:** `probe_success{job="readiness"} == 0` for 1 minute  
**On-call channel:** #task-manager-oncall

---

## 1. Confirm

```bash
# Check readiness probe
curl -s http://localhost:8000/ready
# Expected when DB is down: {"detail": {"status": "not ready", "db": "unreachable"}}

# Check DB container
docker compose ps db

# Test direct DB connectivity
docker compose exec db psql -U taskuser -d taskmanager -c "SELECT 1;"
```

---

## 2. DB Container Down

```bash
# Start the DB
docker compose start db

# Wait for healthy status (up to 30 s)
docker compose ps db   # look for "(healthy)"

# Restart API to clear failed connection pool
docker compose restart api

# Confirm recovery
curl -s http://localhost:8000/ready
```

---

## 3. DB Container Running but API Cannot Connect

```bash
# Check DB logs for errors (OOM, disk full, max_connections hit)
docker compose logs db --since 15m | tail -50

# Check disk
df -h $(docker inspect --format '{{range .Mounts}}{{if eq .Type "volume"}}{{.Source}}{{end}}{{end}}' task-manager-db-1)

# Check PostgreSQL max_connections / active connections
docker compose exec db psql -U taskuser -d taskmanager \
  -c "SELECT count(*), state FROM pg_stat_activity GROUP BY state;"
docker compose exec db psql -U taskuser -d taskmanager \
  -c "SELECT count(*) AS active, max_conn FROM pg_stat_activity, (SELECT setting::int AS max_conn FROM pg_settings WHERE name='max_connections') s GROUP BY max_conn;"
```

**If disk full:** Free space by removing unused Docker images/volumes (`docker system prune`). Alert if DB volume is > 80% full.

**If max_connections hit:** Temporarily increase `max_connections` in `postgresql.conf` or reduce `pool_size` in `backend/app/database.py`.

---

## 3b. Schema Migration Blocking (Lock Contention)

If the DB is running but became unreachable after a deploy:

```bash
# Check for long-running or locked queries
docker compose exec db psql -U taskuser -d taskmanager \
  -c "SELECT pid, query, state, wait_event_type, wait_event FROM pg_stat_activity WHERE wait_event IS NOT NULL;"

# Terminate a blocking query if safe (replace <pid> with actual PID)
# docker compose exec db psql -U taskuser -d taskmanager \
#   -c "SELECT pg_terminate_backend(<pid>);"
```

A stuck Alembic migration holds a table lock that blocks all API queries. Terminate the blocking session and re-run the migration after the incident clears.

---

## 4. DB Data Corruption

If the DB starts but queries fail with `ERROR: invalid page in block`:

```bash
# Stop writes immediately
docker compose stop api

# Run table checks
docker compose exec db psql -U taskuser -d taskmanager \
  -c "SELECT schemaname, tablename FROM pg_tables WHERE schemaname='public';" | \
  while read schema table _; do
    docker compose exec db psql -U taskuser -d taskmanager \
      -c "SELECT count(*) FROM \"$table\";" 2>&1 | grep -v "^$" | head -1
  done

# Restore from backup (see disaster-recovery.md §3)
```

---

## 5. Emergency Read-Only Mode

If data cannot be recovered quickly, put the API in read-only mode by restarting with a read-only replica `DATABASE_URL` pointing to a standby (if provisioned):

```bash
DATABASE_URL="postgresql+asyncpg://taskuser:taskpass@replica-host:5432/taskmanager" \
  docker compose up -d api
```

Write endpoints will return 500 (DB error); read endpoints remain functional.

---

## 6. Verify Resolution

```bash
curl -sf http://localhost:8000/ready && echo "RESOLVED"
# Monitor the Prometheus DatabaseUnreachable alert — it should leave 'firing' within 2 minutes
```

After the alert clears, watch the readiness probe for 5 minutes to confirm stability before marking the incident as resolved.

---

## 7. Post-Incident

- Create post-mortem using [`docs/post-mortems/template.md`](../post-mortems/template.md)
- Validate that daily backup job ran successfully before the incident
- Review connection pool settings if max_connections was hit
- Calculate SLO impact: `minutes_of_503s × (1 / (30 × 24 × 60))` = fraction of monthly availability budget consumed
