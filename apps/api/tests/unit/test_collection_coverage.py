from datetime import date
from types import SimpleNamespace

import pytest

from app.agent.agents.collection import CollectionNodes
from app.agent.runtime.contracts import CollectionPlan
from app.infrastructure.providers.chat import ProviderError


@pytest.mark.parametrize(
    "scenario",
    ["general_analysis", "ecommerce", "internet_product", "hardware_iot", "ai_llm", "finance"],
)
def test_query_template_uses_arbitrary_requested_names_for_every_scenario(scenario):
    from uuid import uuid4

    from app.agent.agents.queries import coverage_searches

    names = ["产品甲" + uuid4().hex[:5], "Example " + uuid4().hex[:5]]
    tasks = coverage_searches(names, None, "quick", scenario, date(2026, 10, 21))
    assert len(tasks) == 6
    assert {t.competitor_name for t in tasks} == set(names)
    for name in names:
        own = [t for t in tasks if t.competitor_name == name]
        assert {t.category for t in own} == {"product", "pricing", "review"}
        assert all(name in t.query and len(t.query) <= 128 for t in own)
        assert all("site:" not in t.query for t in own)


class MemoryCollectionStore:
    """No DB or network; tests the production node's search and persistence boundary."""

    def __init__(self, names: list[str], mode: str = "quick"):
        self.plan = {
            "competitor_names": names,
            "scope": "AI coding tools",
            "request": {"mode": mode},
        }
        self.saved = []

    async def rows(self, model):
        return [SimpleNamespace(payload=self.plan)]

    async def evidence(self):
        return self.saved

    async def save_source(self, page, category):
        self.saved.append({"id": str(len(self.saved)), "category": category, **page})


async def test_quick_collection_covers_every_competitor_and_core_category() -> None:
    store = MemoryCollectionStore(["Cursor", "Claude Code", "Windsurf"])
    queries = []

    async def call(*args, **kwargs):
        return {"searches": [{"query": "Cursor official features", "category": "product"}]}

    async def tool(name, arguments, skill):
        queries.append(arguments["query"])
        return [{"url": "https://controlled.example", "excerpt": "controlled summary"}]

    context = SimpleNamespace(
        store=store,
        call=call,
        tool=tool,
        definitions={
            "ai_llm": {
                "id": "ai_llm",
                "kind": "scenario",
                "instructions": "AI coding",
                "manifest": {},
            }
        },
    )
    await CollectionNodes(context).collector({})
    assert len(queries) == 9
    assert {row["category"] for row in store.saved} == {"product", "pricing", "review"}
    for name in ("Cursor", "Claude Code", "Windsurf"):
        assert len([q for q in queries if name.casefold() in q.casefold()]) == 3
    assert all(len(q) <= 128 for q in queries)
    assert any('"Windsurf" AI software' in q for q in queries)


async def test_collector_model_failure_uses_safe_coverage_searches() -> None:
    store = MemoryCollectionStore(["Unknown Brand"])
    queries = []

    async def call(*args, **kwargs):
        raise ProviderError("model_output_truncated")

    async def tool(name, arguments, skill):
        queries.append(arguments["query"])
        return [{"url": "https://controlled.example", "excerpt": "controlled summary"}]

    context = SimpleNamespace(
        store=store,
        call=call,
        tool=tool,
        definitions={
            "general_analysis": {
                "id": "general_analysis",
                "kind": "scenario",
                "instructions": "",
                "manifest": {},
            }
        },
    )
    result = await CollectionNodes(context).collector({})
    assert len(queries) == 3
    assert len(result["evidence_ids"]) == 3
    assert all("site:" not in query for query in queries)


async def test_empty_results_are_rewritten_once_and_do_not_retry_provider_errors() -> None:
    store = MemoryCollectionStore(["Alpha"])
    queries = []

    async def call(*args, **kwargs):
        return {
            "searches": [
                {"query": "Alpha product", "category": "product"},
                {"query": "Alpha pricing", "category": "pricing"},
                {"query": "Alpha reviews", "category": "review"},
            ]
        }

    async def tool(name, arguments, skill):
        queries.append(arguments["query"])
        if "pricing" in arguments["query"]:
            raise ProviderError("search_http_429")
        return []

    context = SimpleNamespace(
        store=store,
        call=call,
        tool=tool,
        definitions={
            "general_analysis": {
                "id": "general_analysis",
                "kind": "scenario",
                "instructions": "",
                "manifest": {},
            }
        },
    )
    with pytest.raises(ProviderError, match="^collection_unavailable$"):
        await CollectionNodes(context).collector({})
    assert len(queries) == 5
    assert len(set(queries)) == 5


def test_query_coverage_long_identity_keeps_128_character_contract() -> None:
    from app.agent.agents.queries import coverage_searches

    tasks = coverage_searches(
        ["长名称" * 65], CollectionPlan(searches=[]), "quick", "ai_llm", date(2026, 10, 21)
    )
    assert len(tasks) == 3
    assert all(1 <= len(task.query) <= 128 for task in tasks)
    assert any("after:2025-10-21" in task.query for task in tasks)


def test_unverified_site_domain_is_not_used_and_large_plan_is_bounded() -> None:
    from app.agent.agents.queries import coverage_searches

    tasks = coverage_searches(
        ["Unknown"],
        CollectionPlan(
            searches=[{"query": "Unknown site:invented.example pricing", "category": "pricing"}]
        ),
        "quick",
        "general_analysis",
        date(2026, 10, 21),
    )
    assert all("invented.example" not in task.query for task in tasks)
    large = coverage_searches(
        [f"Brand{i}" for i in range(10)], None, "deep", "general_analysis", date(2026, 10, 21)
    )
    assert len(large) == 30


async def test_only_low_relevance_summaries_trigger_one_broader_query() -> None:
    store = MemoryCollectionStore(["Alpha"])
    queries = []

    async def call(*args, **kwargs):
        return {"searches": []}

    async def tool(name, arguments, skill):
        queries.append(arguments["query"])
        return [
            {
                "url": "https://controlled.example",
                "excerpt": "irrelevant sport result",
                "search_result": {"rerank_score": 0.4, "summary": "irrelevant sport result"},
            }
        ]

    context = SimpleNamespace(
        store=store,
        call=call,
        tool=tool,
        definitions={
            "ai_llm": {"id": "ai_llm", "kind": "scenario", "instructions": "", "manifest": {}}
        },
    )
    await CollectionNodes(context).collector({})
    assert len(queries) == 6
    # Rejected candidates remain available to the store's source/score audit policy.
    assert len(store.saved) == 6


def test_model_review_query_keeps_entity_context_and_bounded_recent_date() -> None:
    from app.agent.agents.queries import coverage_searches

    tasks = coverage_searches(
        ["Windsurf"],
        CollectionPlan(
            searches=[{"query": "Windsurf reviews after:2099-01-01", "category": "review"}]
        ),
        "quick",
        "ai_llm",
        date(2026, 10, 21),
    )
    reviews = [task.query for task in tasks if task.category == "review"]
    assert len(reviews) == 1
    assert "AI software" in reviews[0]
    assert "after:2025-10-21" in reviews[0]
    assert "2099" not in reviews[0]
