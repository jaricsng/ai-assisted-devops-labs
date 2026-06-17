from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

_MAX_BYTES = 1_048_576  # 1 MiB


class MaxBodySizeMiddleware(BaseHTTPMiddleware):
    """Reject requests whose Content-Length exceeds 1 MiB to prevent DoS via large payloads."""

    async def dispatch(self, request: Request, call_next) -> Response:
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > _MAX_BYTES:
            return JSONResponse(
                status_code=413,
                content={"detail": "Request body too large. Maximum size is 1 MiB."},
            )
        return await call_next(request)
