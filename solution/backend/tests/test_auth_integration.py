"""Integration tests for authentication endpoints."""
import pytest
from httpx import AsyncClient


@pytest.fixture
def user_payload():
    return {"email": "alice@example.com", "full_name": "Alice", "password": "Alice123!"}


class TestRegister:
    async def test_register_creates_user(self, client: AsyncClient, user_payload):
        resp = await client.post("/auth/register", json=user_payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["email"] == user_payload["email"]
        assert data["full_name"] == user_payload["full_name"]
        assert "id" in data
        assert "hashed_password" not in data

    async def test_register_duplicate_email_returns_409(self, client: AsyncClient, user_payload):
        await client.post("/auth/register", json=user_payload)
        resp = await client.post("/auth/register", json=user_payload)
        assert resp.status_code == 409

    async def test_register_weak_password_returns_422(self, client: AsyncClient):
        resp = await client.post("/auth/register", json={
            "email": "weak@example.com", "full_name": "Weak", "password": "abc"
        })
        assert resp.status_code == 422

    async def test_register_empty_password_returns_422(self, client: AsyncClient):
        resp = await client.post("/auth/register", json={
            "email": "empty@example.com", "full_name": "Empty", "password": ""
        })
        assert resp.status_code == 422

    async def test_register_invalid_email_returns_422(self, client: AsyncClient):
        resp = await client.post("/auth/register", json={
            "email": "notanemail", "full_name": "Bad", "password": "Valid123!"
        })
        assert resp.status_code == 422


class TestLogin:
    async def test_login_returns_access_token(self, client: AsyncClient, user_payload):
        await client.post("/auth/register", json=user_payload)
        resp = await client.post("/auth/login", json={
            "email": user_payload["email"], "password": user_payload["password"]
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    async def test_login_wrong_password_returns_401(self, client: AsyncClient, user_payload):
        await client.post("/auth/register", json=user_payload)
        resp = await client.post("/auth/login", json={
            "email": user_payload["email"], "password": "wrongpassword"
        })
        assert resp.status_code == 401

    async def test_login_unknown_email_returns_401(self, client: AsyncClient):
        resp = await client.post("/auth/login", json={
            "email": "nobody@example.com", "password": "password123"
        })
        assert resp.status_code == 401

    async def test_login_error_responses_identical_for_existing_vs_nonexistent(
        self, client: AsyncClient, user_payload
    ):
        """Verify user enumeration is not possible via differing error messages."""
        await client.post("/auth/register", json=user_payload)
        resp_exists = await client.post("/auth/login", json={
            "email": user_payload["email"], "password": "wrongpassword"
        })
        resp_missing = await client.post("/auth/login", json={
            "email": "nobody@example.com", "password": "wrongpassword"
        })
        assert resp_exists.json()["detail"] == resp_missing.json()["detail"]


class TestProtectedEndpoints:
    async def test_unauthenticated_request_returns_403(self, client: AsyncClient):
        resp = await client.get("/projects")
        assert resp.status_code in (401, 403)

    async def test_invalid_token_returns_401(self, client: AsyncClient):
        resp = await client.get(
            "/projects", headers={"Authorization": "Bearer invalid.token.here"}
        )
        assert resp.status_code == 401

    async def test_alg_none_token_rejected(self, client: AsyncClient):
        none_token = "eyJhbGciOiJub25lIiwidHlwIjoiSldUIn0.eyJzdWIiOiIxIn0."
        resp = await client.get(
            "/projects", headers={"Authorization": f"Bearer {none_token}"}
        )
        assert resp.status_code == 401
