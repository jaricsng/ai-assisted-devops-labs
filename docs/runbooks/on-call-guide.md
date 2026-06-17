# On-Call Guide — Task Manager

**Rotation:** Weekly, starting Monday 09:00 local time  
**Escalation path:** On-call engineer → Team lead → Platform team  
**SLOs:** p95 latency < 500 ms, error rate < 1%, availability > 99.5%

---

## Quick Links

| Resource | URL |
|----------|-----|
| Grafana dashboards | http://localhost:3000 (admin/admin) |
| Jaeger traces | http://localhost:16686 |
| Prometheus | http://localhost:9090 |
| API health | http://localhost:8000/health |
| API readiness | http://localhost:8000/ready |
| Aspire dashboard | https://localhost:15888 |

---

## First 5 Minutes Checklist

When paged, run through this checklist in order:

```bash
# 1. Is the API process alive?
curl -s http://localhost:8000/health | python3 -m json.tool

# 2. Is the database reachable?
curl -s http://localhost:8000/ready | python3 -m json.tool

# 3. Recent errors (last 10 min)
docker compose logs api --since 10m | grep -E '"status_code": [45]' | tail -20

# 4. Current error rate (Prometheus query)
# rate(http_server_requests_total{status=~"5.."}[5m]) / rate(http_server_requests_total[5m])

# 5. p95 latency (Prometheus query)
# histogram_quantile(0.95, rate(http_server_request_duration_seconds_bucket[5m])) * 1000
```

---

## Alert → Runbook Mapping

| Alert | Severity | Runbook |
|-------|----------|---------|
| `DatabaseUnreachable` | P1 Critical | [runbook-database-unreachable.md](runbook-database-unreachable.md) |
| `HighErrorRate` / `ErrorBudgetBurnRateCritical` | P1 Critical | [../operations/runbook-high-error-rate.md](../operations/runbook-high-error-rate.md) |
| `HighLatency` | P2 Warning | Investigate Jaeger traces; check DB query times |
| `HighRejectionRate` | P3 Warning | [runbook-high-rejection-rate.md](runbook-high-rejection-rate.md) |
| API unresponsive | P1 | [runbook-high-error-rate.md](runbook-high-error-rate.md) §2 |
| Need to restore from backup | — | [disaster-recovery.md](disaster-recovery.md) |

---

## Safe Restart Procedure

```bash
# Restart API only (no data loss)
docker compose restart api

# Full stack restart (no data loss — DB volume persists)
docker compose down && docker compose up -d

# Full reset including DB (DATA LOSS — use only in dev/test)
docker compose down -v && docker compose up -d
```

---

## Escalation Thresholds

| Condition | Action |
|-----------|--------|
| Error rate > 5% for > 5 min | Page team lead |
| DB unreachable > 10 min | Page team lead + platform team |
| p95 latency > 2 s for > 10 min | Page team lead |
| Security incident suspected | Page security team immediately |

---

## After Every Incident

1. Open a post-mortem from [`docs/post-mortems/template.md`](../post-mortems/template.md)
2. File a tracking ticket for the root cause fix
3. Update the relevant runbook if a step was missing or wrong
4. Add a monitoring alert if the issue would have been caught sooner with one
5. Calculate SLO impact (see each runbook for formula) and post to the team channel

---

## Handoff Between On-Call Engineers

When handing off a shift or an in-progress incident:

1. Write a brief handoff note with: current state, what was tried, what is still open
2. Post it in `#incidents` mentioning the incoming engineer
3. Confirm the incoming engineer has seen it before stepping away

---

## Common Pitfalls

- **Pen test rate limit bleed-through**: If E2E tests fail with 429 after a pen test, restart the API (`docker compose restart api`) to clear the in-memory rate-limit bucket. See CLAUDE.md.
- **OTel metric name changes**: Alerts use `http_server_duration_milliseconds` — not `http_requests_total`. If an alert stops firing unexpectedly, verify the metric name hasn't changed between SDK versions.
- **Alert flapping**: If an alert fires and clears rapidly, check the `for:` clause in the alert rule — it may be too short for intermittent failures. Increase the evaluation window before investigating root cause.
- **SECRET_KEY rotation invalidates all tokens**: If 401s spike after a deploy, check whether `SECRET_KEY` was rotated. All existing sessions are invalidated — inform users to re-login. This is expected behaviour, not a bug.
