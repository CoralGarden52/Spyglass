from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.integration
PASSWORD = "Research-example-passphrase-42"


def register(client: TestClient, email: str = "alice@example.com") -> dict:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": PASSWORD,
            "display_name": "研究员 Alice",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def csrf(client: TestClient) -> dict[str, str]:
    return {"X-CSRF-Token": client.cookies["sg_csrf"]}


def test_register_me_logout_login_and_default_personal_tenant(api_client: TestClient) -> None:
    identity = register(api_client)
    assert identity["schema_version"] == 1
    assert identity["user"]["email"] == "alice@example.com"
    assert identity["tenant"]["role"] == "owner"
    assert api_client.get("/api/v1/users/me").json() == identity
    session = api_client.cookies["sg_session"]
    assert api_client.post("/api/v1/auth/logout", headers=csrf(api_client)).status_code == 204
    assert api_client.get("/api/v1/users/me").status_code == 401
    api_client.cookies.set("sg_session", session)
    assert api_client.get("/api/v1/users/me").status_code == 401
    api_client.cookies.clear()
    response = api_client.post(
        "/api/v1/auth/login", json={"email": "ALICE@example.com", "password": PASSWORD}
    )
    assert response.status_code == 200
    assert response.json()["tenant"]["id"] == identity["tenant"]["id"]


def test_registration_is_atomic_and_normalizes_email(api_client: TestClient) -> None:
    identity = register(api_client)
    response = api_client.post(
        "/api/v1/auth/register",
        json={
            "email": "ALICE@example.com",
            "password": PASSWORD,
            "display_name": "重复账户",
        },
    )
    assert response.status_code == 409
    assert api_client.get("/api/v1/users/me").json()["tenant"]["id"] == identity["tenant"]["id"]


def test_bad_login_does_not_disclose_account_existence(api_client: TestClient) -> None:
    register(api_client)
    for email in ["alice@example.com", "missing@example.com"]:
        response = api_client.post(
            "/api/v1/auth/login", json={"email": email, "password": "incorrect-password-42"}
        )
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "invalid_credentials"


def test_auth_cookie_attributes_and_csrf_checks(api_client: TestClient) -> None:
    response = api_client.post(
        "/api/v1/auth/register",
        json={"email": "alice@example.com", "password": PASSWORD, "display_name": "Alice"},
    )
    assert response.status_code == 201
    cookies = response.headers.get_list("set-cookie")
    session = next(value for value in cookies if value.startswith("sg_session="))
    assert "HttpOnly" in session and "SameSite=lax" in session and "Path=/" in session
    assert api_client.post("/api/v1/auth/logout").status_code == 403
    assert (
        api_client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": "forged"}).status_code
        == 403
    )
    assert (
        api_client.post(
            "/api/v1/auth/logout", headers={**csrf(api_client), "Origin": "https://evil.example"}
        ).status_code
        == 403
    )
    assert api_client.get("/api/v1/users/me").status_code == 200


def test_login_and_registration_reject_untrusted_origin(api_client: TestClient) -> None:
    for endpoint in ["register", "login"]:
        response = api_client.post(
            f"/api/v1/auth/{endpoint}",
            headers={"Origin": "https://evil.example"},
            json={"email": "alice@example.com", "password": PASSWORD, "display_name": "Alice"},
        )
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "origin_rejected"


def test_login_is_rate_limited_in_real_redis(api_client: TestClient) -> None:
    api_client.app.state.settings.auth_rate_limit = 2
    for _ in range(2):
        assert (
            api_client.post(
                "/api/v1/auth/login", json={"email": "missing@example.com", "password": PASSWORD}
            ).status_code
            == 401
        )
    response = api_client.post(
        "/api/v1/auth/login", json={"email": "missing@example.com", "password": PASSWORD}
    )
    assert response.status_code == 429
    assert int(response.headers["retry-after"]) > 0


@pytest.mark.parametrize(
    "path",
    [
        "/users/me",
        "/research",
        f"/research/{uuid4()}",
        f"/threads/{uuid4()}",
        f"/threads/{uuid4()}/messages",
    ],
)
def test_private_routes_require_authentication(api_client: TestClient, path: str) -> None:
    response = api_client.get("/api/v1" + path)
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


def test_projects_and_threads_are_tenant_isolated_and_idempotent(api_client: TestClient) -> None:
    register(api_client)
    payload = {
        "title": "Alice 的私有调研",
        "mode": "standard",
        "scenario_skill_id": "general_analysis",
    }
    headers = {**csrf(api_client), "Idempotency-Key": str(uuid4())}
    project = api_client.post("/api/v1/research", json=payload, headers=headers)
    assert project.status_code == 201
    project_id = project.json()["data"]["id"]
    assert (
        api_client.post("/api/v1/research", json=payload, headers=headers).json()["data"]["id"]
        == project_id
    )
    assert (
        api_client.post(
            "/api/v1/research", json={**payload, "title": "different"}, headers=headers
        ).status_code
        == 409
    )
    assert api_client.get("/api/v1/research").json()["meta"]["total"] == 1
    thread = api_client.post(
        "/api/v1/threads",
        json={"project_id": project_id, "title": "会话"},
        headers={**csrf(api_client), "Idempotency-Key": str(uuid4())},
    )
    assert thread.status_code == 201
    thread_id = thread.json()["data"]["id"]
    assert api_client.get(f"/api/v1/threads/{thread_id}/messages").json()["data"] == []
    api_client.post("/api/v1/auth/logout", headers=csrf(api_client))
    register(api_client, "bob@example.com")
    assert api_client.get("/api/v1/research").json()["meta"]["total"] == 0
    for path in [
        f"/research/{project_id}",
        f"/threads/{thread_id}",
        f"/threads/{thread_id}/messages",
    ]:
        assert api_client.get("/api/v1" + path).status_code == 404
    assert (
        api_client.post(
            "/api/v1/threads",
            json={"project_id": project_id, "title": "forged"},
            headers={**csrf(api_client), "Idempotency-Key": str(uuid4())},
        ).status_code
        == 404
    )
    assert (
        api_client.post(
            "/api/v1/research",
            json={**payload, "tenant_id": project.json()["data"]["tenant_id"]},
            headers={**csrf(api_client), "Idempotency-Key": str(uuid4())},
        ).status_code
        == 422
    )
