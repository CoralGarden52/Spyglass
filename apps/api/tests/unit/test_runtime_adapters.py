import asyncio
from uuid import uuid4

import httpx
import pytest

from app.agent.runtime.contracts import ModelInput
from app.agent.runtime.sentiment import aggregate_reviews
from app.agent.tools.fetch import validate_url
from app.infrastructure.providers.chat import ChatProvider, ProviderError


async def test_model_calls_overlap_and_respect_global_capacity() -> None:
    active, peak = 0, 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        await asyncio.sleep(0.03)
        active -= 1
        return httpx.Response(
            200,
            json={
                "model": "controlled-fixture",
                "choices": [{"message": {"content": '{"ok":true}'}}],
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = ChatProvider(
            client, "https://provider.example/v1", "test-only", "fixture", 2, 0.5
        )
        results = await asyncio.gather(
            *(
                provider.generate(
                    ModelInput(role="analyst", instructions="Test", context={}, output_schema={})
                )
                for _ in range(5)
            )
        )
    assert peak == 2
    assert all(result.data == {"ok": True} and result.usage is None for result in results)


async def test_model_timeout_cancels_request_and_sanitizes_errors() -> None:
    cancelled = asyncio.Event()

    async def handler(request: httpx.Request) -> httpx.Response:
        try:
            await asyncio.sleep(5)
        finally:
            cancelled.set()
        return httpx.Response(200)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = ChatProvider(
            client, "https://provider.example/v1", "private-secret", "fixture", 1, 0.02
        )
        with pytest.raises(ProviderError, match="model_timeout"):
            await provider.generate(
                ModelInput(role="planner", instructions="Test", context={}, output_schema={})
            )
    assert cancelled.is_set()


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/",
        "http://[::1]/",
        "http://169.254.169.254/",
        "file:///etc/passwd",
        "https://user:pass@example.com/",
        "https://example.com:8443/",
    ],
)
async def test_fetch_rejects_unsafe_urls(url: str) -> None:
    with pytest.raises(ValueError):
        await validate_url(url)


def test_mixed_and_aspect_denominators_use_deduplicated_samples() -> None:
    evidence_id = str(uuid4())
    rows = [
        {
            "fingerprint": "same",
            "overall_sentiment": "mixed",
            "aspects": [
                {"aspect_key": "features", "sentiment": "positive"},
                {"aspect_key": "price", "sentiment": "negative"},
            ],
            "evidence_id": evidence_id,
        }
    ] * 2
    summary = aggregate_reviews(rows)
    assert summary["sample_count"] == 1
    assert summary["overall"]["mixed"] == {"count": 1, "ratio": 1.0}
    assert summary["aspects"]["features"]["denominator"] == 1
    assert summary["aspects"]["price"]["negative"] == 1


async def test_compatible_gateway_stream_and_usage_only_last_frame() -> None:
    import json

    async def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert payload["stream"] is True
        assert payload["stream_options"]["include_usage"] is True
        frames = [
            {"model": "gateway-model", "choices": [{"delta": {"content": '{"ok":'}}]},
            {"choices": [{"delta": {"content": "true}"}}]},
            {
                "choices": [],
                "usage": {"prompt_tokens": 4, "completion_tokens": 3, "total_tokens": 7},
            },
        ]
        return httpx.Response(
            200,
            headers={"content-type": "text/event-stream"},
            text="\n\n".join("data: " + json.dumps(frame) for frame in frames)
            + "\n\ndata: [DONE]\n",
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        reply = await ChatProvider(
            client, "https://example.com/v1", "test-key", "fixture", 1, 1
        ).generate(ModelInput(role="planner", instructions="JSON", context={}, output_schema={}))
    assert reply.data == {"ok": True}
    assert reply.usage == {"prompt_tokens": 4, "completion_tokens": 3, "total_tokens": 7}


async def test_known_price_without_currency_is_rejected_at_node_boundary() -> None:
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    from app.agent.runtime.context import NodeContext
    from app.agent.runtime.contracts import ModelReply
    from app.agent.skills.contracts import PricingResult

    payload = {
        "schema_version": 1,
        "status": "complete",
        "limitations": [],
        "plans": [
            {
                "statement": "Controlled price",
                "evidence_ids": [str(uuid4())],
                "evidence_status": "supported",
                "plan_name": "P",
                "amount": "20",
                "currency": None,
                "billing_unit": None,
                "observed_at": "2026-10-20T00:00:00Z",
            }
        ],
    }
    provider = SimpleNamespace(
        generate=AsyncMock(return_value=ModelReply(data=payload, model="fixture"))
    )
    store = SimpleNamespace(audit=AsyncMock())
    context = NodeContext(store, provider, None, {})
    with pytest.raises(ProviderError, match="schema_error"):
        await context.call("analyst", "Controlled test", {}, PricingResult.model_json_schema())
    assert store.audit.call_args.kwargs["error_code"] == "schema_error"


async def test_redirect_checks_robots_of_destination(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.agent.tools import fetch

    calls = []

    async def resolved(value: str):
        return httpx.URL(value), "93.184.216.34"

    monkeypatch.setattr(fetch, "validate_url", resolved)

    async def handler(request: httpx.Request) -> httpx.Response:
        host = request.headers["host"]
        calls.append((host, request.url.path))
        if request.url.path == "/robots.txt":
            text = (
                "User-agent: *\nDisallow: /secret"
                if host == "target.example"
                else "User-agent: *\nAllow: /"
            )
            return httpx.Response(200, text=text, headers={"content-type": "text/plain"})
        return httpx.Response(302, headers={"location": "https://target.example/secret"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ValueError, match="robots_disallowed"):
            await fetch.SafeFetcher(client).fetch("https://start.example/public")
    assert ("target.example", "/robots.txt") in calls
    assert ("target.example", "/secret") not in calls
