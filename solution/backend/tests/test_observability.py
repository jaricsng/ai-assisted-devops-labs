"""Integration tests for observability endpoints and middleware.

OTel is disabled in CI (OTEL_ENABLED=false) to avoid needing a live Jaeger instance.
When running with Docker Compose (--profile observability), the /metrics endpoint
serves Prometheus text format instead and can be tested via:
    curl http://localhost:8000/metrics | grep http_server_request_duration

Note on capture_logs():
    structlog.testing.capture_logs() does NOT include merge_contextvars in its
    processor chain by design — bound context vars (method, path, request_id) are
    stripped. Only kwargs passed directly to logger.info() appear in captured events.
    Tests that need to verify context-var-bound fields use _capture_with_ctx() below.
"""
import os
from contextlib import contextmanager
from typing import Generator

import pytest
import pytest_asyncio
import structlog
from httpx import ASGITransport, AsyncClient
from structlog.testing import capture_logs
from unittest.mock import AsyncMock


# ── Helper: capture_logs that also merges structlog context vars ──────────────


@contextmanager
def _capture_with_ctx() -> Generator[list[dict], None, None]:
    """Like capture_logs() but includes merge_contextvars so bound fields appear.

    structlog.testing.capture_logs() deliberately omits merge_contextvars so
    captured events stay clean. Use this variant when testing that fields bound
    via bind_contextvars() (e.g. method, path, request_id) appear in log lines.

    Matches structlog's internal implementation: mutates the SAME list instance
    that bound loggers already hold a reference to, so cached loggers pick up
    the change without needing cache_logger_on_first_use=False.
    """
    cap: list[dict] = []

    class _LogCapture:
        def __call__(self, logger, method, event_dict):
            cap.append(event_dict.copy())
            raise structlog.DropEvent()

    configured_processors = structlog.get_config()["processors"]
    old_processors = configured_processors.copy()
    try:
        configured_processors.clear()
        configured_processors.extend([
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_log_level,
            _LogCapture(),
        ])
        structlog.configure(processors=configured_processors)
        yield cap
    finally:
        configured_processors.clear()
        configured_processors.extend(old_processors)
        structlog.configure(processors=configured_processors)


# ── Existing tests ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_health_returns_ok(client):
    response = await client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "environment" in body


@pytest.mark.asyncio
async def test_health_includes_environment_field(client):
    """Health endpoint must return the active environment so operators can confirm
    they are connected to the right deployment (staging vs production)."""
    response = await client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["environment"] == "test"  # set via ENVIRONMENT=test in test runner


@pytest.mark.asyncio
async def test_ready_returns_200_when_db_is_up(client):
    response = await client.get("/ready")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert body["db"] == "ok"


@pytest.mark.asyncio
async def test_metrics_endpoint_not_mounted_when_otel_disabled(client):
    # When OTEL_ENABLED=false (as in CI), setup_telemetry() is skipped and the
    # Prometheus /metrics endpoint is not mounted. In Docker Compose with the
    # observability profile enabled, this endpoint returns Prometheus text format.
    response = await client.get("/metrics")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_request_id_header_present(client):
    """Every response must include X-Request-ID for log correlation."""
    response = await client.get("/health")
    assert "x-request-id" in response.headers
    request_id = response.headers["x-request-id"]
    assert len(request_id) == 36
    assert request_id.count("-") == 4


@pytest.mark.asyncio
async def test_request_id_unique_per_request(client):
    """Each request must get a distinct request ID."""
    r1 = await client.get("/health")
    r2 = await client.get("/health")
    assert r1.headers["x-request-id"] != r2.headers["x-request-id"]


# ── Gap 1: /ready when DB is down ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_ready_returns_503_when_db_is_down(client):
    """Readiness probe must return 503 when the database is unreachable."""
    from app.main import app
    from app.database import get_db

    mock_session = AsyncMock()
    mock_session.execute.side_effect = Exception("connection refused")

    async def mock_get_db():
        yield mock_session

    app.dependency_overrides[get_db] = mock_get_db
    try:
        response = await client.get("/ready")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 503
    body = response.json()
    assert body["detail"]["status"] == "not ready"
    assert body["detail"]["db"] == "unreachable"


