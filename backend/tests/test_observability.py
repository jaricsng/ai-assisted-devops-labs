"""Integration tests for observability endpoints and middleware.

OTel is disabled in CI (OTEL_ENABLED=false) to avoid needing a live Jaeger instance.
When running with Docker Compose (--profile observability), the /metrics endpoint
serves Prometheus text format instead and can be tested via:
    curl http://localhost:8000/metrics | grep http_server_request_duration
"""
import pytest


@pytest.mark.asyncio
async def test_health_returns_ok(client):
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


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
