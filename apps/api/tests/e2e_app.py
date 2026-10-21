"""Controlled provider application exclusively for the disposable browser-test database."""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from pydantic import SecretStr
from sqlalchemy.engine import make_url

from app.agent.runtime.contracts import ModelInput, ModelReply
from app.core.config import Settings
from app.main import create_app
from tests.runtime_fixtures import ControlledModel, ControlledTools

settings = Settings()
assert settings.app_env == "test"
assert str(make_url(settings.database_url.get_secret_value()).database).startswith("spyglass_e2e_")
settings = settings.model_copy(
    update={
        "llm_provider": "deepseek",
        "deepseek_api_key": SecretStr("isolated-controlled-model"),
        "deepseek3_api_key": SecretStr("isolated-controlled-search"),
    }
)
app = create_app(settings)
original_lifespan = app.router.lifespan_context


class BrowserModel(ControlledModel):
    async def generate(self, call: ModelInput) -> ModelReply:
        request = call.context.get("request") or {}
        if call.role == "planner" and "fixture slow" in request.get("user_message", ""):
            await asyncio.sleep(5)
        return await super().generate(call)


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    async with original_lifespan(application):
        application.state.executor.runner.model = BrowserModel()
        application.state.executor.runner.tools = ControlledTools()
        yield


app.router.lifespan_context = lifespan
