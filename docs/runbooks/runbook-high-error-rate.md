# Runbook — High Error Rate

**Alert:** `http_error_rate_5xx > 1%` for 5 minutes  
**Service:** Task Manager API (FastAPI, port 8000)  
**Severity:** P1  
**On-call channel:** #task-manager-oncall

---

## 1. Triage (< 5 minutes)

```bash
# Confirm the alert is real
curl -sf http://localhost:8000/health && echo "API process alive"
curl -sf http://localhost:8000/ready  && echo "DB reachable"

# Tail recent errors
docker compose logs api --since 10m | grep '"status_code": 5'

# Check error rate in Prometheus
# Query: rate(http_server_requests_total{status=~"5.."}[5m]) / rate(http_server_requests_total[5m])
```

**If `/health` returns non-200 → go to §2 (process crash).**  
**If `/ready` returns 503 → go to §3 (database issue).**  
**If both return 200 → go to §4 (application error).**

---

## 2. API Process Crash

```bash
# Check container state
docker compose ps api

# Restart
docker compose restart api

# Watch logs for startup errors
docker compose logs -f api --since 1m
```

Expected log on healthy start:
```json
{"event": "api_started", "environment": "production", "version": "0.1.0"}
```

If restart loop (3+ restarts in 5 min), check:
- Disk space: `df -h`
- Memory: `free -m`
- Config: missing `SECRET_KEY` or `DATABASE_URL` env vars will cause immediate crash

---

## 3. Database Issue

See [`runbook-database-unreachable.md`](runbook-database-unreachable.md).

---

## 4. Application Error Investigation

```bash
# Find error traces in structlog JSON output
docker compose logs api --since 10m | python3 -c "
import sys, json
for line in sys.stdin:
    try:
        e = json.loads(line)
        if e.get('status_code', 0) >= 500 or 'error' in e.get('event', ''):
            print(json.dumps(e, indent=2))
    except: pass
" | head -100

# Correlate with a specific request_id
docker compose logs api | grep '"request_id": "PASTE-UUID-HERE"'
```

Common root causes and fixes:

| Error pattern in logs | Likely cause | Fix |
|-----------------------|-------------|-----|
| `asyncpg.TooManyConnectionsError` | DB connection pool exhausted | Increase `pool_size` in `database.py`; check for connection leaks |
| `sqlalchemy.exc.OperationalError` | DB unreachable mid-request | Go to §3 |
| `jose.exceptions.JWTError` | Clock skew > 5 min between services | Sync NTP; check `exp` claim |
| `ValidationError` in logs | Bug in response schema | Check recent deploys; roll back if needed |
| `unhandled_error` event | Unhandled exception | Read `path` field; check that route for a recent code change |

---

## 5. Rollback

```bash
# Roll back to previous image tag
docker compose pull api:PREVIOUS_TAG
docker compose up -d api

# Verify
curl -s http://localhost:8000/health | python3 -m json.tool
```

---

## 6. Post-Incident

- Create a post-mortem within 48 hours using [`docs/post-mortems/template.md`](../post-mortems/template.md)
- File a ticket to address the root cause before closing the incident
- Update this runbook if the investigation revealed a missing step
