import structlog
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import Base, engine, get_db
from app.logging_config import configure_logging
from app.middleware.logging import RequestLoggingMiddleware
from app.middleware.metrics import MetricsMiddleware
from app.routers import auth, projects, tasks
from app.telemetry import setup_telemetry, shutdown_telemetry

configure_logging(settings.environment)
logger = structlog.get_logger(__name__)

app = FastAPI(
    title="Task Manager API",
    description="AI-Assisted DevOps Lab — three-tier task management application.",
    version="0.1.0",
)

# Middleware order matters: outer middleware wraps inner ones.
# MetricsMiddleware runs first (outermost) so it captures total wall-clock time.
# RequestLoggingMiddleware runs second so request_id is bound before any logging.
app.add_middleware(MetricsMiddleware)
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(projects.router)
app.include_router(tasks.router)


@app.get("/health", tags=["observability"])
async def health():
    """Liveness probe — returns 200 when the API process is running."""
    return {"status": "ok"}


@app.get("/ready", tags=["observability"])
async def ready(db: AsyncSession = Depends(get_db)):
    """Readiness probe — returns 200 only when the API can reach the database."""
    try:
        await db.execute(text("SELECT 1"))
        logger.debug("readiness_check_passed")
        return {"status": "ready", "db": "ok"}
    except Exception as exc:
        logger.error("readiness_check_failed", error=str(exc))
        from fastapi import HTTPException, status
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"status": "not ready", "db": "unreachable"},
        )


@app.on_event("startup")
async def on_startup():
    if settings.environment == "development":
        # DEV-ONLY: create tables from ORM models so the app runs without Alembic.
        # Module 4 replaces this with proper Alembic migrations before shipping to prod.
        from app.models import Comment, Project, Task, User  # noqa: F401
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    if settings.otel_enabled:
        # setup_telemetry mounts /metrics (Prometheus text format) and wires
        # FastAPIInstrumentor + SQLAlchemyInstrumentor to the OTel SDK.
        setup_telemetry(app, engine, settings.otlp_endpoint)
    logger.info("api_started", environment=settings.environment, version=app.version)


@app.on_event("shutdown")
async def on_shutdown():
    shutdown_telemetry()
    logger.info("api_stopped")
