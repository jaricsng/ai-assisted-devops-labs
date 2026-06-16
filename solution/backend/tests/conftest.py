import os

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.database import Base
from app.main import app
from app.middleware.rate_limit import reset_for_testing

# Use the running PostgreSQL container. Inside `docker compose exec api` the
# DATABASE_URL env var is already set. Falls back to the compose default so the
# fixture works without extra config when the stack is up.
TEST_DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+asyncpg://taskuser:taskpass@db:5432/taskmanager",
)


@pytest_asyncio.fixture(scope="session")
async def engine():
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db(engine):
    # Available for future integration tests that need explicit DB access.
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session
        await session.rollback()


@pytest.fixture(autouse=True)
def clear_rate_limit_buckets():
    """Reset in-memory rate-limit state before each test.

    All ASGI test requests share the 'unknown' client IP, so without this
    reset the shared bucket fills after ~10 login calls and subsequent tests
    receive 429 instead of the expected response.
    """
    reset_for_testing()


@pytest_asyncio.fixture
async def client():
    # No get_db override: the app creates its sessions inside the request task,
    # so asyncpg Futures never cross anyio task boundaries (the root cause of
    # the "Future attached to a different loop" error from BaseHTTPMiddleware).
    # Observability tests are all read-only — test isolation is not needed here.
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
