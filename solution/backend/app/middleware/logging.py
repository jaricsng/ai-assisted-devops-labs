import time
import uuid

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.telemetry import get_current_trace_ids

logger = structlog.get_logger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log every HTTP request with method, path, status code, duration, and request ID.

    Binds request_id and OTel trace_id/span_id to structlog context so every log
    line emitted during a request carries identifiers for both log-based and
    trace-based correlation in Grafana.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = str(uuid.uuid4())
        start = time.perf_counter()

        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            method=request.method,
            path=request.url.path,
        )

        logger.info("request_started")

        try:
            response = await call_next(request)
        except Exception:
            duration_ms = round((time.perf_counter() - start) * 1000, 2)
            logger.exception("request_failed", duration_ms=duration_ms)
            raise

        duration_ms = round((time.perf_counter() - start) * 1000, 2)

        # Bind authenticated user_id if set by the route handler.
        if hasattr(request.state, "user_id"):
            structlog.contextvars.bind_contextvars(user_id=request.state.user_id)

        # Inject OTel trace context after call_next so the span is active.
        # These IDs let Grafana link from a log line directly to the Jaeger trace.
        trace_ctx = get_current_trace_ids()
        logger.info(
            "request_finished",
            status_code=response.status_code,
            duration_ms=duration_ms,
            **trace_ctx,
        )

        response.headers["X-Request-ID"] = request_id
        response.headers["server"] = "task-manager"
        return response
