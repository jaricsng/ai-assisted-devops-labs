"""Security property tests — transport, CORS, headers, and schema validation.

These tests verify defence-in-depth properties that are also checked by the
manual pen-test script (pen-tests/manual-checks.sh) but were not covered by
any existing unit or integration test file.
"""
import pytest
from pydantic import ValidationError

from app.schemas.user import UserCreate


# ── Password validator unit tests ─────────────────────────────────────────────


class TestPasswordValidator:
    """Direct unit tests for the Pydantic password_strength validator.

    Covers schemas/user.py lines 16 and 18 (no-uppercase and no-digit raise
    paths) without going through the HTTP stack.
    """

    def test_password_no_uppercase_raises(self):
        with pytest.raises(ValidationError, match="uppercase"):
            UserCreate(email="test@example.com", full_name="T", password="alllower1")

    def test_password_no_digit_raises(self):
        with pytest.raises(ValidationError, match="digit"):
            UserCreate(email="test@example.com", full_name="T", password="NoDigitsZZZ")

    def test_strong_password_accepted(self):
        user = UserCreate(email="test@example.com", full_name="T", password="Strong1Pass")
        assert user.password == "Strong1Pass"


# ── CORS policy ───────────────────────────────────────────────────────────────


class TestCORS:
    """CORSMiddleware must not reflect origins outside the allowlist."""

    @pytest.mark.asyncio
    async def test_cors_does_not_reflect_disallowed_origin(self, client):
        resp = await client.get("/health", headers={"origin": "https://evil.com"})
        acao = resp.headers.get("access-control-allow-origin", "")
        assert acao != "https://evil.com", (
            "CORS must not reflect an origin outside the allowlist"
        )

    @pytest.mark.asyncio
    async def test_cors_reflects_allowed_origin(self, client):
        resp = await client.get("/health", headers={"origin": "http://localhost:5173"})
        assert resp.headers.get("access-control-allow-origin") == "http://localhost:5173"

    @pytest.mark.asyncio
    async def test_cors_preflight_allowed_origin_returns_200(self, client):
        """OPTIONS preflight from an allowed origin must include CORS headers."""
        resp = await client.options(
            "/projects",
            headers={
                "origin": "http://localhost:5173",
                "access-control-request-method": "POST",
                "access-control-request-headers": "Authorization, Content-Type",
            },
        )
        assert resp.status_code == 200
        assert resp.headers.get("access-control-allow-origin") == "http://localhost:5173"
        assert "access-control-allow-methods" in resp.headers

    @pytest.mark.asyncio
    async def test_cors_preflight_disallowed_origin_not_reflected(self, client):
        """OPTIONS preflight from a disallowed origin must not include ACAO header."""
        resp = await client.options(
            "/projects",
            headers={
                "origin": "https://attacker.com",
                "access-control-request-method": "POST",
            },
        )
        acao = resp.headers.get("access-control-allow-origin", "")
        assert acao != "https://attacker.com"


# ── Response header leakage ───────────────────────────────────────────────────


class TestResponseHeaders:
    """API must not fingerprint server technology in response headers."""

    @pytest.mark.asyncio
    async def test_server_header_does_not_expose_version(self, client):
        resp = await client.get("/health")
        server = resp.headers.get("server", "").lower()
        assert "fastapi" not in server
        assert "uvicorn" not in server
        assert "python" not in server

    @pytest.mark.asyncio
    async def test_x_powered_by_header_absent(self, client):
        """X-Powered-By header must not be present — prevents server fingerprinting."""
        resp = await client.get("/health")
        assert "x-powered-by" not in resp.headers
