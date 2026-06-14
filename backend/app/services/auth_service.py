from datetime import datetime, timedelta, timezone

from jose import jwt
from passlib.context import CryptContext

from app.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """Return a bcrypt hash of the given plain-text password."""
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    """Return True if plain-text password matches the stored hash."""
    return pwd_context.verify(plain, hashed)


def create_access_token(subject: str) -> str:
    """Create a signed JWT with the given subject (user email or id)."""
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {"sub": subject, "exp": expire}
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def decode_access_token(token: str) -> str:
    """Decode a JWT and return the subject claim. Raises JWTError on failure."""
    payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
    return payload["sub"]
