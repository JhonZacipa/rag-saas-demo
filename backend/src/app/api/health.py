"""Liveness and readiness probes.

- ``GET /health`` answers "is the process alive?". It never touches dependencies,
  so an orchestrator does not restart the API just because the database is down.
- ``GET /health/ready`` answers "can it serve traffic?". It checks the database
  and returns 503 when a dependency is unavailable.
"""

from collections.abc import Awaitable, Callable
from typing import Annotated, Literal

import psycopg
from fastapi import APIRouter, Depends, Response, status
from loguru import logger
from pydantic import BaseModel

from app.core.config import Settings, get_settings

router = APIRouter(prefix="/health", tags=["health"])

SettingsDep = Annotated[Settings, Depends(get_settings)]
DatabaseCheck = Callable[[], Awaitable[bool]]


class HealthResponse(BaseModel):
    status: Literal["ok"]
    version: str
    git_sha: str
    environment: str


class ReadinessResponse(BaseModel):
    status: Literal["ready", "not_ready"]
    checks: dict[str, bool]


def get_database_check(settings: SettingsDep) -> DatabaseCheck:
    """Build the database probe. Tests replace it through dependency overrides."""

    async def check() -> bool:
        try:
            async with await psycopg.AsyncConnection.connect(
                settings.database_url.get_secret_value(),
                connect_timeout=settings.db_connect_timeout_s,
            ) as conn:
                await conn.execute("SELECT 1")
        except (psycopg.Error, OSError) as exc:
            logger.warning("Database check failed: {error}", error=repr(exc))
            return False
        return True

    return check


@router.get("", response_model=HealthResponse)
def liveness(settings: SettingsDep) -> HealthResponse:
    return HealthResponse(
        status="ok",
        version=settings.app_version,
        git_sha=settings.git_sha,
        environment=settings.app_env,
    )


@router.get(
    "/ready",
    response_model=ReadinessResponse,
    responses={status.HTTP_503_SERVICE_UNAVAILABLE: {"model": ReadinessResponse}},
)
async def readiness(
    response: Response,
    check_database: Annotated[DatabaseCheck, Depends(get_database_check)],
) -> ReadinessResponse:
    database_ok = await check_database()
    if not database_ok:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return ReadinessResponse(
        status="ready" if database_ok else "not_ready",
        checks={"database": database_ok},
    )
