"""Run browser tests against a disposable database, never the developer's accounts."""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import psycopg
from dotenv import dotenv_values
from psycopg import sql
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    values = dotenv_values(ROOT / ".env")
    url = make_url(
        os.environ.get("DATABASE_URL")
        or values.get("DATABASE_URL")
        or "postgresql+psycopg://spyglass:spyglass_local@127.0.0.1:55432/spyglass"
    )
    database_name = "spyglass_e2e_" + uuid4().hex
    admin_url = url.set(drivername="postgresql", database="postgres").render_as_string(False)
    environment = {
        **os.environ,
        "DATABASE_URL": url.set(database=database_name).render_as_string(False),
        "APP_ENV": "test",
        "AUTH_RATE_LIMIT": "100",
        "RATE_LIMIT_NAMESPACE": database_name,
        "CORS_ORIGINS": json.dumps(["http://127.0.0.1:5174"]),
    }
    with psycopg.connect(admin_url, autocommit=True, connect_timeout=5) as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database_name)))
    try:
        migration = subprocess.run(
            [sys.executable, "-m", "alembic", "-c", "apps/api/alembic.ini", "upgrade", "head"],
            cwd=ROOT,
            env=environment,
            check=False,
        )
        if migration.returncode:
            return migration.returncode
        seed = subprocess.run(
            [sys.executable, "tests/e2e/seed_report.py"], cwd=ROOT, env=environment, check=False
        )
        if seed.returncode:
            return seed.returncode
        npm = shutil.which("npm.cmd" if sys.platform == "win32" else "npm")
        if npm is None:
            raise RuntimeError("npm is required")
        return subprocess.call(
            [npm, "exec", "--", "playwright", "test", *sys.argv[1:]], cwd=ROOT, env=environment
        )
    finally:
        assert database_name.startswith("spyglass_e2e_") and len(database_name) == 45
        with psycopg.connect(admin_url, autocommit=True, connect_timeout=5) as admin:
            admin.execute(
                sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(database_name))
            )


if __name__ == "__main__":
    raise SystemExit(main())
