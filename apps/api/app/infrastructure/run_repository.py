from typing import cast
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.auth import TenantContext
from app.infrastructure.database.research import Message, Run, Thread

ACTIVE_STATUSES = ("pending", "running", "waiting_approval", "cancel_requested")


class RunRepository:
    def __init__(self, database: AsyncSession, context: TenantContext) -> None:
        self.database = database
        self.context = context

    async def lock_thread(self, thread_id: UUID) -> Thread | None:
        return cast(
            Thread | None,
            await self.database.scalar(
                select(Thread)
                .where(Thread.tenant_id == self.context.tenant_id, Thread.id == thread_id)
                .with_for_update()
            ),
        )

    async def previous(self, thread_id: UUID, key: str) -> Run | None:
        return cast(
            Run | None,
            await self.database.scalar(
                select(Run).where(
                    Run.tenant_id == self.context.tenant_id,
                    Run.user_id == self.context.user_id,
                    Run.thread_id == thread_id,
                    Run.idempotency_key == key,
                )
            ),
        )

    async def active(self, thread_id: UUID) -> Run | None:
        return cast(
            Run | None,
            await self.database.scalar(
                select(Run).where(
                    Run.tenant_id == self.context.tenant_id,
                    Run.thread_id == thread_id,
                    Run.status.in_(ACTIVE_STATUSES),
                )
            ),
        )

    async def add_message(self, run: Run, content: str) -> None:
        # Caller holds the Thread lock through commit, serializing sequence allocation.
        sequence = await self.database.scalar(
            select(func.coalesce(func.max(Message.sequence), 0)).where(
                Message.tenant_id == self.context.tenant_id, Message.thread_id == run.thread_id
            )
        )
        self.database.add(
            Message(
                tenant_id=run.tenant_id,
                thread_id=run.thread_id,
                run_id=run.id,
                role="user",
                content_json={"schema_version": 1, "text": content},
                sequence=int(sequence or 0) + 1,
            )
        )
