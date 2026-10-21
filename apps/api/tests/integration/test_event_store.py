import asyncio
from uuid import uuid4

import pytest

from app.application.auth import AuthService
from app.application.run_events import stream_run_events
from app.application.run_preparation import RunPreparation, RunRequest
from app.infrastructure.event_store import EventStore, fail_orphaned_runs
from tests.integration.test_skill_snapshots import thread
from tests.integration.test_skills import headers, register

pytestmark = pytest.mark.integration


def prepare(client):
    register(client)
    thread_id = thread(client)
    token = client.cookies["sg_session"]

    async def exercise():
        async with client.app.state.resources.sessions() as db:
            context = await AuthService(db, client.app.state.settings).resolve(token)
            run = await RunPreparation(db, context, client.app.state.skills).prepare(
                thread_id,
                RunRequest(user_message="Isolated event persistence fixture"),
                str(uuid4()),
            )
        return context, run.run_id, token

    return thread_id, client.portal.call(exercise)


def test_parallel_events_have_transactional_sequences_and_restart_finalizes_once(api_client):
    thread_id, (context, run_id, _) = prepare(api_client)

    async def exercise():
        events = EventStore(api_client.app.state.resources.sessions, context, run_id)
        await asyncio.gather(*[events.emit("tool.completed", {"index": i}) for i in range(16)])
        await asyncio.gather(*[events.emit("plan.updated", {}, "stable-plan") for _ in range(4)])
        rows = await events.history(0)
        assert [r.seq for r in rows] == list(range(1, 18))
        assert sum(r.type == "plan.updated" for r in rows) == 1
        await fail_orphaned_runs(api_client.app.state.resources.sessions)
        await fail_orphaned_runs(api_client.app.state.resources.sessions)
        rows = await events.history(0)
        assert sum(r.type == "run.failed" for r in rows) == 1
        assert rows[-1].payload["error_code"] == "process_restarted"
        await events.emit("tool.started", {})
        assert len(await events.history(0)) == len(rows)

    api_client.portal.call(exercise)
    messages = api_client.get(f"/api/v1/threads/{thread_id}/messages").json()["data"]
    assert [r["role"] for r in messages] == ["user", "assistant"]


def test_revoked_cookie_stops_an_existing_sse_subscription(api_client):
    _, (context, run_id, token) = prepare(api_client)
    resources = api_client.app.state.resources

    async def connected():
        await EventStore(resources.sessions, context, run_id).emit("run.started", {})

        async def disconnected():
            return False

        stream = stream_run_events(
            resources, api_client.app.state.settings, context, token, run_id, 0, disconnected
        )
        assert '"type":"run.started"' in await anext(stream)
        return stream

    stream = api_client.portal.call(connected)
    response = api_client.post("/api/v1/auth/logout", headers=headers(api_client))
    assert response.status_code == 204

    async def revoked():
        with pytest.raises(StopAsyncIteration):
            await asyncio.wait_for(anext(stream), timeout=2)
        await stream.aclose()

    api_client.portal.call(revoked)
