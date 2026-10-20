from fastapi.testclient import TestClient

from app.main import create_app


def test_liveness_returns_versioned_contract() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/api/v1/health/live")
    assert response.status_code == 200
    assert response.json() == {"schema_version": 1, "status": "alive"}


def test_not_found_returns_safe_error_and_request_id() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/api/v1/missing")
    assert response.status_code == 404
    body = response.json()
    assert body["error"]["code"] == "not_found"
    assert body["error"]["request_id"] == response.headers["x-request-id"]
    assert len(body["error"]["request_id"]) == 36
