import json

import httpx
import pytest

from app.agent.tools.registry import ToolRegistry
from app.core.config import Settings


async def test_deepseek_search_uses_requested_key_summary_and_native_fields(monkeypatch):
    from app.agent.tools import registry

    async def safe(url):
        return httpx.URL(url), "93.184.216.34"

    monkeypatch.setattr(registry, "validate_url", safe)

    async def handler(request):
        assert str(request.url) == "https://api.deepseek.com/v1/tools/search"
        assert request.headers["Authorization"] == "Bearer search-key-only"
        assert json.loads(request.content) == {
            "query": "Cursor official pricing",
            "count": 5,
            "need_content": False,
        }
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "title": "Cursor pricing",
                        "url": "https://cursor.com/pricing",
                        "snippet": "Short UI text",
                        "summary": "Long model-facing summary",
                        "content": "",
                        "rerank_score": 2.4,
                        "authority": 4,
                        "date": "2026-10-19T00:00:00Z",
                        "site_name": "Cursor",
                        "site_icon": None,
                    }
                ]
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        settings = Settings(
            _env_file=None, deepseek3_api_key="search-key-only", deepseek_api_key="must-not-be-used"
        )
        rows = await ToolRegistry(client, settings).execute(
            "deepseek_search", {"query": "Cursor official pricing", "count": 5}, ["deepseek_search"]
        )
    assert rows[0]["excerpt"] == "Long model-facing summary"
    metadata = rows[0]["search_result"]
    assert metadata["snippet"] == "Short UI text"
    assert metadata["date"] == "2026-10-19T00:00:00Z"
    assert metadata["authority"] == 4
    assert metadata["rerank_score"] == 2.4
    assert metadata["source_confidence"] == 0.86


@pytest.mark.parametrize("status", [401, 402, 429, 500])
async def test_search_errors_never_fall_back_to_bocha_or_expose_keys(status):
    from app.infrastructure.providers.chat import ProviderError

    seen = []

    async def handler(request):
        seen.append(str(request.url))
        return httpx.Response(status, json={"error": {"message": "private-key-body"}})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ProviderError, match="search_http_" + str(status)):
            await ToolRegistry(
                client, Settings(_env_file=None, deepseek3_api_key="private-key")
            ).execute("deepseek_search", {"query": "test"}, ["deepseek_search"])
    assert seen == ["https://api.deepseek.com/v1/tools/search"]


async def test_unknown_scores_stay_unknown_and_short_query_limit_is_enforced():
    from pydantic import ValidationError

    from app.agent.tools.registry import SearchArgs
    from app.domain.search import SearchResultMetadata

    result = SearchResultMetadata(
        title="Unknown",
        url="https://example.com",
        summary="Summary",
        rerank_score=2.5,
        authority=-1,
    )
    assert result.source_confidence is None
    assert result.date is None
    with pytest.raises(ValidationError):
        SearchArgs(query="q" * 129)


async def test_legacy_permission_resolves_only_to_deepseek_and_empty_results_are_valid():
    seen = []

    async def handler(request):
        seen.append(str(request.url))
        return httpx.Response(200, json={"results": []})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        registry = ToolRegistry(client, Settings(_env_file=None, deepseek3_api_key="test-only"))
        assert await registry.execute("deepseek_search", {"query": "Alpha"}, ["bocha_search"]) == []
        with pytest.raises(PermissionError):
            await registry.execute("deepseek_search", {"query": "Alpha"}, ["web_fetch"])
    assert seen == ["https://api.deepseek.com/v1/tools/search"]


@pytest.mark.parametrize("body", [{}, {"results": "invalid"}, {"results": [{"url": "bad"}]}])
async def test_invalid_provider_response_is_sanitized(body):
    from app.infrastructure.providers.chat import ProviderError

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json=body))
    ) as client:
        with pytest.raises(ProviderError, match="^search_invalid_response$"):
            await ToolRegistry(
                client, Settings(_env_file=None, deepseek3_api_key="test-only")
            ).execute("deepseek_search", {"query": "Alpha"}, ["deepseek_search"])


async def test_search_requests_are_shared_bounded_and_rate_limited():
    import asyncio
    import time

    starts = []
    active, peak = 0, 0

    async def handler(request):
        nonlocal active, peak
        starts.append(time.monotonic())
        active += 1
        peak = max(peak, active)
        await asyncio.sleep(0.3)
        active -= 1
        return httpx.Response(200, json={"results": []})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        registry = ToolRegistry(client, Settings(_env_file=None, deepseek3_api_key="test-only"))
        await asyncio.gather(
            *[
                registry.execute("deepseek_search", {"query": "Alpha"}, ["deepseek_search"])
                for _ in range(6)
            ]
        )
    assert 1 < peak <= 3
    assert starts[-1] - starts[0] >= 1
    assert all(sum(start <= other < start + 1 for other in starts) <= 5 for start in starts)
