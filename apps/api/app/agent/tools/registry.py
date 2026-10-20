from typing import Any

import httpx
from pydantic import BaseModel, Field

from app.agent.skills.contracts import Contract
from app.agent.tools.fetch import SafeFetcher, validate_url
from app.core.config import Settings
from app.infrastructure.providers.chat import ProviderError, bounded_body


class SearchArgs(Contract):
    query: str = Field(min_length=2, max_length=400)
    count: int = Field(default=3, ge=1, le=5)


class FetchArgs(Contract):
    url: str = Field(max_length=2000)


class RetrievalArgs(Contract):
    query: str = Field(default="", max_length=400)


class ToolRegistry:
    schemas: dict[str, type[BaseModel]] = {
        "bocha_search": SearchArgs,
        "web_fetch": FetchArgs,
        "evidence_search": RetrievalArgs,
        "knowledge_retrieval": RetrievalArgs,
    }

    def __init__(self, client: httpx.AsyncClient, settings: Settings):
        self.client, self.settings = client, settings
        self.fetcher = SafeFetcher(client)

    async def execute(
        self,
        name: str,
        arguments: dict[str, Any],
        allowed: list[str],
        evidence: list[dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        if name not in allowed or name not in self.schemas:
            raise PermissionError("tool_not_permitted")
        parsed = self.schemas[name].model_validate(arguments)
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
        key = self.settings.bocha_api_key.get_secret_value()
        if not key:
            raise ProviderError("search_unconfigured")
        endpoint = self.settings.bocha_web_search_endpoint
        if not endpoint.startswith("https://"):
            endpoint = self.settings.bocha_base_url.rstrip("/") + "/" + endpoint.lstrip("/")
        async with self.client.stream(
            "POST",
            endpoint,
            headers={"Authorization": "Bearer " + key},
            json={
                "query": parsed.query,
                "count": parsed.count,
                "summary": True,
                "freshness": "noLimit",
            },
        ) as response:
            if response.status_code != 200:
                raise ProviderError("search_http_" + str(response.status_code))
            import json

            body = json.loads(await bounded_body(response))
        if str(body.get("code")) != "200":
            raise ProviderError("search_provider_error")
        result = []
        for row in ((body.get("data") or {}).get("webPages") or {}).get("value", [])[
            : parsed.count
        ]:
            url = row.get("url", "")
            try:
                validated, _ = await validate_url(url)
            except ValueError:
                continue
            excerpt = str(row.get("summary") or row.get("snippet") or "")[:6000]
            if excerpt:
                result.append(
                    {
                        "url": str(validated.copy_with(fragment=None)),
                        "title": str(row.get("name") or "")[:500],
                        "excerpt": excerpt,
                        "origin": "search_snippet",
                        "published_at": row.get("datePublished"),
                    }
                )
        return result
