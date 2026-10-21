"""Ordered, tenant-scoped events. Every write locks its owning Run."""

import re
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4, uuid5

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.application.auth import TenantContext
from app.domain.errors import DomainError
from app.domain.run_schemas import RunEventView
from app.infrastructure.database.events import RunEvent, RunStep, ToolCall
from app.infrastructure.database.knowledge import Report
from app.infrastructure.database.research import Message, Project, Run, Thread

TERMINAL = {"completed", "failed", "cancelled", "needs_review"}
ACTIVE_STEP: ContextVar[UUID | None] = ContextVar("spyglass_step", default=None)


async def fail_orphaned_runs(sessions: async_sessionmaker[AsyncSession]) -> None:
    """Single-process startup maintenance, before accepting new submissions."""
    async with sessions() as db:
        owners = list(
            (
                await db.execute(
                    select(Run.tenant_id, Run.id).where(
                        Run.status.in_(("pending", "running", "cancel_requested"))
                    )
                )
            ).all()
        )
    for tenant_id, run_id in owners:
        await EventStore(sessions, tenant_id, run_id).finish("failed", "process_restarted", None)


def public_arguments(args: dict[str, Any]) -> dict[str, Any]:
    """Only recognized bounded fields enter the user-visible tool log."""
    result: dict[str, Any] = {}
    for key in ("query", "url", "count", "need_content"):
        if key not in args:
            continue
        value = args[key]
        if isinstance(value, str):
            value = re.sub(r"(?i)(bearer\s+|sk-)[\w.-]+", "[redacted]", value)
            value = re.sub(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", "[email]", value)
            # Never expose URL credentials, query tokens or signed URLs.
            if key == "url":
                from urllib.parse import urlsplit, urlunsplit

                try:
                    parsed = urlsplit(value)
                    value = urlunsplit((parsed.scheme, parsed.hostname or "", parsed.path, "", ""))
                except ValueError:
                    value = "[invalid URL]"
            value = value[:400]
        elif not isinstance(value, (bool, int)):
            continue
        result[key] = value
    return result


class EventStore:
    def __init__(
        self,
        sessions: async_sessionmaker[AsyncSession],
        context: TenantContext | UUID,
        run_id: UUID,
    ):
        self.sessions, self.run_id = sessions, run_id
        self.tenant_id = context if isinstance(context, UUID) else context.tenant_id

    async def lock(self, db: AsyncSession) -> Run:
        run = await db.scalar(
            select(Run)
            .where(Run.id == self.run_id, Run.tenant_id == self.tenant_id)
            .with_for_update()
        )
        if run is None:
            raise DomainError(404, "not_found", "运行不存在或无权访问")
        return run

    async def request_cancel(self) -> None:
        async with self.sessions() as db:
            run = await self.lock(db)
            if run.status not in TERMINAL:
                run.status = "cancel_requested"
                await self.append(
                    db,
                    run,
                    "run.cancel_requested",
                    {"status": "cancel_requested"},
                    uuid5(run.id, "cancel-request"),
                )
            await db.commit()

    async def cursor(self, event_id: UUID) -> int:
        async with self.sessions() as db:
            seq = await db.scalar(
                select(RunEvent.seq).where(
                    RunEvent.id == event_id,
                    RunEvent.run_id == self.run_id,
                    RunEvent.tenant_id == self.tenant_id,
                )
            )
            if seq is None:
                raise DomainError(404, "event_cursor_not_found", "事件游标不存在或不属于此运行")
            return seq

    async def append(
        self,
        db: AsyncSession,
        run: Run,
        kind: str,
        payload: dict[str, Any],
        event_id: UUID | None = None,
    ) -> None:
        # Caller holds the Run row lock until commit, including parallel graph nodes.
        if event_id is not None and await db.scalar(
            select(RunEvent.id).where(
                RunEvent.id == event_id,
                RunEvent.tenant_id == self.tenant_id,
                RunEvent.run_id == self.run_id,
            )
        ):
            return
        seq = await db.scalar(
            select(func.coalesce(func.max(RunEvent.seq), 0)).where(
                RunEvent.tenant_id == self.tenant_id, RunEvent.run_id == self.run_id
            )
        )
        db.add(
            RunEvent(
                id=event_id or uuid4(),
                tenant_id=run.tenant_id,
                run_id=run.id,
                seq=int(seq or 0) + 1,
                type=kind,
                schema_version=1,
                payload_json=payload,
            )
        )
        await db.flush()

    async def emit(self, kind: str, payload: dict[str, Any], identity: str | None = None) -> None:
        async with self.sessions() as db:
            run = await self.lock(db)
            if run.status in TERMINAL:
                return
            await self.append(
                db, run, kind, payload, uuid5(self.run_id, identity) if identity else None
            )
            await db.commit()

    async def start_step(self, node: str) -> UUID:
        step_id = uuid4()
        async with self.sessions() as db:
            run = await self.lock(db)
            if run.status in TERMINAL:
                raise DomainError(409, "run_terminal", "运行已经结束")
            db.add(
                RunStep(
                    id=step_id,
                    tenant_id=run.tenant_id,
                    run_id=run.id,
                    node=node,
                    status="running",
                    artifact_refs={},
                )
            )
            await self.append(db, run, "agent.started", {"step_id": str(step_id), "node": node})
            await db.commit()
        return step_id

    async def finish_step(
        self, step_id: UUID, node: str, status: str, refs: dict[str, Any]
    ) -> None:
        async with self.sessions() as db:
            run = await self.lock(db)
            step = await db.scalar(
                select(RunStep).where(
                    RunStep.id == step_id,
                    RunStep.run_id == run.id,
                    RunStep.tenant_id == run.tenant_id,
                )
            )
            if step is not None:
                step.status, step.ended_at, step.artifact_refs = status, datetime.now(UTC), refs
            if run.status not in TERMINAL:
                await self.append(
                    db,
                    run,
                    "agent.completed",
                    {
                        "step_id": str(step_id),
                        "node": node,
                        "status": status,
                        "artifact_refs": refs,
                    },
                )
            await db.commit()

    async def start_tool(self, name: str, args: dict[str, Any]) -> UUID:
        call_id = uuid4()
        async with self.sessions() as db:
            run = await self.lock(db)
            if run.status in TERMINAL:
                raise DomainError(409, "run_terminal", "运行已经结束")
            safe = public_arguments(args)
            db.add(
                ToolCall(
                    id=call_id,
                    tenant_id=run.tenant_id,
                    run_id=run.id,
                    step_id=ACTIVE_STEP.get(),
                    tool_name=name,
                    args_redacted_json=safe,
                    status="running",
                    idempotency_key=str(call_id),
                )
            )
            await self.append(
                db,
                run,
                "tool.started",
                {"tool_call_id": str(call_id), "name": name, "arguments": safe},
            )
            await db.commit()
        return call_id

    async def finish_tool(
        self, call_id: UUID, name: str, count: int | None, error: str | None
    ) -> None:
        async with self.sessions() as db:
            run = await self.lock(db)
            call = await db.scalar(
                select(ToolCall).where(
                    ToolCall.id == call_id,
                    ToolCall.run_id == run.id,
                    ToolCall.tenant_id == run.tenant_id,
                )
            )
            status = "cancelled" if error == "cancelled" else "failed" if error else "completed"
            if call is not None:
                call.status, call.error_code, call.ended_at = status, error, datetime.now(UTC)
                call.result_ref = {"result_count": count}
            if run.status not in TERMINAL:
                await self.append(
                    db,
                    run,
                    "tool.completed",
                    {
                        "tool_call_id": str(call_id),
                        "name": name,
                        "status": status,
                        "result_count": count,
                        "error_code": error,
                    },
                )
            await db.commit()

    async def model_call(self, call_id: UUID, values: dict[str, Any]) -> None:
        async with self.sessions() as db:
            run = await self.lock(db)
            if run.status in TERMINAL:
                return
            step_id = ACTIVE_STEP.get()
            step = (
                await db.scalar(
                    select(RunStep).where(
                        RunStep.id == step_id,
                        RunStep.run_id == run.id,
                        RunStep.tenant_id == run.tenant_id,
                    )
                )
                if step_id
                else None
            )
            usage = values.get("usage_json")
            if step is not None:
                before = step.usage_json or {"model_calls": 0, "known_calls": 0, "total_tokens": 0}
                total = before.get("total_tokens")
                step.usage_json = {
                    "model_calls": before["model_calls"] + 1,
                    "known_calls": before["known_calls"] + int(usage is not None),
                    "total_tokens": total + usage["total_tokens"]
                    if total is not None and usage and "total_tokens" in usage
                    else None,
                }
            await self.append(
                db,
                run,
                "model.completed",
                {
                    "call_id": str(call_id),
                    "name": values["name"],
                    "model": values.get("model"),
                    "status": values["status"],
                    "error_code": values.get("error_code"),
                    "usage": usage,
                    "prompt_version": values.get("prompt_version"),
                    "started_at": values["started_at"].isoformat(),
                    "ended_at": values["ended_at"].isoformat(),
                },
            )
            await db.commit()

    async def finish(self, status: str, error: str | None, usage: dict[str, Any] | None) -> None:
        async with self.sessions() as db:
            # Thread then Run matches RunPreparation's ordering and message allocation.
            thread_id = await db.scalar(
                select(Run.thread_id).where(Run.id == self.run_id, Run.tenant_id == self.tenant_id)
            )
            await db.scalar(
                select(Thread)
                .where(Thread.id == thread_id, Thread.tenant_id == self.tenant_id)
                .with_for_update()
            )
            run = await self.lock(db)
            if run.status in TERMINAL:
                return
            if run.status == "cancel_requested":
                status, error = "cancelled", "run_cancelled"
            run.status, run.error_code, run.finished_at = status, error, datetime.now(UTC)
            for entity in (RunStep, ToolCall):
                await db.execute(
                    update(entity)
                    .where(
                        entity.run_id == run.id,
                        entity.tenant_id == run.tenant_id,
                        entity.status == "running",
                    )
                    .values(
                        status="cancelled" if status == "cancelled" else "failed",
                        ended_at=run.finished_at,
                    )
                )
            run.usage_json = usage
            report_id = await db.scalar(
                select(Report.id).where(Report.run_id == run.id, Report.tenant_id == run.tenant_id)
            )
            sequence = await db.scalar(
                select(func.coalesce(func.max(Message.sequence), 0)).where(
                    Message.thread_id == run.thread_id, Message.tenant_id == run.tenant_id
                )
            )
            text = {
                "completed": "研究已完成，可查看报告及证据。",
                "needs_review": "研究结果需要复核，请查看报告限制与运行记录。",
                "failed": "研究执行失败，请查看错误原因后重试。",
                "cancelled": "研究已取消，已保存的结果仍可查看。",
            }[status]
            message_id = uuid5(run.id, "final-message")
            db.add(
                Message(
                    id=message_id,
                    tenant_id=run.tenant_id,
                    thread_id=run.thread_id,
                    run_id=run.id,
                    role="assistant",
                    sequence=int(sequence or 0) + 1,
                    content_json={
                        "schema_version": 1,
                        "text": text,
                        "run_id": str(run.id),
                        "status": status,
                        "report_id": str(report_id) if report_id else None,
                    },
                )
            )
            await self.append(
                db, run, "message.delta", {"message_id": str(message_id), "final": True}
            )
            terminal = (
                "run.cancelled"
                if status == "cancelled"
                else "run.failed"
                if status == "failed"
                else "run.completed"
            )
            await self.append(
                db,
                run,
                terminal,
                {
                    "status": status,
                    "error_code": error,
                    "report_id": str(report_id) if report_id else None,
                },
            )
            project = await db.scalar(
                select(Project)
                .where(Project.id == run.project_id, Project.tenant_id == run.tenant_id)
                .with_for_update()
            )
            if project is not None:
                other_active = await db.scalar(
                    select(Run.id)
                    .where(
                        Run.project_id == run.project_id,
                        Run.tenant_id == run.tenant_id,
                        Run.id != run.id,
                        Run.status.in_(("pending", "running", "cancel_requested")),
                    )
                    .limit(1)
                )
                project.status = (
                    "running" if other_active else "draft" if status == "cancelled" else status
                )
            await db.commit()

    async def history(self, after_seq: int, limit: int = 500) -> list[RunEventView]:
        async with self.sessions() as db:
            run = await db.scalar(
                select(Run).where(Run.id == self.run_id, Run.tenant_id == self.tenant_id)
            )
            if run is None:
                raise DomainError(404, "not_found", "运行不存在或无权访问")
            rows = await db.scalars(
                select(RunEvent)
                .where(
                    RunEvent.run_id == run.id,
                    RunEvent.tenant_id == run.tenant_id,
                    RunEvent.seq > after_seq,
                )
                .order_by(RunEvent.seq)
                .limit(limit)
            )
            return [
                RunEventView(
                    event_id=r.id,
                    seq=r.seq,
                    run_id=run.id,
                    thread_id=run.thread_id,
                    type=r.type,
                    timestamp=r.created_at,
                    payload=r.payload_json,
                )
                for r in rows
            ]
