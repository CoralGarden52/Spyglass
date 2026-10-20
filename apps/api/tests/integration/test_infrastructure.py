import pytest
from conftest import migrate
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.event_loop import database_event_loop
from app.main import create_app

pytestmark = pytest.mark.integration


def test_fresh_database_migration_roundtrip_and_real_readiness(empty_database: str) -> None:
    settings = Settings(database_url=empty_database)
    app = create_app(settings)
    with TestClient(app, backend_options={"loop_factory": database_event_loop}) as client:
        before = client.get("/api/v1/health/ready")
        assert before.status_code == 503
        assert before.json()["dependencies"]["postgres"] == "ok"
        assert before.json()["dependencies"]["pgvector"] == "unavailable"
        assert before.json()["dependencies"]["migrations"] == "unavailable"

    migrate(empty_database, "upgrade", "head")
    with TestClient(
        create_app(settings), backend_options={"loop_factory": database_event_loop}
    ) as client:
        after = client.get("/api/v1/health/ready")
        assert after.status_code == 200
        assert after.json()["dependencies"] == {
            "postgres": "ok",
            "redis": "ok",
            "pgvector": "ok",
            "migrations": "ok",
        }

    migrate(empty_database, "downgrade", "base")
    migrate(empty_database, "upgrade", "head")
    with TestClient(
        create_app(settings), backend_options={"loop_factory": database_event_loop}
    ) as client:
        assert client.get("/api/v1/health/ready").status_code == 200
