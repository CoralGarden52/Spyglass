from typing import Any, Literal, cast
from uuid import UUID

from app.agent.runtime.context import NodeContext
from app.agent.runtime.contracts import (
    Issue,
    ReportClaim,
    ReportDraft,
    ReportSection,
    ReviewResult,
    ReviewVerdict,
    WritingPlan,
)
from app.agent.runtime.sentiment import aggregate_reviews
from app.agent.runtime.state import ResearchState
from app.infrastructure.database.knowledge import ReportVersion, ReviewSample
from app.infrastructure.providers.chat import ProviderError
from app.infrastructure.research_store import digest


class ReportingNodes:
    def __init__(self, context: NodeContext, max_repairs: int):
        self.c, self.max_repairs = context, max_repairs

    async def build_draft(self, plan: WritingPlan | None = None) -> ReportDraft:
        artifacts = await self.c.store.artifacts()
        claims = await self.c.store.claims()
        sections = []
        for key, skill in self.c.definitions.items():
            if skill["kind"] == "scenario":
                continue
            artifact = artifacts.get(key)
            selected = (
                next((s.claim_ids for s in plan.sections if s.skill_id == key), [])
                if plan
                else [UUID(c["id"]) for c in claims if c["skill_id"] == key]
            )
            owned = [c for c in claims if c["skill_id"] == key and UUID(c["id"]) in selected]
            sections.append(
                ReportSection(
                    skill_id=key,
                    heading=skill["manifest"]["name"],
                    status=artifact.status if artifact else "insufficient_evidence",
                    claims=[
                        ReportClaim.model_validate({k: v for k, v in c.items() if k != "skill_id"})
                        for c in owned
                    ],
                    analysis=artifact.payload if artifact else {},
                    limitations=artifact.payload.get("limitations", [])
                    if artifact
                    else ["未完成分析"],
                )
            )
        samples = await self.c.store.rows(ReviewSample)
        sentiment = artifacts.get("user_sentiment")
        observations = sentiment.payload.get("reviews", []) if sentiment else []
        summary = aggregate_reviews(observations)
        summary["classified_count"] = summary["sample_count"]
        summary["sample_count"] = len(samples)
        summary["unclassified_count"] = len(samples) - summary["classified_count"]
        for value in summary["overall"].values():
            value["ratio"] = value["count"] / len(samples) if samples else None
        return ReportDraft(
            title=plan.title if plan else "竞品分析报告（待复核）",
            status="partial",
            sections=sections,
            limitations=[
                "基于本轮可访问来源；搜索摘要与网页原文分别标记，样本不足不代表没有用户反馈。"
            ],
            sentiment_summary=summary,
        )

    async def writer(self, state: ResearchState) -> ResearchState:
        artifacts = await self.c.store.artifacts()
        claims = await self.c.store.claims()
        plan = None
        writer_error = None
        try:
            raw = await self.c.call(
                "writer",
                (
                    "Compose a report plan with exactly one section per supplied "
                    "Skill. Select only existing claim IDs under their original Skill."
                    " Do not invent prose facts, claims or numbers. Section text is "
                    "rendered from verified structured analyses and claims. Include "
                    "all factual claims. Respond in Chinese."
                ),
                {
                    "artifacts": {k: v.payload for k, v in artifacts.items()},
                    "claims": claims,
                    "repair": state.get("review_result"),
                },
                WritingPlan,
            )
            plan = WritingPlan.model_validate(raw)
            selected = {s.skill_id for s in plan.sections}
            expected = set(artifacts)
            if (
                selected != expected
                or len(plan.sections) != len(expected)
                or any(
                    not any(c["id"] == str(i) and c["skill_id"] == s.skill_id for c in claims)
                    for s in plan.sections
                    for i in s.claim_ids
                )
            ):
                raise ProviderError("schema_error:writer_references")
        except ProviderError as exc:
            # Honest structural readback; never fabricate missing prose or analysis.
            plan = None
            writer_error = str(exc)
        draft = await self.build_draft(plan)
        report_id = await self.c.store.save_report(draft, state.get("review_count", 0))
        return {"report_draft_id": str(report_id), "writer_error": writer_error}

    async def reviewer(self, state: ResearchState) -> ResearchState:
        artifacts = await self.c.store.artifacts()
        evidence = await self.c.store.evidence()
        valid = {e["id"] for e in evidence}
        claims = await self.c.store.claims()
        versions = await self.c.store.rows(ReportVersion)
        draft = ReportDraft.model_validate(max(versions, key=lambda v: v.version).content_json)
        issues = []
        if state.get("writer_error"):
            issues.append(
                Issue(
                    type="schema_error",
                    target="writer",
                    description="Writer 输出不符合报告 Schema 或引用约束",
                    repair_request="按已有 Claim 和技能清单重新生成报告结构",
                )
            )
        for key, artifact in artifacts.items():
            limits = artifact.payload.get("limitations", [])
            if "missing_evidence" in limits:
                issues.append(
                    Issue(
                        type="missing_evidence",
                        target="collector",
                        skill_id=key,
                        description="事实产物缺少证据引用",
                        repair_request="采集来源后补齐可验证的引用",
                    )
                )
            if any(str(i).startswith(("schema_error", "model_invalid_json")) for i in limits):
                issues.append(
                    Issue(
                        type="schema_error",
                        target="analyst",
                        skill_id=key,
                        description="分析输出不符合冻结的 Schema",
                        repair_request="按该 Skill 的输出 Schema 重新生成结构化产物",
                    )
                )

            def check(value: Any, skill_key: str = key) -> None:
                if isinstance(value, dict):
                    if "statement" in value and (
                        any(str(i) not in valid for i in value.get("evidence_ids", []))
                        or (
                            value.get("evidence_status") in {"supported", "partial"}
                            and not value.get("evidence_ids")
                        )
                    ):
                        issues.append(
                            Issue(
                                type="missing_evidence",
                                target="collector",
                                skill_id=skill_key,
                                description="事实引用缺失或不属于当前运行证据",
                                repair_request="采集可定位来源并在分析中替换无效引用",
                            )
                        )
                    for child in value.values():
                        check(child)
                elif isinstance(value, list):
                    for child in value:
                        check(child)

            check(artifact.payload)
        expected = {k for k, d in self.c.definitions.items() if d["kind"] != "scenario"}
        if {s.skill_id for s in draft.sections} != expected:
            issues.append(
                Issue(
                    type="schema_error",
                    target="writer",
                    description="报告缺少选中技能章节",
                    repair_request="补齐全部必选与增强章节",
                )
            )
        try:
            verdict = ReviewVerdict.model_validate(
                await self.c.call(
                    "reviewer",
                    (
                        "Independently audit facts against exact supplied evidence, "
                        "contradictions, pricing dates and units, missing claims/sections "
                        "and review authenticity. Return actionable issues targeted to "
                        "collector (source gaps/outdated), analyst "
                        "(interpretation/contradiction/schema), or writer (section/claim "
                        "mapping). A declared insufficiency is honest but cannot become a "
                        "supported fact. Never invent evidence. passed may be true only if"
                        " issues is empty."
                    ),
                    {
                        "report": draft.model_dump(mode="json"),
                        "claims": claims,
                        "untrusted_evidence": evidence,
                        "prior_review": state.get("review_result"),
                    },
                    ReviewVerdict,
                )
            )
            issues.extend(verdict.issues)
            if not verdict.passed and not verdict.issues:
                issues.append(
                    Issue(
                        type="schema_error",
                        target="writer",
                        description="Reviewer 拒绝通过但未给出可执行问题",
                        repair_request="重新组织报告并保留数据不足说明",
                    )
                )
        except ProviderError:
            issues.append(
                Issue(
                    type="schema_error",
                    target="writer",
                    description="Reviewer 调用失败或输出无效，未完成质量确认",
                    repair_request="保留报告并重新执行审查",
                )
            )
        count = state.get("review_count", 0) + 1
        # Exclude freshly allocated Claim IDs: IDs alone are not evidence of repair.
        current_digest = digest(
            {
                "artifacts": {k: a.payload for k, a in artifacts.items()},
                "title": draft.title,
                "sections": [
                    {
                        "skill": s.skill_id,
                        "claims": [
                            {
                                "statement": c.statement,
                                "status": c.status,
                                "evidence_ids": sorted(map(str, c.evidence_ids)),
                            }
                            for c in s.claims
                        ],
                    }
                    for s in draft.sections
                ],
            }
        )
        previous = state.get("review_result") or {}
        changed = not previous or previous.get("before_digest") != current_digest
        passed = not issues and changed
        if not changed and previous.get("issues"):
            issues.append(
                Issue(
                    type="schema_error",
                    target="writer",
                    description="返工后报告产物未发生变化",
                    repair_request="人工检查未解决的问题",
                )
            )
        target = next(
            (t for t in ("collector", "analyst", "writer") if any(i.target == t for i in issues)),
            None,
        )
        status = (
            "passed"
            if passed
            else "repair"
            if count <= self.max_repairs and changed
            else "needs_review"
        )
        result = ReviewResult(
            passed=passed,
            issues=issues,
            next_target=cast(Literal["collector", "analyst", "writer"] | None, target),
            review_count=count,
            status=cast(Literal["passed", "repair", "needs_review"], status),
            before_digest=current_digest,
        )
        await self.c.store.review(result.model_dump(mode="json"), count)
        terminal = passed or status == "needs_review"
        final = (
            "completed"
            if passed and all(a.status == "complete" for a in artifacts.values())
            else "needs_review"
        )
        if terminal:
            draft.status = "complete" if final == "completed" else "needs_review"
            draft.limitations.extend(i.description for i in issues)
            await self.c.store.save_report(draft, count)
        return {
            "review_result": result.model_dump(mode="json"),
            "review_count": count,
            "status": final if terminal else "running",
            "repair_changed": bool(previous) and changed,
        }
