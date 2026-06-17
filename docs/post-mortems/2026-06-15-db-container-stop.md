# Post-Mortem: Database Container Stopped During Load Test

| Field | Value |
|-------|-------|
| **Date** | 2026-06-15 |
| **Duration** | ~5 minutes |
| **Severity** | P1 (lab environment) |
| **Impact** | All write operations failed; readiness probe returned 503 |
| **Root cause** | PostgreSQL container stopped unexpectedly while k6 load test was running |
| **Author** | Lab session |
| **Reviewers** | — |

---

## Timeline

| Time | Event |
|------|-------|
| T+0:00 | k6 load test (`load.js`) started with 50 VUs |
| T+1:30 | PostgreSQL container stopped (reason: resource contention or manual stop) |
| T+1:31 | `/ready` probe began returning 503; `readiness_check_failed` logged |
| T+1:32 | k6 began recording HTTP 500 errors for task create/update endpoints |
| T+2:00 | `docker compose start db` executed |
| T+2:15 | DB container reached healthy state |
| T+2:20 | `docker compose restart api` executed to reset connection pool |
| T+2:35 | `/ready` returned 200; load test traffic recovered |
| T+6:00 | Load test completed; all thresholds within calibrated bounds |

---

## Impact

- **Users affected:** 50 virtual users (k6 load test only — lab environment)
- **Requests failed:** ~180 (estimated from k6 error count during outage window)
- **Data loss:** None — PostgreSQL WAL ensures committed transactions are durable
- **SLO breach:** Yes — error rate exceeded 1% threshold during the 90-second outage

---

## Root Cause

The PostgreSQL Docker container stopped unexpectedly while the API was under load. The `asyncpg` connection pool had open connections to the DB that were not released, causing all subsequent DB operations to fail with `OperationalError`. The `/ready` endpoint correctly detected the failure and returned 503. The API did not automatically reconnect after the DB came back up until `docker compose restart api` was run.

---

## Contributing Factors

1. **No automatic API reconnection:** `asyncpg` pool does not automatically re-establish connections after a total DB outage without a pool recycle — the API required a manual restart.
2. **No persistent alert:** The lab environment had no automated pager that would have fired within 60 seconds of `/ready` returning 503.
3. **Single DB instance:** No replica or standby to fail over to.

---

## Detection

Detected manually by observing k6 error output during the load test run. The `/ready` endpoint returned 503 (as designed), but no alert was configured to page on this condition.

---

## Resolution

1. `docker compose start db` — restarted the PostgreSQL container
2. Waited for `(healthy)` status in `docker compose ps`
3. `docker compose restart api` — forced asyncpg pool to reconnect

---

## Action Items

| # | Action | Owner | Due date | Priority |
|---|--------|-------|----------|----------|
| 1 | Configure Prometheus alert on `/ready` returning 503 for > 60 s | Platform | 2026-06-30 | P1 |
| 2 | Evaluate `asyncpg` pool `pool_recycle` or health-check parameter to auto-reconnect | Backend | 2026-06-30 | P2 |
| 3 | Document restart procedure in `runbook-database-unreachable.md` §2 | On-call | Done | P3 |

---

## Lessons Learned

**What went well:** The `/ready` probe correctly surfaced the DB failure with the expected `{"status": "not ready", "db": "unreachable"}` response. The recovery procedure was straightforward and documented.

**What could be improved:** An automated alert on sustained `/ready` 503 responses would have cut detection time from 90 seconds to under 60 seconds.

**Surprise:** The API required a manual restart after DB recovery — asyncpg does not automatically drain and refill the connection pool after a full outage. This should be handled by adding a `pool_recycle` interval.

---

## References

- Readiness probe implementation: `backend/app/main.py::ready()`
- Recovery runbook: `docs/runbooks/runbook-database-unreachable.md`
- k6 load test: `load-tests/k6/load.js`
