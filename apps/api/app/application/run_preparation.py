from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.skills.models import Selection, Snapshot
from app.agent.skills.registry import SkillRegistry
from app.application.auth import TenantContext
from app.application.research import fingerprint
from app.application.skills import SkillService
from app.domain.errors import DomainError
from app.infrastructure.database.research import Run
from app.infrastructure.run_repository import RunRepository


class RunRequest(Selection):
    user_message: str = Field(min_length=1, max_length=8000, pattern=r"\S")


class PreparedRun(BaseModel):
    schema_version: Literal[1] = 1
    run_id: UUID
    skills: list[Snapshot]


class RunPreparation:
    """Atomic pending Run persistence. Execution is introduced in the next slices."""

    def __init__(self, database: AsyncSession, context: TenantContext, registry: SkillRegistry):
        self.database = database
        self.context = context
        self.repository = RunRepository(database, context)
        self.skills = SkillService(database, context, registry)

    async def prepare(self, thread_id: UUID, request: RunRequest, key: str) -> PreparedRun:
        thread = await self.repository.lock_thread(thread_id)
        if thread is None:
            raise DomainError(404, "not_found", "会话不存在或无权访问")
        checksum = fingerprint(request)
        previous = await self.repository.previous(thread_id, key)
        if previous is not None:
            if previous.request_hash != checksum:
                raise DomainError(409, "idempotency_conflict", "幂等键已用于其他运行请求")
            result = PreparedRun(
                run_id=previous.id,
                skills=[Snapshot.model_validate(s) for s in previous.skills_snapshot_json],
            )
            await self.database.commit()
            return result
        if await self.repository.active(thread_id) is not None:
            raise DomainError(409, "active_run_conflict", "此会话已有活动运行")
        selection = Selection.model_validate(request.model_dump(exclude={"user_message"}))
        resolution = await self.skills.resolution(selection, commit=False)
        run = Run(
            tenant_id=self.context.tenant_id,
            project_id=thread.project_id,
            thread_id=thread.id,
            user_id=self.context.user_id,
            status="pending",
            idempotency_key=key,
            request_hash=checksum,
            skills_snapshot_json=[s.model_dump(mode="json") for s in resolution.data.skills],
        )
        self.database.add(run)
        await self.database.flush()
        await self.repository.add_message(run, request.user_message)
        result = PreparedRun(run_id=run.id, skills=resolution.data.skills)
        await self.database.commit()
        return result
