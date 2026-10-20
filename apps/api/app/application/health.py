import asyncio
from collections.abc import Awaitable, Callable
from typing import Literal, Protocol

from pydantic import BaseModel

from app.core.config import Settings


class HealthResources(Protocol):
    async def check_postgres(self) -> None: ...
    async def check_vector(self) -> None: ...
    async def check_migration(self) -> None: ...
    async def check_redis(self) -> None: ...


class LivenessResponse(BaseModel):
    schema_version: Literal[1] = 1
    status: Literal["alive"] = "alive"


class Dependencies(BaseModel):
    postgres: Literal["ok", "unavailable"]
    redis: Literal["ok", "unavailable"]
    pgvector: Literal["ok", "unavailable"]
    migrations: Literal["ok", "unavailable"]


class ProviderConfiguration(BaseModel):
    deepseek: Literal["configured", "unconfigured"]
    deepseek_search: Literal["configured", "unconfigured"]


class ReadinessResponse(BaseModel):
    schema_version: Literal[1] = 1
    status: Literal["ready", "degraded"]
    dependencies: Dependencies
    providers: ProviderConfiguration
    research_available: Literal[False] = False


async def get_readiness(resources: HealthResources, settings: Settings) -> ReadinessResponse:
    async def probe(check: Callable[[], Awaitable[None]]) -> Literal["ok", "unavailable"]:
        try:
            async with asyncio.timeout(settings.dependency_timeout_seconds):
                await check()
            return "ok"
        except Exception:
            # Intentionally return no exception text, DSN, credentials or provider keys.
            return "unavailable"

    postgres, redis, vector, migrations = await asyncio.gather(
        probe(resources.check_postgres),
        probe(resources.check_redis),
        probe(resources.check_vector),
        probe(resources.check_migration),
    )
    dependencies = Dependencies(
        postgres=postgres, redis=redis, pgvector=vector, migrations=migrations
    )
    return ReadinessResponse(
        status="ready"
        if all(v == "ok" for v in dependencies.model_dump().values())
        else "degraded",
        dependencies=dependencies,
        providers=ProviderConfiguration(
            deepseek="configured"
            if settings.deepseek_api_key.get_secret_value()
            else "unconfigured",
            deepseek_search="configured"
            if settings.deepseek3_api_key.get_secret_value()
            else "unconfigured",
        ),
    )
