import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
from jose import jwt

from app.config import settings

# In-memory revoked token set — keyed by JTI.
# For multi-instance deployments, replace with a Redis-backed set.
# See docs/adr/0003-security-controls.md for the trade-off discussion.
_revoked_jtis: set[str] = set()


def hash_password(password: str) -> str:
    """Return a bcrypt hash of the given plain-text password."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """Return True if plain-text password matches the stored hash."""
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


def create_access_token(subject: str) -> str:
    """Create a signed JWT with the given subject and a unique jti claim."""
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {"sub": subject, "exp": expire, "jti": str(uuid.uuid4())}
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def get_token_payload(token: str) -> dict:
    """Decode a JWT and return the full payload dict. Raises JWTError on failure."""
    return jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])


def decode_access_token(token: str) -> str:
    """Decode a JWT and return the subject claim. Raises JWTError on failure."""
    return get_token_payload(token)["sub"]


def revoke_token(jti: str) -> None:
    """Add a JTI to the revocation set — token will be rejected on next use."""
    _revoked_jtis.add(jti)


def is_revoked(jti: str) -> bool:
    """Return True if this JTI has been revoked."""
    return jti in _revoked_jtis
