"""Opt-in paid DeepSeek Search adapter check; no model calls or business DB writes."""

import argparse
import asyncio
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/api"))

from app.agent.tools.registry import ToolRegistry  # noqa: E402
from app.core.config import Settings  # noqa: E402
from app.infrastructure.providers.chat import ProviderError  # noqa: E402


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--query", action="append", required=True)
    queries = parser.parse_args().query
    settings = Settings()
    if not settings.deepseek3_api_key.get_secret_value():
        raise SystemExit("DEEPSEEK3_API_KEY is unconfigured")
    async with httpx.AsyncClient(timeout=20, follow_redirects=False, trust_env=False) as client:
        registry = ToolRegistry(client, settings)

        async def search(query: str) -> dict:
            started = time.perf_counter()
            try:
                rows = await registry.execute(
                    "deepseek_search", {"query": query, "count": 5}, ["deepseek_search"]
                )
                return {
                    "query": query,
                    "ok": bool(rows),
                    "elapsed_seconds": round(time.perf_counter() - started, 3),
                    "results": [row["search_result"] for row in rows],
                }
            except ProviderError as exc:
                return {
                    "query": query,
                    "ok": False,
                    "error": str(exc),
                    "elapsed_seconds": round(time.perf_counter() - started, 3),
                }

        started = time.perf_counter()
        results = await asyncio.gather(*[search(query) for query in queries])
    output = {
        "kind": "live_deepseek_search_adapter",
        "as_of": datetime.now(UTC).isoformat(),
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "queries": results,
    }
    artifact = (
        ROOT
        / ".artifacts"
        / ("deepseek-search-adapter-" + datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ") + ".json")
    )
    artifact.parent.mkdir(exist_ok=True)
    artifact.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "artifact": artifact.name,
                "elapsed_seconds": output["elapsed_seconds"],
                "queries": [
                    {k: v for k, v in r.items() if k != "results"}
                    | {"count": len(r.get("results", []))}
                    for r in results
                ],
            },
            ensure_ascii=False,
        )
    )
    if not all(r["ok"] for r in results):
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
