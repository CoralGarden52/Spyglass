from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from app.api.auth import router as auth_router
from app.api.health import router
from app.api.research import router as research_router
from app.core.config import Settings
from app.core.errors import ErrorResponse, install_error_handlers
from app.infrastructure.resources import Resources


def create_app(settings: Settings | None = None) -> FastAPI:
    config = settings or Settings()

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        resources = Resources(config)
        application.state.settings = config
        application.state.resources = resources
        try:
            yield
        finally:
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
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "X-CSRF-Token", "Idempotency-Key"],
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
    return application


app = create_app()
