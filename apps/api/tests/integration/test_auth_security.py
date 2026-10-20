from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import psycopg
import pytest
from fastapi.testclient import TestClient
from redis.asyncio import Redis
from sqlalchemy.engine import make_url

pytestmark = pytest.mark.integration
PASSWORD = "Security-test-passphrase-42"


def connect(client: TestClient) -> psycopg.Connection:
    url = make_url(client.app.state.settings.database_url.get_secret_value())
    return psycopg.connect(
        url.set(drivername="postgresql").render_as_string(False), connect_timeout=5
    )


def register(client: TestClient, email: str = "security@example.com") -> dict:
    response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": PASSWORD, "display_name": "Security test"},
    )
    assert response.status_code == 201
    return response.json()


def test_session_password_and_csrf_are_hashed_and_expired_session_is_rejected(
    api_client: TestClient,
) -> None:
    register(api_client)
    with connect(api_client) as db:
        password_hash = db.execute("SELECT password_hash FROM users").fetchone()[0]
        token_hash, csrf_hash = db.execute("SELECT token_hash, csrf_hash FROM sessions").fetchone()
        assert password_hash.startswith("$argon2id$") and PASSWORD not in password_hash
        assert token_hash != api_client.cookies["sg_session"] and len(token_hash) == 64
        assert csrf_hash != api_client.cookies["sg_csrf"] and len(csrf_hash) == 64
        db.execute("UPDATE sessions SET expires_at=%s", (datetime.now(UTC) - timedelta(seconds=1),))
    assert api_client.get("/api/v1/users/me").status_code == 401
    api_client.cookies.clear()
    api_client.cookies.set("sg_session", "forged-session-value")
    assert api_client.get("/api/v1/users/me").status_code == 401


def test_inactive_member_cannot_read_existing_resources(api_client: TestClient) -> None:
    register(api_client)
    with connect(api_client) as db:
        db.execute("UPDATE tenant_members SET status='inactive'")
    assert api_client.get("/api/v1/users/me").status_code == 401
    assert api_client.get("/api/v1/research").status_code == 401


def test_concurrent_duplicate_registration_creates_only_one_personal_tenant(
    api_client: TestClient,
) -> None:
    payload = {"email": "race@example.com", "password": PASSWORD, "display_name": "Race"}
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(
                lambda _: api_client.post("/api/v1/auth/register", json=payload).status_code,
                range(2),
            )
        )
    assert sorted(results) == [201, 409]
    with connect(api_client) as db:
        assert db.execute("SELECT count(*) FROM users").fetchone()[0] == 1
        assert db.execute("SELECT count(*) FROM tenants").fetchone()[0] == 1
        assert db.execute("SELECT count(*) FROM tenant_members").fetchone()[0] == 1


def test_private_writes_require_csrf_and_idempotency_key(api_client: TestClient) -> None:
    register(api_client)
    payload = {"title": "Private write"}
    assert api_client.post("/api/v1/research", json=payload).status_code == 403
    headers = {"X-CSRF-Token": api_client.cookies["sg_csrf"]}
    assert api_client.post("/api/v1/research", json=payload, headers=headers).status_code == 422
    assert (
        api_client.post(
            "/api/v1/research",
            json={"title": " "},
            headers={**headers, "Idempotency-Key": str(uuid4())},
        ).status_code
        == 422
    )


def test_database_enforces_cross_tenant_links_roles_and_active_run_invariant(
    api_client: TestClient,
) -> None:
    first = register(api_client)
    headers = {"X-CSRF-Token": api_client.cookies["sg_csrf"], "Idempotency-Key": str(uuid4())}
    project = api_client.post(
        "/api/v1/research", json={"title": "DB constraints"}, headers=headers
    ).json()["data"]
    thread = api_client.post(
        "/api/v1/threads",
        json={"project_id": project["id"], "title": "Thread"},
        headers={**headers, "Idempotency-Key": str(uuid4())},
    ).json()["data"]
    other = register(api_client, "another@example.com")
    with connect(api_client) as db:
        with pytest.raises(psycopg.errors.ForeignKeyViolation), db.transaction():
            db.execute(
                "INSERT INTO threads (id,tenant_id,project_id,created_by,title,idempotency_key,"
                "request_hash) VALUES (%s,%s,%s,%s,'bad','bad-key','hash')",
                (uuid4(), other["tenant"]["id"], project["id"], other["user"]["id"]),
            )
        with pytest.raises(psycopg.errors.CheckViolation), db.transaction():
            db.execute("UPDATE tenant_members SET role='superadmin'")
        values = (
            uuid4(),
            first["tenant"]["id"],
            project["id"],
            thread["id"],
            first["user"]["id"],
            "run-key-1",
        )
        db.execute(
            "INSERT INTO runs (id,tenant_id,project_id,thread_id,user_id,idempotency_key) "
            "VALUES (%s,%s,%s,%s,%s,%s)",
            values,
        )
        with pytest.raises(psycopg.errors.UniqueViolation), db.transaction():
            db.execute(
                "INSERT INTO runs (id,tenant_id,project_id,thread_id,user_id,idempotency_key) "
                "VALUES (%s,%s,%s,%s,%s,%s)",
                (uuid4(), *values[1:5], "run-key-2"),
            )
        db.execute("UPDATE runs SET status='completed' WHERE id=%s", (values[0],))
        db.execute(
            "INSERT INTO runs (id,tenant_id,project_id,thread_id,user_id,idempotency_key) "
            "VALUES (%s,%s,%s,%s,%s,%s)",
            (uuid4(), *values[1:5], "run-key-3"),
        )


def test_invalid_registration_never_echoes_password(api_client: TestClient) -> None:
    response = api_client.post(
        "/api/v1/auth/register",
        json={"email": "not-an-email", "password": "short-secret", "display_name": ""},
    )
    assert response.status_code == 422
    assert "short-secret" not in response.text
    assert "not-an-email" not in response.text


def test_missing_origin_rejected_before_authentication_write(api_client: TestClient) -> None:
    api_client.headers.pop("origin")
    response = api_client.post(
        "/api/v1/auth/register",
        json={"email": "origin@example.com", "password": PASSWORD, "display_name": "Origin"},
    )
    assert response.status_code == 403


def test_redis_unavailable_does_not_bypass_authentication_rate_limit(
    api_client: TestClient,
) -> None:
    resources = api_client.app.state.resources
    original = resources.redis
    unavailable = Redis(host="127.0.0.1", port=1, socket_connect_timeout=0.1)
    resources.redis = unavailable
    try:
        response = api_client.post(
            "/api/v1/auth/login", json={"email": "missing@example.com", "password": PASSWORD}
        )
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "auth_temporarily_unavailable"
        assert "127.0.0.1" not in response.text
    finally:
        resources.redis = original
        assert api_client.portal is not None
        api_client.portal.call(unavailable.aclose)
