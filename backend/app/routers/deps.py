import structlog
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request

from app.database import get_db
from app.models.user import User
from app.repositories import user_repository
from app.services.auth_service import get_token_payload, is_revoked

bearer = HTTPBearer()


async def current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(bearer),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Resolve the authenticated user from the Bearer token in the Authorization header."""
    try:
        payload = get_token_payload(credentials.credentials)
        user_id = int(payload["sub"])
        jti = payload.get("jti")
    except (JWTError, ValueError, KeyError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token."
        )
    if jti and is_revoked(jti):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has been revoked."
        )
    user = await user_repository.get_by_id(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found."
        )
    request.state.user_id = user.id
    request.state.jti = jti
    # Bind user_id to the structlog context so every downstream log line —
    # including audit events — carries the authenticated user's identity.
    structlog.contextvars.bind_contextvars(user_id=str(user.id))
    return user
