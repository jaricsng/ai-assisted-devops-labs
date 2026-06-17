"""Integration tests for auth endpoints: register, login, logout, GDPR account deletion."""

import uuid

import pytest

_PASS = "Pass1234"  # satisfies: ≥8 chars, uppercase, digit


def _email() -> str:
    return f"auth_{uuid.uuid4().hex[:8]}@example.com"


@pytest.mark.asyncio
async def test_register_creates_user(client):
    response = await client.post(
        "/auth/register",
        json={"email": _email(), "full_name": "Test User", "password": _PASS},
    )
    assert response.status_code == 201
    body = response.json()
    assert "id" in body
    assert "hashed_password" not in body


@pytest.mark.asyncio
async def test_register_duplicate_email_returns_409(client):
    email = _email()
    payload = {"email": email, "full_name": "Test", "password": _PASS}
    await client.post("/auth/register", json=payload)
    response = await client.post("/auth/register", json=payload)
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_login_returns_access_token(client):
    email = _email()
    await client.post(
        "/auth/register", json={"email": email, "full_name": "T", "password": _PASS}
    )
    response = await client.post(
        "/auth/login", json={"email": email, "password": _PASS}
    )
    assert response.status_code == 200
    assert "access_token" in response.json()


@pytest.mark.asyncio
async def test_login_wrong_password_returns_401(client):
    email = _email()
    await client.post(
        "/auth/register", json={"email": email, "full_name": "T", "password": _PASS}
    )
    response = await client.post(
        "/auth/login", json={"email": email, "password": "wrongPass1"}
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_login_unknown_email_returns_401(client):
    response = await client.post(
        "/auth/login", json={"email": "nobody@example.com", "password": "pass"}
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_logout_revokes_token(client):
    email = _email()
    await client.post(
        "/auth/register", json={"email": email, "full_name": "T", "password": _PASS}
    )
    login = await client.post("/auth/login", json={"email": email, "password": _PASS})
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    logout = await client.post("/auth/logout", headers=headers)
    assert logout.status_code == 204

    # The same token must now be rejected
    response = await client.get("/projects", headers=headers)
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_delete_account_returns_204(client):
    email = _email()
    await client.post(
        "/auth/register", json={"email": email, "full_name": "T", "password": _PASS}
    )
    login = await client.post("/auth/login", json={"email": email, "password": _PASS})
    token = login.json()["access_token"]

    response = await client.delete(
        "/auth/users/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 204


@pytest.mark.asyncio
async def test_deleted_user_token_rejected(client):
    """After account deletion, the issued token should be rejected (user not found)."""
    email = _email()
    await client.post(
        "/auth/register", json={"email": email, "full_name": "T", "password": _PASS}
    )
    login = await client.post("/auth/login", json={"email": email, "password": _PASS})
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    await client.delete("/auth/users/me", headers=headers)

    response = await client.get("/projects", headers=headers)
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_deleted_user_cannot_login(client):
    """After soft-delete, the email+password pair should no longer authenticate."""
    email = _email()
    await client.post(
        "/auth/register", json={"email": email, "full_name": "T", "password": _PASS}
    )
    login = await client.post("/auth/login", json={"email": email, "password": _PASS})
    token = login.json()["access_token"]

    await client.delete("/auth/users/me", headers={"Authorization": f"Bearer {token}"})

    response = await client.post(
        "/auth/login", json={"email": email, "password": _PASS}
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_security_headers_present(client):
    response = await client.get("/health")
    assert response.headers.get("x-frame-options") == "DENY"
    assert response.headers.get("x-content-type-options") == "nosniff"
    assert response.headers.get("x-xss-protection") == "1; mode=block"
    assert "strict-transport-security" in response.headers
    assert response.headers.get("referrer-policy") == "strict-origin-when-cross-origin"
    assert "content-security-policy" in response.headers


@pytest.mark.asyncio
async def test_unauthenticated_request_rejected(client):
    # FastAPI 0.108+ returns 401 (was 403) when Bearer credentials are absent
    response = await client.get("/projects")
    assert response.status_code in (401, 403)
