"""Native search metadata in a real migrated, tenant-scoped disposable database."""

from uuid import uuid4

import pytest

from app.application.auth import AuthService
from app.application.run_preparation import RunPreparation, RunRequest
from app.domain.search import SearchResultMetadata
from app.infrastructure.database.knowledge import Evidence
from app.infrastructure.research_store import ResearchStore
from tests.integration.test_skill_snapshots import thread
from tests.integration.test_skills import headers, register

pytestmark = pytest.mark.integration


def test_native_metadata_relevance_recency_and_tenant_readback(api_client):
    register(api_client)
    thread_id = thread(api_client)
    token = api_client.cookies["sg_session"]

    async def exercise():
        async with api_client.app.state.resources.sessions() as db:
            context = await AuthService(db, api_client.app.state.settings).resolve(token)
            prepared = await RunPreparation(db, context, api_client.app.state.skills).prepare(
                thread_id, RunRequest(user_message="Isolated native metadata test"), str(uuid4())
            )
        store = ResearchStore(api_client.app.state.resources.sessions, context, prepared.run_id)
        ids = []
        for score, summary, date in [
            (2.4, "Old model summary", "2023-01-01T00:00:00Z"),
            (2.4, "Recent model summary", "2026-10-19T00:00:00Z"),
            (2.4, "Unknown date summary", None),
            (1.4, "Irrelevant summary", "2026-10-20T00:00:00Z"),
            (2.4, "", "2026-10-20T00:00:00Z"),
        ]:
            native = SearchResultMetadata(
                title="TEST FIXTURE",
                url="https://example.com/pricing",
                summary=summary,
                snippet="UI only, never a fallback",
                content="Content is not model evidence",
                rerank_score=score,
                authority=4,
                date=date,
            )
            page = {
                "url": native.url,
                "title": native.title,
                "excerpt": native.summary,
                "origin": "search_summary",
                "published_at": date,
                "search_query": "Product pricing",
                "search_result": native.model_dump(mode="json"),
            }
            evidence_id = await store.save_source(page, "pricing")
            assert await store.save_source(page, "pricing") == evidence_id
            ids.append(str(evidence_id))
        all_rows = await store.rows(Evidence)
        assert len(all_rows) == 5
        assert sum(row.validity_status == "rejected" for row in all_rows) == 2
        usable = await store.evidence()
        assert [row["excerpt"] for row in usable] == [
            "Recent model summary",
            "Old model summary",
            "Unknown date summary",
        ]
        assert all("search_result" not in row["locator"] for row in usable)
        assert usable[0]["search_scores"]["source_confidence"] == 0.86
        assert "UI only" not in str(usable) and "Content is not" not in str(usable)
        return ids

    ids = api_client.portal.call(exercise)
    saved = api_client.get(f"/api/v1/evidence/{ids[1]}").json()["data"]
    assert saved["search_result"]["date"] == "2026-10-19T00:00:00Z"
    assert saved["search_result"]["summary"] == saved["excerpt"]
    assert saved["search_result"]["source_confidence"] == 0.86
    rejected = api_client.get(f"/api/v1/evidence/{ids[3]}").json()["data"]
    assert rejected["validity_status"] == "rejected"
    assert rejected["locator"]["rejection_reason"] == "low_or_unknown_relevance"
    api_client.post("/api/v1/auth/logout", headers=headers(api_client))
    register(api_client, "other-native@example.com")
    for evidence_id in ids:
        assert api_client.get(f"/api/v1/evidence/{evidence_id}").status_code == 404
