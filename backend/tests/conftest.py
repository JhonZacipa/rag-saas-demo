import asyncio
import sys
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from loguru import logger
from pydantic import SecretStr

from app.core.config import Settings
from app.main import create_app

# psycopg's async mode does not support the ProactorEventLoop that Python uses by
# default on Windows, so tests run the app on a SelectorEventLoop there.
# Linux and macOS already use a selector loop.
_BACKEND_OPTIONS: dict[str, Any] = (
    {"loop_factory": asyncio.SelectorEventLoop} if sys.platform == "win32" else {}
)


@pytest.fixture
def settings() -> Settings:
    return Settings(
        app_env="test",
        git_sha="abc1234",
        log_json=False,
        database_url=SecretStr("postgresql://user:pass@127.0.0.1:1/db"),
        db_connect_timeout_s=1,
    )


@pytest.fixture
def client(settings: Settings) -> Iterator[TestClient]:
    with TestClient(create_app(settings), backend_options=_BACKEND_OPTIONS) as test_client:
        yield test_client


@pytest.fixture
def captured_logs(client: TestClient) -> Iterator[list[str]]:
    """Collect log messages emitted while the test runs."""
    messages: list[str] = []
    sink_id = logger.add(lambda message: messages.append(message.record["message"]), level="DEBUG")
    yield messages
    logger.remove(sink_id)
