import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
from uuid import UUID

from app.application.auth import AuthService, TenantContext
from app.core.config import Settings
from app.domain.errors import DomainError
from app.domain.run_schemas import RunEventView
from app.infrastructure.event_store import TERMINAL, EventStore
from app.infrastructure.resources import Resources
from app.infrastructure.run_read_repository import RunReadRepository


def sse_frame(event: RunEventView) -> str:
    return f"id: {event.event_id}\nevent: {event.type}\ndata: {event.model_dump_json()}\n\n"


async def stream_run_events(
    resources: Resources,
    settings: Settings,
    context: TenantContext,
    token: str | None,
    run_id: UUID,
    after_seq: int,
    disconnected: Callable[[], Awaitable[bool]],
) -> AsyncIterator[str]:
    store = EventStore(resources.sessions, context, run_id)
    cursor, ticks = after_seq, 0
    while not await disconnected():
        # A stream does not grant a permanent session: revalidate membership and expiry.
        async with resources.sessions() as db:
            try:
                current = await AuthService(db, settings).resolve(token)
            except DomainError:
                return
            if current.tenant_id != context.tenant_id:
                return
        for event in await store.history(cursor):
            cursor = event.seq
            yield sse_frame(event)
        async with resources.sessions() as db:
            status = (await RunReadRepository(db, context).get(run_id)).data.status
        if status in TERMINAL:
            # Terminal transition and its last event are atomic. Drain all remaining pages.
            while tail := await store.history(cursor):
                for event in tail:
                    cursor = event.seq
                    yield sse_frame(event)
            return
        ticks += 1
        if ticks % 20 == 0:
            yield ": keep-alive\n\n"
        await asyncio.sleep(0.25)
