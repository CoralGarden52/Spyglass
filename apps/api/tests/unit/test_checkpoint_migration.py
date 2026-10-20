import os
import subprocess
import sys

from app.core.config import ROOT


def test_offline_checkpoint_sql_generation_never_connects_to_database() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "-c", "apps/api/alembic.ini", "upgrade", "head", "--sql"],
        cwd=ROOT,
        env={
            **os.environ,
            "DATABASE_URL": "postgresql+psycopg://offline:unused@127.0.0.1:1/offline",
        },
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode != 0
    assert "requires online migration" in result.stderr
    assert "connection failed" not in result.stderr.lower()
