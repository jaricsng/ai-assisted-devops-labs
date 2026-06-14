Run a load test scenario against the Task Manager API and analyse the results. Correlates load test data with Prometheus metrics and Jaeger traces to identify bottlenecks.

If `$ARGUMENTS` specifies a scenario (`smoke`, `load`, `spike`), run that k6 scenario.
If no argument is given, run the smoke test first and ask which scenario to run next.

## Steps

### Step 1 — Verify prerequisites

```bash
# Check k6 is available
k6 version 2>/dev/null || docker run --rm grafana/k6 version 2>/dev/null || echo "k6 not found"

# Check Locust is available (for web UI mode)
locust --version 2>/dev/null || echo "locust not found"

# Check the API is running
curl -sf http://localhost:8000/health || echo "API not reachable at http://localhost:8000"
```

If the API is not reachable, tell the user to run `docker compose up -d` first.

If k6 is not installed, offer two options:
- Install via Homebrew: `brew install k6`
- Use Docker: `docker run --rm -i --network host grafana/k6 run - < load-tests/k6/smoke.js`

### Step 2 — Run the requested scenario

**smoke** (default if no argument):
```bash
k6 run load-tests/k6/smoke.js
```
Expected: all checks pass, zero errors, P95 < 1000 ms.

**load**:
```bash
k6 run load-tests/k6/load.js
```
Runs for ~9 minutes (1m ramp + 2m ramp + 5m hold + 1m ramp-down).
Thresholds: P95 < 500 ms, error rate < 1%.

**spike**:
```bash
k6 run load-tests/k6/spike.js
```
Runs for ~5 minutes. Acceptable: up to 5% errors during peak, full recovery afterward.

**locust** (web UI mode):
```bash
locust -f load-tests/locustfile.py --host http://localhost:8000
```
Then open http://localhost:8089 in a browser.

### Step 3 — Parse and report results

After k6 completes, parse the output:

1. **Summary table** — extract from k6's stdout:
   ```
   ┌─ Scenario Results ─────────────────────────────────┐
   │  Checks passed:  N% (N/N)                          │
   │  Error rate:     N% (threshold: <1%)   ✅ / ❌     │
   │  P50 latency:    Nms                               │
   │  P95 latency:    Nms (threshold: <500ms)  ✅ / ❌  │
   │  P99 latency:    Nms                               │
   │  RPS peak:       N req/s                           │
   └────────────────────────────────────────────────────┘
   ```

2. **Threshold results** — did any thresholds fail? List each failing threshold with:
   - The metric and threshold: `http_req_duration p(95) < 500ms`
   - The actual value: `measured: 847ms`
   - Likely cause and investigation step

3. **Bottleneck investigation** — if any thresholds failed or latency was high:
   - Check Prometheus for the time window: `histogram_quantile(0.95, rate(http_server_request_duration_seconds_bucket[1m])) * 1000`
   - Identify which endpoint drove the high latency
   - Check Jaeger for slow traces in that time window
   - Look at database spans — is the latency in the API code or in SQL?

### Step 4 — Recommendations

Based on the results, produce a ranked list of findings:

```
Performance Findings
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[HIGH]   POST /projects/{id}/tasks P95 = 847 ms (SLO: 500 ms)
         Jaeger shows SQLAlchemy SELECT taking 620 ms.
         Fix: add index on tasks.project_id (missing FK index).

[MEDIUM] Connection pool exhausted at 150 VUs
         Error: asyncpg.TooManyConnectionsError
         Fix: increase pool_size in create_async_engine(pool_size=20).

[INFO]   Error rate 0.3% (below 1% threshold) — all errors are 422
         (invalid status transitions from the load test script itself).
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

For each HIGH or MEDIUM finding, offer to fix it immediately if the cause is clear, or show the investigation steps to confirm.

## Context

- Load test scripts are in `load-tests/` — Locust (`locustfile.py`) and k6 (`k6/`)
- The observability stack (Prometheus + Jaeger + Grafana) must be running for bottleneck analysis
- Load tests generate real data in the database — reset with `docker compose down -v && docker compose up -d` after heavy testing
- Never point load tests at staging or production without explicit team approval
