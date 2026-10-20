import asyncio
from typing import Any, Protocol, cast
from uuid import UUID

from sqlalchemy import select

from app.agent.agents.reporting import ReportingNodes
from app.agent.runtime.checkpoint import postgres_checkpoint
from app.agent.runtime.context import NodeContext, empty_analysis
from app.agent.runtime.contracts import ModelProvider
from app.agent.runtime.graph import build_graph
from app.agent.runtime.state import ResearchState
from app.agent.tools.registry import ToolRegistry
from app.application.auth import TenantContext
from app.core.config import Settings
from app.domain.errors import DomainError
from app.infrastructure.database.knowledge import QualityReview, ReportVersion
from app.infrastructure.database.research import Run
from app.infrastructure.providers.chat import ProviderError
from app.infrastructure.research_store import ResearchStore
from app.infrastructure.resources import Resources


class RunExecutor(Protocol):
    async def submit(self, context: TenantContext, run_id: UUID) -> None: ...
    async def request_cancel(self, context: TenantContext, run_id: UUID) -> None: ...
    async def get_status(self, context: TenantContext, run_id: UUID) -> str: ...


class ResearchRunner:
    def __init__(
        self, resources: Resources, settings: Settings, model: ModelProvider, tools: ToolRegistry
    ):
        self.resources, self.settings, self.model, self.tools = resources, settings, model, tools

    async def claim(self, store: ResearchStore) -> bool:
        async with store.sessions() as db:
            row = await db.scalar(
                select(Run)
                .where(Run.id == store.run_id, Run.tenant_id == store.context.tenant_id)
                .with_for_update()
            )
            if row is None:
                raise DomainError(404, "not_found", "运行不存在或无权访问")
            if row.status != "pending":
                return False
            from datetime import UTC, datetime

            row.status = "running"
            row.started_at = datetime.now(UTC)
            await db.commit()
            return True

    async def execute(self, context: TenantContext, run_id: UUID) -> ResearchState:
        store = ResearchStore(self.resources.sessions, context, run_id)
        run = await store.run()
        if not await self.claim(store):
            return {"run_id": str(run_id), "status": run.status}
        node_context: NodeContext | None = None
        state: ResearchState = {
            "tenant_id": str(context.tenant_id),
            "user_id": str(context.user_id),
            "project_id": str(run.project_id),
            "thread_id": str(run.thread_id),
            "run_id": str(run_id),
            "plan_id": None,
            "evidence_ids": [],
            "profile_ids": [],
            "product_ref": None,
            "pricing_ref": None,
            "sentiment_ref": None,
            "analysis_refs": {},
            "report_draft_id": None,
            "review_result": None,
            "review_count": 0,
            "status": "running",
            "repair_changed": False,
            "writer_error": None,
        }
        failure = None
        try:
            async with asyncio.timeout(self.settings.run_timeout_seconds):
                node_context = NodeContext(store, self.model, self.tools, await store.definitions())
                async with postgres_checkpoint(self.settings) as checkpoint:
                    graph = build_graph(
                        node_context, checkpoint, self.settings.research_max_repairs
                    )
                    state = cast(
                        ResearchState,
                        await graph.ainvoke(
                            state,
                            {
                                "configurable": {"thread_id": str(run.thread_id)},
                                "recursion_limit": 100,
                            },
                        ),
                    )
        except TimeoutError:
            failure = "run_timeout"
        except ProviderError as exc:
            failure = str(exc)
        except asyncio.CancelledError:
            failure = "run_cancelled"
        except Exception as exc:
            failure = "runtime_error_" + type(exc).__name__[:50]
        if failure:
            state["status"] = "cancelled" if failure == "run_cancelled" else "needs_review"
            try:
                async with asyncio.timeout(15):
                    if node_context is None:
                        state["status"] = "cancelled" if failure == "run_cancelled" else "failed"
                    else:
                        existing = await store.artifacts()
                        reviews = await store.rows(QualityReview)
                        if reviews:
                            latest = max(reviews, key=lambda r: r.payload["review_count"])
                            state["review_count"] = latest.payload["review_count"]
                            state["review_result"] = latest.payload
                        state["analysis_refs"] = {k: str(a.id) for k, a in existing.items()}
                        state["evidence_ids"] = [e["id"] for e in await store.evidence()]
                        for key, skill in node_context.definitions.items():
                            if skill["kind"] != "scenario" and key not in existing:
                                await store.artifact(
                                    skill, empty_analysis(skill["output_schema"], failure), 0
                                )
                        draft = await ReportingNodes(node_context, 0).build_draft()
                        draft.status = "needs_review"
                        draft.limitations.append(failure)
                        versions = await store.rows(ReportVersion)
                        state["report_draft_id"] = str(
                            await store.save_report(
                                draft, max((v.version for v in versions), default=0)
                            )
                        )
            except (Exception, asyncio.CancelledError):
                cancelled = failure == "run_cancelled"
                state["status"] = "cancelled" if cancelled else "failed"
                failure = "cancel_cleanup_error" if cancelled else "failure_cleanup_error"
        # Cleanup failure cannot bypass terminal persistence on a healthy database.
        await asyncio.shield(store.status(state["status"], failure))
        return state

    async def checkpoint(self, context: TenantContext, run_id: UUID) -> dict[str, Any]:
        store = ResearchStore(self.resources.sessions, context, run_id)
        run = await store.run()
        async with postgres_checkpoint(self.settings) as checkpoint:
            saved = await checkpoint.aget_tuple({"configurable": {"thread_id": str(run.thread_id)}})
            values = saved.checkpoint.get("channel_values", {}) if saved else {}
            if values.get("run_id") != str(run_id):
                raise DomainError(404, "checkpoint_not_found", "当前检查点不属于此运行")
            return dict(values)


class LocalRunExecutor:
    def __init__(self, runner: ResearchRunner, capacity: int):
        self.runner, self.capacity = runner, capacity
        self.tasks: dict[UUID, asyncio.Task[ResearchState]] = {}
        self.contexts: dict[UUID, TenantContext] = {}

    async def submit(self, context: TenantContext, run_id: UUID) -> None:
        await ResearchStore(self.runner.resources.sessions, context, run_id).run()
        if run_id in self.tasks:
            return
        if len(self.tasks) >= self.capacity:
            raise DomainError(503, "executor_busy", "本地运行容量已满，请稍后重试")
        task = asyncio.create_task(self.runner.execute(context, run_id))
        self.tasks[run_id] = task
        self.contexts[run_id] = context

        def completed(done: asyncio.Task[ResearchState]) -> None:
            self.tasks.pop(run_id, None)
            self.contexts.pop(run_id, None)
            if not done.cancelled():
                done.exception()

        task.add_done_callback(completed)

    async def request_cancel(self, context: TenantContext, run_id: UUID) -> None:
        store = ResearchStore(self.runner.resources.sessions, context, run_id)
        run = await store.run()
        if run_id in self.tasks:
            task = self.tasks[run_id]
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
            if (await store.run()).status in {"pending", "running", "cancel_requested"}:
                await store.status("cancelled", "run_cancelled")
        elif run.status == "pending":
            await store.status("cancelled", "run_cancelled")

    async def get_status(self, context: TenantContext, run_id: UUID) -> str:
        return (await ResearchStore(self.runner.resources.sessions, context, run_id).run()).status

    async def close(self) -> None:
        active = list(self.contexts.items())
        if active:
            await asyncio.gather(
                *(self.request_cancel(context, run_id) for run_id, context in active),
                return_exceptions=True,
            )
