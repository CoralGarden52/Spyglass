"""Synthetic report only for the disposable Playwright database, never normal service data."""

import json
import sys
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "apps/api"))
sys.path.insert(0, str(ROOT / "apps/api/tests"))
from runtime_fixtures import ControlledModel, ControlledTools  # noqa: E402

from app.agent.runtime.executor import ResearchRunner  # noqa: E402
from app.application.auth import AuthService  # noqa: E402
from app.application.research import ResearchService  # noqa: E402
from app.application.run_preparation import RunPreparation, RunRequest  # noqa: E402
from app.core.config import Settings  # noqa: E402
from app.core.event_loop import database_event_loop  # noqa: E402
from app.domain.schemas import ProjectInput, ThreadInput  # noqa: E402
from app.main import create_app  # noqa: E402

settings = Settings()
assert settings.app_env == "test"
assert str(make_url(settings.database_url.get_secret_value()).database).startswith("spyglass_e2e_")
email = f"report-{uuid4().hex}@example.com"
with TestClient(
    create_app(settings),
    backend_options={"loop_factory": database_event_loop},
    headers={"Origin": "http://127.0.0.1:5174"},
) as client:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "Browser-test-passphrase-42",
            "display_name": "隔离测试研究员",
        },
    )
    response.raise_for_status()
    token = client.cookies["sg_session"]

    async def seed():
        async with client.app.state.resources.sessions() as db:
            context = await AuthService(db, settings).resolve(token)
            research = ResearchService(db, context)
            project = await research.create_project(
                ProjectInput(title="CONTROLLED SYNTHETIC REPORT"), str(uuid4())
            )
            thread = await research.create_thread(
                ThreadInput(project_id=project.data.id, title="隔离浏览器验收"), str(uuid4())
            )
            prepared = await RunPreparation(db, context, client.app.state.skills).prepare(
                thread.data.id,
                RunRequest(user_message="Controlled fixture: compare Alpha"),
                str(uuid4()),
            )
        state = await ResearchRunner(
            client.app.state.resources,
            settings,
            ControlledModel(repair_target="analyst"),
            ControlledTools(),
        ).execute(context, prepared.run_id)
        assert state["status"] == "completed"
        return str(project.data.id)

    project_id = client.portal.call(seed)
artifact = ROOT / ".artifacts/e2e-report-seed.json"
artifact.parent.mkdir(exist_ok=True)
artifact.write_text(
    json.dumps({"email": email, "project_id": project_id, "kind": "isolated_synthetic_fixture"}),
    "utf-8",
)
print("Created isolated synthetic report for browser assertions.")
