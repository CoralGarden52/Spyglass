import hashlib
import json
from datetime import UTC, datetime
from typing import Any, TypeVar, cast
from uuid import UUID, uuid5

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.agent.runtime.contracts import ReportDraft
from app.application.auth import TenantContext
from app.domain.errors import DomainError
from app.domain.search import SearchResultMetadata
from app.infrastructure.database.knowledge import (
    AnalysisArtifact,
    Claim,
    ClaimEvidence,
    Evidence,
    QualityReview,
    Report,
    ReportVersion,
    ResearchPlanRecord,
    RunEntity,
    RuntimeCall,
    Source,
)
from app.infrastructure.database.research import Run
from app.infrastructure.database.skills import SkillVersion

T = TypeVar("T", bound=RunEntity)


def digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, ensure_ascii=False, default=str, separators=(",", ":")
        ).encode()
    ).hexdigest()


class ResearchStore:
    """A per-run tenant boundary; each operation owns a separate short transaction."""

    def __init__(
        self, sessions: async_sessionmaker[AsyncSession], context: TenantContext, run_id: UUID
    ):
        self.sessions, self.context, self.run_id = sessions, context, run_id

    async def run(self) -> Run:
        async with self.sessions() as db:
            row = await db.scalar(
                select(Run).where(Run.id == self.run_id, Run.tenant_id == self.context.tenant_id)
            )
            if row is None:
                raise DomainError(404, "not_found", "运行不存在或无权访问")
            return row

    async def rows(self, entity: type[T]) -> list[T]:
        async with self.sessions() as db:
            rows = await db.scalars(
                select(entity)
                .where(entity.tenant_id == self.context.tenant_id, entity.run_id == self.run_id)
                .order_by(entity.created_at, entity.id)
            )
            return list(rows)

    async def put(self, entity: type[T], values: dict[str, Any]) -> UUID:
        values = {**values, "tenant_id": self.context.tenant_id, "run_id": self.run_id}
        async with self.sessions() as db:
            await db.execute(insert(entity).values(**values).on_conflict_do_nothing())
            await db.commit()
        return cast(UUID, values["id"])

    async def definitions(self) -> dict[str, dict[str, Any]]:
        run = await self.run()
        result = {}
        async with self.sessions() as db:
            for snapshot in run.skills_snapshot_json:
                saved = await db.get(SkillVersion, (snapshot["id"], snapshot["version"]))
                if saved is None or saved.manifest_checksum != snapshot["manifest_checksum"]:
                    raise DomainError(409, "skill_snapshot_invalid", "冻结的技能版本无法校验")
                result[snapshot["id"]] = {
                    **snapshot,
                    "manifest": saved.metadata_json["manifest"],
                    "instructions": saved.instructions,
                    "input_schema": saved.metadata_json["input_json_schema"],
                    "output_schema": saved.metadata_json["output_json_schema"],
                }
        return result

    async def save_plan(self, payload: dict[str, Any]) -> UUID:
        return await self.put(
            ResearchPlanRecord, {"id": uuid5(self.run_id, "plan"), "payload": payload}
        )

    async def evidence(self) -> list[dict[str, Any]]:
        sources = {s.id: s for s in await self.rows(Source)}
        evidence = [
            {
                "id": str(e.id),
                "source_id": str(e.source_id),
                "excerpt": e.excerpt,
                "category": e.category,
                "validity_status": e.validity_status,
                "locator": {k: v for k, v in e.locator_json.items() if k != "search_result"},
                "search_scores": {
                    k: v
                    for k, v in e.locator_json.get("search_result", {}).items()
                    if k
                    in {
                        "date",
                        "rerank_score",
                        "authority",
                        "source_confidence",
                        "confidence_policy",
                    }
                },
                "url": sources[e.source_id].canonical_url,
                "origin": sources[e.source_id].origin_type,
                "collected_at": e.created_at.isoformat(),
            }
            for e in await self.rows(Evidence)
            if e.validity_status == "valid"
        ]
        # Native UTC publication dates determine recency; collection time is not publication.
        return sorted(evidence, key=lambda e: e["search_scores"].get("date") or "", reverse=True)

    async def save_source(self, page: dict[str, Any], category: str) -> UUID:
        fingerprint = digest([page["url"], page["excerpt"]])
        source_id = uuid5(self.run_id, "source:" + fingerprint)
        await self.put(
            Source,
            {
                "id": source_id,
                "canonical_url": page["url"],
                "title": page.get("title", ""),
                "origin_type": page["origin"],
                "content_hash": fingerprint,
                "permission_note": "公开检索摘要；需结合原网页核验"
                if page["origin"] in {"search_snippet", "search_summary"}
                else "公开页面，已检查 robots；保存受控文本片段",
            },
        )
        native = (
            SearchResultMetadata.model_validate(page["search_result"])
            if page.get("search_result") is not None
            else None
        )
        evidence_id = uuid5(
            source_id,
            category
            + (":" + digest([page["search_result"], page.get("search_query")]) if native else ""),
        )
        rejection = None
        if native:
            if not native.summary.strip():
                rejection = "missing_summary"
            elif not native.high_quality:
                rejection = "low_or_unknown_relevance"
        await self.put(
            Evidence,
            {
                "id": evidence_id,
                "source_id": source_id,
                "excerpt": page["excerpt"],
                "category": category,
                "locator_json": {
                    "url": page["url"],
                    "kind": page["origin"],
                    "published_at": page.get("published_at"),
                    **(
                        {
                            "search_result": native.model_dump(mode="json"),
                            "search_query": page.get("search_query"),
                            "rejection_reason": rejection,
                        }
                        if native
                        else {}
                    ),
                },
                "validity_status": "rejected" if rejection else "valid",
            },
        )
        return evidence_id

    async def artifacts(self) -> dict[str, AnalysisArtifact]:
        result: dict[str, AnalysisArtifact] = {}
        for row in await self.rows(AnalysisArtifact):
            if row.skill_id not in result or row.revision > result[row.skill_id].revision:
                result[row.skill_id] = row
        return result

    async def artifact(
        self, skill: dict[str, Any], payload: dict[str, Any], round_number: int
    ) -> UUID:
        artifact_id = uuid5(self.run_id, f"analysis:{skill['id']}:{round_number}")
        await self.put(
            AnalysisArtifact,
            {
                "id": artifact_id,
                "skill_id": skill["id"],
                "skill_version": skill["version"],
                "revision": round_number + 1,
                "status": payload["status"],
                "payload": payload,
                "digest": digest(payload),
            },
        )
        evidence = {e["id"] for e in await self.evidence()}

        async def extract(value: Any) -> None:
            if isinstance(value, dict):
                if "statement" in value:
                    references = list(dict.fromkeys(str(i) for i in value.get("evidence_ids", [])))
                    valid = [i for i in references if i in evidence]
                    status = value.get("evidence_status", "insufficient_evidence")
                    if len(valid) != len(references) or (status == "supported" and not valid):
                        status = "unsupported"
                    claim_id = uuid5(artifact_id, digest(value))
                    await self.put(
                        Claim,
                        {
                            "id": claim_id,
                            "artifact_id": artifact_id,
                            "statement": value["statement"],
                            "status": status,
                        },
                    )
                    if valid:
                        async with self.sessions() as db:
                            await db.execute(
                                insert(ClaimEvidence)
                                .values(
                                    [
                                        {
                                            "tenant_id": self.context.tenant_id,
                                            "claim_id": claim_id,
                                            "evidence_id": UUID(i),
                                            "relation": "supports",
                                        }
                                        for i in valid
                                    ]
                                )
                                .on_conflict_do_nothing()
                            )
                            await db.commit()
                for child in value.values():
                    await extract(child)
            elif isinstance(value, list):
                for child in value:
                    await extract(child)

        await extract(payload)
        return artifact_id

    async def claims(self) -> list[dict[str, Any]]:
        artifacts = await self.artifacts()
        owners = {r.id: r.skill_id for r in artifacts.values()}
        async with self.sessions() as db:
            links = list(
                await db.scalars(
                    select(ClaimEvidence).where(
                        ClaimEvidence.tenant_id == self.context.tenant_id,
                        ClaimEvidence.claim_id.in_(
                            select(Claim.id).where(
                                Claim.run_id == self.run_id,
                                Claim.tenant_id == self.context.tenant_id,
                            )
                        ),
                    )
                )
            )
        return [
            {
                "id": str(c.id),
                "skill_id": owners[c.artifact_id],
                "statement": c.statement,
                "status": c.status,
                "evidence_ids": [str(link.evidence_id) for link in links if link.claim_id == c.id],
            }
            for c in await self.rows(Claim)
            if c.artifact_id in owners
        ]

    async def save_report(self, draft: ReportDraft, round_number: int) -> UUID:
        run = await self.run()
        report_id = uuid5(self.run_id, "report")
        async with self.sessions() as db:
            await db.execute(
                insert(Report)
                .values(
                    id=report_id,
                    tenant_id=self.context.tenant_id,
                    run_id=self.run_id,
                    project_id=run.project_id,
                    title=draft.title,
                    current_version=round_number + 1,
                )
                .on_conflict_do_nothing()
            )
            row = await db.scalar(
                select(Report)
                .where(Report.id == report_id, Report.tenant_id == self.context.tenant_id)
                .with_for_update()
            )
            if row is not None:
                row.current_version = max(row.current_version, round_number + 1)
            await db.execute(
                insert(ReportVersion)
                .values(
                    id=uuid5(report_id, str(round_number)),
                    tenant_id=self.context.tenant_id,
                    run_id=self.run_id,
                    report_id=report_id,
                    version=round_number + 1,
                    content_json=draft.model_dump(mode="json"),
                )
                .on_conflict_do_nothing()
            )
            await db.commit()
        return report_id

    async def audit(self, **values: Any) -> None:
        from uuid import uuid4

        await self.put(RuntimeCall, {"id": uuid4(), **values})

    async def review(self, payload: dict[str, Any], round_number: int) -> None:
        await self.put(
            QualityReview, {"id": uuid5(self.run_id, f"review:{round_number}"), "payload": payload}
        )

    async def status(self, status: str, error: str | None = None) -> None:
        async with self.sessions() as db:
            row = await db.scalar(
                select(Run)
                .where(Run.id == self.run_id, Run.tenant_id == self.context.tenant_id)
                .with_for_update()
            )
            if row is None:
                raise DomainError(404, "not_found", "运行不存在")
            row.status = status
            row.error_code = error
            if status == "running":
                row.started_at = datetime.now(UTC)
            else:
                row.finished_at = datetime.now(UTC)
                usages = [c.usage_json for c in await self.rows(RuntimeCall) if c.kind == "model"]
                row.usage_json = {
                    "known_calls": sum(u is not None for u in usages),
                    "total_tokens": sum(u.get("total_tokens", 0) for u in usages if u is not None)
                    if usages and all(u is not None and "total_tokens" in u for u in usages)
                    else None,
                }
            await db.commit()
