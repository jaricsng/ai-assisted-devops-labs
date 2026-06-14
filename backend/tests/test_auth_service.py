"""Unit tests for auth_service — no database required."""
from jose import JWTError
import pytest

from app.services.auth_service import hash_password, verify_password, create_access_token, decode_access_token


def test_hash_and_verify_round_trip():
    hashed = hash_password("mysecret")
    assert verify_password("mysecret", hashed)


def test_wrong_password_does_not_verify():
    hashed = hash_password("mysecret")
    assert not verify_password("wrongpassword", hashed)


def test_create_and_decode_token():
    token = create_access_token("42")
    assert decode_access_token(token) == "42"


def test_tampered_token_raises():
    token = create_access_token("42")
    tampered = token[:-5] + "xxxxx"
    with pytest.raises(JWTError):
        decode_access_token(tampered)