# ── Gap 2: Structured log fields ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_request_finished_log_emits_status_and_duration(client):
    """request_finished must carry status_code and duration_ms as explicit kwargs."""
    with capture_logs() as cap:
        await client.get("/health")

    finished = [e for e in cap if e.get("event") == "request_finished"]
    assert len(finished) >= 1, f"no request_finished log emitted; captured: {cap}"
    log = finished[0]
    assert log["status_code"] == 200
    assert "duration_ms" in log
    assert isinstance(log["duration_ms"], (int, float))
    assert log["duration_ms"] >= 0


@pytest.mark.asyncio
async def test_both_request_log_events_emitted(client):
    """RequestLoggingMiddleware must emit request_started then request_finished."""
    with capture_logs() as cap:
        await client.get("/health")

    events = [e["event"] for e in cap]
    assert "request_started" in events
    assert "request_finished" in events


@pytest.mark.asyncio
async def test_method_path_request_id_bound_to_log_context(client):
    """method, path, and request_id must be bound via contextvars so every log line carries them."""
    with _capture_with_ctx() as cap:
        await client.get("/health")

    finished = [e for e in cap if e.get("event") == "request_finished"]
    assert len(finished) >= 1, f"no request_finished log; captured: {cap}"
    log = finished[0]
    assert log["method"] == "GET"
    assert log["path"] == "/health"
    assert "request_id" in log
    assert len(log["request_id"]) == 36  # UUID format


# ── Gap 3: X-Request-ID — client-supplied header behaviour ───────────────────


@pytest.mark.asyncio
async def test_server_generates_own_request_id_ignoring_client_header(client):
    """Server always generates a fresh X-Request-ID; client-supplied value is not echoed."""
    response = await client.get("/health", headers={"X-Request-ID": "client-supplied-id"})
    server_id = response.headers["x-request-id"]
    assert server_id != "client-supplied-id"
    assert len(server_id) == 36
    assert server_id.count("-") == 4


# ── Gap 4 & 5: /metrics content and Prometheus metric names when OTel is on ──


@pytest_asyncio.fixture(scope="module")
async def otel_client():
    """ASGI client against an isolated FastAPI app with OTel (metrics) enabled.

    Uses a separate app instance so the main test app is not mutated.
    Module scope so setup_telemetry() runs once for all OTel gap tests.
    follow_redirects=True handles the Starlette 307 on mounted ASGI paths.
    """
    from fastapi import FastAPI
    from sqlalchemy.ext.asyncio import create_async_engine
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
    from app.telemetry import setup_telemetry
    from app.middleware.logging import RequestLoggingMiddleware

    db_url = os.environ.get(
        "DATABASE_URL",
        "postgresql+asyncpg://taskuser:taskpass@db:5432/taskmanager",
    )

    otel_app = FastAPI()
    otel_app.add_middleware(RequestLoggingMiddleware)

    @otel_app.get("/ping")
    async def ping():
        return {"pong": True}

    dummy_engine = create_async_engine(db_url, echo=False)
    setup_telemetry(otel_app, dummy_engine, "http://localhost:4317")

    async with AsyncClient(
        transport=ASGITransport(app=otel_app),
        base_url="http://test",
        follow_redirects=True,
    ) as ac:
        yield ac

    FastAPIInstrumentor().uninstrument_app(otel_app)
    SQLAlchemyInstrumentor().uninstrument()
    await dummy_engine.dispose()


@pytest.mark.asyncio
async def test_metrics_endpoint_returns_prometheus_format(otel_client):
    """/metrics must return 200 with Prometheus text exposition format when OTel is enabled."""
    response = await otel_client.get("/metrics")
    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]
    assert "# HELP" in response.text
    assert "# TYPE" in response.text


@pytest.mark.asyncio
async def test_metrics_contains_http_server_duration(otel_client):
    """After at least one request, /metrics must expose the OTel HTTP duration histogram.

    The installed opentelemetry-instrumentation-fastapi uses the pre-1.23 semconv
    name http.server.duration (→ http_server_duration_milliseconds in Prometheus).
    """
    await otel_client.get("/ping")
    response = await otel_client.get("/metrics")
    assert response.status_code == 200
    assert "http_server_duration" in response.text


# ── Gap 6: Trace IDs in logs when OTel is active ─────────────────────────────


