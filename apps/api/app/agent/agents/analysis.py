from uuid import UUID

from app.agent.runtime.context import NodeContext, empty_analysis
from app.agent.runtime.state import ResearchState
from app.agent.skills.contracts import DependentAnalysisInput, EvidenceInput, ScenarioContext
from app.infrastructure.database.knowledge import ReviewSample
from app.infrastructure.providers.chat import ProviderError


class AnalysisNodes:
    def __init__(self, context: NodeContext):
        self.c = context

    async def analyse(self, state: ResearchState) -> ResearchState:
        return {"status": "running"}

    async def skill(self, skill_id: str, state: ResearchState) -> str:
        skill = self.c.definitions[skill_id]
        run = await self.c.store.run()
        previous = state.get("review_result") or {}
        issues = previous.get("issues", [])
        existing = await self.c.store.artifacts()
        # Analyst-directed repairs only recompute the affected Skill and dependants.
        targeted = {i.get("skill_id") for i in issues if i.get("target") == "analyst"}
        if (
            previous.get("next_target") == "analyst"
            and targeted
            and skill_id not in targeted
            and skill_id in existing
            and skill_id in {"product_capability", "pricing_analysis", "user_sentiment"}
        ):
            return str(existing[skill_id].id)
        scenario = next(d for d in self.c.definitions.values() if d["kind"] == "scenario")
        try:
            if "analyst" not in skill["manifest"]["applies_to"]:
                raise ProviderError("skill_role_rejected")
            evidence = await self.c.tool("evidence_search", {}, skill_id)
            common = {
                "user_request": (run.request_json or {}).get("user_message", ""),
                "competitor_ids": [UUID(i) for i in state.get("profile_ids", [])],
                "evidence_ids": [UUID(e["id"]) for e in evidence],
                "scenario_context": ScenarioContext(
                    dimensions=list(scenario["manifest"]["dimensions"]),
                    source_priorities=list(scenario["manifest"]["source_priorities"]),
                    review_aspects=list(scenario["manifest"]["review_aspects"]),
                ),
            }
            dependencies = {
                k: UUID(str(v.id)) for k, v in existing.items() if k in skill["requires"]
            }
            handoff = (
                DependentAnalysisInput(**common, analysis_refs=dependencies)
                if skill["manifest"]["input_schema"] == "DependentAnalysisInput"
                else EvidenceInput(**common)
            ).model_dump(mode="json")
            samples = (await self.c.store.rows(ReviewSample))[
                : int(skill["config"].get("review_sample_limit", 100))
            ]
            output = await self.c.call(
                "analyst",
                skill["instructions"]
                + (
                    "\nUse only supplied evidence IDs. Analyze all requested "
                    "competitors. Do not treat search snippets as full-page "
                    "verification. Distinguish unavailable data from explicitly "
                    "unsupported functionality. Review classification must reference "
                    "the supplied literal review samples, never create a new sample."
                ),
                {
                    "schema_version": 1,
                    "run_id": str(run.id),
                    "producer": "normalizer",
                    "skill_id": skill_id,
                    "skill_input": handoff,
                    "config": skill["config"],
                    "untrusted_evidence": evidence,
                    "review_samples": [r.payload for r in samples]
                    if skill_id == "user_sentiment"
                    else [],
                    "upstream": {
                        k: v.payload for k, v in existing.items() if k in skill["requires"]
                    },
                    "repair_issues": issues,
                },
                skill["output_schema"],
                f"{skill_id}:{skill['version']}",
            )
            if skill_id == "user_sentiment":
                by_fingerprint = {r.fingerprint: r for r in samples}
                by_evidence: dict[str, list[ReviewSample]] = {}
                for candidate in samples:
                    by_evidence.setdefault(str(candidate.evidence_id), []).append(candidate)
                accepted = {}
                for observation in output["reviews"]:
                    sample: ReviewSample | None = by_fingerprint.get(observation["fingerprint"])
                    if sample is None:
                        candidates = by_evidence.get(observation["evidence_id"], [])
                        sample = candidates[0] if len(candidates) == 1 else None
                    if (
                        sample is None
                        or observation["evidence_id"] != str(sample.evidence_id)
                        or any(
                            a["evidence_id"] != str(sample.evidence_id)
                            or a["opinion_span"] not in sample.payload["quote"]
                            for a in observation["aspects"]
                        )
                    ):
                        raise ProviderError("schema_error:unverified_review")
                    # Model-provided fingerprints and platform labels cannot inflate denominators.
                    observation = {
                        **observation,
                        "fingerprint": sample.fingerprint,
                        "source_platform": sample.payload["source_platform"],
                    }
                    accepted[sample.fingerprint] = observation
                    async with self.c.store.sessions() as db:
                        row = await db.get(ReviewSample, sample.id)
                        if row is not None and row.tenant_id == self.c.store.context.tenant_id:
                            row.payload = {**row.payload, "classification": observation}
                            await db.commit()
                output["reviews"] = list(accepted.values())
                if len(accepted) < len(samples):
                    output["status"] = "partial"
                    output["limitations"].append("存在尚未完成分类的真实样本，未分类数量单独报告")
            return str(await self.c.store.artifact(skill, output, state.get("review_count", 0)))
        except ProviderError as exc:
            output = empty_analysis(skill["output_schema"], str(exc))
            return str(await self.c.store.artifact(skill, output, state.get("review_count", 0)))

    async def product(self, state: ResearchState) -> ResearchState:
        return {"product_ref": await self.skill("product_capability", state)}

    async def pricing(self, state: ResearchState) -> ResearchState:
        return {"pricing_ref": await self.skill("pricing_analysis", state)}

    async def sentiment(self, state: ResearchState) -> ResearchState:
        return {"sentiment_ref": await self.skill("user_sentiment", state)}

    async def synthesis(self, state: ResearchState) -> ResearchState:
        # All three depend on the completed base analyses, not on each other.
        import asyncio

        await asyncio.gather(
            *(
                self.skill(i, state)
                for i in ("swot_analysis", "market_landscape", "business_model")
                if i in self.c.definitions
            )
        )
        if "strategic_recommendation" in self.c.definitions:
            await self.skill("strategic_recommendation", state)
        return {
            "analysis_refs": {k: str(v.id) for k, v in (await self.c.store.artifacts()).items()}
        }
