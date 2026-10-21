from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from uuid import uuid4

import httpx
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from app.agent.runtime.executor import LocalRunExecutor, ResearchRunner
from app.agent.skills.registry import SkillRegistry
from app.agent.tools.registry import ToolRegistry
from app.api.auth import router as auth_router
from app.api.health import router
from app.api.reports import router as reports_router
from app.api.research import router as research_router
from app.api.runs import router as runs_router
from app.api.skills import router as skills_router
from app.core.config import ROOT, Settings
from app.core.errors import ErrorResponse, install_error_handlers
from app.infrastructure.event_store import fail_orphaned_runs
from app.infrastructure.providers.chat import ChatProvider
from app.infrastructure.resources import Resources


def create_app(settings: Settings | None = None) -> FastAPI:
    config = settings or Settings()

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        resources = Resources(config)
        application.state.settings = config
        application.state.resources = resources
        application.state.skills = SkillRegistry.from_directory(ROOT / "extensions/skills")
        client = httpx.AsyncClient(
            timeout=httpx.Timeout(config.llm_request_timeout_seconds, connect=10),
            trust_env=False,
            follow_redirects=False,
        )
        provider = ChatProvider(
            client,
            config.active_model_base_url,
            config.active_model_key.get_secret_value(),
            config.active_model_name,
            config.llm_max_concurrency,
            config.llm_request_timeout_seconds,
            role_budgets=config.llm_role_max_tokens,
            thinking=None if config.llm_thinking == "provider_default" else config.llm_thinking,
        )
        application.state.executor = LocalRunExecutor(
            ResearchRunner(resources, config, provider, ToolRegistry(client, config)),
            config.local_run_capacity,
        )
        # Liveness remains available before migrations. Never execute orphaned work twice.
        try:
            await resources.check_migration()
        except Exception:
            application.state.recovery_status = "database_unavailable"
        else:
            await fail_orphaned_runs(resources.sessions)
            application.state.recovery_status = "complete"
        try:
            yield
        finally:
            await application.state.executor.close()
            await client.aclose()
            await resources.close()

    application = FastAPI(
        title="Spyglass API",
        version="0.0.1",
        lifespan=lifespan,
        responses={
            code: {"model": ErrorResponse} for code in (401, 403, 404, 409, 422, 429, 500, 503)
        },
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=config.cors_origins,
        allow_methods=["GET", "POST", "PATCH"],
        allow_headers=["Content-Type", "X-CSRF-Token", "Idempotency-Key", "Last-Event-ID"],
        allow_credentials=True,
        expose_headers=["X-Request-ID"],
    )

    @application.middleware("http")
    async def request_id(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request.state.request_id = str(uuid4())
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        if request.url.path.startswith("/api/v1/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    install_error_handlers(application)
    application.include_router(router)
    application.include_router(auth_router)
    application.include_router(research_router)
    application.include_router(skills_router)
    application.include_router(reports_router)
    application.include_router(runs_router)
    return application


app = create_app()
