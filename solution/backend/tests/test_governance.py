"""Module 14 enterprise governance and compliance tests.

Tests are grouped by the three governance phases:
  Phase 1 — Transport Security  (headers, body limit, input constraints)
  Phase 2 — Identity & Audit   (password policy, audit log emission)
  Phase 3 — Supply chain controls are verified via CI (bandit, Trivy, SBOM)
             and are not directly testable here.
"""
import uuid

import pytest
from structlog.testing import capture_logs


def _email() -> str:
    return f"gov_{uuid.uuid4().hex[:8]}@example.com"


_PASS = "Pass1234"  # satisfies: ≥8 chars, uppercase, digit


async def _register_and_login(client) -> dict:
    """Register a fresh user and return bearer auth headers."""
    email = _email()
    await client.post(
        "/auth/register",
        json={"email": email, "full_name": "Gov User", "password": _PASS},
    )
    resp = await client.post("/auth/login", json={"email": email, "password": _PASS})
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


# ── Phase 1a: Security Headers ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_all_security_headers_present(client):
    """SecurityHeadersMiddleware must set all eight OWASP headers on every response."""
    response = await client.get("/health")
    assert response.headers.get("x-content-type-options") == "nosniff"
    assert response.headers.get("x-frame-options") == "DENY"
    assert response.headers.get("x-xss-protection") == "1; mode=block"
    assert "strict-transport-security" in response.headers
    assert response.headers.get("referrer-policy") == "strict-origin-when-cross-origin"
    assert "content-security-policy" in response.headers
    assert response.headers.get("cache-control") == "no-store"
    assert "permissions-policy" in response.headers


@pytest.mark.asyncio
async def test_security_headers_present_on_error_response(client):
    """Security headers must be included even on 401/403 error responses."""
    response = await client.get("/projects")  # no auth → 401 or 403
    assert response.headers.get("x-frame-options") == "DENY"
    assert response.headers.get("x-content-type-options") == "nosniff"
    assert "content-security-policy" in response.headers


# ── Phase 1b: Body Size Limit ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_oversized_body_returns_413(client):
    """MaxBodySizeMiddleware must reject Content-Length > 1 MiB with HTTP 413.

    httpx respects explicitly set Content-Length headers; the middleware checks
    this header before reading any body bytes, so the actual payload can be tiny.
    """
    response = await client.post(
        "/auth/register",
        content=b'{"email":"test@example.com","full_name":"T","password":"Pass1"}',
        headers={
            "content-type": "application/json",
            "content-length": str(1_048_576 + 1),
        },
    )
    assert response.status_code == 413
    assert "too large" in response.json()["detail"].lower()


# ── Phase 1c: Input Length Constraints ───────────────────────────────────────


