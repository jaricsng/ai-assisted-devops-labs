# Post-Mortem: Database Container Stopped — 2026-06-15

**Severity:** P1  
**Duration:** ~8 minutes  
**Impact:** Full service outage — all API requests returning 503 for the duration  
**Author:** Lab Student  
**Status:** Resolved / Action items open

---

## Timeline (UTC)

| Time | Event |
|------|-------|
| 14:02 | `docker compose stop db` issued as part of Module 18 incident simulation |
| 14:02 | `/ready` first returned 503 (`{"detail":"Database unavailable"}`) |
| 14:03 | `DatabaseUnreachable` alert entered `firing` state in Prometheus (1-minute `for:` clause elapsed) |
| 14:03 | Grafana Alerting panel turned red; on-call engineer noticed alert |
| 14:04 | Opened `runbook-database-unreachable.md` |
| 14:05 | Ran `curl -sf http://localhost:8000/health` → 200 (API process alive) |
| 14:05 | Ran `curl -sf http://localhost:8000/ready` → 503 (DB unreachable) |
| 14:06 | Ran `docker compose ps db` → confirmed container `Exited (0)` |
| 14:06 | Ran `docker compose up -d db` → container started |
| 14:07 | Ran `docker compose exec db pg_isready` → `accepting connections` |
| 14:07 | Ran `docker compose restart api` → API restarted |
| 14:08 | Ran `curl -sf http://localhost:8000/ready` → 200 (DB reachable) |
| 14:10 | `DatabaseUnreachable` alert left `firing` state (2 minutes after service restored) |

---

## Root Cause

The PostgreSQL container was stopped manually as part of a controlled incident simulation
(`docker compose stop db`). In production, the equivalent scenario would be an OOM-killed
DB container, a failed volume mount, or an unintended `docker stop` during maintenance.

The **systemic condition** that caused the outage: the API has no connection retry logic
outside of SQLAlchemy's pool. When the DB becomes unavailable, all in-flight and new
requests fail immediately with a 503. There is no circuit-breaker or graceful degradation.

---

## Contributing Factors

1. **Connection pool holds stale connections**: After the DB restarted, the API's connection
   pool contained stale connections from before the outage. These needed to be recycled before
   requests could succeed. The `pool_pre_ping=True` setting in the engine config mitigates this
   by testing connections before use, but there is still a brief period of 503s after DB restart.

2. **1-minute alert `for:` clause**: The `DatabaseUnreachable` alert requires the probe to fail
   for 1 minute before firing. This means the minimum guaranteed notification delay is 1 minute —
   plus however long it takes the on-call engineer to notice the alert.

3. **No graceful read degradation**: Read-only endpoints (task listing, project listing) could
   potentially be served from a cache during a DB outage, but the current architecture has no
   caching layer. All endpoints fail equally when the DB is unreachable.

---

## What Went Well

- The `DatabaseUnreachable` alert fired promptly after the 1-minute `for:` clause elapsed.
- The runbook steps were clear and led directly to the root cause within 3 minutes.
- `pg_isready` correctly confirmed DB health before restarting the API.
- The total time from alert firing to resolution was 5 minutes — within the P1 SLA.

---

## What Went Wrong

- The runbook did not include an explicit step to verify pool recycling after the DB restarts.
  There were ~30 seconds of sporadic 503s after the DB came back before the pool fully recycled.
- The on-call guide didn't mention that the alert takes 2 minutes to clear after service is
  restored (Prometheus evaluation interval). The on-call engineer initially thought the
  resolution hadn't worked.

---

## Action Items

| Action | Owner | Due | Status |
|--------|-------|-----|--------|
| Add pool recycling verification step to `runbook-database-unreachable.md` | Lab student | Next session | Open |
| Add note to on-call guide: "Alert takes 2min to clear after resolution" | Lab student | Next session | Open |
| Verify `pool_pre_ping=True` is set in `backend/app/database.py` engine config | Lab student | Now | Closed — already present |
| Review 1-minute `for:` clause on `DatabaseUnreachable` — consider 30s for faster notification | Lab student | Next sprint | Open |

---

## Lessons Learned

1. **Runbooks should cover the recovery window, not just the fix.** After restarting the DB,
   there is a brief period of instability. The runbook should tell the on-call engineer to wait
   and verify `/ready` returns 200 for at least 60 seconds before declaring resolution.

2. **Alert clearing delay is confusing.** New on-call engineers don't know that Prometheus needs
   one evaluation interval after a condition clears before the alert leaves `firing`. Document this
   explicitly in the on-call guide.

3. **A 5-minute simulation exposed two runbook gaps.** Real incidents will find more. Schedule
   quarterly game days to stress-test runbooks against novel failure modes before they happen in
   production.
