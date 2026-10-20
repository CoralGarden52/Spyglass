import asyncio
import json
from typing import Any

import httpx
from pydantic import BaseModel, Field, ValidationError

from app.agent.skills.contracts import Contract
from app.agent.tools.fetch import SafeFetcher, validate_url
from app.core.config import Settings
from app.domain.search import SearchResultMetadata
from app.infrastructure.providers.chat import ProviderError, bounded_body


class SearchArgs(Contract):
    query: str = Field(min_length=1, max_length=128, pattern=r"\S")
    count: int = Field(default=5, ge=1, le=5)
    need_content: bool = False


class FetchArgs(Contract):
    url: str = Field(max_length=2000)


class RetrievalArgs(Contract):
    query: str = Field(default="", max_length=400)


class ToolRegistry:
    schemas: dict[str, type[BaseModel]] = {
        "deepseek_search": SearchArgs,
        "web_fetch": FetchArgs,
        "evidence_search": RetrievalArgs,
        "knowledge_retrieval": RetrievalArgs,
    }

    def __init__(self, client: httpx.AsyncClient, settings: Settings):
        self.client, self.settings = client, settings
        self.fetcher = SafeFetcher(client)
        self.search_gate = asyncio.Semaphore(3)
        self.search_clock = asyncio.Lock()
        self.next_search_at = 0.0

    async def execute(
        self,
        name: str,
        arguments: dict[str, Any],
        allowed: list[str],
        evidence: list[dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        # Legacy immutable snapshots retain their old logical tool permission.
        # The compatibility name always resolves to DeepSeek; no Bocha adapter exists.
        canonical = "deepseek_search" if name == "bocha_search" else name
        permissions = {"deepseek_search" if item == "bocha_search" else item for item in allowed}
        if canonical not in permissions or canonical not in self.schemas:
            raise PermissionError("tool_not_permitted")
        parsed = self.schemas[canonical].model_validate(arguments)
        if isinstance(parsed, RetrievalArgs):
            # Evidence is supplied by the tenant-scoped repository, never a global cache.
            return [
                e
                for e in (evidence or [])
                if parsed.query.lower() in str(e.get("excerpt", "")).lower()
            ]
        if isinstance(parsed, FetchArgs):
            return [await self.fetcher.fetch(parsed.url)]
        if not isinstance(parsed, SearchArgs):
            raise ValueError("invalid_tool_arguments")
        key = self.settings.deepseek3_api_key.get_secret_value()
        if not key:
            raise ProviderError("search_unconfigured")
        try:
            async with asyncio.timeout(30), self.search_gate:
                async with self.search_clock:
                    loop = asyncio.get_running_loop()
                    await asyncio.sleep(max(0, self.next_search_at - loop.time()))
                    self.next_search_at = loop.time() + 0.21
                async with self.client.stream(
                    "POST",
                    "https://api.deepseek.com/v1/tools/search",
                    headers={"Authorization": "Bearer " + key},
                    json={
                        "query": parsed.query,
                        "count": parsed.count,
                        "need_content": parsed.need_content,
                    },
                ) as response:
                    if response.status_code != 200:
                        raise ProviderError("search_http_" + str(response.status_code))
                    body = json.loads(await bounded_body(response))
            if not isinstance(body, dict) or not isinstance(body.get("results"), list):
                raise ProviderError("search_invalid_response")
            hits = [
                SearchResultMetadata.model_validate(row) for row in body["results"][: parsed.count]
            ]
        except TimeoutError:
            raise ProviderError("search_timeout") from None
        except httpx.HTTPError:
            raise ProviderError("search_transport_error") from None
        except (ValueError, ValidationError, TypeError):
            raise ProviderError("search_invalid_response") from None
        result = []
        for hit in hits:
            try:
                validated, _ = await validate_url(hit.url)
            except ValueError:
                continue
            result.append(
                {
                    "url": str(validated.copy_with(fragment=None)),
                    "title": hit.title[:500],
                    "excerpt": hit.summary[:6000],
                    "origin": "search_summary",
                    "published_at": hit.date.isoformat() if hit.date else None,
                    "search_result": hit.model_dump(mode="json"),
                    "search_query": parsed.query,
                }
            )
        return result
