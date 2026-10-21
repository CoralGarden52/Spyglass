import hashlib
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.auth import TenantContext
from app.domain.errors import DomainError
from app.domain.schemas import (
    MessageList,
    MessageView,
    PageMeta,
    ProjectInput,
    ProjectList,
    ProjectResult,
    ProjectView,
    ThreadInput,
    ThreadList,
    ThreadResult,
    ThreadView,
)
from app.infrastructure.research_repository import ResearchRepository


def fingerprint(payload: BaseModel) -> str:
    return hashlib.sha256(payload.model_dump_json().encode()).hexdigest()


class ResearchService:
    def __init__(self, database: AsyncSession, context: TenantContext) -> None:
        self.database = database
        self.repository = ResearchRepository(database, context)

    async def project(self, project_id: UUID) -> ProjectResult:
        row = await self.repository.project(project_id)
        if row is None:
            raise DomainError(404, "not_found", "调研不存在或无权访问")
        return ProjectResult(data=ProjectView.model_validate(row))

    async def list_projects(self, query: str, limit: int, offset: int) -> ProjectList:
        rows, total = await self.repository.list_projects(query, limit, offset)
        return ProjectList(
            data=[ProjectView.model_validate(row) for row in rows],
            meta=PageMeta(total=total, limit=limit, offset=offset),
        )

    async def create_project(self, payload: ProjectInput, key: str) -> ProjectResult:
        checksum = fingerprint(payload)
        row = await self.repository.create_project(payload, key, checksum)
        if row.request_hash != checksum:
            raise DomainError(409, "idempotency_conflict", "该幂等键已用于不同请求")
        await self.database.commit()
        return ProjectResult(data=ProjectView.model_validate(row))

    async def thread(self, thread_id: UUID) -> ThreadResult:
        row = await self.repository.thread(thread_id)
        if row is None:
            raise DomainError(404, "not_found", "会话不存在或无权访问")
        return ThreadResult(data=ThreadView.model_validate(row))

    async def threads(self, project_id: UUID) -> ThreadList:
        await self.project(project_id)
        return ThreadList(
            data=[
                ThreadView.model_validate(row) for row in await self.repository.threads(project_id)
            ]
        )

    async def create_thread(self, payload: ThreadInput, key: str) -> ThreadResult:
        await self.project(payload.project_id)
        checksum = fingerprint(payload)
        row = await self.repository.create_thread(payload, key, checksum)
        if row.request_hash != checksum:
            raise DomainError(409, "idempotency_conflict", "该幂等键已用于不同请求")
        await self.database.commit()
        return ThreadResult(data=ThreadView.model_validate(row))

    async def messages(self, thread_id: UUID) -> MessageList:
        await self.thread(thread_id)
        rows = await self.repository.messages(thread_id)
        return MessageList(data=[MessageView.model_validate(row) for row in rows])
