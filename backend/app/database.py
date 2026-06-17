from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool

from app.config import settings

# In test mode, NullPool avoids the "Future attached to a different loop" error.
# Starlette's BaseHTTPMiddleware creates a new task per request; asyncpg Futures
# are tied to the task that created the connection. When the pool reuses a
# connection across requests (tasks), asyncpg raises RuntimeError.
# NullPool creates a fresh connection per request and closes it immediately,
# sidestepping the cross-task-boundary issue entirely.
if settings.environment in ("test", "testing"):
    engine = create_async_engine(settings.database_url, poolclass=NullPool)
else:
    engine = create_async_engine(
        settings.database_url,
        pool_size=20,
        max_overflow=30,
        pool_pre_ping=True,
        pool_recycle=3600,
        echo=settings.environment == "development",
    )
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session
