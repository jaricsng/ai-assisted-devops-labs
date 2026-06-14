"""Sliding-window in-memory rate limiter for sensitive endpoints.

Keyed by client IP. Uses a deque of timestamps so old entries drop off
automatically without a background sweeper task.
"""

import time
from collections import defaultdict, deque
from typing import Deque

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Block requests to `path` that exceed `max_requests` within `window_seconds`."""

    def __init__(self, app, *, path: str, max_requests: int = 5, window_seconds: int = 60):
        super().__init__(app)
        self._path = path
        self._max = max_requests
        self._window = window_seconds
        self._buckets: dict[str, Deque[float]] = defaultdict(deque)

    def _client_ip(self, request: Request) -> str:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    async def dispatch(self, request: Request, call_next) -> Response:
        if request.url.path != self._path or request.method != "POST":
            return await call_next(request)

        ip = self._client_ip(request)
        now = time.monotonic()
        bucket = self._buckets[ip]

        # Drop timestamps outside the sliding window
        cutoff = now - self._window
        while bucket and bucket[0] < cutoff:
            bucket.popleft()

        if len(bucket) >= self._max:
            retry_after = int(self._window - (now - bucket[0])) + 1
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many login attempts. Please try again later."},
                headers={"Retry-After": str(retry_after)},
            )

        bucket.append(now)
        return await call_next(request)
