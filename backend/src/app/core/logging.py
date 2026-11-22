"""Structured logging with loguru.

Standard library and uvicorn logs are routed through loguru, so every log line
shares the same format and carries the same context: request id, app version,
git commit and environment.
"""

import logging
import sys
from types import FrameType
from typing import TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    from loguru import Record

_HUMAN_FORMAT = (
    "<green>{time:HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | "
    "<cyan>{extra[request_id]}</cyan> | {message}"
)


class InterceptHandler(logging.Handler):
    """Forward standard logging records to loguru, keeping the original caller."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            level: str | int = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        frame: FrameType | None = logging.currentframe()
        depth = 2
        while frame is not None and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())


def _ensure_request_id(record: "Record") -> None:
    # Logs emitted outside a request (startup, shutdown) still need the field.
    record["extra"].setdefault("request_id", "-")


def configure_logging(level: str, json_logs: bool, **static_context: str) -> None:
    """Configure loguru as the single logging sink for the process.

    ``static_context`` is attached to every log line; it is the version
    fingerprint that lets you tell which build produced a given log.
    """
    logger.remove()
    logger.configure(extra=static_context, patcher=_ensure_request_id)
    if json_logs:
        logger.add(sys.stdout, level=level, serialize=True, backtrace=False, diagnose=False)
    else:
        logger.add(sys.stdout, level=level, format=_HUMAN_FORMAT, backtrace=False, diagnose=False)

    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)
    for name in ("uvicorn", "uvicorn.error"):
        std_logger = logging.getLogger(name)
        std_logger.handlers = [InterceptHandler()]
        std_logger.propagate = False
    # The request middleware already writes one access line per request.
    logging.getLogger("uvicorn.access").disabled = True
