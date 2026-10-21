from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.runtime.executor import LocalRunExecutor
from app.agent.skills.registry import SkillRegistry
from app.application.auth import TenantContext
from app.application.run_preparation import RunPreparation, RunRequest
from app.core.config import Settings
from app.domain.errors import DomainError
from app.domain.run_schemas import RunCreated, RunList, RunResponse
from app.infrastructure.event_store import EventStore
from app.infrastructure.run_read_repository import RunReadRepository
from app.infrastructure.run_repository import RunRepository


class RunService:
    def __init__(self, db: AsyncSession, context: TenantContext, executor: LocalRunExecutor):
        self.db, self.context, self.executor = db, context, executor
        self.reads = RunReadRepository(db, context)

    async def get(self, run_id: UUID) -> RunResponse:
        return await self.reads.get(run_id)

    async def list(self, thread_id: UUID) -> RunList:
        return await self.reads.list(thread_id)

    async def create(
        self,
        thread_id: UUID,
        request: RunRequest,
        key: str,
        registry: SkillRegistry,
        settings: Settings,
    ) -> RunCreated:
        # Reserve capacity across transaction and scheduling.
        async with self.executor.submission_lock:
            repository = RunRepository(self.db, self.context)
            if await repository.lock_thread(thread_id) is None:
                raise DomainError(404, "not_found", "会话不存在或无权访问")
            previous = await repository.previous(thread_id, key)
            if previous is None:
                if not (
                    settings.model_configured and settings.deepseek3_api_key.get_secret_value()
                ):
                    raise DomainError(
                        503, "research_unconfigured", "模型或 DeepSeek 搜索未配置，无法开始真实研究"
                    )
                if len(self.executor.tasks) >= self.executor.capacity:
                    raise DomainError(503, "executor_busy", "本地运行容量已满，请稍后重试")
            prepared = await RunPreparation(self.db, self.context, registry).prepare(
                thread_id, request, key
            )
            if previous is None:
                await self.reads.mark_project_running(prepared.run_id)
                await self.db.commit()
                try:
                    await self.executor.submit(self.context, prepared.run_id)
                except Exception:
                    await EventStore(
                        self.executor.runner.resources.sessions, self.context, prepared.run_id
                    ).finish("failed", "executor_submit_failed", None)
                    raise
        return RunCreated(
            data=(await self.get(prepared.run_id)).data,
            events_url=f"/api/v1/runs/{prepared.run_id}/events",
        )

    async def cancel(self, run_id: UUID) -> RunResponse:
        # Release this API session's read transaction before the executor's short transactions.
        await self.reads.row(run_id)
        await self.db.rollback()
        sessions = self.executor.runner.resources.sessions
        store = EventStore(sessions, self.context, run_id)
        await store.request_cancel()
        await self.executor.request_cancel(self.context, run_id)
        return await self.get(run_id)

    async def resume(self, run_id: UUID) -> RunResponse:
        await self.reads.row(run_id)
        # This graph has no pending human interrupt. Never pretend a finished Run resumed.
        raise DomainError(
            409, "run_not_resumable", "此运行没有可恢复的审批中断；可读取历史或发起后继运行"
        )
