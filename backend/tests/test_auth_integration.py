"""Integration tests for authentication security properties.

Covers gaps not tested in test_auth_endpoints.py:
  - Input validation (weak/empty password, invalid email format)
  - Response content safety (hashed_password not exposed)
  - Anti-enumeration (identical error for wrong email vs wrong password)
  - JWT attack surface (alg:none, malformed token)
"""

import uuid

import pytest
from httpx import AsyncClient


@pytest.fixture
def user_payload():
    unique = uuid.uuid4().hex[:8]
    return {
        "email": f"alice_{unique}@example.com",
        "full_name": "Alice",
        "password": "Alice123!",
    }


class TestRegister:
    @pytest.mark.asyncio
    async def test_register_weak_password_returns_422(self, client: AsyncClient):
        resp = await client.post(
            "/auth/register",
            json={
                "email": "weak@example.com",
                "full_name": "Weak",
                "password": "abc",
            },
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_register_empty_password_returns_422(self, client: AsyncClient):
        resp = await client.post(
            "/auth/register",
            json={
                "email": "empty@example.com",
                "full_name": "Empty",
                "password": "",
            },
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_register_invalid_email_returns_422(self, client: AsyncClient):
        resp = await client.post(
            "/auth/register",
            json={
                "email": "notanemail",
                "full_name": "Bad",
                "password": "Valid123!",
            },
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_register_does_not_expose_hashed_password(
        self, client: AsyncClient, user_payload
    ):
        resp = await client.post("/auth/register", json=user_payload)
        assert resp.status_code == 201
        assert "hashed_password" not in resp.json()


class TestLogin:
    @pytest.mark.asyncio
    async def test_login_error_responses_identical_for_existing_vs_nonexistent(
        self, client: AsyncClient, user_payload
    ):
        """Verify user enumeration is not possible via differing error messages."""
        await client.post("/auth/register", json=user_payload)

        resp_exists = await client.post(
            "/auth/login",
            json={
                "email": user_payload["email"],
                "password": "wrongpassword",
            },
        )
        resp_missing = await client.post(
            "/auth/login",
            json={
                "email": "nobody@example.com",
                "password": "wrongpassword",
            },
        )

        assert resp_exists.status_code == 401
        assert resp_missing.status_code == 401
        assert resp_exists.json()["detail"] == resp_missing.json()["detail"]


class TestProtectedEndpoints:
    @pytest.mark.asyncio
    async def test_invalid_token_returns_401(self, client: AsyncClient):
        resp = await client.get(
            "/projects", headers={"Authorization": "Bearer invalid.token.here"}
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_alg_none_token_rejected(self, client: AsyncClient):
        """A JWT signed with alg:none must be rejected — prevents alg:none attack (A02)."""
        none_token = "eyJhbGciOiJub25lIiwidHlwIjoiSldUIn0.eyJzdWIiOiIxIn0."
        resp = await client.get(
            "/projects", headers={"Authorization": f"Bearer {none_token}"}
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_expired_token_returns_401(self, client: AsyncClient):
        """A JWT whose exp claim is in the past must be rejected with 401."""
        from datetime import datetime, timedelta, timezone

        from jose import jwt as jose_jwt

        from app.config import settings

        expired_payload = {
            "sub": "999",
            "jti": "expired-test-jti",
            "exp": datetime.now(timezone.utc) - timedelta(minutes=5),
        }
        token = jose_jwt.encode(
            expired_payload, settings.secret_key, algorithm=settings.algorithm
        )
        resp = await client.get(
            "/projects", headers={"Authorization": f"Bearer {token}"}
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_token_missing_sub_claim_returns_401(self, client: AsyncClient):
        """A validly signed JWT without a sub claim must be rejected with 401."""
        from datetime import datetime, timedelta, timezone

        from jose import jwt as jose_jwt

        from app.config import settings

        no_sub_payload = {
            "jti": "no-sub-test-jti",
            "exp": datetime.now(timezone.utc) + timedelta(minutes=30),
        }
        token = jose_jwt.encode(
            no_sub_payload, settings.secret_key, algorithm=settings.algorithm
        )
        resp = await client.get(
            "/projects", headers={"Authorization": f"Bearer {token}"}
        )
        assert resp.status_code == 401
