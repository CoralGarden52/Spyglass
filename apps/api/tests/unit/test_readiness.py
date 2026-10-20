import asyncio

from fastapi.testclient import TestClient

from app.application.health import get_readiness
from app.core.config import Settings
from app.main import create_app


class AvailableResources:
    async def check_postgres(self) -> None:
        return None

    async def check_redis(self) -> None:
        return None

    async def check_vector(self) -> None:
        return None

    async def check_migration(self) -> None:
        return None


class FailedCache(AvailableResources):
    async def check_redis(self) -> None:
        raise ConnectionError("redis://private-credential@host")


class SlowCache(AvailableResources):
    async def check_redis(self) -> None:
        await asyncio.sleep(10)


async def test_readiness_sanitizes_dependency_failures() -> None:
    result = await get_readiness(FailedCache(), Settings(_env_file=None))
    assert result.status == "degraded"
    assert result.dependencies.redis == "unavailable"
    assert result.dependencies.postgres == "ok"
    assert "private-credential" not in result.model_dump_json()


async def test_readiness_has_bounded_wait_for_unresponsive_services() -> None:
    result = await get_readiness(
        SlowCache(), Settings(_env_file=None, dependency_timeout_seconds=0.01)
    )
    assert result.status == "degraded"
    assert result.dependencies.redis == "unavailable"


def test_readiness_http_status_degrades_without_failing_liveness() -> None:
    app = create_app(Settings(_env_file=None))
    with TestClient(app) as client:
        app.state.resources = FailedCache()
        response = client.get("/api/v1/health/ready")
        assert response.status_code == 503
        assert response.json()["dependencies"]["redis"] == "unavailable"
        assert client.get("/api/v1/health/live").status_code == 200


def test_ready_contract_does_not_treat_configured_keys_as_working_research() -> None:
    app = create_app(Settings(_env_file=None, deepseek_api_key="test-only"))
    with TestClient(app) as client:
        app.state.resources = AvailableResources()
        response = client.get("/api/v1/health/ready")
    assert response.status_code == 200
    assert response.json()["providers"] == {"deepseek": "configured", "bocha": "unconfigured"}
    assert response.json()["research_available"] is False
    assert "test-only" not in response.text
