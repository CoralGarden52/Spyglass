from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.auth import AuthService, TenantContext
from app.core.security import matches
from app.domain.errors import DomainError
from app.infrastructure.rate_limit import check_auth_limit


async def database(request: Request) -> AsyncIterator[AsyncSession]:
    async with request.app.state.resources.sessions() as session:
        yield session


Database = Annotated[AsyncSession, Depends(database)]


def require_origin(request: Request) -> None:
    origin = request.headers.get("origin")
    if origin not in request.app.state.settings.cors_origins:
        raise DomainError(403, "origin_rejected", "请求来源不受信任")


async def auth_limit(request: Request) -> None:
    subject = request.client.host if request.client else "unknown"
    # Deliberately do not trust browser-supplied X-Forwarded-For.
    await check_auth_limit(
        request.app.state.resources.redis, request.app.state.settings, request.url.path, subject
    )


async def tenant_context(request: Request, db: Database) -> TenantContext:
    return await AuthService(db, request.app.state.settings).resolve(
        request.cookies.get("sg_session")
    )


Context = Annotated[TenantContext, Depends(tenant_context)]


def csrf_context(request: Request, context: Context) -> TenantContext:
    require_origin(request)
    token = request.headers.get("x-csrf-token", "")
    if not token or len(token) > 128 or not matches(token, context.csrf_hash):
        raise DomainError(403, "csrf_rejected", "安全校验失败，请刷新页面后重试")
    return context


WriteContext = Annotated[TenantContext, Depends(csrf_context)]
IdempotencyKey = Annotated[
    str,
    Header(alias="Idempotency-Key", min_length=8, max_length=128, pattern=r"^[A-Za-z0-9_.:-]+$"),
]
