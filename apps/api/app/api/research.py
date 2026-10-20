from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query

from app.application.research import ResearchService
from app.core.dependencies import Context, Database, IdempotencyKey, WriteContext
from app.domain.schemas import (
    MessageList,
    ProjectInput,
    ProjectList,
    ProjectResult,
    ThreadInput,
    ThreadResult,
)

router = APIRouter(prefix="/api/v1", tags=["research"])


@router.get("/research", response_model=ProjectList)
async def list_projects(
    db: Database,
    context: Context,
    q: Annotated[str, Query(max_length=100)] = "",
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0, le=10000)] = 0,
) -> ProjectList:
    return await ResearchService(db, context).list_projects(q, limit, offset)


@router.post("/research", status_code=201, response_model=ProjectResult)
async def create_project(
    payload: ProjectInput, db: Database, context: WriteContext, key: IdempotencyKey
) -> ProjectResult:
    return await ResearchService(db, context).create_project(payload, key)


@router.get("/research/{project_id}", response_model=ProjectResult)
async def project(project_id: UUID, db: Database, context: Context) -> ProjectResult:
    return await ResearchService(db, context).project(project_id)


@router.post("/threads", status_code=201, response_model=ThreadResult)
async def create_thread(
    payload: ThreadInput, db: Database, context: WriteContext, key: IdempotencyKey
) -> ThreadResult:
    return await ResearchService(db, context).create_thread(payload, key)


@router.get("/threads/{thread_id}", response_model=ThreadResult)
async def thread(thread_id: UUID, db: Database, context: Context) -> ThreadResult:
    return await ResearchService(db, context).thread(thread_id)


@router.get("/threads/{thread_id}/messages", response_model=MessageList)
async def messages(thread_id: UUID, db: Database, context: Context) -> MessageList:
    return await ResearchService(db, context).messages(thread_id)
