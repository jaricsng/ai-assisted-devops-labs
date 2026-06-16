# Module 15 — SLIs, SLOs, and Error Budgets

## Learning Objectives

- Understand the hierarchy: SLI → SLO → SLA, and the role of error budgets
- Identify the right SLIs for a REST API (availability, latency, readiness)
- Write Prometheus recording rules that materialise SLIs as queryable time series
- Encode SLO thresholds as Grafana alerting rules and visualise compliance on a dashboard
- Calculate error budget burn rate and understand why burn rate is more actionable than raw error rate
- Configure Grafana contact points and notification policies so alerts reach on-call engineers
- Write a runbook for the `HighErrorRate` alert — the operational response to a burning error budget
- Simulate an incident using the existing spike load test and follow your runbook

---

## Background

### The three-level hierarchy

| Term | Owned by | Meaning |
|------|----------|---------|
| **SLI** (Service Level Indicator) | Engineering | A measurable signal: *"4.7% of requests returned 5xx in the last 5 minutes"* |
| **SLO** (Service Level Objective) | Product + Engineering | A target for an SLI over a time window: *"99% of requests succeed over 30 days"* |
| **SLA** (Service Level Agreement) | Business + Legal | A contract with customers: *"If the SLO is missed, customers receive a credit"* |

The SLO is the engineering team's internal commitment. It must be tighter than the SLA — otherwise, by the time the SLA is threatened, there is no time to react.

### Error budget

If the SLO is 99% availability over 30 days, the **error budget** is 1% of all request-minutes — roughly 7.2 hours of downtime, or 1 in every 100 requests failing.

Error budget is a decision-making tool:

- **Budget is healthy** → ship features fast; take calculated risks
- **Budget is low** → slow down deployments; focus on reliability work
- **Budget is exhausted** → freeze non-critical deployments; all hands on reliability

### The four golden signals

Google SRE defines four signals every service should measure. Three of them directly map to SLOs:

| Signal | SLI example | SLO example |
|--------|------------|-------------|
| **Latency** | P95 request duration | < 500 ms for 95% of requests |
| **Traffic** | Requests per second | (baselines burns, not a threshold) |
| **Errors** | 5xx rate | < 1% of all requests |
| **Saturation** | CPU/memory usage | < 80% average |

This module defines SLOs for the first three.

---

## Prerequisites

The observability stack must be running:

```bash
docker compose --profile observability up -d
```

Verify Prometheus is scraping the API:

```bash
curl -s http://localhost:9090/api/v1/targets | python3 -m json.tool | grep '"health"'
# Expected: "health": "up" for the task-manager-api job
```

Verify Grafana is reachable at http://localhost:3000 (admin / admin).

---

## Activities

### 1. Discover your actual metric names

Before writing SLO queries, verify which metric names your OTel instrumentation emits. Labels and names vary between SDK versions.

```bash
# List all metric names available in Prometheus
curl -s 'http://localhost:9090/api/v1/label/__name__/values' \
  | python3 -c "import sys,json; [print(n) for n in json.load(sys.stdin)['data'] if 'http' in n or 'request' in n]"
```

You should see metrics starting with `http_server_request_duration_seconds` — the histogram emitted by OpenTelemetry's FastAPI auto-instrumentation.

```bash
# Inspect available labels on the histogram
curl -s 'http://localhost:9090/api/v1/labels' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['data'])"
```

Look for a label that carries the HTTP status code. It is typically `http_response_status_code`.

Ask Claude Code:
> "Look at `backend/app/telemetry.py`. Which OpenTelemetry instrumentors are configured? Based on the OTel semantic conventions, what Prometheus metric names and label names would the FastAPI instrumentor emit for request duration and status code?"

---

### 2. Write the three SLIs as PromQL queries

Open the Prometheus UI at http://localhost:9090 and test each query in the **Graph** tab.

**SLI 1 — Availability (target: 99% of requests succeed)**

```promql
# Availability = 1 - (5xx requests / total requests)
1 - (
  sum(rate(http_server_request_duration_seconds_count{http_response_status_code=~"5.."}[5m]))
  /
  sum(rate(http_server_request_duration_seconds_count[5m]))
)
```

This should return a value close to 1.0 (meaning ~100% availability) when the service is healthy. If no 5xx errors have occurred in the window, the numerator is 0 and availability is 1.0.

**SLI 2 — Latency (target: P95 < 500 ms)**

```promql
# P95 request duration in seconds
histogram_quantile(
  0.95,
  sum by (le) (rate(http_server_request_duration_seconds_bucket[5m]))
)
```

**SLI 3 — Readiness (target: /ready returns 200)**

