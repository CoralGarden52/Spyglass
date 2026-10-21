import time
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.agent.runtime.executor import LocalRunExecutor, ResearchRunner
from app.application.auth import AuthService
from app.application.run_preparation import RunPreparation, RunRequest
from app.infrastructure.database.knowledge import AnalysisArtifact, QualityReview, ReportVersion
from app.infrastructure.research_store import ResearchStore
from tests.integration.test_skill_snapshots import thread
from tests.integration.test_skills import headers, register
from tests.runtime_fixtures import ControlledModel, ControlledTools

pytestmark = pytest.mark.integration


def test_real_graph_persists_parallel_analysis_and_directed_repairs(api_client: TestClient) -> None:
    register(api_client)
    thread_id = thread(api_client)
    token = api_client.cookies["sg_session"]

    async def exercise():
        async with api_client.app.state.resources.sessions() as db:
            context = await AuthService(db, api_client.app.state.settings).resolve(token)
            prepared = await RunPreparation(db, context, api_client.app.state.skills).prepare(
                thread_id,
                RunRequest(user_message="Controlled fixture: compare Alpha"),
                str(uuid4()),
            )
        model = ControlledModel(repair_target="analyst")
        runner = ResearchRunner(
            api_client.app.state.resources, api_client.app.state.settings, model, ControlledTools()
        )
        result = await runner.execute(context, prepared.run_id)
        assert result["status"] == "completed"
        assert model.peak_analysts == 3
        assert result["review_count"] == 2
        assert result["repair_changed"] is True
        checkpoint = await runner.checkpoint(context, prepared.run_id)
        assert checkpoint["run_id"] == str(prepared.run_id)
        return prepared.run_id

    run_id = api_client.portal.call(exercise)
    response = api_client.get(
        f"/api/v1/research/{api_client.get(f'/api/v1/threads/{thread_id}').json()['data']['project_id']}/reports"
    )
    assert response.status_code == 200
    report_id = response.json()["data"][0]["id"]
    report = api_client.get(f"/api/v1/reports/{report_id}").json()["data"]
    assert len(report["content"]["sections"]) == 4
    assert report["run_id"] == str(run_id)
    assert len(report["search_sources"]) == 4
    assert report["search_sources"][0]["result"]["source_confidence"] == 0.86
    assert report["content"]["sentiment_summary"]["sample_count"] == 1
    evidence_id = report["content"]["sections"][0]["claims"][0]["evidence_ids"][0]
    assert api_client.get(f"/api/v1/evidence/{evidence_id}").status_code == 200
    api_client.post("/api/v1/auth/logout", headers=headers(api_client))
    register(api_client, "other-runtime@example.com")
    assert api_client.get(f"/api/v1/reports/{report_id}").status_code == 404
    assert api_client.get(f"/api/v1/evidence/{evidence_id}").status_code == 404


@pytest.mark.parametrize("target", ["collector", "writer"])
def test_reviewer_routes_to_actual_responsible_node(api_client: TestClient, target: str) -> None:
    register(api_client)
    thread_id = thread(api_client)
    token = api_client.cookies["sg_session"]

    async def exercise():
        async with api_client.app.state.resources.sessions() as db:
            context = await AuthService(db, api_client.app.state.settings).resolve(token)
            prepared = await RunPreparation(db, context, api_client.app.state.skills).prepare(
                thread_id, RunRequest(user_message="Controlled fixture Alpha"), str(uuid4())
            )
        model = ControlledModel(repair_target=target)
        # A writer repair changes the selected title without recomputing analyses.
        if target == "writer":
            model.calls["writer"] = -1
        runner = ResearchRunner(
            api_client.app.state.resources, api_client.app.state.settings, model, ControlledTools()
        )
        result = await runner.execute(context, prepared.run_id)
        assert result["review_count"] == 2
        assert model.calls[target] >= 2 if target != "writer" else model.calls["writer"] == 1
        records = await ResearchStore(
            api_client.app.state.resources.sessions, context, prepared.run_id
        ).rows(QualityReview)
        assert records[0].payload["next_target"] == target
        assert result["status"] == "completed"

    api_client.portal.call(exercise)


