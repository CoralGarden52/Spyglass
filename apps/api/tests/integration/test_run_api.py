"""Public Run/SSE contracts against disposable PostgreSQL and controlled providers.

All synthetic model/source data stays inside the existing ``api_client`` test DB.
The executor and LangGraph remain real; no paid provider is called.
"""

import asyncio
import json
import time
from collections.abc import Iterator
from datetime import datetime
from threading import Event
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.agent.runtime.contracts import ModelInput, ModelReply
from tests.integration.test_skill_snapshots import thread
from tests.integration.test_skills import headers, register
from tests.runtime_fixtures import ControlledModel, ControlledTools

pytestmark = pytest.mark.integration
TERMINAL = {"completed", "failed", "cancelled", "needs_review"}
REQUEST = {"user_message": "CONTROLLED SYNTHETIC FIXTURE: compare Alpha"}


class GatedModel(ControlledModel):
    """Pause actual Planner execution until the test releases it or cancels the Run."""

    def __init__(self) -> None:
        super().__init__()
        self.entered = asyncio.Event()
        self.release = asyncio.Event()

    async def generate(self, call: ModelInput) -> ModelReply:
        if call.role == "planner":
            self.entered.set()
            await self.release.wait()
        return await super().generate(call)


@pytest.fixture
def controlled_run(api_client: TestClient) -> tuple[ControlledModel, ControlledTools]:
    model, tools = ControlledModel(), ControlledTools()
    api_client.app.state.settings = api_client.app.state.settings.model_copy(
        update={
            "llm_provider": "deepseek",
            "deepseek_api_key": SecretStr("synthetic-unused-model-key"),
            "deepseek3_api_key": SecretStr("synthetic-unused-search-key"),
        }
    )
    api_client.app.state.executor.runner.model = model
    api_client.app.state.executor.runner.tools = tools
    return model, tools


@pytest.fixture
def gated_run(
    api_client: TestClient, controlled_run: tuple[ControlledModel, ControlledTools]
) -> Iterator[GatedModel]:
    async def create() -> GatedModel:
        return GatedModel()

    model = api_client.portal.call(create)
    api_client.app.state.executor.runner.model = model
    try:
        yield model
    finally:

        async def release() -> None:
            model.release.set()

        api_client.portal.call(release)


def create_run(client: TestClient, thread_id: UUID, key: str | None = None) -> dict[str, Any]:
    response = client.post(
        f"/api/v1/threads/{thread_id}/runs",
        json=REQUEST,
        headers={**headers(client), "Idempotency-Key": key or str(uuid4())},
    )
    assert response.status_code in {200, 201}, response.text
    body = response.json()
    assert body["schema_version"] == 1
    run = body["data"]
    UUID(run["id"])
    assert run["thread_id"] == str(thread_id)
    assert body["events_url"].endswith(f"/runs/{run['id']}/events")
    return run


def wait_terminal(client: TestClient, run_id: str) -> dict[str, Any]:
    deadline = time.monotonic() + 15
    last: dict[str, Any] = {}
    while time.monotonic() < deadline:
        response = client.get(f"/api/v1/runs/{run_id}")
        assert response.status_code == 200, response.text
        last = response.json()["data"]
        if last["status"] in TERMINAL:
            return last
        Event().wait(0.02)  # Bounded polling of actual persisted status.
    pytest.fail(f"Run {run_id} failed to terminate within 15s; latest public state: {last}")


def wait_planner(client: TestClient, model: GatedModel) -> None:
    async def entered() -> None:
        await asyncio.wait_for(model.entered.wait(), timeout=10)

    client.portal.call(entered)


def history(client: TestClient, run_id: str, **params: int) -> list[dict[str, Any]]:
    response = client.get(f"/api/v1/runs/{run_id}/events/history", params=params)
    assert response.status_code == 200, response.text
    assert response.json()["schema_version"] == 1
    return response.json()["data"]


def sse_events(text: str) -> list[dict[str, Any]]:
    result = []
    for frame in text.replace("\r\n", "\n").split("\n\n"):
        fields = [line for line in frame.splitlines() if line and not line.startswith(":")]
        if not fields:
            continue
        ids = [line.removeprefix("id:").strip() for line in fields if line.startswith("id:")]
        data = [line.removeprefix("data:").lstrip() for line in fields if line.startswith("data:")]
        if not data:
            continue
        item = json.loads("\n".join(data))
        assert ids == [item["event_id"]], f"SSE id must equal persisted event_id: {frame}"
        result.append(item)
    return result