@pytest.mark.asyncio
async def test_project_name_too_long_returns_422(client):
    """Project name > 255 chars must be rejected by Pydantic StringConstraints."""
    headers = await _register_and_login(client)
    response = await client.post(
        "/projects", json={"name": "x" * 256}, headers=headers
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_project_name_empty_returns_422(client):
    """Project name with min_length=1 must reject blank strings."""
    headers = await _register_and_login(client)
    response = await client.post(
        "/projects", json={"name": ""}, headers=headers
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_task_title_too_long_returns_422(client):
    """Task title > 255 chars must be rejected by Pydantic StringConstraints."""
    headers = await _register_and_login(client)
    pid = (
        await client.post("/projects", json={"name": "Gov Project"}, headers=headers)
    ).json()["id"]
    response = await client.post(
        f"/projects/{pid}/tasks",
        json={"title": "t" * 256, "priority": "LOW"},
        headers=headers,
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_comment_body_too_long_returns_422(client):
    """Comment body > 5000 chars must be rejected by Pydantic StringConstraints."""
    headers = await _register_and_login(client)
    pid = (
        await client.post("/projects", json={"name": "Gov Project 2"}, headers=headers)
    ).json()["id"]
    tid = (
        await client.post(
            f"/projects/{pid}/tasks",
            json={"title": "Task", "priority": "LOW"},
            headers=headers,
        )
    ).json()["id"]
    response = await client.post(
        f"/projects/{pid}/tasks/{tid}/comments",
        json={"body": "c" * 5001},
        headers=headers,
    )
    assert response.status_code == 422


# ── Phase 2a: Password Policy ─────────────────────────────────────────────────


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "password,label",
    [
        ("Sh0rt", "too short (< 8 chars)"),
        ("alllower1", "no uppercase letter"),
        ("NODIGITSZ", "no digit"),
    ],
)
async def test_weak_password_rejected(client, password, label):
    """Pydantic field_validator must reject passwords that violate the policy."""
    response = await client.post(
        "/auth/register",
        json={"email": _email(), "full_name": "Test", "password": password},
    )
    assert response.status_code == 422, f"Expected 422 for '{label}'"


# ── Phase 2b: Audit Log Emission ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_audit_log_on_project_create(client):
    """POST /projects must emit a structlog audit event with action=PROJECT_CREATED."""
    headers = await _register_and_login(client)
    with capture_logs() as cap:
        resp = await client.post(
            "/projects", json={"name": "Audit Project"}, headers=headers
        )
    assert resp.status_code == 201
    audit_events = [e for e in cap if e.get("event") == "audit"]
    assert any(e.get("action") == "PROJECT_CREATED" for e in audit_events), (
        f"PROJECT_CREATED audit event not found; captured: {audit_events}"
    )


@pytest.mark.asyncio
async def test_audit_log_on_project_delete(client):
    """DELETE /projects/{id} must emit a structlog audit event with action=PROJECT_DELETED."""
    headers = await _register_and_login(client)
    pid = (
        await client.post("/projects", json={"name": "To Delete"}, headers=headers)
    ).json()["id"]
    with capture_logs() as cap:
        await client.delete(f"/projects/{pid}", headers=headers)
    audit_events = [e for e in cap if e.get("event") == "audit"]
    assert any(e.get("action") == "PROJECT_DELETED" for e in audit_events), (
        f"PROJECT_DELETED audit event not found; captured: {audit_events}"
    )


@pytest.mark.asyncio
async def test_audit_log_on_task_create(client):
    """POST /projects/{id}/tasks must emit a structlog audit event with action=TASK_CREATED."""
    headers = await _register_and_login(client)
    pid = (
        await client.post("/projects", json={"name": "Audit Task Project"}, headers=headers)
    ).json()["id"]
    with capture_logs() as cap:
        resp = await client.post(
            f"/projects/{pid}/tasks",
            json={"title": "Audit Task", "priority": "LOW"},
            headers=headers,
        )
    assert resp.status_code == 201
    audit_events = [e for e in cap if e.get("event") == "audit"]
    assert any(e.get("action") == "TASK_CREATED" for e in audit_events), (
        f"TASK_CREATED audit event not found; captured: {audit_events}"
    )


@pytest.mark.asyncio
async def test_audit_log_on_logout(client):
    """POST /auth/logout must emit a structlog audit event with action=LOGOUT."""
    email = _email()
    await client.post(
        "/auth/register",
        json={"email": email, "full_name": "Audit User", "password": _PASS},
    )
    resp = await client.post("/auth/login", json={"email": email, "password": _PASS})
    headers = {"Authorization": f"Bearer {resp.json()['access_token']}"}

    with capture_logs() as cap:
        await client.post("/auth/logout", headers=headers)
    audit_events = [e for e in cap if e.get("event") == "audit"]
    assert any(e.get("action") == "LOGOUT" for e in audit_events), (
        f"LOGOUT audit event not found; captured: {audit_events}"
    )


@pytest.mark.asyncio
async def test_audit_log_on_gdpr_delete(client):
    """DELETE /auth/users/me must emit a structlog audit event with action=USER_DELETED."""
    email = _email()
    await client.post(
        "/auth/register",
        json={"email": email, "full_name": "GDPR User", "password": _PASS},
    )
    resp = await client.post("/auth/login", json={"email": email, "password": _PASS})
    headers = {"Authorization": f"Bearer {resp.json()['access_token']}"}

    with capture_logs() as cap:
        await client.delete("/auth/users/me", headers=headers)
    audit_events = [e for e in cap if e.get("event") == "audit"]
    assert any(e.get("action") == "USER_DELETED" for e in audit_events), (
        f"USER_DELETED audit event not found; captured: {audit_events}"
    )


# ── Phase 4: Rate Limiting & Disclosure ───────────────────────────────────────


@pytest.mark.asyncio
async def test_rate_limit_blocks_after_threshold(client):
    """RateLimitMiddleware must return 429 with Retry-After once the bucket fills.

    The middleware is configured with max_requests=10 per 60-second window.
    After 10 calls the 11th must be rejected.
    """
    payload = {"email": "ratelimit@example.com", "password": "any"}
    for _ in range(10):
        await client.post("/auth/login", json=payload)
    resp = await client.post("/auth/login", json=payload)
    assert resp.status_code == 429
    assert "retry-after" in resp.headers


@pytest.mark.asyncio
async def test_security_txt_endpoint_returns_disclosure_policy(client):
    """GET /.well-known/security.txt must return an RFC 9116 compliant plain-text policy."""
    resp = await client.get("/.well-known/security.txt")
    assert resp.status_code == 200
    assert "Contact:" in resp.text
    assert "Expires:" in resp.text


# ── Module 05 Activity 7 — SECRET_KEY production validator ──────────────────

def test_secret_key_validator_rejects_short_key_in_production():
    """SECRET_KEY shorter than 32 chars must raise ValueError in production."""
    from pydantic import ValidationError
    from app.config import Settings

    with pytest.raises((ValidationError, ValueError)):
        Settings(
            database_url="postgresql+asyncpg://u:p@localhost/db",
            secret_key="short",
            environment="production",
        )


def test_secret_key_validator_rejects_example_key_in_production():
    """Known example SECRET_KEY values must be rejected in production."""
    from pydantic import ValidationError
    from app.config import Settings

    with pytest.raises((ValidationError, ValueError)):
        Settings(
            database_url="postgresql+asyncpg://u:p@localhost/db",
            secret_key="change-me",
            environment="production",
        )


def test_secret_key_validator_rejects_long_example_key_in_production():
    """Example keys ≥32 chars must fail the placeholder check (not just the length check)."""
    from pydantic import ValidationError
    from app.config import Settings

    # "test-secret-key-for-local-dev-only" is 34 chars — passes length, fails placeholder check
    with pytest.raises((ValidationError, ValueError)):
        Settings(
            database_url="postgresql+asyncpg://u:p@localhost/db",
            secret_key="test-secret-key-for-local-dev-only",
            environment="production",
        )


def test_secret_key_validator_accepts_strong_key_in_production():
    """A strong SECRET_KEY (≥32 chars, not an example value) must be accepted in production."""
    from app.config import Settings

    s = Settings(
        database_url="postgresql+asyncpg://u:p@localhost/db",
        secret_key="a" * 32,
        environment="production",
    )
    assert s.environment == "production"


def test_secret_key_validator_allows_short_key_in_non_production():
    """SHORT or example SECRET_KEY is allowed in dev/test environments."""
    from app.config import Settings

    s = Settings(
        database_url="postgresql+asyncpg://u:p@localhost/db",
        secret_key="test-secret-key-for-local-dev-only",
        environment="test",
    )
    assert s.environment == "test"


# ── Rate Limit — IP extraction paths ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_rate_limit_uses_x_forwarded_for_header(client):
    """_client_ip must extract the first IP from X-Forwarded-For when present."""
    from app.middleware import rate_limit as rl

    resp = await client.post(
        "/auth/login",
        json={"email": "xforward@example.com", "password": "any"},
        headers={"X-Forwarded-For": "10.0.0.1, 192.168.1.1"},
    )
    assert resp.status_code != 429
    assert len(rl._instance._buckets.get("10.0.0.1", [])) == 1


@pytest.mark.asyncio
async def test_rate_limit_sliding_window_drops_expired_entries(client):
    """Bucket entries older than the window must be dropped (covers the popleft path)."""
    from app.middleware import rate_limit as rl

    # Pre-populate bucket with a stale timestamp (epoch 0 is far outside the 60s window)
    rl._instance._buckets["10.0.0.2"].append(0.0)
    resp = await client.post(
        "/auth/login",
        json={"email": "window@example.com", "password": "any"},
        headers={"X-Forwarded-For": "10.0.0.2"},
    )
    # Stale entry dropped; only the current request remains — not rate-limited
    assert resp.status_code != 429
    assert len(rl._instance._buckets["10.0.0.2"]) == 1


# ── Audit log — auth events ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_audit_log_on_register(client):
    """POST /auth/register must emit a structlog audit event with action=REGISTER."""
    with capture_logs() as cap:
        await client.post(
            "/auth/register",
            json={"email": _email(), "full_name": "Audit Register", "password": _PASS},
        )
    audit_events = [e for e in cap if e.get("event") == "audit"]
    assert any(e.get("action") == "REGISTER" for e in audit_events), (
        f"REGISTER audit event not found; captured: {audit_events}"
    )


@pytest.mark.asyncio
async def test_audit_log_on_login_success(client):
    """POST /auth/login with valid credentials must emit action=LOGIN_SUCCESS."""
    email = _email()
    await client.post(
        "/auth/register",
        json={"email": email, "full_name": "Login User", "password": _PASS},
    )
    with capture_logs() as cap:
        resp = await client.post("/auth/login", json={"email": email, "password": _PASS})
    assert resp.status_code == 200
    audit_events = [e for e in cap if e.get("event") == "audit"]
    assert any(e.get("action") == "LOGIN_SUCCESS" for e in audit_events), (
        f"LOGIN_SUCCESS audit event not found; captured: {audit_events}"
    )


@pytest.mark.asyncio
async def test_audit_log_on_login_failed(client):
    """POST /auth/login with wrong credentials must emit action=LOGIN_FAILED."""
    with capture_logs() as cap:
        resp = await client.post(
            "/auth/login",
            json={"email": "nosuchuser@example.com", "password": "WrongPass1"},
        )
    assert resp.status_code == 401
    audit_events = [e for e in cap if e.get("event") == "audit"]
    assert any(e.get("action") == "LOGIN_FAILED" for e in audit_events), (
        f"LOGIN_FAILED audit event not found; captured: {audit_events}"
    )


# ── Audit log — task lifecycle events ────────────────────────────────────────


@pytest.mark.asyncio
async def test_audit_log_on_task_update(client):
    """PATCH /projects/{id}/tasks/{tid} must emit a structlog audit event with action=TASK_UPDATED."""
    headers = await _register_and_login(client)
    pid = (
        await client.post("/projects", json={"name": "Audit Update Project"}, headers=headers)
    ).json()["id"]
    tid = (
        await client.post(
            f"/projects/{pid}/tasks",
            json={"title": "Task to Update", "priority": "LOW"},
            headers=headers,
        )
    ).json()["id"]
    with capture_logs() as cap:
        await client.patch(
            f"/projects/{pid}/tasks/{tid}",
            json={"title": "Updated Title"},
            headers=headers,
        )
    audit_events = [e for e in cap if e.get("event") == "audit"]
    assert any(e.get("action") == "TASK_UPDATED" for e in audit_events), (
        f"TASK_UPDATED audit event not found; captured: {audit_events}"
    )


@pytest.mark.asyncio
async def test_audit_log_on_task_delete(client):
    """DELETE /projects/{id}/tasks/{tid} must emit a structlog audit event with action=TASK_DELETED."""
    headers = await _register_and_login(client)
    pid = (
        await client.post("/projects", json={"name": "Audit Delete Project"}, headers=headers)
    ).json()["id"]
    tid = (
        await client.post(
            f"/projects/{pid}/tasks",
            json={"title": "Task to Delete", "priority": "LOW"},
            headers=headers,
        )
    ).json()["id"]
    with capture_logs() as cap:
        await client.delete(f"/projects/{pid}/tasks/{tid}", headers=headers)
    audit_events = [e for e in cap if e.get("event") == "audit"]
    assert any(e.get("action") == "TASK_DELETED" for e in audit_events), (
        f"TASK_DELETED audit event not found; captured: {audit_events}"
    )
