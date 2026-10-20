from collections.abc import Awaitable
from typing import cast

from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import Settings


class Resources:
    def __init__(self, settings: Settings) -> None:
        self.engine = create_async_engine(
            settings.database_url.get_secret_value(),
            pool_pre_ping=True,
            hide_parameters=True,
            connect_args={"connect_timeout": 3},
        )
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)
        self.redis: Redis = Redis.from_url(
            settings.redis_url.get_secret_value(),
            socket_connect_timeout=settings.dependency_timeout_seconds,
            socket_timeout=settings.dependency_timeout_seconds,
            decode_responses=True,
        )

    async def check_postgres(self) -> None:
        async with self.engine.connect() as connection:
            await connection.execute(text("SELECT 1"))

    async def check_vector(self) -> None:
        async with self.engine.connect() as connection:
            await connection.execute(text("SELECT '[1,0,0]'::vector <-> '[0,1,0]'::vector"))

    async def check_migration(self) -> None:
        async with self.engine.connect() as connection:
            result = await connection.scalar(text("SELECT version_num FROM alembic_version"))
            if result != "0005_langgraph_checkpoint":
                raise RuntimeError("Migration required")

    async def check_redis(self) -> None:
        # Redis shares sync/async command annotations; narrow the async client's result.
        if not await cast(Awaitable[bool], self.redis.ping()):
            raise RuntimeError("Cache unavailable")

    async def close(self) -> None:
        await self.redis.aclose()
        await self.engine.dispose()
