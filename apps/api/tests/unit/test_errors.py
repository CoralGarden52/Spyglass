from fastapi import Query
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


def test_validation_omits_rejected_inputs() -> None:
    app = create_app(Settings(_env_file=None))

    @app.get("/test/validation")
    async def validate(limit: int = Query(ge=1)) -> dict[str, int]:
        return {"limit": limit}

    with TestClient(app) as client:
        response = client.get("/test/validation?limit=test-secret-must-not-echo")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
    assert response.json()["error"]["details"] == [{"field": "query.limit", "type": "int_parsing"}]
    assert "test-secret-must-not-echo" not in response.text


def test_unexpected_exception_does_not_leak_internal_details() -> None:
    app = create_app(Settings(_env_file=None))

    @app.get("/test/error")
    async def crash() -> None:
        raise RuntimeError("private-password-and-database-host")

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/test/error")
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "internal_error"
    assert "private-password" not in response.text
    assert response.headers["x-request-id"] == response.json()["error"]["request_id"]


def test_cors_does_not_allow_unknown_origins() -> None:
    with TestClient(create_app(Settings(_env_file=None))) as client:
        response = client.get("/api/v1/health/live", headers={"Origin": "https://untrusted.test"})
    assert "access-control-allow-origin" not in response.headers


def test_method_not_allowed_preserves_required_allow_header() -> None:
    with TestClient(create_app(Settings(_env_file=None))) as client:
        response = client.post("/api/v1/health/live")
    assert response.status_code == 405
    assert response.json()["error"]["code"] == "method_not_allowed"
    assert response.headers.get("allow") == "GET"
