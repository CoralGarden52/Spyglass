import asyncio
from datetime import UTC, datetime
from uuid import UUID, uuid5

from app.agent.agents.prompts import COLLECTOR, NORMALIZER, PLANNER, PROMPT_VERSION
from app.agent.agents.queries import coverage_searches, rewrite_empty_query
from app.agent.runtime.context import NodeContext
from app.agent.runtime.contracts import CollectionPlan, NormalizedBundle, ResearchPlan, SearchTask
from app.agent.runtime.state import ResearchState
from app.infrastructure.database.knowledge import (
    CompetitorProfile,
    ResearchPlanRecord,
    ReviewSample,
)
from app.infrastructure.providers.chat import ProviderError
from app.infrastructure.research_store import digest


class CollectionNodes:
    def __init__(self, context: NodeContext):
        self.c = context

    async def planner(self, state: ResearchState) -> ResearchState:
        run = await self.c.store.run()
        request = run.request_json or {}
        scenario = next(d for d in self.c.definitions.values() if d["kind"] == "scenario")
        try:
            plan = await self.c.call(
                "planner",
                PLANNER + scenario["instructions"],
                {"request": request, "scenario_dimensions": scenario["manifest"]["dimensions"]},
                ResearchPlan,
                version="planner-" + PROMPT_VERSION,
            )
        except ProviderError:
            # No trustworthy scope means there is no valid collection task to execute.
            raise
        plan_id = await self.c.store.save_plan({**plan, "request": request})
        return {"plan_id": str(plan_id), "status": "running"}

    async def resolver(self, state: ResearchState) -> ResearchState:
        # Frozen database definitions were integrity-checked before compilation.
        required = {"product_capability", "pricing_analysis", "user_sentiment", "swot_analysis"}
        if (
            not required <= self.c.definitions.keys()
            or sum(d["kind"] == "scenario" for d in self.c.definitions.values()) != 1
        ):
            raise ValueError("invalid_frozen_skills")
        return {"status": "running"}

    async def collector(self, state: ResearchState) -> ResearchState:
        plans = await self.c.store.rows(ResearchPlanRecord)
        plan = plans[0].payload
        scenario = next(d for d in self.c.definitions.values() if d["kind"] == "scenario")
        previous = state.get("review_result") or {}
        as_of = datetime.now(UTC).date()
        try:
            raw = await self.c.call(
                "collector",
                COLLECTOR + scenario["instructions"],
                {
                    "plan": plan,
                    "repair": previous.get("issues", []),
                    "as_of_utc": as_of.isoformat(),
                },
                CollectionPlan,
                version="collector-" + PROMPT_VERSION,
            )
            collection = CollectionPlan.model_validate(raw)
        except ProviderError:
            # Query planning is optional; trusted scope still allows bounded real searches.
            collection = None
        mode = (plan.get("request") or {}).get("mode", "standard")
        searches = coverage_searches(
            plan["competitor_names"], collection, mode, scenario["id"], as_of
        )
        gate = asyncio.Semaphore(3)

        async def collect(task: SearchTask) -> None:
            async with gate:
                try:
                    pages = await self.c.tool(
                        "deepseek_search", {"query": task.query, "count": 5}, scenario["id"]
                    )
                    for page in pages:
                        await self.c.store.save_source(
                            {**page, "competitor_name": task.competitor_name}, task.category
                        )
                    # Empty/irrelevant summaries get one broader rewrite, never infinite
                    # retries. Provider errors (especially rate limits) are not retried here.
                    usable_count = sum(
                        p.get("excerpt", "").strip()
                        and (
                            p.get("search_result") is None
                            or (p["search_result"].get("rerank_score") or 0) >= 1.5
                        )
                        for p in pages
                    )
                    rewrite = rewrite_empty_query(task, scenario["id"], as_of)
                    native = any(p.get("search_result") is not None for p in pages)
                    # A single review hit may only be a secondary article. Broaden once.
                    target = 2 if task.category == "review" and native else 1
                    if usable_count < target and rewrite:
                        pages = await self.c.tool(
                            "deepseek_search", {"query": rewrite, "count": 5}, scenario["id"]
                        )
                        for page in pages:
                            await self.c.store.save_source(
                                {**page, "competitor_name": task.competitor_name}, task.category
                            )
                except ProviderError:
                    return

        await asyncio.gather(*(collect(task) for task in searches))
        if not await self.c.store.evidence():
            raise ProviderError("collection_unavailable")
        return {"evidence_ids": [e["id"] for e in await self.c.store.evidence()]}

    async def normalizer(self, state: ResearchState) -> ResearchState:
        evidence = await self.c.store.evidence()
        plans = await self.c.store.rows(ResearchPlanRecord)
        try:
            result = NormalizedBundle.model_validate(
                await self.c.call(
                    "normalizer",
                    NORMALIZER,
                    {"plan": plans[0].payload, "untrusted_evidence": evidence},
                    NormalizedBundle,
                    version="normalizer-" + PROMPT_VERSION,
                )
            )
        except ProviderError:
            return {"profile_ids": []}
        valid = {e["id"]: e for e in evidence}
        profiles = []
        for profile in result.profiles:
            if profile.name not in plans[0].payload["competitor_names"]:
                continue
            if any(str(i) not in valid for i in profile.evidence_ids):
                continue
            if profile.website not in {valid[str(i)]["url"] for i in profile.evidence_ids}:
                profile.website = None
            profile_id = uuid5(self.c.store.run_id, "profile:" + profile.name.casefold())
            await self.c.store.put(
                CompetitorProfile,
                {
                    "id": profile_id,
                    "canonical_name": profile.name,
                    "profile_json": profile.model_dump(mode="json"),
                },
            )
            profiles.append(str(profile_id))
        for review in result.reviews:
            source = valid.get(str(review.evidence_id))
            if (
                not source
                or source["category"] != "review"
                or review.quote not in source["excerpt"]
                or review.competitor_name not in plans[0].payload["competitor_names"]
            ):
                continue
            fingerprint = digest(
                [review.competitor_name.casefold(), " ".join(review.quote.casefold().split())]
            )
            await self.c.store.put(
                ReviewSample,
                {
                    "id": uuid5(self.c.store.run_id, "review:" + fingerprint),
                    "evidence_id": review.evidence_id,
                    "source_id": UUID(source["source_id"]),
                    "fingerprint": fingerprint,
                    "payload": {**review.model_dump(mode="json"), "fingerprint": fingerprint},
                },
            )
        return {"profile_ids": profiles}
