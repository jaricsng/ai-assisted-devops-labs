# On-Call Guide — Task Manager

## Who is on call?

For this lab: you. In a production team, on-call is assigned via a rotation in an incident
management tool (PagerDuty, OpsGenie, Grafana OnCall). New engineers join the rotation after
shadowing two on-call shifts.

## How to know an alert fired

Grafana can send alerts via email, Slack, PagerDuty, or webhook. For local dev:

- Grafana UI: http://localhost:3000 → Alerting → Alert rules (shows firing state)
- Prometheus UI: http://localhost:9090/alerts
- API logs: `docker compose logs -f api | grep '"level":"error"'`

## First 5 minutes checklist

- [ ] Open Grafana — which alert is firing, for how long?
- [ ] Check `/health` and `/ready`:
  ```bash
  curl -sf http://localhost:8000/health && echo "API: UP" || echo "API: DOWN"
  curl -sf http://localhost:8000/ready && echo "DB: REACHABLE" || echo "DB: UNREACHABLE"
  ```
- [ ] Check recent deployments (GitHub Actions → last 10 runs)
- [ ] Open the relevant runbook from `docs/runbooks/`
- [ ] Post to `#incidents`: "Investigating [alert name] at [time]. Update in 15 minutes."

## Alert → Runbook mapping

| Alert | Severity | Runbook |
|-------|----------|---------|
| `DatabaseUnreachable` | P1 Critical | `runbook-database-unreachable.md` |
| `HighErrorRate` | P1 Critical | `../operations/runbook-high-error-rate.md` |
| `HighLatency` | P2 Warning | Investigate Jaeger traces; check DB query times |
| `HighRejectionRate` | P3 Warning | `runbook-high-rejection-rate.md` |

## Escalation contacts

| When | Who | How |
|------|-----|-----|
| P1 not resolved in 15 min | Engineering lead | Slack DM + phone |
| P1 not resolved in 30 min | CTO / VP Engineering | Phone |
| Security incident (data breach suspected) | Security team | Dedicated security Slack channel |

## After resolving

- [ ] Write a post-mortem in `docs/post-mortems/YYYY-MM-DD-<title>.md` (within 48 hours for P1/P2)
- [ ] Update the runbook with anything that wasn't in it
- [ ] Close the incident in your tracking tool
- [ ] Post resolution to `#incidents`
- [ ] Calculate SLO impact (see runbook for formula)

## Handoff between on-call engineers

When handing off a shift or an in-progress incident:

1. Write a brief handoff note with: current state, what was tried, what is still open
2. Post it in `#incidents` mentioning the incoming engineer
3. Confirm the incoming engineer has seen it before stepping away

## Common pitfalls

- **Pen test rate limit bleed-through**: If E2E tests fail with 429 after a pen test, restart the API (`docker compose restart api`). See CLAUDE.md.
- **OTel metric name changes**: Alerts use `http_server_duration_milliseconds` — not `http_requests_total`. If an alert stops firing unexpectedly, verify the metric name hasn't changed.
- **Alert flapping**: If an alert fires and clears rapidly, check the `for:` clause — it may be too short for intermittent failures.
