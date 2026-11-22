"""Request context: request id, access log, timing and a safety net for errors."""

import re
import time
import uuid
from collections.abc import Awaitable, Callable

from fastapi import Request, Response, status
from fastapi.responses import JSONResponse
from loguru import logger

REQUEST_ID_HEADER = "X-Request-ID"

# Only short ids made of safe characters are reused, which prevents log injection.
_VALID_REQUEST_ID = re.compile(r"[A-Za-z0-9\-]{1,64}")

CallNext = Callable[[Request], Awaitable[Response]]


def resolve_request_id(incoming: str | None) -> str:
    """Reuse a well-formed incoming id so a request can be followed across services."""
    if incoming and _VALID_REQUEST_ID.fullmatch(incoming):
        return incoming
    return uuid.uuid4().hex


async def request_context_middleware(request: Request, call_next: CallNext) -> Response:
    """Bind a request id to every log line of the request and return it in a header."""
    request_id = resolve_request_id(request.headers.get(REQUEST_ID_HEADER))
    request.state.request_id = request_id
    start = time.perf_counter()

    with logger.contextualize(request_id=request_id):
        try:
            response = await call_next(request)
        except Exception:
            logger.exception("Unhandled error")
            response = JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={"detail": "Internal server error", "request_id": request_id},
            )
        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        logger.info(
            "{method} {path} -> {status_code} in {duration_ms} ms",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=duration_ms,
        )

    response.headers[REQUEST_ID_HEADER] = request_id
    return response
