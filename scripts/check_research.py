"""Opt-in PAID live research on a disposable database; never seeds business data."""

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from uuid import uuid4

import psycopg
from fastapi.testclient import TestClient
from psycopg import sql
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/api"))

from app.application.auth import AuthService  # noqa: E402
from app.application.research import ResearchService  # noqa: E402
from app.application.run_preparation import RunPreparation, RunRequest  # noqa: E402
from app.core.config import Settings  # noqa: E402
from app.core.event_loop import database_event_loop  # noqa: E402
from app.domain.schemas import ProjectInput, ThreadInput  # noqa: E402
from app.infrastructure.database.knowledge import RuntimeCall  # noqa: E402
from app.infrastructure.research_store import ResearchStore  # noqa: E402
from app.main import create_app  # noqa: E402


def main() -> None:
    settings = Settings()
    if (
        not settings.bocha_api_key.get_secret_value()
        or not settings.deepseek_api_key.get_secret_value()
    ):
        raise SystemExit("Required research providers are unconfigured")
    url = make_url(settings.database_url.get_secret_value())
    name = "spyglass_live_" + uuid4().hex
    admin = url.set(drivername="postgresql", database="postgres").render_as_string(False)
    with psycopg.connect(admin, autocommit=True) as db:
        db.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    output = {"kind": "opt_in_live_research", "isolated_database": True}
    try:
        isolated = url.set(database=name).render_as_string(False)
        subprocess.run(
            [sys.executable, "-m", "alembic", "-c", "apps/api/alembic.ini", "upgrade", "head"],
            cwd=ROOT,
            env={**os.environ, "DATABASE_URL": isolated},
            check=True,
            capture_output=True,
            timeout=30,
        )
        scoped = Settings(
            **{
                **settings.model_dump(),
                "database_url": isolated,
                "app_env": "test",
                "auth_rate_limit": 100,
                "rate_limit_namespace": name,
            }
        )
        with TestClient(
            create_app(scoped),
            backend_options={"loop_factory": database_event_loop},
            headers={"Origin": "http://127.0.0.1:5173"},
        ) as client:
            registration = client.post(
                "/api/v1/auth/register",
                json={
                    "email": name + "@example.com",
                    "password": "Live-check-only-passphrase-42",
                    "display_name": "隔离库真实联网验收",
                },
            )
            registration.raise_for_status()
            token = client.cookies["sg_session"]

            async def exercise():
                async with client.app.state.resources.sessions() as db:
                    context = await AuthService(db, scoped).resolve(token)
                    research = ResearchService(db, context)
                    project = await research.create_project(
                        ProjectInput(
                            title="真实联网：AI 编程工具竞品研究", scenario_skill_id="ai_llm"
                        ),
                        str(uuid4()),
                    )
                    thread = await research.create_thread(
                        ThreadInput(project_id=project.data.id, title="真实联网验收"), str(uuid4())
                    )
                    prepared = await RunPreparation(db, context, client.app.state.skills).prepare(
                        thread.data.id,
                        RunRequest(
                            user_message=(
                                "研究 Cursor、Claude Code 与 Windsurf 的产品定位、"
                                "核心功能、定价策略和公开用户评价。"
                                "保留币种、单位与采集日期，区分四类情感及方面，生成有来源的 SWOT；"
                                "不得虚构缺失价格或评价。"
                            ),
                            scenario_skill_id="ai_llm",
                            advanced_skill_ids=["market_landscape"],
                        ),
                        str(uuid4()),
                    )
                started = time.monotonic()
                result = await client.app.state.executor.runner.execute(context, prepared.run_id)
                store = ResearchStore(client.app.state.resources.sessions, context, prepared.run_id)
                evidence = await store.evidence()
                calls = await store.rows(RuntimeCall)
                checkpoint = await client.app.state.executor.runner.checkpoint(
                    context, prepared.run_id
                )
                return {
                    "state": result,
                    "elapsed_seconds": round(time.monotonic() - started, 2),
                    "project_id": str(project.data.id),
                    "evidence": evidence,
                    "call_summary": [
                        {
                            "kind": c.kind,
                            "name": c.name,
                            "model": c.model,
                            "status": c.status,
                            "error_code": c.error_code,
                            "usage": c.usage_json,
                            "started_at": c.started_at.isoformat(),
                            "ended_at": c.ended_at.isoformat(),
                        }
                        for c in calls
                    ],
                    "checkpoint_run_id": checkpoint["run_id"],
                }

            live = client.portal.call(exercise)
            listing = client.get("/api/v1/research/" + live["project_id"] + "/reports")
            listing.raise_for_status()
            report_id = listing.json()["data"][0]["id"]
            report = client.get("/api/v1/reports/" + report_id)
            report.raise_for_status()
            output.update(live)
            output["report"] = report.json()["data"]
            output["report_read_http_status"] = report.status_code
            output["evidence_count"] = len(live["evidence"])
            output["report_sections"] = len(output["report"]["content"]["sections"])
    finally:
        assert name.startswith("spyglass_live_") and len(name) == 46
        with psycopg.connect(admin, autocommit=True) as db:
            db.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name)))
    path = ROOT / ".artifacts/live-research.json"
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(output, ensure_ascii=False, indent=2, default=str), "utf-8")
    print(
        json.dumps(
            {
                k: output[k]
                for k in [
                    "kind",
                    "elapsed_seconds",
                    "evidence_count",
                    "report_sections",
                    "report_read_http_status",
                ]
            },
            ensure_ascii=False,
        )
    )
    print("Run status:", output["state"]["status"])
    print("Artifact: .artifacts/live-research.json")


if __name__ == "__main__":
    main()
