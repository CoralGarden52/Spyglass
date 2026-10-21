from typing import cast
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.auth import TenantContext
from app.domain.schemas import ProjectInput, ThreadInput
from app.infrastructure.database.research import Message, Project, Thread


class ResearchRepository:
    def __init__(self, database: AsyncSession, context: TenantContext) -> None:
        self.database = database
        self.context = context

    async def project(self, project_id: UUID) -> Project | None:
        return cast(
            Project | None,
            await self.database.scalar(
                select(Project).where(
                    Project.id == project_id, Project.tenant_id == self.context.tenant_id
                )
            ),
        )

    async def list_projects(self, query: str, limit: int, offset: int) -> tuple[list[Project], int]:
        filters = [Project.tenant_id == self.context.tenant_id]
        if query:
            filters.append(Project.title.icontains(query, autoescape=True))
        total = await self.database.scalar(
            select(func.count()).select_from(Project).where(*filters)
        )
        rows = await self.database.scalars(
            select(Project)
            .where(*filters)
            .order_by(Project.created_at.desc(), Project.id.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(rows), int(total or 0)

    async def create_project(self, payload: ProjectInput, key: str, fingerprint: str) -> Project:
        values = payload.model_dump() | {
            "tenant_id": self.context.tenant_id,
            "created_by": self.context.user_id,
            "idempotency_key": key,
            "request_hash": fingerprint,
        }
        await self.database.execute(
            insert(Project).values(**values).on_conflict_do_nothing(constraint="uq_project_request")
        )
        row = await self.database.scalar(
            select(Project).where(
                Project.tenant_id == self.context.tenant_id,
                Project.created_by == self.context.user_id,
                Project.idempotency_key == key,
            )
        )
        assert row is not None
        return row

    async def thread(self, thread_id: UUID) -> Thread | None:
        return cast(
            Thread | None,
            await self.database.scalar(
                select(Thread).where(
                    Thread.id == thread_id, Thread.tenant_id == self.context.tenant_id
                )
            ),
        )

    async def threads(self, project_id: UUID) -> list[Thread]:
        return list(
            await self.database.scalars(
                select(Thread)
                .where(Thread.project_id == project_id, Thread.tenant_id == self.context.tenant_id)
                .order_by(Thread.created_at.desc(), Thread.id)
                .limit(100)
            )
        )

    async def create_thread(self, payload: ThreadInput, key: str, fingerprint: str) -> Thread:
        values = payload.model_dump() | {
            "tenant_id": self.context.tenant_id,
            "created_by": self.context.user_id,
            "idempotency_key": key,
            "request_hash": fingerprint,
        }
        await self.database.execute(
            insert(Thread).values(**values).on_conflict_do_nothing(constraint="uq_thread_request")
        )
        row = await self.database.scalar(
            select(Thread).where(
                Thread.tenant_id == self.context.tenant_id,
                Thread.created_by == self.context.user_id,
                Thread.idempotency_key == key,
            )
        )
        assert row is not None
        return row

    async def messages(self, thread_id: UUID) -> list[Message]:
        rows = await self.database.scalars(
            select(Message)
            .where(Message.tenant_id == self.context.tenant_id, Message.thread_id == thread_id)
            .order_by(Message.sequence)
        )
        return list(rows)
