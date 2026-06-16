# Module 11 — Load Testing

## Learning Objectives

- Understand the four types of load test and when to run each
- Write realistic load test scenarios with Locust (Python) and k6 (JavaScript)
- Define SLOs as pass/fail thresholds in code so CI can enforce them
- Use the Grafana + Prometheus observability stack to find bottlenecks while load is applied
- Identify the difference between a performance bug and a capacity limit

---

## Background: Types of Load Tests

| Test type | Pattern | Question it answers |
|-----------|---------|-------------------|
| **Smoke** | 1 user, 1 min | Does the API work at all under minimal load? |
| **Load** | Ramp to expected peak, hold | Does the API meet SLOs at normal production traffic? |
| **Stress** | Keep increasing users until failure | What is the breaking point? Where does it fail? |
| **Spike** | Sudden burst to 10–40× normal | Does the API survive sudden traffic events? Does it recover? |

Run them in this order. Never run a stress test on a shared environment — use an isolated instance.

---

## Tools

### Locust (Python — primary tool)

Locust defines user behaviour as Python classes. It has a live web UI at `http://localhost:8089` showing real-time RPS, response times, and failure rates. Scenarios live in `load-tests/locustfile.py`.

**Install:**
```bash
pip install locust
```

### k6 (Go binary — CI-friendly)

k6 scripts are JavaScript and define pass/fail thresholds in code. When a threshold is breached, k6 exits non-zero — CI treats this as a build failure. Scenarios live in `load-tests/k6/`.

**Install (macOS):**
```bash
brew install k6
```

**Install (Docker — no local install):**
```bash
docker run --rm -i grafana/k6 version
```

---

## Setup

Start the full stack (with observability so you can watch the dashboards during tests):

```bash
docker compose --profile observability up -d
```

Verify the API is up:
```bash
curl http://localhost:8000/health
```

---

## Activities

### 1. Run the smoke test (k6)

The smoke test verifies the complete user journey works under a single virtual user:

```bash
k6 run load-tests/k6/smoke.js
```

Watch the output. Every check should pass:
```
✓ health 200
✓ register 201
✓ login 200
✓ create project 201
✓ create task 201
✓ status transition 200
✓ invalid transition 422
```

If any check fails here, fix it before continuing. A failing smoke test means a broken API, not a performance problem.

### 2. Explore Locust's web UI

Start Locust with the web interface:

```bash
locust -f load-tests/locustfile.py --host http://localhost:8000
```

Open http://localhost:8089.

Set:
- **Number of users:** 10
- **Spawn rate:** 2 (users added per second during ramp)
- Click **Start**

Watch the real-time charts. After 2 minutes, look at:
- **RPS** — requests per second across all endpoints
- **Response time median and 95th percentile** — P50 and P95
- **Failure rate** — any non-2xx responses

Ask Claude Code:
> "The Locust locustfile.py has three user classes with different weights. Explain what `weight = 6` means on ReadHeavyUser and how Locust distributes users across the three classes."

### 3. Apply realistic load and watch Grafana

Increase to 50 users in Locust (or stop Locust and use k6):

```bash
k6 run load-tests/k6/load.js
```

While the test runs, open Grafana at http://localhost:3000 → **Task Manager API** dashboard. Watch:

- **Request Rate** panel climbing as VUs ramp
- **P95 Latency** panel — does it stay below 500 ms?
- **Error Rate %** panel — any spikes?
- **HTTP Errors Over Time** — which status codes appear?

Open Jaeger at http://localhost:16686. Find a slow trace (sort by duration). Expand the waterfall — is the latency in the API code or in a database query (SQLAlchemy child span)?

Ask Claude Code:
> "The P95 latency for POST /projects/{id}/tasks is 450 ms. Looking at the Jaeger trace, the SQLAlchemy SELECT spans take 380 ms combined. What could cause a SELECT to be slow on this endpoint, and what would you check first?"

### 4. Find the breaking point (stress test)

In the Locust UI, keep increasing users — try 100, 200, 500. Watch:

- When does the error rate start climbing above 1%?
- When does P95 latency exceed 1 second?
- Does the API crash (Locust shows connection refused) or just slow down?

Common bottlenecks in this stack:

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| DB query spans go from 10 ms to 2 s | Connection pool exhausted | Increase `pool_size` in `create_async_engine` |
| API returns 500 on all requests | Uvicorn worker threads exhausted | Add `--workers` to uvicorn command |
| Latency climbs slowly then stabilises | CPU-bound (bcrypt hashing) | Expected — bcrypt is intentionally slow |
| Auth endpoints fail but task endpoints are fine | Rate limiting applied | Expected if rate limiting is implemented |

