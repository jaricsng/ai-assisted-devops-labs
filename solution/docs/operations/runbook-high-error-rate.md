# Runbook — ErrorBudgetBurnRateCritical

**Alert:** ErrorBudgetBurnRateCritical  
**Severity:** Critical  
**SLO:** 99% of requests succeed over 30 days  
**Trigger:** Burn rate > 14.4× for 2 minutes (budget exhaustion in < 2 hours)

---

## Immediate triage (< 5 minutes)

1. **Check service health**
   ```bash
   curl -s http://localhost:8000/health   # or your production URL
   curl -s http://localhost:8000/ready
   ```
   If either returns non-200: the service is down. Skip to **Escalation**.

2. **Identify which endpoints are failing**

   In Prometheus (http://localhost:9090):
   ```promql
   sum by (http_route, http_status_code) (
     rate(http_server_duration_milliseconds_count{http_status_code=~"5.."}[5m])
   )
   ```
   Sort by rate descending. Note the endpoint and status code.

3. **Check recent deployments**

   In GitHub: Actions → Workflow runs. Did a deployment complete in the last 30 minutes?  
   If yes: this is likely a deployment regression — see **Rollback**.

4. **Inspect error traces in Jaeger**

   Open Jaeger at http://localhost:16686. Filter by service `task-manager-api`, tag
   `error=true`. Open the slowest/most recent failing trace. Look at the span where
   the error originates — is it in the application code or in the database span?

---

## If error originates in database

- Check database connectivity:
  ```bash
  docker compose exec db psql -U taskuser -c '\l'
  docker compose exec db pg_isready -U taskuser -d taskmanager
  ```
- Check connection pool exhaustion in API logs:
  ```bash
  docker compose logs api --since=10m | grep -i "error\|exception\|pool"
  ```
- If pool exhausted: check for long-running queries:
  ```bash
  docker compose exec db psql -U taskuser -d taskmanager \
    -c "SELECT pid, now() - query_start AS duration, query, state FROM pg_stat_activity WHERE state != 'idle' ORDER BY duration DESC;"
  ```
- Restart API to flush stale pool connections:
  ```bash
  docker compose restart api
  ```

---

## If error originates in application code

- Read the full stack trace from the structured log:
  ```bash
  docker compose logs api --since=10m | python3 -c "
  import sys, json
  for line in sys.stdin:
      try:
          d = json.loads(line)
          if d.get('level') == 'error':
              print(json.dumps(d, indent=2))
      except Exception:
          pass
  "
  ```
- Identify the code path from the stack trace
- If a recent deployment introduced the regression: **Rollback**

---

## Rollback

```bash
# Fly.io
flyctl releases rollback --app task-manager-api

# Verify the rollback restored health
curl -s https://task-manager-api.fly.dev/health
```

After rollback: verify the burn rate drops below 1.0 in Prometheus within 5 minutes:
```promql
job:http_error_ratio:rate5m
```

---

## Escalation

If triage takes > 15 minutes without resolution, escalate to the team lead and open
a severity-1 incident in your incident management tool with:
- Alert name and trigger time
- Current burn rate and estimated time to budget exhaustion
- Steps already taken
- Hypothesis for root cause

---

## Post-incident

After resolution, write a blameless post-mortem in `docs/post-mortems/YYYY-MM-DD-<title>.md`:
- Timeline of events
- Root cause (the systemic condition, not the person)
- Contributing factors
- Action items with owners and due dates

Calculate the error budget consumed:
```
minutes_of_503s × (1 / (30 × 24 × 60)) = fraction of monthly budget consumed
```

---

## Recording rules reference

These are the pre-computed SLI time series loaded into Prometheus:

| Rule | PromQL | Alert threshold |
|------|--------|----------------|
| `job:http_error_ratio:rate5m` | 5-minute error ratio | > 0.01 (1%) |
| `job:http_p95_latency_ms:rate5m` | P95 latency in ms | > 500 |
| Burn rate (14.4×) | `job:http_error_ratio:rate5m / 0.01` | > 14.4 |