def test_no_change_cannot_be_called_successful_repair(api_client: TestClient) -> None:
    register(api_client)
    thread_id = thread(api_client)
    token = api_client.cookies["sg_session"]

    async def exercise():
        async with api_client.app.state.resources.sessions() as db:
            context = await AuthService(db, api_client.app.state.settings).resolve(token)
            prepared = await RunPreparation(db, context, api_client.app.state.skills).prepare(
                thread_id, RunRequest(user_message="Controlled fixture Alpha"), str(uuid4())
            )
        runner = ResearchRunner(
            api_client.app.state.resources,
            api_client.app.state.settings,
            ControlledModel(repair_target="analyst", unchanged=True),
            ControlledTools(),
        )
        result = await runner.execute(context, prepared.run_id)
        assert result["status"] == "needs_review"
        assert result["repair_changed"] is False

    api_client.portal.call(exercise)


def test_schema_error_is_repaired_and_real_output_changes(api_client: TestClient) -> None:
    register(api_client)
    thread_id = thread(api_client)
    token = api_client.cookies["sg_session"]

    async def exercise():
        async with api_client.app.state.resources.sessions() as db:
            context = await AuthService(db, api_client.app.state.settings).resolve(token)
            prepared = await RunPreparation(db, context, api_client.app.state.skills).prepare(
                thread_id, RunRequest(user_message="Controlled fixture Alpha"), str(uuid4())
            )
        model = ControlledModel(invalid_schema=True)
        result = await ResearchRunner(
            api_client.app.state.resources, api_client.app.state.settings, model, ControlledTools()
        ).execute(context, prepared.run_id)
        assert result["status"] == "completed"
        store = ResearchStore(api_client.app.state.resources.sessions, context, prepared.run_id)
        revisions = [
            r for r in await store.rows(AnalysisArtifact) if r.skill_id == "product_capability"
        ]
        assert len(revisions) == 2 and revisions[0].digest != revisions[1].digest

    api_client.portal.call(exercise)


def test_run_deadline_stops_models_and_preserves_explicit_missing_core(
    api_client: TestClient,
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
        # Leave enough time for real PostgreSQL trace writes before the slow analysts.
        settings = api_client.app.state.settings.model_copy(update={"run_timeout_seconds": 1.0})
        model = ControlledModel(slow_analysis=10)
        started = time.monotonic()
        result = await ResearchRunner(
            api_client.app.state.resources, settings, model, ControlledTools()
        ).execute(context, prepared.run_id)
        assert time.monotonic() - started < 3
        assert result["status"] == "needs_review"
        assert model.peak_analysts == 3
        assert model.active_analysts == 0
        store = ResearchStore(api_client.app.state.resources.sessions, context, prepared.run_id)
        assert (await store.run()).error_code == "run_timeout"
        assert {r.skill_id for r in await store.rows(AnalysisArtifact)} == {
            "product_capability",
            "pricing_analysis",
            "user_sentiment",
            "swot_analysis",
        }
        assert await store.rows(ReportVersion)

    api_client.portal.call(exercise)


def test_executor_capacity_and_immediate_cancel_release_active_run(api_client: TestClient) -> None:
    register(api_client)
    thread_id = thread(api_client)
    second = thread(api_client)
    token = api_client.cookies["sg_session"]

    async def exercise():
        async with api_client.app.state.resources.sessions() as db:
            context = await AuthService(db, api_client.app.state.settings).resolve(token)
            preparation = RunPreparation(db, context, api_client.app.state.skills)
            first = await preparation.prepare(
                thread_id, RunRequest(user_message="Controlled fixture Alpha"), str(uuid4())
            )
            other = await preparation.prepare(
                second, RunRequest(user_message="Controlled fixture Alpha"), str(uuid4())
            )
        executor = LocalRunExecutor(
            ResearchRunner(
                api_client.app.state.resources,
                api_client.app.state.settings,
                ControlledModel(slow_analysis=10),
                ControlledTools(),
            ),
            1,
        )
        await executor.submit(context, first.run_id)
        from app.domain.errors import DomainError

        with pytest.raises(DomainError, match="executor_busy"):
            await executor.submit(context, other.run_id)
        await executor.request_cancel(context, first.run_id)
        assert await executor.get_status(context, first.run_id) == "cancelled"
        await executor.close()

    api_client.portal.call(exercise)