Ask Claude Code:
> "When I stress-test the API to 300 concurrent users, the SQLAlchemy connection pool raises `TimeoutError: QueuePool limit of size 5 overflow 10 reached`. How do I tune the pool settings for our async engine? What are the trade-offs of a very large pool?"

### 5. Run the spike test

```bash
k6 run load-tests/k6/spike.js
```

The spike test ramps to 100 VUs in 10 seconds, holds for 3 minutes, then drops back. Watch the Grafana dashboard for:

1. Does error rate spike above 5% during the peak?
2. After the spike subsides, does P95 latency return to baseline within 30 seconds?
3. Does the API remain healthy after the test, or does `docker compose logs api` show errors?

> **Rate-limit pitfall:** The spike test uses a token pool pattern — 10 users are registered and logged in once during the k6 `setup()` phase (with 7 s sleep between logins to stay under the 10 req/min rate limit: 9×7 s = 63 s means login[0] exits the 60-second sliding window before login[9] fires), and all 100 VUs share those tokens via round-robin. This avoids the common mistake of calling `register → login` inside the per-iteration `default()` function: at 100 concurrent VUs that pattern exhausts the rate limit immediately and causes a high error rate on logins instead of exercising the API under real load.

Ask Claude Code:
> "The spike test shows P95 latency rising to 3 seconds during the peak but dropping to 200 ms after the spike ends. No 5xx errors were returned. Is this acceptable behaviour? What would an unrecoverable spike failure look like?"

### 6. Define SLOs and enforce them in CI

SLOs (Service Level Objectives) are performance targets expressed as thresholds. Open `load-tests/k6/load.js` and read the `thresholds` block:

```javascript
thresholds: {
  http_req_failed:            ["rate<0.01"],   // <1% error rate
  http_req_duration:          ["p(95)<500"],   // p95 < 500 ms overall
  "http_req_duration{name:list_tasks}":     ["p(95)<400"],  // indexed FK reads
  "http_req_duration{name:list_projects}":  ["p(95)<400"],  // indexed owner_id reads
  errors:                     ["rate<0.01"],
  task_create_duration:       ["p(95)<600"],
  status_transition_duration: ["p(95)<600"],  // 2 DB round-trips (GET + PATCH)
  comment_duration:           ["p(95)<600"],  // FK insert + task existence check
}
```

> **Threshold calibration:** The per-operation thresholds (`list_tasks`, `status_transition_duration`) are calibrated for local Docker at 50 VUs where network round-trips add overhead. Cloud deployments will comfortably beat these numbers. If you hit a threshold violation, open Jaeger and compare the span duration — is the time in the API code or in a database query?

When a threshold is breached, k6 exits with a non-zero code. You can run the smoke test in CI to catch regressions:

Ask Claude Code:
> "Add a step to `.github/workflows/ci.yml` that runs the k6 smoke test against the Docker Compose stack. The step should only run on PRs to `main` (like the E2E job) and should fail the PR if any k6 threshold is breached."

Implement the step and verify it runs on your next PR.

### 7. Add a custom metric

The locustfile tracks the full request cycle. Add a custom metric to measure only the database write time:

Ask Claude Code:
> "In load-tests/locustfile.py, add a ResponseTime custom metric that records only the duration of PATCH requests (status transitions). Use locust's `environment.events.request` hook to capture the response time for requests where the name is '/projects/{id}/tasks/{id} [PATCH]'."

After adding it, rerun the load test and observe the metric in the Locust UI.

---

## Reading the Results

### What good looks like

| Metric | Target | Action if breached |
|--------|--------|-------------------|
| Error rate | < 1% | Investigate 5xx logs, check DB health |
| P50 latency | < 100 ms | Normal — reads should be fast |
| P95 latency | < 500 ms | Investigate slow spans in Jaeger |
| P99 latency | < 2 s | Investigate outliers — often connection pool timeouts |
| Recovery time after spike | < 60 s | Check for memory leaks or connection leaks |

### What to do with a failing threshold

1. Open Jaeger and find the slowest traces during the failing period
2. Look for which span (HTTP handler, specific SQLAlchemy query) is the bottleneck
3. Check `docker stats` to see if CPU or memory is saturated
4. Check `docker compose logs db` for PostgreSQL errors (connection refused, max connections)
5. Fix the bottleneck and re-run the same test to verify improvement

---

## Checkpoint

- [ ] `k6 run load-tests/k6/smoke.js` passes with all checks green
- [ ] Locust web UI shows the API handling 50 users with P95 < 500 ms
- [ ] You identified at least one bottleneck by correlating Locust/k6 data with Jaeger traces
- [ ] You ran the spike test and observed recovery behaviour
- [ ] k6 thresholds are defined in `load-tests/k6/load.js` and you understand what they enforce
- [ ] Commit: `test(load): add Locust and k6 scenarios with SLO thresholds`
