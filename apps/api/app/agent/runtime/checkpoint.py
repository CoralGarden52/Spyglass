from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg import AsyncConnection
from psycopg.rows import dict_row
from sqlalchemy.engine import make_url

from app.core.config import Settings


@asynccontextmanager
async def postgres_checkpoint(settings: Settings) -> AsyncIterator[AsyncPostgresSaver]:
    url = make_url(settings.database_url.get_secret_value()).set(drivername="postgresql")
    async with await AsyncConnection.connect(
        url.render_as_string(False),
        autocommit=True,
        prepare_threshold=0,
        row_factory=dict_row,
        options="-c search_path=langgraph",
        connect_timeout=5,
    ) as conn:
        saver = AsyncPostgresSaver(conn)
        # SDK migration runs once in Alembic 0005, before traffic. Setup here
        # can deadlock CREATE INDEX CONCURRENTLY across concurrent Runs.
        yield saver
