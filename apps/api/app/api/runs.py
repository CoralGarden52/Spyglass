from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Header, Query, Request
from fastapi.responses import StreamingResponse

from app.application.run_events import stream_run_events
from app.application.run_preparation import RunRequest
from app.application.runs import RunService
from app.core.dependencies import Context, Database, IdempotencyKey, WriteContext
from app.domain.run_schemas import EmptyCommand, EventList, RunCreated, RunList, RunResponse
from app.infrastructure.event_store import EventStore

router = APIRouter(prefix="/api/v1", tags=["runs"])


@router.post("/threads/{thread_id}/runs", status_code=201, response_model=RunCreated)
async def create_run(
    thread_id: UUID,
    payload: RunRequest,
    request: Request,
    db: Database,
    context: WriteContext,
    key: IdempotencyKey,
) -> RunCreated:
    return await RunService(db, context, request.app.state.executor).create(
        thread_id, payload, key, request.app.state.skills, request.app.state.settings
    )


@router.get("/threads/{thread_id}/runs", response_model=RunList)
async def list_runs(thread_id: UUID, request: Request, db: Database, context: Context) -> RunList:
    return await RunService(db, context, request.app.state.executor).list(thread_id)


@router.get("/runs/{run_id}", response_model=RunResponse)
async def run(run_id: UUID, request: Request, db: Database, context: Context) -> RunResponse:
    return await RunService(db, context, request.app.state.executor).get(run_id)


@router.post("/runs/{run_id}/cancel", response_model=RunResponse)
async def cancel(
    run_id: UUID,
    payload: EmptyCommand,
    request: Request,
    db: Database,
    context: WriteContext,
    key: IdempotencyKey,
) -> RunResponse:
    return await RunService(db, context, request.app.state.executor).cancel(run_id)


@router.post("/runs/{run_id}/resume", response_model=RunResponse)
async def resume(
    run_id: UUID,
    payload: EmptyCommand,
    request: Request,
    db: Database,
    context: WriteContext,
    key: IdempotencyKey,
) -> RunResponse:
    return await RunService(db, context, request.app.state.executor).resume(run_id)


@router.get("/runs/{run_id}/events/history", response_model=EventList)
async def history(
    run_id: UUID,
    request: Request,
    context: Context,
    after_seq: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=500)] = 500,
) -> EventList:
    store = EventStore(request.app.state.resources.sessions, context, run_id)
    return EventList(data=await store.history(after_seq, limit))


@router.get(
    "/runs/{run_id}/events",
    response_class=StreamingResponse,
    responses={
        200: {
            "content": {"text/event-stream": {}},
            "description": "Persisted RunEventView JSON envelopes, ordered by seq",
        }
    },
)
async def events(
    run_id: UUID,
    request: Request,
    db: Database,
    context: Context,
    after_seq: Annotated[int, Query(ge=0)] = 0,
    last_event_id: Annotated[UUID | None, Header(alias="Last-Event-ID")] = None,
) -> StreamingResponse:
    service = RunService(db, context, request.app.state.executor)
    await service.get(run_id)  # All authorization and cursor errors happen before response headers.
    store = EventStore(request.app.state.resources.sessions, context, run_id)
    if last_event_id is not None:
        after_seq = max(after_seq, await store.cursor(last_event_id))
    await db.rollback()
    stream = stream_run_events(
        request.app.state.resources,
        request.app.state.settings,
        context,
        request.cookies.get("sg_session"),
        run_id,
        after_seq,
        request.is_disconnected,
    )
    return StreamingResponse(
        stream,
        media_type="text/event-stream",
        headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
    )
