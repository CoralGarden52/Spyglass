import asyncio
import hashlib
import json
import shutil
from dataclasses import replace
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select, text
from sqlalchemy.exc import DBAPIError

from app.agent.skills.contracts import schema_document
from app.agent.skills.models import Selection
from app.agent.skills.registry import SkillRegistry
from app.application.auth import AuthService
from app.application.run_preparation import RunPreparation, RunRequest
from app.core.config import ROOT
from app.domain.errors import DomainError
from app.infrastructure.database.research import Message, Run
from app.infrastructure.database.skills import SkillVersion
from app.infrastructure.research_store import ResearchStore
from tests.integration.test_skills import headers, register

pytestmark = pytest.mark.integration


def thread(client: TestClient) -> UUID:
    project = client.post(
        "/api/v1/research", json={"title": "Snapshot test"}, headers=headers(client)
    )
    assert project.status_code == 201
    result = client.post(
        "/api/v1/threads",
        json={"title": "Test", "project_id": project.json()["data"]["id"]},
        headers=headers(client),
    )
    assert result.status_code == 201
    return UUID(result.json()["data"]["id"])


def test_legacy_crlf_catalogue_loads_without_rewriting_history_or_breaking_runs(
    api_client: TestClient,
) -> None:
    register(api_client)
    current = api_client.app.state.skills
    legacy = []
    for definition in current.all():
        manifest = definition.manifest
        directory = ROOT / "extensions/skills" / manifest.id

        def crlf(raw: bytes) -> bytes:
            return raw.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")

        instructions = crlf((directory / "SKILL.md").read_bytes())
        schemas = [
            schema_document(name)
            for name in (manifest.input_schema, manifest.output_schema, manifest.config_schema)
        ]
        old_hash = hashlib.sha256(
            crlf((directory / "manifest.yaml").read_bytes())
            + b"\0"
            + instructions
            + b"\0"
            + json.dumps(schemas, sort_keys=True, ensure_ascii=False).encode()
        ).hexdigest()
        legacy.append(replace(definition, instructions=instructions.decode(), checksum=old_hash))
    api_client.app.state.skills = SkillRegistry(legacy)
    first = api_client.get("/api/v1/skills")
    assert first.status_code == 200
    historical = {item["id"]: item["manifest_checksum"] for item in first.json()["data"]}
    api_client.app.state.skills = current
    loaded = api_client.get("/api/v1/skills")
    assert loaded.status_code == 200
    assert {item["id"]: item["manifest_checksum"] for item in loaded.json()["data"]} == historical
    thread_id = thread(api_client)
    token = api_client.cookies["sg_session"]

    async def prepare_and_check():
        async with api_client.app.state.resources.sessions() as db:
            context = await AuthService(db, api_client.app.state.settings).resolve(token)
            prepared = await RunPreparation(db, context, current).prepare(
                thread_id, RunRequest(user_message="Line ending regression fixture"), str(uuid4())
            )
            rows = (await db.scalars(select(SkillVersion))).all()
            assert len(rows) == 13
            assert {row.id: row.manifest_checksum for row in rows} == historical
            assert all("\r\n" in row.instructions for row in rows)
        for snapshot in prepared.skills:
            assert snapshot.manifest_checksum == historical[snapshot.id]
        definitions = await ResearchStore(
            api_client.app.state.resources.sessions, context, prepared.run_id
        ).definitions()
        assert len(definitions) == 5
        assert all("\r\n" in item["instructions"] for item in definitions.values())

    api_client.portal.call(prepare_and_check)


def test_snapshot_is_atomic_frozen_and_idempotent(api_client: TestClient) -> None:
    register(api_client)
    thread_id = thread(api_client)
    token = api_client.cookies["sg_session"]
    request = RunRequest(
        user_message="Synthetic test request",
        **Selection(advanced_skill_ids=["market_landscape"]).model_dump(),
    )
    key = str(uuid4())

    async def prepare():
        async with api_client.app.state.resources.sessions() as db:
            context = await AuthService(db, api_client.app.state.settings).resolve(token)
            service = RunPreparation(db, context, api_client.app.state.skills)
            return await service.prepare(thread_id, request, key)

    first = api_client.portal.call(prepare)
    api_client.patch(
        "/api/v1/skills/market_landscape/config",
        json={"enabled": False, "expected_revision": 0},
        headers=headers(api_client),
    ).raise_for_status()
    replay = api_client.portal.call(prepare)
    assert replay == first
    assert len(first.skills) == 6
    assert all(s.version == "0.1.0" for s in first.skills)

    async def inspect():
        async with api_client.app.state.resources.sessions() as db:
            assert await db.scalar(select(func.count()).select_from(Run)) == 1
            assert await db.scalar(select(func.count()).select_from(Message)) == 1
            row = await db.get(Run, first.run_id)
            assert row.skills_snapshot_json == [s.model_dump(mode="json") for s in first.skills]
            context = await AuthService(db, api_client.app.state.settings).resolve(token)
            with pytest.raises(DomainError, match="active_run_conflict"):
                await RunPreparation(db, context, api_client.app.state.skills).prepare(
                    thread_id, RunRequest(user_message="Other"), str(uuid4())
                )

    api_client.portal.call(inspect)


