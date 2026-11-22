from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.health import DatabaseCheck, get_database_check


def _fake_database_check(result: bool) -> DatabaseCheck:
    async def check() -> bool:
        return result

    return check


def _override_database(client: TestClient, result: bool) -> None:
    app = client.app
    assert isinstance(app, FastAPI)
    app.dependency_overrides[get_database_check] = lambda: _fake_database_check(result)


def test_liveness_reports_version_fingerprint(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["git_sha"] == "abc1234"
    assert body["environment"] == "test"
    assert body["version"]


def test_readiness_is_ready_when_database_answers(client: TestClient) -> None:
    _override_database(client, result=True)

    response = client.get("/health/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready", "checks": {"database": True}}


def test_readiness_returns_503_when_database_is_down(client: TestClient) -> None:
    _override_database(client, result=False)

    response = client.get("/health/ready")

    assert response.status_code == 503
    assert response.json() == {"status": "not_ready", "checks": {"database": False}}


def test_readiness_with_unreachable_database_is_not_ready(
    client: TestClient, captured_logs: list[str]
) -> None:
    # Uses the real probe against a port where nothing listens.
    response = client.get("/health/ready")

    assert response.status_code == 503
    failure = next(message for message in captured_logs if "Database check failed" in message)
    # The probe must fail because nothing listens, not because of the event loop.
    assert "ProactorEventLoop" not in failure
