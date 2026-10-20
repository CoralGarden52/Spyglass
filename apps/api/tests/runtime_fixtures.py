"""Controlled synthetic contracts for disposable DB tests; never imported by production."""

import asyncio
from collections import Counter
from typing import Any

from app.agent.runtime.contracts import ModelInput, ModelReply
from app.agent.tools.registry import ToolRegistry
from app.domain.search import SearchResultMetadata

QUOTE = "Alpha is fast and easy but expensive."
SECOND_QUOTE = "Another user says Alpha is reliable."


class ControlledTools(ToolRegistry):
    def __init__(self) -> None:
        self.search_count = 0

    async def execute(
        self,
        name: str,
        arguments: dict[str, Any],
        allowed: list[str],
        evidence: list[dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        if name not in allowed:
            raise PermissionError("tool_not_permitted")
        if name in {"evidence_search", "knowledge_retrieval"}:
            return evidence or []
        if name == "web_fetch":
            return []
        self.search_count += 1
        rows = [
            {
                "url": f"https://alpha.example/source/{self.search_count}",
                "title": "CONTROLLED SYNTHETIC FIXTURE",
                "excerpt": (
                    "Alpha supports basic and advanced features. Price USD 10 per month. "
                    f"{QUOTE} {SECOND_QUOTE} Source revision {self.search_count}."
                ),
                "origin": "search_snippet",
                "published_at": None,
            }
        ]

        for row in rows:
            row["origin"] = "search_summary"
            row["published_at"] = "2026-10-19T00:00:00Z"
            row["search_query"] = arguments["query"]
            row["search_result"] = SearchResultMetadata(
                title=row["title"],
                url=row["url"],
                snippet="Synthetic short UI snippet",
                summary=row["excerpt"],
                rerank_score=2.4,
                authority=4,
                date="2026-10-19T00:00:00Z",
                site_name="Controlled fixture",
            ).model_dump(mode="json")
        return rows


class ControlledModel:
    def __init__(
        self,
        repair_target: str | None = None,
        unchanged: bool = False,
        always_fail: bool = False,
        slow_analysis: float = 0.06,
        invalid_schema: bool = False,
    ):
        self.repair_target, self.unchanged, self.always_fail = repair_target, unchanged, always_fail
        self.slow_analysis, self.invalid_schema = slow_analysis, invalid_schema
        self.calls: Counter[str] = Counter()
        self.active_analysts = 0
        self.peak_analysts = 0

    async def generate(self, call: ModelInput) -> ModelReply:
        role = call.role
        key = call.context.get("skill_id", role)
        self.calls[key] += 1
        data: dict[str, Any]
        if role == "planner":
            data = {"competitor_names": ["Alpha"], "scope": "Controlled fixture research"}
        elif role == "collector":
            data = {
                "searches": [
                    {"query": "Alpha " + kind, "category": kind}
                    for kind in ("product", "pricing", "review")
                ]
            }
        elif role == "normalizer":
            evidence = call.context["untrusted_evidence"]
            review = next((e for e in evidence if e["category"] == "review"), None)
            data = {
                "profiles": [{"name": "Alpha", "evidence_ids": []}],
                "reviews": [
                    {
                        "competitor_name": "Alpha",
                        "evidence_id": review["id"],
                        "quote": QUOTE,
                        "source_platform": "controlled fixture",
                    }
                ]
                if review
                else [],
                "limitations": [],
            }
        elif role == "analyst":
            self.active_analysts += 1
            self.peak_analysts = max(self.peak_analysts, self.active_analysts)
            try:
                await asyncio.sleep(self.slow_analysis)
            finally:
                self.active_analysts -= 1
            evidence = call.context["untrusted_evidence"]
            evidence_id = evidence[0]["id"]
            claim = {
                "statement": "Alpha supports "
                + (
                    "basic features"
                    if self.calls[key] == 1 or self.unchanged
                    else "basic and advanced features"
                ),
                "evidence_ids": [evidence_id],
                "evidence_status": "supported",
            }
            data = {"schema_version": 1, "status": "complete", "limitations": []}
            if self.invalid_schema and key == "product_capability" and self.calls[key] == 1:
                data = {"bad_output": True}
            elif key == "product_capability":
                data.update(positioning=[claim], features=[])
            elif key == "pricing_analysis":
                data["plans"] = [
                    {
                        **claim,
                        "statement": "Alpha costs USD 10 per month",
                        "plan_name": "Controlled plan",
                        "amount": "10",
                        "currency": "USD",
                        "billing_unit": "month",
                        "observed_at": "2026-10-20T00:00:00Z",
                    }
                ]
            elif key == "user_sentiment":
                sample = call.context["review_samples"][0]
                data.update(
                    reviews=[
                        {
                            "evidence_id": sample["evidence_id"],
                            "source_platform": "fixture",
                            "fingerprint": "ignored-model-fingerprint",
                            "overall_sentiment": "mixed",
                            "aspects": [
                                {
                                    "aspect_key": "performance",
                                    "opinion_span": "fast",
                                    "sentiment": "positive",
                                    "evidence_id": sample["evidence_id"],
                                },
                                {
                                    "aspect_key": "pricing",
                                    "opinion_span": "expensive",
                                    "sentiment": "negative",
                                    "evidence_id": sample["evidence_id"],
                                },
                            ],
                        }
                    ],
                    sampling_bias=["Controlled synthetic test sample, not business data"],
                )
            elif key == "swot_analysis":
                data.update(strengths=[claim], weaknesses=[], opportunities=[], threats=[])
            elif key == "market_landscape":
                data.update(participants=[claim], positioning_differences=[])
            elif key == "business_model":
                data.update(revenue_paths=[claim], channels_and_costs=[])
            else:
                data.update(opportunities=[claim], risks=[], recommendations=[])
        elif role == "writer":
            data = {
                "title": "Controlled fixture report"
                if self.calls["writer"]
                else "Incomplete fixture report",
                "sections": [
                    {
                        "skill_id": key,
                        "claim_ids": [
                            c["id"] for c in call.context["claims"] if c["skill_id"] == key
                        ],
                    }
                    for key in call.context["artifacts"]
                ],
            }
        else:
            issue = self.repair_target and (self.calls["reviewer"] == 1 or self.always_fail)
            data = {
                "passed": not bool(issue),
                "issues": [
                    {
                        "type": "contradiction"
                        if self.repair_target == "analyst"
                        else "missing_evidence"
                        if self.repair_target == "collector"
                        else "schema_error",
                        "target": self.repair_target,
                        "skill_id": "product_capability",
                        "description": "Controlled incomplete handoff",
                        "repair_request": (
                            "Use the advanced capability explicitly present in evidence"
                        ),
                    }
                ]
                if issue
                else [],
            }
        return ModelReply(data=data, model="controlled-test-provider", usage=None)