@pytest.mark.asyncio
async def test_trace_ids_injected_into_request_finished_log(otel_client):
    """When OTel is active, request_finished log must contain trace_id and span_id."""
    with capture_logs() as cap:
        await otel_client.get("/ping")

    finished = [e for e in cap if e.get("event") == "request_finished"]
    assert len(finished) >= 1, f"no request_finished log; captured: {cap}"
    log = finished[0]
    assert "trace_id" in log, f"trace_id missing from request_finished: {log}"
    assert "span_id" in log, f"span_id missing from request_finished: {log}"
    # OTel trace_id is a 128-bit value rendered as 32 hex chars
    assert len(log["trace_id"]) == 32
    # OTel span_id is a 64-bit value rendered as 16 hex chars
    assert len(log["span_id"]) == 16


# ── Gap 17: task_status_transitions_total counter in /metrics ────────────────


@pytest.mark.asyncio
async def test_task_status_transitions_counter_in_metrics(otel_client):
    """/metrics must expose task_status_transitions_total after a counter increment."""
    from app.business_metrics import task_status_transitions_total
    task_status_transitions_total.labels(from_status="TODO", to_status="IN_PROGRESS").inc()

    response = await otel_client.get("/metrics")
    assert response.status_code == 200
    assert "task_status_transitions_total" in response.text


# ── Gap 18: user_id bound to structlog context ───────────────────────────────


@pytest.mark.asyncio
async def test_user_id_bound_to_audit_log_context(client):
    """Authenticated requests must bind user_id to structlog context so every
    downstream log line — including audit events — carries the user's identity."""
    import uuid
    email = f"obs_{uuid.uuid4().hex[:8]}@example.com"
    await client.post("/auth/register", json={"email": email, "full_name": "Obs", "password": "Obs12345!"})
    login = await client.post("/auth/login", json={"email": email, "password": "Obs12345!"})
    token = login.json()["access_token"]

    with _capture_with_ctx() as cap:
        await client.post(
            "/projects",
            json={"name": "Audit Context Project"},
            headers={"Authorization": f"Bearer {token}"},
        )

    audit_events = [e for e in cap if e.get("event") == "audit"]
    assert len(audit_events) >= 1, f"no audit events; captured events: {[e.get('event') for e in cap]}"
    assert "user_id" in audit_events[0], (
        f"user_id not bound to audit log context; event: {audit_events[0]}"
    )


# ── Unhandled exception catch-all handler ─────────────────────────────────────


@pytest.mark.asyncio
async def test_unhandled_exception_handler_returns_safe_json():
    """The catch-all exception handler must return HTTP 500 with a safe generic
    message — never leaking stack traces or internal details to the caller.

    Calls the handler function directly (not via ASGI) to avoid the BaseHTTPMiddleware
    task-group re-raise behaviour that causes exceptions to escape in test transports.
    """
    import json
    from starlette.requests import Request
    import app.main as main_module

    scope = {
        "type": "http",
        "method": "GET",
        "path": "/test",
        "headers": [],
        "query_string": b"",
    }
    request = Request(scope)
    exc = RuntimeError("unexpected internal crash — must not leak to client")

    response = await main_module.unhandled_exception_handler(request, exc)

    assert response.status_code == 500
    body = json.loads(response.body)
    assert body["detail"] == "An internal error occurred."
    assert "RuntimeError" not in json.dumps(body)
    assert "Traceback" not in json.dumps(body)


# ── Gap: telemetry.py shutdown path ──────────────────────────────────────────


def test_shutdown_telemetry_calls_provider_shutdown_when_active():
    """shutdown_telemetry() must flush pending spans via _tracer_provider.shutdown().

    Called once at application shutdown (lifespan teardown). Verifies the provider
    is not abandoned when OTel is enabled.
    """
    from unittest.mock import MagicMock, patch
    from app import telemetry

    mock_provider = MagicMock()
    with patch.object(telemetry, "_tracer_provider", mock_provider):
        telemetry.shutdown_telemetry()

    mock_provider.shutdown.assert_called_once()


def test_shutdown_telemetry_is_safe_when_no_provider():
    """shutdown_telemetry() must not raise when OTel was never initialised (provider is None)."""
    from unittest.mock import patch
    from app import telemetry

    with patch.object(telemetry, "_tracer_provider", None):
        telemetry.shutdown_telemetry()  # must not raise


# ── Gap: logging_config.py production path ───────────────────────────────────


