import asyncio
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.agent.agents.reporting import ReportingNodes
from app.agent.runtime.contracts import ModelInput, ModelReply
from app.agent.runtime.executor import LocalRunExecutor, ResearchRunner
from app.application.auth import AuthService
from app.application.run_preparation import RunPreparation, RunRequest
from app.infrastructure.database.knowledge import ReportVersion
from app.infrastructure.providers.chat import ProviderError
from app.infrastructure.research_store import ResearchStore
from tests.integration.test_skill_snapshots import thread
from tests.integration.test_skills import register
from tests.runtime_fixtures import SECOND_QUOTE, ControlledModel, ControlledTools

pytestmark = pytest.mark.integration


class MissingEvidenceModel(ControlledModel):
    async def generate(self, call: ModelInput) -> ModelReply:
        reply = await super().generate(call)
        if (
            call.role == "analyst"
            and call.context["skill_id"] == "product_capability"
            and self.calls["product_capability"] == 1
        ):
            reply.data["positioning"][0]["evidence_ids"] = [str(uuid4())]
        return reply


def test_missing_evidence_fixture_triggers_real_collector_repair(api_client: TestClient) -> None:
    register(api_client)
    thread_id = thread(api_client)
    token = api_client.cookies["sg_session"]

    async def exercise():
        async with api_client.app.state.resources.sessions() as db:
            context = await AuthService(db, api_client.app.state.settings).resolve(token)
            prepared = await RunPreparation(db, context, api_client.app.state.skills).prepare(
                thread_id, RunRequest(user_message="Controlled fixture Alpha"), str(uuid4())
            )
        model = MissingEvidenceModel()
        result = await ResearchRunner(
            api_client.app.state.resources, api_client.app.state.settings, model, ControlledTools()
        ).execute(context, prepared.run_id)
        assert result["status"] == "completed"
        assert model.calls["collector"] == 2
        assert result["repair_changed"] is True
        from app.infrastructure.database.knowledge import QualityReview

        reviews = await ResearchStore(
            api_client.app.state.resources.sessions, context, prepared.run_id
        ).rows(QualityReview)
        assert reviews[0].payload["issues"][0]["type"] == "missing_evidence"
        assert reviews[0].payload["next_target"] == "collector"

    api_client.portal.call(exercise)


class MultiReviewModel(ControlledModel):
    def __init__(self, drop: bool):
        super().__init__(repair_target="analyst" if drop else None)
        self.drop = drop

    async def generate(self, call: ModelInput) -> ModelReply:
        reply = await super().generate(call)
        if call.role == "normalizer":
            reply.data["reviews"].append({**reply.data["reviews"][0], "quote": SECOND_QUOTE})
        if call.role == "analyst" and call.context["skill_id"] == "user_sentiment":
            observations = []
            for sample in call.context["review_samples"]:
                opinion = "fast" if "fast" in sample["quote"] else "reliable"
                observations.append(
                    {
                        "evidence_id": sample["evidence_id"],
                        "fingerprint": sample["fingerprint"],
                        "source_platform": sample["source_platform"],
                        "overall_sentiment": "positive",
                        "aspects": [
                            {
                                "aspect_key": "performance",
                                "opinion_span": opinion,
                                "sentiment": "positive",
                                "evidence_id": sample["evidence_id"],
                            }
                        ],
                    }
                )
            reply.data["reviews"] = (
                [] if self.drop and self.calls["user_sentiment"] > 1 else observations
            )
        if call.role == "reviewer" and reply.data["issues"]:
            reply.data["issues"][0]["skill_id"] = "user_sentiment"
        return reply


@pytest.mark.parametrize("drop", [False, True])
def test_same_page_reviews_remain_distinct_and_stale_classifications_are_excluded(
    api_client: TestClient, drop: bool
) -> None:
    register(api_client)
    thread_id = thread(api_client)
    token = api_client.cookies["sg_session"]

    async def exercise():
        async with api_client.app.state.resources.sessions() as db:
            context = await AuthService(db, api_client.app.state.settings).resolve(token)
            prepared = await RunPreparation(db, context, api_client.app.state.skills).prepare(
                thread_id, RunRequest(user_message="Controlled fixture Alpha"), str(uuid4())
            )
        result = await ResearchRunner(
            api_client.app.state.resources,
            api_client.app.state.settings,
            MultiReviewModel(drop),
            ControlledTools(),
        ).execute(context, prepared.run_id)
        store = ResearchStore(api_client.app.state.resources.sessions, context, prepared.run_id)
        versions = await store.rows(ReportVersion)
        summary = max(versions, key=lambda r: r.version).content_json["sentiment_summary"]
        assert summary["sample_count"] == 2
        assert summary["classified_count"] == (0 if drop else 2)
        assert summary["unclassified_count"] == (2 if drop else 0)
        assert summary["overall"]["positive"]["count"] == (0 if drop else 2)
        assert result["status"] == ("needs_review" if drop else "completed")

    api_client.portal.call(exercise)


