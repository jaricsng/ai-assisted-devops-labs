from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


async def get_by_email(db: AsyncSession, email: str) -> User | None:
    """Return the active user with the given email, or None if not found or deleted."""
    result = await db.execute(
        select(User).where(User.email == email, User.deleted_at.is_(None))
    )
    return result.scalar_one_or_none()


async def get_by_id(db: AsyncSession, user_id: int) -> User | None:
    """Return the active user with the given id, or None if not found or deleted."""
    result = await db.execute(
        select(User).where(User.id == user_id, User.deleted_at.is_(None))
    )
    return result.scalar_one_or_none()


async def create(
    db: AsyncSession, email: str, full_name: str, hashed_password: str
) -> User:
    """Insert a new user and return the persisted instance."""
    user = User(email=email, full_name=full_name, hashed_password=hashed_password)
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def soft_delete(db: AsyncSession, user_id: int) -> None:
    """Soft-delete a user by setting deleted_at to the current UTC time."""
    result = await db.execute(
        select(User).where(User.id == user_id, User.deleted_at.is_(None))
    )
    user = result.scalar_one_or_none()
    if user:
        user.deleted_at = datetime.now(timezone.utc)
        await db.commit()
