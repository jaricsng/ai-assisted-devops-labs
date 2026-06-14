import time
from collections import defaultdict
from dataclasses import dataclass, field

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = structlog.get_logger(__name__)


@dataclass
class _Counters:
    requests_total: int = 0
    errors_4xx: int = 0
    errors_5xx: int = 0
    duration_sum_ms: float = 0.0
    slow_requests: int = 0          # > 500 ms
    path_counts: dict = field(default_factory=lambda: defaultdict(int))


# Module-level counters — simple in-process metrics without an external system.
# For production use, replace with Prometheus or OpenTelemetry counters.
_counters = _Counters()
SLOW_REQUEST_THRESHOLD_MS = 500


def get_metrics() -> dict:
    """Return a snapshot of current in-process counters.

    Exposed by GET /metrics for lightweight operational visibility.
    """
    total = _counters.requests_total or 1  # avoid division by zero
    return {
        "requests_total": _counters.requests_total,
        "errors_4xx": _counters.errors_4xx,
        "errors_5xx": _counters.errors_5xx,
        "slow_requests": _counters.slow_requests,
        "avg_duration_ms": round(_counters.duration_sum_ms / total, 2),
        "top_paths": dict(
            sorted(_counters.path_counts.items(), key=lambda x: x[1], reverse=True)[:10]
        ),
    }


class MetricsMiddleware(BaseHTTPMiddleware):
    """Collect request counts, error rates, latency, and slow-request counts.

    These in-process counters are intentionally simple — they reset on restart
    and are not shared across multiple API instances. For production multi-instance
    deployments, export to Prometheus via `prometheus-fastapi-instrumentator` instead.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = (time.perf_counter() - start) * 1000

        _counters.requests_total += 1
        _counters.duration_sum_ms += duration_ms
        _counters.path_counts[request.url.path] += 1

        if 400 <= response.status_code < 500:
            _counters.errors_4xx += 1
        elif response.status_code >= 500:
            _counters.errors_5xx += 1
            logger.warning(
                "server_error",
                path=request.url.path,
                status_code=response.status_code,
                duration_ms=round(duration_ms, 2),
            )

        if duration_ms > SLOW_REQUEST_THRESHOLD_MS:
            _counters.slow_requests += 1
            logger.warning(
                "slow_request",
                path=request.url.path,
                duration_ms=round(duration_ms, 2),
                threshold_ms=SLOW_REQUEST_THRESHOLD_MS,
            )

        return response