def test_cancel_during_definition_loading_is_cancelled_not_failed(
    api_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    register(api_client)
    thread_id = thread(api_client)
    token = api_client.cookies["sg_session"]

    async def exercise():
        async with api_client.app.state.resources.sessions() as db:
            context = await AuthService(db, api_client.app.state.settings).resolve(token)
            prepared = await RunPreparation(db, context, api_client.app.state.skills).prepare(
                thread_id, RunRequest(user_message="Controlled fixture Alpha"), str(uuid4())
            )
        started = asyncio.Event()

        async def blocked():
            started.set()
            await asyncio.sleep(10)

        # Match bound-method signature while blocking inside initialized lifecycle.
        async def definitions(store):
            return await blocked()

        monkeypatch.setattr(ResearchStore, "definitions", definitions)
        executor = LocalRunExecutor(
            ResearchRunner(
                api_client.app.state.resources,
                api_client.app.state.settings,
                ControlledModel(),
                ControlledTools(),
            ),
            1,
        )
        await executor.submit(context, prepared.run_id)
        await asyncio.wait_for(started.wait(), 1)
        await executor.request_cancel(context, prepared.run_id)
        assert await executor.get_status(context, prepared.run_id) == "cancelled"
        await executor.close()

    api_client.portal.call(exercise)


def test_two_threads_execute_with_distinct_checkpoint_and_evidence_state(
    api_client: TestClient,
) -> None:
    register(api_client)
    first_thread, second_thread = thread(api_client), thread(api_client)
    token = api_client.cookies["sg_session"]

    async def exercise():
        async with api_client.app.state.resources.sessions() as db:
            context = await AuthService(db, api_client.app.state.settings).resolve(token)
            service = RunPreparation(db, context, api_client.app.state.skills)
            first = await service.prepare(
                first_thread, RunRequest(user_message="Controlled fixture Alpha"), str(uuid4())
            )
            second = await service.prepare(
                second_thread, RunRequest(user_message="Controlled fixture Alpha"), str(uuid4())
            )
        runner = ResearchRunner(
            api_client.app.state.resources,
            api_client.app.state.settings,
            ControlledModel(),
            ControlledTools(),
        )
        results = await asyncio.gather(
            runner.execute(context, first.run_id), runner.execute(context, second.run_id)
        )
        diagnostics = []
        for prepared in (first, second):
            store = ResearchStore(api_client.app.state.resources.sessions, context, prepared.run_id)
            records = await store.rows(ReportVersion)
            diagnostics.append(
                {
                    "error": (await store.run()).error_code,
                    "sections": [
                        (s["skill_id"], s["status"], s["limitations"])
                        for s in max(records, key=lambda r: r.version).content_json["sections"]
                    ],
                }
            )
        assert all(r["status"] == "completed" for r in results), diagnostics
        assert set(results[0]["evidence_ids"]).isdisjoint(results[1]["evidence_ids"])
        one = await runner.checkpoint(context, first.run_id)
        two = await runner.checkpoint(context, second.run_id)
        assert one["run_id"] == str(first.run_id) and two["run_id"] == str(second.run_id)

    api_client.portal.call(exercise)


@pytest.mark.parametrize("stage", ["definitions", "cleanup"])
def test_initialization_and_failure_cleanup_always_persist_terminal_state(
    api_client: TestClient, monkeypatch: pytest.MonkeyPatch, stage: str
) -> None:
    register(api_client)
    thread_id = thread(api_client)
    token = api_client.cookies["sg_session"]

    async def exercise():
        async with api_client.app.state.resources.sessions() as db:
            context = await AuthService(db, api_client.app.state.settings).resolve(token)
            prepared = await RunPreparation(db, context, api_client.app.state.skills).prepare(
                thread_id, RunRequest(user_message="Controlled fixture Alpha"), str(uuid4())
            )
        model = ControlledModel()
        if stage == "definitions":
            monkeypatch.setattr(
                ResearchStore,
                "definitions",
                AsyncMock(side_effect=RuntimeError("controlled initialization failure")),
            )
        else:
            monkeypatch.setattr(
                model, "generate", AsyncMock(side_effect=ProviderError("model_unconfigured"))
            )
            monkeypatch.setattr(
                ReportingNodes,
                "build_draft",
                AsyncMock(side_effect=RuntimeError("controlled cleanup failure")),
            )
        result = await ResearchRunner(
            api_client.app.state.resources, api_client.app.state.settings, model, ControlledTools()
        ).execute(context, prepared.run_id)
        assert result["status"] == "failed"
        assert (
            await ResearchStore(
                api_client.app.state.resources.sessions, context, prepared.run_id
            ).run()
        ).status == "failed"

    api_client.portal.call(exercise)