def test_versions_are_immutable_in_database(api_client: TestClient) -> None:
    register(api_client)
    api_client.get("/api/v1/skills").raise_for_status()

    async def mutate():
        async with api_client.app.state.resources.sessions() as db:
            with pytest.raises(DBAPIError):
                await db.execute(
                    text("UPDATE skills SET instructions = 'changed' WHERE id = 'ai_llm'")
                )
            await db.rollback()
            with pytest.raises(DBAPIError):
                await db.execute(text("DELETE FROM skills WHERE id = 'ai_llm'"))

    api_client.portal.call(mutate)


def test_version_transition_preserves_history_and_can_migrate_config(
    api_client: TestClient, tmp_path: Path
) -> None:
    register(api_client)
    api_client.patch(
        "/api/v1/skills/user_sentiment/config",
        json={"config": {"review_sample_limit": 80}, "expected_revision": 0},
        headers=headers(api_client),
    ).raise_for_status()
    before = api_client.get("/api/v1/skills/user_sentiment").json()["data"]
    root = tmp_path / "skills"
    shutil.copytree(ROOT / "extensions/skills", root)
    guidance = root / "user_sentiment/SKILL.md"
    guidance.write_text(guidance.read_text("utf-8") + "\nNew version research guidance.\n", "utf-8")
    api_client.app.state.skills = SkillRegistry.from_directory(root)
    assert api_client.get("/api/v1/skills").status_code == 409
    manifest = root / "user_sentiment/manifest.yaml"
    manifest.write_text(
        manifest.read_text("utf-8")
        .replace("version: 0.1.0", "version: 1.0.0")
        .replace("config_schema: SentimentConfig", "config_schema: AnalysisConfig"),
        "utf-8",
    )
    api_client.app.state.skills = SkillRegistry.from_directory(root)
    current = api_client.get("/api/v1/skills/user_sentiment")
    assert current.status_code == 200
    assert current.json()["data"]["config_status"] == "migration_required"
    assert current.json()["data"]["config_version"] == "0.1.0"
    historical = api_client.get("/api/v1/skills/user_sentiment?version=0.1.0").json()["data"]
    assert historical["manifest_checksum"] == before["manifest_checksum"]
    assert historical["instructions"] == before["instructions"]
    assert (
        api_client.post("/api/v1/skills/resolve", json={}, headers=headers(api_client)).json()[
            "error"
        ]["code"]
        == "skill_config_migration_required"
    )
    migrated = api_client.patch(
        "/api/v1/skills/user_sentiment/config",
        json={"config": {"max_findings": 15}, "expected_revision": 1},
        headers=headers(api_client),
    )
    assert migrated.status_code == 200
    assert migrated.json()["data"]["config_status"] == "current"
    assert migrated.json()["data"]["config_version"] == "1.0.0"
    assert (
        api_client.post("/api/v1/skills/resolve", json={}, headers=headers(api_client)).status_code
        == 200
    )


def test_concurrent_preparation_is_tenant_isolated_and_thread_serialized(
    api_client: TestClient,
) -> None:
    register(api_client)
    first_thread, second_thread = thread(api_client), thread(api_client)
    token = api_client.cookies["sg_session"]

    async def prepare(thread_id: UUID, key: str, session_token: str = token):
        async with api_client.app.state.resources.sessions() as db:
            context = await AuthService(db, api_client.app.state.settings).resolve(session_token)
            return await RunPreparation(db, context, api_client.app.state.skills).prepare(
                thread_id, RunRequest(user_message="Concurrent fixture"), key
            )

    async def concurrent():
        key = str(uuid4())
        same, replay, independent = await asyncio.gather(
            prepare(first_thread, key),
            prepare(first_thread, key),
            prepare(second_thread, str(uuid4())),
        )
        assert same == replay
        assert independent.run_id != same.run_id
        outcomes = await asyncio.gather(
            prepare(first_thread, str(uuid4())),
            prepare(first_thread, str(uuid4())),
            return_exceptions=True,
        )
        assert all(
            isinstance(outcome, DomainError) and outcome.code == "active_run_conflict"
            for outcome in outcomes
        )

    api_client.portal.call(concurrent)
    api_client.cookies.clear()
    register(api_client, "another-snapshot@example.com")
    other_token = api_client.cookies["sg_session"]

    async def forbidden():
        with pytest.raises(DomainError, match="not_found"):
            await prepare(first_thread, str(uuid4()), other_token)

    api_client.portal.call(forbidden)
