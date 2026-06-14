from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


async def get_by_email(db: AsyncSession, email: str) -> User | None:
    """Return the user with the given email, or None if not found."""
    result = await db.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


async def get_by_id(db: AsyncSession, user_id: int) -> User | None:
    """Return the user with the given id, or None if not found."""
    return await db.get(User, user_id)


async def create(db: AsyncSession, email: str, full_name: str, hashed_password: str) -> User:
    """Insert a new user and return the persisted instance."""
    user = User(email=email, full_name=full_name, hashed_password=hashed_password)
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user
