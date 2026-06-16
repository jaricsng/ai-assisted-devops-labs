# ADR 0006 — Observability Stack: structlog + OpenTelemetry + Prometheus + Jaeger

**Date:** 2026-06-16
**Status:** Accepted

## Context

A three-tier web application without observability is a black box in production. We need to answer three questions at runtime:

1. **What happened?** — structured logs with request context
2. **How long did it take?** — distributed traces for latency attribution
3. **Is it healthy?** — metrics for SLO tracking and alerting

The solution must work in the local Docker Compose environment without cloud accounts, integrate with the FastAPI async runtime, and not add mandatory infrastructure to the critical path (i.e., the API must start even if Jaeger or Prometheus is unreachable).

## Decisions

### 1. structlog for structured JSON logging

All log output uses `structlog` with a JSON renderer. Every log line carries:
- ISO timestamp and log level
- Module name and caller context
- Request-scoped fields bound via `structlog.contextvars` (request ID, user ID, method, path)
- OTel trace and span IDs injected by `get_current_trace_ids()` for log/trace correlation

**Why structlog over Python's stdlib `logging`?** The stdlib logger produces unstructured text. structlog produces machine-parseable JSON that Grafana Loki, CloudWatch Logs Insights, and GCP Cloud Logging can query without regex parsing. The `contextvars` API allows binding request-scoped fields once (in `RequestLoggingMiddleware`) so every downstream log call within that request automatically includes them.

**Audit events** use the same logger with `action`, `resource`, and `resource_id` keys:
```python
logger.info("audit", action="PROJECT_CREATED", resource="project", resource_id=project.id)
```

### 2. OpenTelemetry SDK for distributed tracing

Traces are exported to Jaeger via OTLP gRPC (`BatchSpanProcessor` + `OTLPSpanExporter`). Two auto-instrumentors add spans with zero boilerplate:

| Instrumentor | Spans created |
|---|---|
| `FastAPIInstrumentor` | One span per HTTP request (method, path, status, duration) |
| `SQLAlchemyInstrumentor` | One child span per SQL query (statement, duration, DB name) |

The SQLAlchemy instrumentor uses `enable_commenter=True`, which appends OTel trace context as SQL comments — useful for correlating slow query logs in PostgreSQL with API traces.

**Why OTel over a vendor SDK?** OTel is the CNCF standard. The same instrumentation code exports to Jaeger locally, to AWS X-Ray in production (via the OTel Collector), or to Azure Monitor — no code change required, only exporter config.

**Resilience:** If Jaeger is unreachable, `OTLPSpanExporter` logs a warning and drops spans. The API continues serving requests normally.

**Disabling in tests:** `OTEL_ENABLED=false` skips `setup_telemetry()` entirely so unit tests never require a running Jaeger instance.

### 3. Prometheus for metrics via PrometheusMetricReader

`FastAPIInstrumentor` records OTel metrics (request count, duration histogram) via a `PrometheusMetricReader`. The reader registers these metrics with the `prometheus_client` library, which serves them at `/metrics` in the standard Prometheus text exposition format.

Prometheus scrapes `/metrics` every 15 seconds (configured in `observability/prometheus.yml`). Grafana reads from Prometheus for dashboards and alerting.

**Why not StatsD or a custom metrics endpoint?** Prometheus pull-based scraping requires no push infrastructure from the API side. `prometheus_client` is the de facto Python library for this format and has zero runtime overhead when no metrics are being observed.

### 4. Jaeger for trace storage and UI

Jaeger receives OTLP gRPC on `:4317` and exposes a trace search UI at `http://localhost:16686`. Its in-memory storage is sufficient for the local lab; production deployments use Elasticsearch or Cassandra backends managed by the cloud provider.

**Why Jaeger over Zipkin?** Both support OTLP. Jaeger has tighter Kubernetes and Prometheus ecosystem integration and is the more widely deployed open-source option in enterprise environments where students will work.

### 5. Grafana as the unified observability front-end

Grafana reads from both Prometheus (metrics) and Jaeger (traces) and displays them in a single dashboard. Provisioned dashboards and data sources are committed to `observability/grafana/provisioning/` so the stack starts pre-configured without manual setup.

**Optional profile:** The observability stack (Jaeger, Prometheus, Grafana) runs under `docker compose --profile observability up` — not part of the default `docker compose up`. This keeps the default stack minimal (API, DB, frontend only) for students in Modules 1–4.

### 6. Blackbox Exporter for synthetic readiness probes

The Prometheus Blackbox Exporter (`prom/blackbox-exporter`) probes the API's `/ready` endpoint every 15 seconds from outside the application process. This is **external / synthetic monitoring** — it detects failures that internal metrics cannot, such as a hung process that still emits metrics but does not respond to HTTP requests.

The probe result is exposed as `probe_success{job="readiness"}` (1 = healthy, 0 = failing). Prometheus scrapes this metric and the `DatabaseUnreachable` Grafana alert fires when `probe_success` stays at 0 for more than 1 minute.

**Why external probes in addition to `/metrics`?** Internal OTel metrics (request counts, latency histograms) can only be emitted if the application is running and processing requests. An external probe detects the case where the database is down and the API's readiness check returns non-200 — a condition that produces zero internal metrics because no requests succeed.

**Scope:** The Blackbox Exporter runs under the `--profile observability` Docker Compose profile (port 9115). Students can verify probe output directly:

```bash
curl "http://localhost:9115/probe?target=http://localhost:8000/ready&module=http_2xx"
# → probe_success 1
```

The comparison between OTel internal metrics (request-driven) and Blackbox external probes (time-driven, independent of traffic) is covered in Module 05b Activity 11.

## Middleware Stack Position

`RequestLoggingMiddleware` sits inside `SecurityHeadersMiddleware` and `MetricsMiddleware` (which records HTTP durations). The log/metrics/trace trio fires in this order per request:

```
Incoming request
  → SecurityHeadersMiddleware  (adds headers on response)
  → CORS middleware
  → MaxBodySizeMiddleware
  → RateLimitMiddleware
  → RequestLoggingMiddleware   (binds request_id, logs request_received + request_finished)
  → MetricsMiddleware          (records http_request_duration histogram)
  → FastAPI router             (OTel span active here)
  → SQLAlchemy query           (child span from SQLAlchemyInstrumentor)
```

## Consequences

- `OTEL_ENABLED=false` must be set in all test environments — otherwise tests require a running Jaeger and Prometheus to pass
- The `/metrics` endpoint is public (no auth) — acceptable for local dev; production deployments must either restrict it via network policy or place it on an internal-only port
- Structured JSON logs are not human-friendly in a terminal; use `docker compose logs api | jq '.'` or configure structlog's `dev` renderer for local development
- Log/trace correlation requires the OTel SDK to be initialised before the first request — `setup_telemetry()` is called at application startup in `main.py`; if it fails, the API should not start
- Grafana provisioning YAMLs in `observability/grafana/provisioning/` must be kept in sync with any Prometheus metric name changes
- Jaeger's in-memory storage is reset on container restart — traces from before the restart are not persisted; for persistent trace storage use Jaeger with an Elasticsearch backend
