"""OpenTelemetry setup — wires traces to Jaeger and metrics to Prometheus.

Call setup_telemetry(app, engine) once at application startup.

Architecture:
  FastAPI app
    └─ FastAPIInstrumentor  → spans & metrics via OTel SDK
    └─ SQLAlchemyInstrumentor → DB query spans
         │
         ├─ TracerProvider ──► BatchSpanProcessor ──► OTLPSpanExporter ──► Jaeger (gRPC :4317)
         │
         └─ MeterProvider ──► PrometheusMetricReader ──► /metrics (Prometheus text format)
                                                               │
                                                        Prometheus scrapes
                                                               │
                                                           Grafana reads
"""

import structlog
from opentelemetry import metrics, trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.prometheus import PrometheusMetricReader
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.semconv.resource import ResourceAttributes
from prometheus_client import make_asgi_app

logger = structlog.get_logger(__name__)

_tracer_provider: TracerProvider | None = None


def setup_telemetry(app, engine, otlp_endpoint: str) -> None:
    """Configure OTel SDK, auto-instrument FastAPI + SQLAlchemy, mount /metrics.

    Args:
        app: The FastAPI application instance.
        engine: The SQLAlchemy AsyncEngine (async engine wraps a sync engine we instrument).
        otlp_endpoint: gRPC endpoint for the OTLP trace exporter (e.g. Jaeger).
    """
    global _tracer_provider

    resource = Resource.create(
        {
            ResourceAttributes.SERVICE_NAME: "task-manager-api",
            ResourceAttributes.SERVICE_VERSION: "0.1.0",
            ResourceAttributes.DEPLOYMENT_ENVIRONMENT: "development",
        }
    )

    # ── Tracing ──────────────────────────────────────────────────────────────
    # BatchSpanProcessor buffers spans and sends them in batches to Jaeger via
    # OTLP gRPC. If Jaeger is unreachable the exporter logs a warning and drops
    # spans — it does not crash the API.
    _tracer_provider = TracerProvider(resource=resource)
    otlp_exporter = OTLPSpanExporter(endpoint=otlp_endpoint, insecure=True)
    _tracer_provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
    trace.set_tracer_provider(_tracer_provider)

    # ── Metrics ───────────────────────────────────────────────────────────────
    # PrometheusMetricReader registers OTel metrics with the prometheus_client
    # library. The make_asgi_app() mounted at /metrics serves them in the
    # Prometheus text exposition format that Prometheus scrapes.
    prometheus_reader = PrometheusMetricReader()
    meter_provider = MeterProvider(
        resource=resource, metric_readers=[prometheus_reader]
    )
    metrics.set_meter_provider(meter_provider)

    # ── Auto-instrumentation ──────────────────────────────────────────────────
    # FastAPIInstrumentor creates spans for every HTTP request and records
    # http_server_request_duration_seconds histogram metrics automatically.
    FastAPIInstrumentor.instrument_app(
        app,
        tracer_provider=_tracer_provider,
        meter_provider=meter_provider,
        http_capture_headers_server_request=["x-request-id"],
        http_capture_headers_server_response=["x-request-id"],
    )

    # SQLAlchemyInstrumentor creates child spans for every database query,
    # showing exact SQL and duration inside the parent request span.
    # AsyncEngine exposes the underlying sync engine via .sync_engine.
    SQLAlchemyInstrumentor().instrument(
        engine=engine.sync_engine,
        tracer_provider=_tracer_provider,
        enable_commenter=True,
    )

    # ── Prometheus /metrics endpoint ──────────────────────────────────────────
    # Mount the Prometheus ASGI app at /metrics. This replaces our old JSON
    # metrics endpoint with the standard Prometheus text format.
    prometheus_asgi = make_asgi_app()
    app.mount("/metrics", prometheus_asgi)

    logger.info("telemetry_configured", otlp_endpoint=otlp_endpoint)


def get_current_trace_ids() -> dict[str, str]:
    """Return the current span's trace_id and span_id for log correlation.

    Returns empty dict when there is no active span (e.g. background tasks,
    startup hooks, or when OTel is disabled).
    """
    span = trace.get_current_span()
    ctx = span.get_span_context()
    if not ctx.is_valid:
        return {}
    return {
        "trace_id": format(ctx.trace_id, "032x"),
        "span_id": format(ctx.span_id, "016x"),
    }


def shutdown_telemetry() -> None:
    """Flush pending spans on graceful shutdown so no data is lost."""
    if _tracer_provider:
        _tracer_provider.shutdown()
        logger.info("telemetry_shutdown")
