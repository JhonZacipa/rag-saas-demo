"""FastAPI application factory.

Run it with ``uvicorn app.main:create_app --factory``. A factory instead of a
module-level ``app`` lets tests and scripts build the app with their own settings.
"""

from fastapi import FastAPI

from app.api import health
from app.core.config import Settings, get_settings
from app.core.logging import configure_logging
from app.core.middleware import request_context_middleware


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(
        settings.log_level,
        settings.log_json,
        app_version=settings.app_version,
        git_sha=settings.git_sha,
        environment=settings.app_env,
    )

    app = FastAPI(title="Dental Clinic Assistant API", version=settings.app_version)
    # Every dependency that asks for settings receives the same instance.
    app.dependency_overrides[get_settings] = lambda: settings
    app.middleware("http")(request_context_middleware)
    app.include_router(health.router)
    return app
