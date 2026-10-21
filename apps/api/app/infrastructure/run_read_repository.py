from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.skills.models import Selection
from app.application.auth import TenantContext
from app.domain.errors import DomainError
from app.domain.run_schemas import RunList, RunResponse, RunView
from app.infrastructure.database.knowledge import Report
from app.infrastructure.database.research import Project, Run, Thread


class RunReadRepository:
    def __init__(self, db: AsyncSession, context: TenantContext):
        self.db, self.context = db, context

    async def row(self, run_id: UUID) -> Run:
        row = await self.db.scalar(
            select(Run)
            .where(Run.id == run_id, Run.tenant_id == self.context.tenant_id)
            .execution_options(populate_existing=True)
        )
        if row is None:
            raise DomainError(404, "not_found", "运行不存在或无权访问")
        return row

    async def view(self, row: Run) -> RunView:
        report_id = await self.db.scalar(
            select(Report.id).where(
                Report.run_id == row.id, Report.tenant_id == self.context.tenant_id
            )
        )
        selection = Selection.model_validate(
            {k: v for k, v in (row.request_json or {}).items() if k in Selection.model_fields}
        )
        return RunView(
            **RunView.model_validate(row).model_dump(exclude={"report_id", "selection"}),
            report_id=report_id,
            selection=selection,
        )

    async def get(self, run_id: UUID) -> RunResponse:
        return RunResponse(data=await self.view(await self.row(run_id)))

    async def list(self, thread_id: UUID) -> RunList:
        thread = await self.db.scalar(
            select(Thread.id).where(
                Thread.id == thread_id, Thread.tenant_id == self.context.tenant_id
            )
        )
        if thread is None:
            raise DomainError(404, "not_found", "会话不存在或无权访问")
        rows = await self.db.scalars(
            select(Run)
            .where(Run.thread_id == thread_id, Run.tenant_id == self.context.tenant_id)
            .order_by(Run.requested_at.desc(), Run.id)
            .limit(100)
        )
        return RunList(data=[await self.view(row) for row in rows])

    async def mark_project_running(self, run_id: UUID) -> None:
        run = await self.row(run_id)
        await self.db.execute(
            update(Project)
            .where(Project.id == run.project_id, Project.tenant_id == self.context.tenant_id)
            .values(status="running")
        )
