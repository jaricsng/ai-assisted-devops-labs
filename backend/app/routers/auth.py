import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.repositories import user_repository
from app.routers.deps import current_user
from app.schemas.user import LoginRequest, Token, UserCreate, UserRead
from app.services.auth_service import (
    create_access_token,
    hash_password,
    revoke_token,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["auth"])
logger = structlog.get_logger(__name__)


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def register(payload: UserCreate, db: AsyncSession = Depends(get_db)):
    existing = await user_repository.get_by_email(db, payload.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Email already registered."
        )
    user = await user_repository.create(
        db, payload.email, payload.full_name, hash_password(payload.password)
    )
    logger.info("audit", action="REGISTER", resource="user", resource_id=user.id)
    return user


@router.post("/login", response_model=Token)
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_db)):
    user = await user_repository.get_by_email(db, payload.email)
    if not user or not verify_password(payload.password, user.hashed_password):
        logger.info(
            "audit", action="LOGIN_FAILED", resource="user", email=payload.email
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials."
        )
    logger.info("audit", action="LOGIN_SUCCESS", resource="user", resource_id=user.id)
    return Token(access_token=create_access_token(str(user.id)))


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(request: Request, user: User = Depends(current_user)):
    jti = getattr(request.state, "jti", None)
    if jti:
        revoke_token(jti)
    logger.info(
        "audit", action="LOGOUT", resource="session", resource_id=jti, user_id=user.id
    )


@router.delete("/users/me", status_code=status.HTTP_204_NO_CONTENT)
async def delete_account(
    user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
):
    await user_repository.soft_delete(db, user.id)
    logger.info("audit", action="USER_DELETED", resource="user", resource_id=user.id)
