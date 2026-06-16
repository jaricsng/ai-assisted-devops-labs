# Runbook — DatabaseUnreachable

**Alert:** DatabaseUnreachable  
**Severity:** Critical (P1)  
**SLO impact:** Service fully unavailable — readiness probe failing  
**Trigger:** `probe_success{job="readiness"} == 0` for 1 minute

---

## Triage (< 5 minutes)

**Goal: determine whether the DB container is down, overloaded, or unreachable from the API.**

1. Check API health:
   ```bash
   curl -sf http://localhost:8000/health && echo "API process: UP" || echo "API process: DOWN"
   curl -sf http://localhost:8000/ready && echo "DB: REACHABLE" || echo "DB: UNREACHABLE"
   ```

2. Check DB container:
   ```bash
   docker compose ps db
   docker compose logs --tail=20 db
   ```

3. Test direct DB connectivity (bypasses the API):
   ```bash
   docker compose exec db pg_isready -U taskuser -d taskmanager
   ```

4. Check API logs for the exact error:
   ```bash
   docker compose logs --tail=30 api | grep -i "error\|exception\|db\|postgres"
   ```

---

## Remediation

### If DB container is stopped:
```bash
docker compose up -d db
# Wait for healthy
docker compose exec db pg_isready -U taskuser -d taskmanager
docker compose restart api
```

### If DB is up but API can't connect (pool exhaustion):
```bash
# Check connection count
docker compose exec db psql -U taskuser -d taskmanager \
  -c "SELECT count(*), state FROM pg_stat_activity GROUP BY state;"
# Restart API to flush stale pool connections
docker compose restart api
```

### If DB disk is full:
```bash
docker compose exec db psql -U taskuser -d taskmanager \
  -c "SELECT pg_size_pretty(pg_database_size('taskmanager'));"
# Free space or expand volume before restarting
```

### If schema migration is blocking (lock contention):
```bash
docker compose exec db psql -U taskuser -d taskmanager \
  -c "SELECT pid, query, state, wait_event_type, wait_event FROM pg_stat_activity WHERE wait_event IS NOT NULL;"
# Terminate blocking query if safe:
# SELECT pg_terminate_backend(<pid>);
```

---

## Verify resolution
```bash
curl -sf http://localhost:8000/ready && echo "RESOLVED"
# Monitor the Prometheus DatabaseUnreachable alert — it should leave 'firing' within 2 minutes
```

After the alert clears, watch the readiness probe for 5 minutes to confirm stability before
marking the incident as resolved.

---

## Escalation

If not resolved in 15 minutes:
1. Post to `#incidents`: alert name, time firing, steps taken, current hypothesis
2. Escalate to the DB team / infrastructure owner
3. Check if a deploy preceded the alert (GitHub Actions → recent runs)

---

## Post-incident

See post-mortem template in `docs/runbooks/disaster-recovery.md` §7.  
SLO impact: calculate minutes of `probe_success == 0` × (1 / total_minutes_in_month) for the availability SLO.

Example: 8 minutes down in a 30-day month = 8 / 43200 ≈ 0.018% of the monthly error budget consumed.
