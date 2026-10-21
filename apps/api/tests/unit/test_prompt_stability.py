"""Controlled provider responses only; no external research or paid model requests."""

import json

import httpx
import pytest
from pydantic import ValidationError

from app.agent.runtime.contracts import ModelInput
from app.core.config import Settings
from app.infrastructure.providers.chat import ChatProvider, ProviderError


@pytest.mark.parametrize("mode", [None, "disabled"])
async def test_thinking_is_an_explicit_compatible_provider_option(mode):
    async def handler(request):
        payload = json.loads(request.content)
        if mode is None:
            assert "thinking" not in payload
        else:
            assert payload["thinking"] == {"type": "disabled"}
        return httpx.Response(200, json={"choices": [{"message": {"content": "{}"}}]})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = ChatProvider(
            client, "https://fixture.example", "test", "fixture", 1, 1, thinking=mode
        )
        await provider.generate(
            ModelInput(role="analyst", instructions="JSON", context={}, output_schema={})
        )


@pytest.mark.parametrize("streaming", [False, True])
async def test_length_finish_reason_rejects_even_valid_json_and_keeps_actual_usage(
    streaming: bool,
) -> None:
    usage = {"prompt_tokens": 10, "completion_tokens": 3000, "total_tokens": 3010}

    async def handler(request: httpx.Request) -> httpx.Response:
        if not streaming:
            return httpx.Response(
                200,
                json={
                    "model": "controlled-reasoner",
                    "usage": usage,
                    "choices": [{"message": {"content": '{"ok":true}'}, "finish_reason": "length"}],
                },
            )
        frames = [
            {
                "model": "controlled-reasoner",
                "choices": [
                    {
                        "delta": {"reasoning_content": "not public", "content": '{"ok":true}'},
                        "finish_reason": "length",
                    }
                ],
            },
            {"choices": [], "usage": usage},
        ]
        return httpx.Response(
            200,
            headers={"content-type": "text/event-stream"},
            text="\n\n".join("data: " + json.dumps(f) for f in frames) + "\n\ndata: [DONE]\n",
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ProviderError, match="^model_output_truncated$") as caught:
            await ChatProvider(
                client, "https://fixture.example", "private-test", "fixture", 1, 1
            ).generate(
                ModelInput(role="analyst", instructions="JSON", context={}, output_schema={})
            )
    assert caught.value.model == "controlled-reasoner"
    assert caught.value.usage == usage
    assert "not public" not in str(caught.value)


async def test_roles_have_distinct_budgets_and_explicit_override_wins() -> None:
    budgets = []

    async def handler(request: httpx.Request) -> httpx.Response:
        budgets.append(json.loads(request.content)["max_tokens"])
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": '{"ok":true}'}, "finish_reason": "stop"}]},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = ChatProvider(client, "https://fixture.example", "test", "fixture", 1, 1)
        for role in ("planner", "analyst", "writer"):
            await provider.generate(
                ModelInput(role=role, instructions="JSON", context={}, output_schema={})
            )
        await provider.generate(
            ModelInput(
                role="analyst", instructions="JSON", context={}, output_schema={}, max_tokens=4500
            )
        )
    assert budgets == [2000, 6000, 3000, 4500]


async def test_environment_budget_is_used_in_provider_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LLM_ROLE_MAX_TOKENS", '{"analyst":7500}')
    settings = Settings(_env_file=None)
    sent = []

    async def handler(request: httpx.Request) -> httpx.Response:
        sent.append(json.loads(request.content)["max_tokens"])
        return httpx.Response(200, json={"choices": [{"message": {"content": "{}"}}]})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = ChatProvider(
            client,
            "https://fixture.example",
            "test",
            "fixture",
            1,
            1,
            role_budgets=settings.llm_role_max_tokens,
        )
        await provider.generate(
            ModelInput(role="analyst", instructions="JSON", context={}, output_schema={})
        )
        await provider.generate(
            ModelInput(role="planner", instructions="JSON", context={}, output_schema={})
        )
    assert sent == [7500, 2000]


@pytest.mark.parametrize("budgets", [{"analyst": 99}, {"analyst": 12001}, {"unknown": 500}])
def test_invalid_environment_budgets_rejected(budgets: dict[str, int]) -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, llm_role_max_tokens=budgets)


async def test_malformed_output_keeps_usage_without_repairing_json() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "model": "fixture",
                "usage": {"total_tokens": 7},
                "choices": [{"message": {"content": '{"unfinished":'}}],
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ProviderError, match="^model_invalid_json$") as caught:
            await ChatProvider(client, "https://fixture.example", "test", "fixture", 1, 1).generate(
                ModelInput(role="planner", instructions="JSON", context={}, output_schema={})
            )
    assert caught.value.usage == {"total_tokens": 7}
