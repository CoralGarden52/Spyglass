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


@pytest.fixture
def empty_database() -> Iterator[str]:
    url = make_url(Settings().database_url.get_secret_value())
    database_name = "spyglass_test_" + uuid4().hex
    admin_dsn = url.set(drivername="postgresql", database="postgres").render_as_string(False)
    with psycopg.connect(admin_dsn, autocommit=True, connect_timeout=5) as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database_name)))
    try:
        yield url.set(database=database_name).render_as_string(False)
    finally:
        assert database_name.startswith("spyglass_test_") and len(database_name) == 46
        with psycopg.connect(admin_dsn, autocommit=True, connect_timeout=5) as admin:
            admin.execute(
                sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(database_name))
            )


def migrate(url: str, action: str, target: str) -> None:
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "-c", "apps/api/alembic.ini", action, target],
        cwd=ROOT,
        env={**os.environ, "DATABASE_URL": url, "APP_ENV": "test"},
        capture_output=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, "Alembic migration failed; inspect local configuration"


@pytest.fixture
def api_client(empty_database: str) -> Iterator[TestClient]:
    migrate(empty_database, "upgrade", "head")
    settings = Settings(
        database_url=empty_database,
        app_env="test",
        auth_rate_limit=100,
        rate_limit_namespace="spyglass-test-" + uuid4().hex,
    )
    with TestClient(
        create_app(settings),
        backend_options={"loop_factory": database_event_loop},
        headers={"Origin": "http://127.0.0.1:5173"},
    ) as client:
        yield client