def read_sse(
    client: TestClient,
    run_id: str,
    *,
    after_seq: int | None = None,
    last_event_id: str | None = None,
    disconnect_on_event: bool = False,
) -> tuple[int, dict[str, str], str]:
    """Drive real ASGI with a strict deadline; TestClient buffers live streams."""
    cookie = "; ".join(f"{name}={value}" for name, value in client.cookies.items())

    async def stream() -> tuple[int, dict[str, str], str]:
        disconnected = asyncio.Event()
        sent_request = False
        body = bytearray()
        status = 0
        response_headers: dict[str, str] = {}

        async def receive() -> dict[str, Any]:
            nonlocal sent_request
            if not sent_request:
                sent_request = True
                return {"type": "http.request", "body": b"", "more_body": False}
            await disconnected.wait()
            return {"type": "http.disconnect"}

        async def send(message: dict[str, Any]) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
                response_headers.update(
                    (key.decode(), value.decode()) for key, value in message["headers"]
                )
            if message["type"] == "http.response.body":
                body.extend(message.get("body", b""))
                if disconnect_on_event and b"data:" in body:
                    disconnected.set()

        path = f"/api/v1/runs/{run_id}/events"
        request_headers = [
            (b"cookie", cookie.encode()),
            (b"origin", b"http://127.0.0.1:5173"),
        ]
        if last_event_id is not None:
            request_headers.append((b"last-event-id", last_event_id.encode()))
        scope = {
            "type": "http",
            "http_version": "1.1",
            "method": "GET",
            "scheme": "http",
            "path": path,
            "raw_path": path.encode(),
            "query_string": b"" if after_seq is None else f"after_seq={after_seq}".encode(),
            "root_path": "",
            "server": ("testserver", 80),
            "client": ("testclient", 50000),
            "asgi": {"version": "3.0", "spec_version": "2.0"},
            "headers": request_headers,
        }
        await asyncio.wait_for(client.app(scope, receive, send), timeout=10)
        if disconnect_on_event:
            assert disconnected.is_set(), "No persisted event delivered before stream ended"
        return status, response_headers, body.decode()

    return client.portal.call(stream)


def test_public_run_routes_require_authentication(api_client: TestClient) -> None:
    run_id, thread_id = uuid4(), uuid4()
    for method, path in [
        ("GET", f"/threads/{thread_id}/runs"),
        ("POST", f"/threads/{thread_id}/runs"),
        ("GET", f"/runs/{run_id}"),
        ("GET", f"/runs/{run_id}/events/history"),
        ("GET", f"/runs/{run_id}/events"),
        ("POST", f"/runs/{run_id}/cancel"),
        ("POST", f"/runs/{run_id}/resume"),
    ]:
        response = api_client.request(method, "/api/v1" + path)
        assert response.status_code == 401, f"{method} {path}: {response.text}"
        assert response.json()["error"]["code"] == "unauthorized"


def test_project_threads_are_queryable_and_tenant_isolated(api_client: TestClient) -> None:
    register(api_client)
    thread_id = thread(api_client)
    thread_view = api_client.get(f"/api/v1/threads/{thread_id}").json()["data"]
    path = f"/api/v1/research/{thread_view['project_id']}/threads"
    response = api_client.get(path)
    assert response.status_code == 200, response.text
    assert response.json() == {"schema_version": 1, "data": [thread_view]}
    api_client.post("/api/v1/auth/logout", headers=headers(api_client)).raise_for_status()
    assert api_client.get(path).status_code == 401
    register(api_client, "other-thread-list-fixture@example.com")
    assert api_client.get(path).status_code == 404