def test_configure_logging_production_uses_json_renderer():
    """configure_logging('production') must install JSONRenderer for machine-parseable logs.

    Log aggregators (Loki, CloudWatch, Datadog) require structured JSON output.
    In all other environments, ConsoleRenderer is used for human readability.

    Restoration note: configure_logging() always creates a *new* processors list.
    Cached loggers (cache_logger_on_first_use=True) hold a reference to the
    *original* list. Restoring via configure_logging("test") would leave cached
    loggers pointing at the old list while structlog's config points at a new one —
    breaking capture_logs() in subsequent tests. Instead we save the original list
    object, restore its contents in-place, then re-point structlog at it so both
    structlog's config and all cached loggers share the same list reference again.
    """
    import structlog
    from app.logging_config import configure_logging

    # Capture the *original* list object (not just a copy of its contents).
    original_list = structlog.get_config()["processors"]
    saved_contents = original_list[:]

    try:
        configure_logging("production")  # creates a new list; cached loggers keep original_list
        processor_types = [type(p).__name__ for p in structlog.get_config()["processors"]]
        assert "JSONRenderer" in processor_types, (
            f"JSONRenderer missing in production logging config; got: {processor_types}"
        )
    finally:
        # Restore in-place so cached loggers (which reference original_list) stay consistent
        # with structlog's config after the test.
        original_list.clear()
        original_list.extend(saved_contents)
        structlog.configure(processors=original_list)


# ── Gap: well_known.py security.txt response ─────────────────────────────────


@pytest.mark.asyncio
async def test_security_txt_returns_rfc_9116_policy(client):
    """GET /.well-known/security.txt must return a plain-text RFC 9116 security policy
    with at least Contact and Expires fields required by the standard."""
    response = await client.get("/.well-known/security.txt")

    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]
    assert "Contact:" in response.text
    assert "Expires:" in response.text


# ── Gap: metrics.py slow request counter ─────────────────────────────────────


@pytest.mark.asyncio
async def test_metrics_middleware_counts_slow_requests(client):
    """MetricsMiddleware must increment slow_requests when a response exceeds 500 ms.

    time.perf_counter is patched so the simulated elapsed time triggers the threshold
    without requiring the test suite to actually wait.
    """
    from unittest.mock import patch
    from app.middleware.metrics import _counters, SLOW_REQUEST_THRESHOLD_MS

    initial_slow = _counters.slow_requests

    # Return start=0, end=threshold+0.1s to simulate a request just over the limit
    slow_duration = (SLOW_REQUEST_THRESHOLD_MS + 100) / 1000  # seconds
    with patch("app.middleware.metrics.time") as mock_time:
        mock_time.perf_counter.side_effect = [0.0, slow_duration]
        await client.get("/health")

    assert _counters.slow_requests > initial_slow, (
        "slow_requests counter was not incremented after a simulated slow request"
    )


# ── Gap: logging.py request_failed path ──────────────────────────────────────


@pytest.mark.asyncio
async def test_request_logging_emits_failed_log_on_unhandled_exception(client):
    """RequestLoggingMiddleware must call logger.exception('request_failed', ...) with
    duration_ms when a route handler raises an unhandled exception.

    structlog's cache_logger_on_first_use=True freezes the processor chain on first
    call, so capture_logs() / _capture_with_ctx() don't intercept cached loggers.
    Patching the module-level logger avoids this caching issue.
    """
    from unittest.mock import patch
    from app.main import app
    from app.database import get_db

    async def crashing_db():
        mock_session = AsyncMock()
        mock_session.execute.side_effect = RuntimeError("simulated crash")
        yield mock_session

    app.dependency_overrides[get_db] = crashing_db
    try:
        with patch("app.middleware.logging.logger") as mock_logger:
            with pytest.raises(Exception):
                await client.post(
                    "/auth/register",
                    json={"email": "crash@example.com", "full_name": "Crash", "password": "Crash123!"},
                )
    finally:
        app.dependency_overrides.pop(get_db, None)

    # Verify logger.exception was called with "request_failed" and duration_ms kwarg
    assert mock_logger.exception.called, "logger.exception was never called"
    call_args = mock_logger.exception.call_args
    assert "request_failed" in call_args.args, (
        f"logger.exception not called with 'request_failed'; args: {call_args}"
    )
    assert "duration_ms" in call_args.kwargs, (
        f"duration_ms missing from logger.exception call; kwargs: {call_args.kwargs}"
    )
