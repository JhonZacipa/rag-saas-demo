import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.middleware import REQUEST_ID_HEADER, resolve_request_id


def test_generates_request_id_when_missing(client: TestClient) -> None:
    response = client.get("/health")

    assert len(response.headers[REQUEST_ID_HEADER]) == 32


def test_propagates_valid_incoming_request_id(client: TestClient) -> None:
    response = client.get("/health", headers={REQUEST_ID_HEADER: "trace-123"})

    assert response.headers[REQUEST_ID_HEADER] == "trace-123"


@pytest.mark.parametrize("incoming", ["", "has spaces", "x" * 65, "line\nbreak", "<script>"])
def test_replaces_malformed_request_ids(incoming: str) -> None:
    resolved = resolve_request_id(incoming)

    assert resolved != incoming
    assert len(resolved) == 32


def test_unhandled_error_returns_500_with_request_id(client: TestClient) -> None:
    app = client.app
    assert isinstance(app, FastAPI)

    @app.get("/boom")
    def boom() -> None:
        raise RuntimeError("unexpected failure")

    response = client.get("/boom", headers={REQUEST_ID_HEADER: "req-42"})

    assert response.status_code == 500
    assert response.json() == {"detail": "Internal server error", "request_id": "req-42"}
    assert response.headers[REQUEST_ID_HEADER] == "req-42"
