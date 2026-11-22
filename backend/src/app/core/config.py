"""Application settings, read from environment variables and the .env file."""

from functools import lru_cache
from importlib.metadata import PackageNotFoundError, version
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


def _package_version() -> str:
    try:
        return version("rag-saas-backend")
    except PackageNotFoundError:
        return "0.0.0"


class Settings(BaseSettings):
    """Runtime configuration.

    Every field can be overridden by an environment variable with the same name,
    for example ``LOG_LEVEL=DEBUG``. Missing required values fail at startup
    instead of failing later in the middle of a request.
    """

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: Literal["local", "test", "ci", "production"] = "local"
    app_version: str = Field(default_factory=_package_version)
    git_sha: str = "unknown"

    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    log_json: bool = True

    # SecretStr keeps the password out of logs, reprs and tracebacks.
    database_url: SecretStr
    db_connect_timeout_s: int = 2


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide settings. FastAPI dependencies use this function."""
    return Settings()
