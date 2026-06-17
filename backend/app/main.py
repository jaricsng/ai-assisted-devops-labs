from contextlib import asynccontextmanager

import structlog
from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import Base, engine, get_db
from app.logging_config import configure_logging
from app.middleware.body_limit import MaxBodySizeMiddleware
from app.middleware.logging import RequestLoggingMiddleware
from app.middleware.metrics import MetricsMiddleware
from app.middleware.rate_limit import RateLimitMiddleware
from app.middleware.security_headers import SecurityHeadersMiddleware
from app.routers import auth, projects, tasks
from app.telemetry import setup_telemetry, shutdown_telemetry
from app.well_known import router as well_known_router

configure_logging(settings.environment)
logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.environment == "development":
        # Dev-only convenience: create tables without running migrations.
        # Production deployments must run: alembic upgrade head
        from app.models import Comment, Project, Task, User  # noqa: F401

        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    if settings.otel_enabled:
        setup_telemetry(app, engine, settings.otlp_endpoint)
    logger.info("api_started", environment=settings.environment, version=app.version)
    yield
    shutdown_telemetry()
    logger.info("api_stopped")


app = FastAPI(
    title="Task Manager API",
    description="AI-Assisted DevOps Lab — three-tier task management application.",
    version="0.1.0",
    lifespan=lifespan,
)

# Middleware registration — Starlette applies in reverse registration order,
# so the LAST add_middleware call becomes the OUTERMOST layer (runs first).
#
# Execution order (outermost → innermost):
#   SecurityHeaders → CORS → MaxBodySize → RateLimit → Logging → Metrics → route
app.add_middleware(MetricsMiddleware)
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(
    RateLimitMiddleware, path="/auth/login", max_requests=10, window_seconds=60
)
app.add_middleware(MaxBodySizeMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)
app.add_middleware(SecurityHeadersMiddleware)

app.include_router(auth.router)
app.include_router(projects.router)
app.include_router(tasks.router)
app.include_router(well_known_router)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all handler that prevents stack traces from leaking to clients."""
    logger.exception("unhandled_error", path=request.url.path)
    return JSONResponse(
        status_code=500, content={"detail": "An internal error occurred."}
    )


@app.get("/health", tags=["observability"])
async def health():
    """Liveness probe — returns 200 when the API process is running.

    Includes the active environment name so operators can quickly confirm
    which environment they are connected to (staging vs production).
    """
    return {"status": "ok", "environment": settings.environment}


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