def test_public_create_runs_real_graph_and_persists_refresh_state(
    api_client: TestClient, controlled_run: tuple[ControlledModel, ControlledTools]
) -> None:
    register(api_client)
    thread_id = thread(api_client)
    key = str(uuid4())
    initial = create_run(api_client, thread_id, key)
    assert initial["requested_at"]
    assert initial["usage_json"] is None
    run = wait_terminal(api_client, initial["id"])
    assert run["status"] == "completed", run
    assert run["error_code"] is None
    assert run["usage_json"] is None
    assert datetime.fromisoformat(run["requested_at"]) <= datetime.fromisoformat(run["started_at"])
    assert datetime.fromisoformat(run["started_at"]) <= datetime.fromisoformat(run["finished_at"])
    UUID(run["report_id"])
    listing = api_client.get(f"/api/v1/threads/{thread_id}/runs")
    assert listing.status_code == 200, listing.text
    assert listing.json() == {"schema_version": 1, "data": [run]}
    report_response = api_client.get(f"/api/v1/reports/{run['report_id']}")
    assert report_response.status_code == 200, report_response.text
    report = report_response.json()["data"]
    assert report["run_id"] == run["id"]
    assert {s["skill_id"] for s in report["content"]["sections"]} == {
        "product_capability",
        "pricing_analysis",
        "user_sentiment",
        "swot_analysis",
    }
    assert report["content"]["sentiment_summary"]["sample_count"] == 1
    messages = api_client.get(f"/api/v1/threads/{thread_id}/messages").json()["data"]
    assert [m["role"] for m in messages] == ["user", "assistant"]
    assert [m["sequence"] for m in messages] == [1, 2]
    replay = create_run(api_client, thread_id, key)
    assert replay == run
    assert api_client.get(f"/api/v1/threads/{thread_id}/messages").json()["data"] == messages
    model, tools = controlled_run
    assert model.calls["planner"] == 1 and model.calls["writer"] == 1
    assert tools.search_count >= 3
    assert model.peak_analysts == 3
    events_before_cancel = history(api_client, run["id"])
    late_cancel = api_client.post(
        f"/api/v1/runs/{run['id']}/cancel", json={}, headers=headers(api_client)
    )
    assert late_cancel.status_code == 200, late_cancel.text
    assert late_cancel.json()["data"] == run
    assert history(api_client, run["id"]) == events_before_cancel


@pytest.mark.parametrize("unavailable", ["provider", "capacity"])
def test_unavailable_provider_or_capacity_cannot_leave_an_orphan_pending_run(
    api_client: TestClient,
    controlled_run: tuple[ControlledModel, ControlledTools],
    unavailable: str,
) -> None:
    register(api_client)
    thread_id = thread(api_client)
    if unavailable == "provider":
        api_client.app.state.settings = api_client.app.state.settings.model_copy(
            update={"deepseek_api_key": SecretStr(""), "deepseek3_api_key": SecretStr("")}
        )
    else:
        api_client.app.state.executor.capacity = 0
    response = api_client.post(
        f"/api/v1/threads/{thread_id}/runs", json=REQUEST, headers=headers(api_client)
    )
    assert response.status_code == 503, response.text
    assert api_client.get(f"/api/v1/threads/{thread_id}/runs").json()["data"] == []
    assert api_client.get(f"/api/v1/threads/{thread_id}/messages").json()["data"] == []
    model, tools = controlled_run
    assert not model.calls
    assert tools.search_count == 0


def test_active_idempotency_thread_conflict_and_independent_thread(
    api_client: TestClient, gated_run: GatedModel
) -> None:
    register(api_client)
    first_thread, second_thread = thread(api_client), thread(api_client)
    key = str(uuid4())
    first = create_run(api_client, first_thread, key)
    wait_planner(api_client, gated_run)
    assert create_run(api_client, first_thread, key)["id"] == first["id"]
    changed = api_client.post(
        f"/api/v1/threads/{first_thread}/runs",
        json={"user_message": "Different synthetic request"},
        headers={**headers(api_client), "Idempotency-Key": key},
    )
    assert changed.status_code == 409, changed.text
    assert changed.json()["error"]["code"] == "idempotency_conflict"
    conflict = api_client.post(
        f"/api/v1/threads/{first_thread}/runs", json=REQUEST, headers=headers(api_client)
    )
    assert conflict.status_code == 409, conflict.text
    assert conflict.json()["error"]["code"] == "active_run_conflict"
    second = create_run(api_client, second_thread)
    assert first["id"] != second["id"]
    assert len(api_client.get(f"/api/v1/threads/{first_thread}/runs").json()["data"]) == 1
    assert len(api_client.get(f"/api/v1/threads/{second_thread}/runs").json()["data"]) == 1
    assert len(api_client.get(f"/api/v1/threads/{first_thread}/messages").json()["data"]) == 1


def test_run_writes_require_csrf_idempotency_and_valid_input(
    api_client: TestClient, gated_run: GatedModel
) -> None:
    register(api_client)
    thread_id = thread(api_client)
    path = f"/api/v1/threads/{thread_id}/runs"
    missing_csrf = api_client.post(path, json=REQUEST, headers={"Idempotency-Key": str(uuid4())})
    assert missing_csrf.status_code == 403, missing_csrf.text
    missing_key = api_client.post(
        path, json=REQUEST, headers={"X-CSRF-Token": api_client.cookies["sg_csrf"]}
    )
    assert missing_key.status_code == 422, missing_key.text
    for bad in [
        {"user_message": " "},
        {**REQUEST, "scenario_skill_id": ["general_analysis", "ai_llm"]},
        {**REQUEST, "tenant_id": str(uuid4())},
    ]:
        response = api_client.post(path, json=bad, headers=headers(api_client))
        assert response.status_code == 422, response.text
    assert api_client.get(path).json()["data"] == []
    run = create_run(api_client, thread_id)
    wait_planner(api_client, gated_run)
    for operation in ["cancel", "resume"]:
        path = f"/api/v1/runs/{run['id']}/{operation}"
        response = api_client.post(path, json={}, headers={"Idempotency-Key": str(uuid4())})
        assert response.status_code == 403, response.text
        response = api_client.post(
            path, json={}, headers={"X-CSRF-Token": api_client.cookies["sg_csrf"]}
        )
        assert response.status_code == 422, response.text