The Blackbox Exporter probes `/ready` every 15 seconds and emits a `probe_success` gauge (1 = up, 0 = down):

```promql
probe_success{instance="http://api:8000/ready"}
```

Ask Claude Code:
> "I'm using `rate(...[5m])` for my SLI queries. Why does the choice of time window matter? What happens to the SLI value if I use `[1m]` vs `[1h]`? Which is better for alerting vs dashboards?"

---

### 3. Add Prometheus recording rules for SLO compliance

Recording rules pre-compute expensive queries and store the result as a new time series. This makes dashboards fast and alert evaluation cheap. Add them to a new file:

Create `observability/prometheus-rules.yml`:

```yaml
groups:
  - name: task-manager-sli
    interval: 30s
    rules:
      # Availability SLI: ratio of successful requests (non-5xx)
      - record: task_manager:request_availability:rate5m
        expr: |
          1 - (
            sum(rate(http_server_request_duration_seconds_count{http_response_status_code=~"5.."}[5m]))
            /
            sum(rate(http_server_request_duration_seconds_count[5m]))
          )

      # Latency SLI: P95 request duration
      - record: task_manager:request_p95_seconds:rate5m
        expr: |
          histogram_quantile(
            0.95,
            sum by (le) (rate(http_server_request_duration_seconds_bucket[5m]))
          )

      # Error budget burn rate (30-day window, 1-hour burn rate)
      # Burn rate > 1.0 means we are on track to exhaust the budget in < 30 days
      # Burn rate > 14.4 means the budget will be gone in < 2 hours (page immediately)
      - record: task_manager:error_budget_burn_rate:1h
        expr: |
          (
            sum(rate(http_server_request_duration_seconds_count{http_response_status_code=~"5.."}[1h]))
            /
            sum(rate(http_server_request_duration_seconds_count[1h]))
          )
          / 0.01
          # Divide by SLO error rate (1 - 0.99 = 0.01)
          # Result > 1.0 means burning faster than the 30-day budget allows
```

Wire the rules file into `observability/prometheus.yml`:

```yaml
# Add at the top level of prometheus.yml:
rule_files:
  - /etc/prometheus/prometheus-rules.yml
```

Mount the file in `docker-compose.yml`:

```yaml
prometheus:
  volumes:
    - ./observability/prometheus.yml:/etc/prometheus/prometheus.yml
    - ./observability/prometheus-rules.yml:/etc/prometheus/prometheus-rules.yml  # add this
```

Restart Prometheus and verify:

```bash
docker compose restart prometheus

# Check that the recording rules loaded without errors
curl -s http://localhost:9090/api/v1/rules | python3 -m json.tool | grep '"name"'
# Expected: "task_manager:request_availability:rate5m" etc.

# Query the new series
curl -s 'http://localhost:9090/api/v1/query?query=task_manager:request_availability:rate5m' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['result'])"
```

Ask Claude Code:
> "Explain the error budget burn rate formula above. If the API serves 10,000 requests per hour and returns 200 errors in an hour, what is the burn rate? How long until the 30-day error budget is exhausted at that rate?"

---

### 4. Add SLO alerting rules

Add to `observability/prometheus-rules.yml` under a new group:

```yaml
  - name: task-manager-slo
    rules:
      # Page immediately if burn rate is so high the budget will be gone in 2 hours
      - alert: ErrorBudgetBurnRateCritical
        expr: task_manager:error_budget_burn_rate:1h > 14.4
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "SLO error budget burning at critical rate"
          description: >
            Burn rate {{ $value | humanize }}x — at this rate the 30-day error budget
            (1% of requests) will be exhausted in less than 2 hours.
            Immediate action required.

      # Warn if burn rate predicts budget exhaustion in < 6 hours
      - alert: ErrorBudgetBurnRateHigh
        expr: task_manager:error_budget_burn_rate:1h > 6
        for: 15m
        labels:
          severity: warning
        annotations:
          summary: "SLO error budget burning at elevated rate"
          description: >
            Burn rate {{ $value | humanize }}x — budget exhaustion predicted in < 6 hours.

      # Latency SLO breach
      - alert: LatencySLOBreach
        expr: task_manager:request_p95_seconds:rate5m > 0.5
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "P95 latency exceeds 500 ms SLO"
          description: "Current P95: {{ $value | humanizeDuration }}"

      # Readiness SLO breach
      - alert: ServiceUnreachable
        expr: probe_success{instance="http://api:8000/ready"} == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "Service readiness probe failing"
          description: "The /ready endpoint has not returned 200 for more than 1 minute."
```

Reload Prometheus:

```bash
docker compose restart prometheus

# Verify all alerts are in 'inactive' state (healthy system)
curl -s http://localhost:9090/api/v1/alerts | python3 -m json.tool
```

Ask Claude Code:
> "Why are there two burn-rate alerts with different thresholds (14.4x and 6x) rather than a single alert at one threshold? What does 'for: 2m' mean in an alert rule, and why is the critical alert set to 2m while the warning is 15m?"

---

### 5. Build a Grafana SLO dashboard

Navigate to Grafana at http://localhost:3000 (admin / admin) → **Dashboards → New dashboard**.

Add four panels using the recording rule series:

**Panel 1 — Availability SLI (stat panel)**

- Query: `task_manager:request_availability:rate5m * 100`
- Unit: Percent (0-100)
- Thresholds: green ≥ 99, yellow ≥ 98, red < 98
- Title: "Availability — 5 min window"

**Panel 2 — P95 Latency SLI (stat panel)**

- Query: `task_manager:request_p95_seconds:rate5m * 1000`
- Unit: Milliseconds
- Thresholds: green ≤ 500, yellow ≤ 800, red > 800
- Title: "P95 Latency"

**Panel 3 — Error Budget Burn Rate (gauge panel)**

- Query: `task_manager:error_budget_burn_rate:1h`
- Min: 0, Max: 20
- Thresholds: green ≤ 1, yellow ≤ 6, red > 6
- Title: "Error Budget Burn Rate (1-hour)"
- Description: "1.0 = sustainable; >14.4 = budget gone in 2 hours"

**Panel 4 — Readiness (state timeline or stat panel)**

- Query: `probe_success{instance="http://api:8000/ready"}`
- Value mappings: 1 → "UP" (green), 0 → "DOWN" (red)
- Title: "Service Readiness"

Save the dashboard as "Task Manager — SLO Overview".

Ask Claude Code:
> "Open `observability/grafana/provisioning/alerting/rules.yaml`. The existing `HighErrorRate` alert fires when the 5-minute error rate exceeds 5%. How does this differ from the burn-rate alerts we just added? Which approach is more useful for an on-call engineer and why?"

---

### 6. Configure Grafana alert contact points

An alert rule that fires but goes nowhere is useless. Grafana's **Contact Points** define where alerts are delivered: email, Slack, PagerDuty, or webhook.

In Grafana: **Alerting → Contact points → + New contact point**

For local development, use the built-in test webhook to verify the pipeline:

