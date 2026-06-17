"""Unit tests for auth_service — no database required."""
import pytest
from jose import JWTError

from app.services.auth_service import (
    create_access_token,
    decode_access_token,
    get_token_payload,
    hash_password,
    is_revoked,
    revoke_token,
    verify_password,
)


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


def test_get_token_payload_returns_full_dict():
    token = create_access_token("55")
    payload = get_token_payload(token)
    assert payload["sub"] == "55"
    assert "jti" in payload
    assert "exp" in payload


def test_jti_is_unique_per_token():
    t1 = create_access_token("1")
    t2 = create_access_token("1")
    assert get_token_payload(t1)["jti"] != get_token_payload(t2)["jti"]


def test_revoke_and_check_token():
    token = create_access_token("99")
    jti = get_token_payload(token)["jti"]
    assert not is_revoked(jti)
    revoke_token(jti)
    assert is_revoked(jti)