def test_guessed_run_thread_and_cursor_uuids_cannot_cross_tenants(
    api_client: TestClient, controlled_run: tuple[ControlledModel, ControlledTools]
) -> None:
    register(api_client)
    first_thread = thread(api_client)
    first = wait_terminal(api_client, create_run(api_client, first_thread)["id"])
    foreign_cursor = history(api_client, first["id"])[0]["event_id"]
    api_client.post("/api/v1/auth/logout", headers=headers(api_client)).raise_for_status()
    register(api_client, "other-run-fixture@example.com")
    second_thread = thread(api_client)
    second = wait_terminal(api_client, create_run(api_client, second_thread)["id"])
    for method, path, body in [
        ("GET", f"/threads/{first_thread}/runs", None),
        ("POST", f"/threads/{first_thread}/runs", REQUEST),
        ("GET", f"/runs/{first['id']}", None),
        ("GET", f"/runs/{first['id']}/events/history", None),
        ("GET", f"/runs/{first['id']}/events", None),
        ("POST", f"/runs/{first['id']}/cancel", {}),
        ("POST", f"/runs/{first['id']}/resume", {}),
    ]:
        response = api_client.request(
            method, "/api/v1" + path, json=body, headers=headers(api_client)
        )
        assert response.status_code == 404, f"{method} {path}: {response.text}"
    response = api_client.get(
        f"/api/v1/runs/{second['id']}/events", headers={"Last-Event-ID": foreign_cursor}
    )
    assert response.status_code == 404, response.text
    assert len(api_client.get(f"/api/v1/threads/{second_thread}/runs").json()["data"]) == 1


def test_cancel_is_idempotent_and_persists_one_terminal_message_event(
    api_client: TestClient, gated_run: GatedModel
) -> None:
    register(api_client)
    thread_id = thread(api_client)
    run = create_run(api_client, thread_id)
    wait_planner(api_client, gated_run)
    key = str(uuid4())
    path = f"/api/v1/runs/{run['id']}/cancel"
    cancel_headers = {**headers(api_client), "Idempotency-Key": key}
    first = api_client.post(path, json={}, headers=cancel_headers)
    assert first.status_code == 200, first.text
    terminal = wait_terminal(api_client, run["id"])
    assert terminal["status"] == "cancelled", terminal
    assert terminal["error_code"] == "run_cancelled"
    first_events = history(api_client, run["id"])
    first_messages = api_client.get(f"/api/v1/threads/{thread_id}/messages").json()["data"]
    for write_headers in [cancel_headers, headers(api_client)]:
        repeated = api_client.post(path, json={}, headers=write_headers)
        assert repeated.status_code == 200, repeated.text
        assert repeated.json()["data"] == terminal
    assert history(api_client, run["id"]) == first_events
    assert api_client.get(f"/api/v1/threads/{thread_id}/messages").json()["data"] == first_messages
    assert [m["role"] for m in first_messages] == ["user", "assistant"]
    assert [e["type"] for e in first_events].count("run.cancelled") == 1
    assert first_events[-1]["payload"]["status"] == "cancelled"


def test_resume_without_valid_interrupt_is_explicit_conflict(
    api_client: TestClient, controlled_run: tuple[ControlledModel, ControlledTools]
) -> None:
    register(api_client)
    thread_id = thread(api_client)
    run = wait_terminal(api_client, create_run(api_client, thread_id)["id"])
    before = history(api_client, run["id"])
    response = api_client.post(
        f"/api/v1/runs/{run['id']}/resume", json={}, headers=headers(api_client)
    )
    assert response.status_code == 409, response.text
    assert history(api_client, run["id"]) == before
    assert api_client.get(f"/api/v1/runs/{run['id']}").json()["data"] == run


