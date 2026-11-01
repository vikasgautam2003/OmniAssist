import time
from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.observability.logging import get_logger, new_request

logger = get_logger("http")

# Paths that would otherwise dominate the log. A load balancer probing every
# ten seconds is 8,640 lines a day saying nothing.
QUIET_PATHS = frozenset({"/healthz"})


class RequestLogging(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request_id = new_request()
        started = time.perf_counter()

        try:
            response = await call_next(request)
        except Exception:
            # Logged here and re-raised: the handler below us has already
            # failed, and without this the only record is a stack trace with
            # no request id, no path and no duration attached.
            logger.exception(
                "request.failed",
                method=request.method,
                path=request.url.path,
                duration_ms=round((time.perf_counter() - started) * 1000, 1),
            )
            raise

        duration = round((time.perf_counter() - started) * 1000, 1)
        response.headers["X-Request-ID"] = request_id

        if request.url.path not in QUIET_PATHS:
            logger.info(
                "request",
                method=request.method,
                path=request.url.path,
                status=response.status_code,
                duration_ms=duration,
            )

        return response