1. Set type: **Webhook**
2. URL: `http://host.docker.internal:8080` (a local listener you'll start in a moment)
3. Save

Start a listener to receive the webhook:
```bash
python3 -m http.server 8080
```

Trigger the `DatabaseUnreachable` alert:
```bash
docker compose stop db
```

After 60 seconds, the alert should fire and Grafana should POST to your listener. Verify the JSON payload in the listener output.

For a real notification channel:
```
# Slack: create a Slack App with Incoming Webhooks enabled
# → Grafana: type=Slack, Webhook URL from Slack App settings

# Email: Grafana → Settings → SMTP must be configured
# → Contact point type=Email, address=your@email.com

# PagerDuty: requires a PagerDuty API key
# → Contact point type=PagerDuty, Integration Key from PagerDuty service
```

After setting up a contact point, create a **Notification policy** to route alerts:
- **Alerting → Notification policies → Edit default policy**
- Set Default contact point to your new contact point

Restart the DB after testing:
```bash
docker compose up db -d
```

Ask Claude Code:
> "Grafana has two concepts: Contact Points (where to send alerts) and Notification Policies (which alerts go where). If I have two contact points — Slack for warnings and PagerDuty for critical alerts — what does the Notification Policy need to look like? Show me the label matcher syntax."

---

### 8. Write the runbook

A runbook is the structured response procedure an on-call engineer follows when an alert fires. It prevents ad-hoc panic.

Create `docs/operations/runbook-high-error-rate.md`:

```markdown
# Runbook — ErrorBudgetBurnRateCritical

**Alert:** ErrorBudgetBurnRateCritical  
**Severity:** Critical  
**SLO:** 99% of requests succeed over 30 days  
**Trigger:** Burn rate > 14.4x for 2 minutes (budget exhaustion in < 2 hours)

## Immediate triage (< 5 minutes)

1. **Check service health**
   ```bash
   curl -s http://localhost:8000/health   # or your production URL
   curl -s http://localhost:8000/ready
   ```
   If either returns non-200: the service is down. Skip to **Escalation**.

2. **Identify which endpoints are failing**
   
   In Prometheus:
   ```promql
   sum by (http_route, http_response_status_code) (
     rate(http_server_request_duration_seconds_count{http_response_status_code=~"5.."}[5m])
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

## If error originates in database

- Check database connectivity: `docker compose exec db psql -U taskuser -c '\l'`
- Check connection pool: look for `asyncpg.TooManyConnectionsError` in logs
  ```bash
  docker compose logs api --since=10m | grep -i "error\|exception"
  ```
- If pool exhausted: check for long-running queries and whether replicas are available

## If error originates in application code

- Read the full stack trace from the structured log:
  ```bash
  docker compose logs api --since=10m | jq 'select(.level=="error")'
  ```
- Identify the code path from the stack trace
- If a recent deployment introduced the regression: **Rollback**

## Rollback

```bash
# Fly.io
flyctl releases rollback --app task-manager-api

# Verify the rollback restored health
curl -s http://localhost:8000/health
```

After rollback: verify the burn rate drops below 1.0 in Prometheus within 5 minutes.

## Escalation

If triage takes > 15 minutes without resolution, escalate to the team lead and open
a severity-1 incident in your incident management tool with:
- Alert name and trigger time
- Current burn rate and estimated time to budget exhaustion
- Steps already taken
- Hypothesis for root cause

## Post-incident

After resolution, write a blameless post-mortem in `docs/post-mortems/YYYY-MM-DD-<title>.md`:
- Timeline of events
- Root cause (the systemic condition, not the person)
- Contributing factors
- Action items with owners and due dates
```

Ask Claude Code:
> "Review this runbook. What's missing that a real on-call engineer would need? Suggest two specific improvements, citing examples from SRE industry practice."

---

### 9. Simulate an incident and follow the runbook

Use the spike load test from Module 11 to trigger the burn-rate alerts:

```bash
# Start the observability stack if not already running
docker compose --profile observability up -d

# Run the spike test (ramps to 200 VUs, triggering 5xx errors from rate limiting)
k6 run load-tests/k6/spike.js
```

While the spike test runs, watch Grafana's SLO dashboard. Within 2–5 minutes the
error rate panel should turn red and the burn rate should climb above 1.0.

Open the Prometheus alerts page (http://localhost:9090/alerts) and watch for
`ErrorBudgetBurnRateCritical` to enter the `firing` state.

Now follow your runbook:
1. Open the Grafana SLO dashboard — identify the severity
2. Check `/health` and `/ready`
3. Query Prometheus for the failing endpoints
4. Open Jaeger — find error traces

After the spike test ends, verify the burn rate drops back below 1.0 within 5 minutes
(the 1-hour window means recovery is gradual).

Ask Claude Code:
> "After following the runbook, what would you write in the post-mortem 'Contributing Factors' section for this incident? The root cause was a load spike hitting the rate limiter. What systemic conditions allowed it to burn significant error budget?"

---

## Checkpoint

- [ ] Prometheus recording rules loaded; `task_manager:request_availability:rate5m` returns a value
- [ ] Error budget burn rate formula understood — can explain what 14.4x means
- [ ] `ErrorBudgetBurnRateCritical` and `LatencySLOBreach` alerts visible in Prometheus alerts page
- [ ] Grafana SLO dashboard created with 4 panels showing traffic-light SLO status (Activity 5)
- [ ] Grafana contact point configured — alert delivered (webhook, email, or Slack) when `DatabaseUnreachable` fires (Activity 6)
- [ ] Runbook written in `docs/operations/runbook-high-error-rate.md` (Activity 8)
- [ ] Spike load test triggered the burn-rate alert; runbook steps followed (Activity 9)
- [ ] Burn rate recovered to < 1.0 after spike test ended
- [ ] Commit: `feat(slo): add SLI recording rules, burn-rate alerts, SLO dashboard, alert delivery, and error rate runbook`

---

## Troubleshooting

| Problem | Likely cause | Fix |
|---------|-------------|-----|
| Recording rule series not appearing | Rules file not mounted in container | Verify `docker-compose.yml` volume mount and restart Prometheus |
| `http_server_request_duration_seconds_count` not found | OTel not enabled | Check `OTEL_ENABLED=true` in compose env; check `/metrics` endpoint directly |
| Burn rate stays at 0 during spike | Rate limiter returns 429 (client error), not 5xx | 429 is not a server error; update the SLI to count 429s if rate-limit exhaustion is a reliability concern |
| Grafana alert rules not appearing | Alertmanager not configured | For the lab, Grafana evaluates alerts directly — check Grafana → Alerting → Alert rules |
| Prometheus restart fails | Syntax error in rules file | Run `docker run --rm -v $(pwd)/observability:/etc/prometheus prom/prometheus promtool check rules /etc/prometheus/prometheus-rules.yml` |