def test_persisted_events_have_ordered_ids_and_replay_through_terminal_sse(
    api_client: TestClient, controlled_run: tuple[ControlledModel, ControlledTools]
) -> None:
    register(api_client)
    thread_id = thread(api_client)
    run = wait_terminal(api_client, create_run(api_client, thread_id)["id"])
    events = history(api_client, run["id"], limit=500)
    assert len(events) > 10
    assert [e["seq"] for e in events] == list(range(1, len(events) + 1))
    assert len({e["event_id"] for e in events}) == len(events)
    for event in events:
        UUID(event["event_id"])
        assert event["schema_version"] == 1
        assert event["run_id"] == run["id"]
        assert event["thread_id"] == str(thread_id)
        assert datetime.fromisoformat(event["timestamp"]).tzinfo is not None
        assert isinstance(event["payload"], dict)
    event_types = {e["type"] for e in events}
    assert {"agent.started", "agent.completed", "tool.started", "tool.completed"} <= event_types
    assert events[-1]["type"] == "run.completed"
    assert events[-1]["payload"]["status"] == "completed"
    assert events[-1]["payload"]["report_id"] == run["report_id"]
    cursor = events[len(events) // 2]
    expected = [e for e in events if e["seq"] > cursor["seq"]]
    assert history(api_client, run["id"], after_seq=cursor["seq"], limit=500) == expected
    assert history(api_client, run["id"], after_seq=cursor["seq"], limit=2) == expected[:2]
    assert history(api_client, run["id"], after_seq=events[-1]["seq"]) == []
    for arguments in [{"after_seq": cursor["seq"]}, {"last_event_id": cursor["event_id"]}]:
        status, response_headers, body = read_sse(api_client, run["id"], **arguments)
        assert status == 200, body
        assert response_headers["content-type"].startswith("text/event-stream")
        assert sse_events(body) == expected
    status, _, body = read_sse(api_client, run["id"], last_event_id=events[-1]["event_id"])
    assert status == 200, body
    assert sse_events(body) == []


def test_event_cursor_validation_and_same_tenant_run_scope(
    api_client: TestClient, controlled_run: tuple[ControlledModel, ControlledTools]
) -> None:
    register(api_client)
    first = wait_terminal(api_client, create_run(api_client, thread(api_client))["id"])
    second = wait_terminal(api_client, create_run(api_client, thread(api_client))["id"])
    foreign_cursor = history(api_client, first["id"])[0]["event_id"]
    for invalid in [{"after_seq": -1}, {"limit": 0}, {"limit": 501}]:
        response = api_client.get(f"/api/v1/runs/{second['id']}/events/history", params=invalid)
        assert response.status_code == 422, response.text
    negative = api_client.get(f"/api/v1/runs/{second['id']}/events?after_seq=-1")
    assert negative.status_code == 422, negative.text
    for cursor in [foreign_cursor, str(uuid4())]:
        response = api_client.get(
            f"/api/v1/runs/{second['id']}/events", headers={"Last-Event-ID": cursor}
        )
        assert response.status_code == 404, response.text
    malformed = api_client.get(
        f"/api/v1/runs/{second['id']}/events", headers={"Last-Event-ID": "not-a-uuid"}
    )
    assert malformed.status_code == 422, malformed.text


def test_sse_disconnect_does_not_cancel_independent_executor(
    api_client: TestClient, gated_run: GatedModel
) -> None:
    register(api_client)
    thread_id = thread(api_client)
    run = create_run(api_client, thread_id)
    wait_planner(api_client, gated_run)
    status, _, body = read_sse(api_client, run["id"], disconnect_on_event=True)
    assert status == 200, body
    assert sse_events(body)
    still_running = api_client.get(f"/api/v1/runs/{run['id']}").json()["data"]
    assert still_running["status"] == "running", still_running

    async def release() -> None:
        gated_run.release.set()

    api_client.portal.call(release)
    completed = wait_terminal(api_client, run["id"])
    assert completed["status"] == "completed", completed
    assert completed["report_id"]
    assert "run.cancelled" not in {e["type"] for e in history(api_client, run["id"])}


def test_transport_failure_before_evidence_is_failed_not_completed(api_client, controlled_run):
    from app.infrastructure.providers.chat import ProviderError

    class FailedModel:
        async def generate(self, call):
            raise ProviderError("model_transport_error_ConnectError")

    api_client.app.state.executor.runner.model = FailedModel()
    register(api_client)
    run = wait_terminal(api_client, create_run(api_client, thread(api_client))["id"])
    assert run["status"] == "failed"
    assert run["usage_json"] is None
    assert history(api_client, run["id"])[-1]["type"] == "run.failed"
