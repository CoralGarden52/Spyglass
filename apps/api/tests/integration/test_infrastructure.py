import os
import subprocess
import sys
from collections.abc import Iterator
from uuid import uuid4

import psycopg
import pytest
from fastapi.testclient import TestClient
from psycopg import sql
from sqlalchemy.engine import make_url

from app.core.config import ROOT, Settings
from app.core.event_loop import database_event_loop
from app.main import create_app

pytestmark = pytest.mark.integration


@pytest.fixture
def empty_database() -> Iterator[str]:
    url = make_url(Settings().database_url.get_secret_value())
    database_name = "spyglass_test_" + uuid4().hex
    admin_dsn = url.set(drivername="postgresql", database="postgres").render_as_string(
        hide_password=False
    )
    with psycopg.connect(admin_dsn, autocommit=True, connect_timeout=5) as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database_name)))
    test_url = url.set(database=database_name).render_as_string(hide_password=False)
    try:
        yield test_url
    finally:
        # Only this fixture's newly created random database is eligible for cleanup.
        assert database_name.startswith("spyglass_test_") and len(database_name) == 46
        with psycopg.connect(admin_dsn, autocommit=True, connect_timeout=5) as admin:
            admin.execute(
                sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(database_name))
            )


def migrate(url: str, action: str, target: str) -> None:
    environment = {**os.environ, "DATABASE_URL": url, "APP_ENV": "test"}
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "-c", "apps/api/alembic.ini", action, target],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        timeout=30,
        check=False,
    )
    # Do not put raw subprocess error/DSN into test reports.
    assert result.returncode == 0, "Alembic migration failed; inspect local configuration"


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
