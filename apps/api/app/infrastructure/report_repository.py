from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.runtime.contracts import ReportDraft, ReviewResult
from app.application.auth import TenantContext
from app.domain.errors import DomainError
from app.domain.report_schemas import (
    ArtifactView,
    AuditView,
    EvidenceRead,
    EvidenceResponse,
    ReportList,
    ReportRead,
    ReportResponse,
    ReportSummary,
)
from app.domain.search import SearchResultMetadata, SearchSourceView
from app.infrastructure.database.knowledge import (
    AnalysisArtifact,
    Evidence,
    QualityReview,
    Report,
    ReportVersion,
    RuntimeCall,
    Source,
)


class ReportRepository:
    def __init__(self, db: AsyncSession, context: TenantContext):
        self.db, self.tenant_id = db, context.tenant_id

    async def list(self, project_id: UUID) -> ReportList:
        rows = await self.db.scalars(
            select(Report)
            .where(Report.tenant_id == self.tenant_id, Report.project_id == project_id)
            .order_by(Report.created_at.desc())
            .limit(100)
        )
        return ReportList(data=[ReportSummary.model_validate(r) for r in rows])

    async def report(self, report_id: UUID) -> ReportResponse:
        row = await self.db.scalar(
            select(Report).where(Report.id == report_id, Report.tenant_id == self.tenant_id)
        )
        if row is None:
            raise DomainError(404, "not_found", "报告不存在或无权访问")
        version = await self.db.scalar(
            select(ReportVersion).where(
                ReportVersion.report_id == row.id,
                ReportVersion.version == row.current_version,
                ReportVersion.tenant_id == self.tenant_id,
            )
        )
        if version is None:
            raise DomainError(409, "report_version_missing", "报告当前版本不可读取")
        reviews = await self.db.scalars(
            select(QualityReview)
            .where(QualityReview.run_id == row.run_id, QualityReview.tenant_id == self.tenant_id)
            .order_by(QualityReview.created_at)
        )
        artifacts = await self.db.scalars(
            select(AnalysisArtifact)
            .where(
                AnalysisArtifact.run_id == row.run_id, AnalysisArtifact.tenant_id == self.tenant_id
            )
            .order_by(AnalysisArtifact.skill_id, AnalysisArtifact.revision)
        )
        calls = await self.db.scalars(
            select(RuntimeCall)
            .where(RuntimeCall.run_id == row.run_id, RuntimeCall.tenant_id == self.tenant_id)
            .order_by(RuntimeCall.started_at)
        )
        return ReportResponse(
            data=ReportRead(
                **ReportSummary.model_validate(row).model_dump(),
                content=ReportDraft.model_validate(version.content_json),
                review_history=[ReviewResult.model_validate(r.payload) for r in reviews],
                artifact_history=[ArtifactView.model_validate(a) for a in artifacts],
                calls=[AuditView.model_validate(c) for c in calls],
                search_sources=[
                    SearchSourceView(
                        evidence_id=str(e.id),
                        validity_status=e.validity_status,
                        result=SearchResultMetadata.model_validate(e.locator_json["search_result"]),
                    )
                    for e in await self.db.scalars(
                        select(Evidence)
                        .where(Evidence.run_id == row.run_id, Evidence.tenant_id == self.tenant_id)
                        .order_by(Evidence.created_at, Evidence.id)
                    )
                    if e.locator_json.get("search_result") is not None
                ],
            )
        )

    async def evidence(self, evidence_id: UUID) -> EvidenceResponse:
        row = await self.db.scalar(
            select(Evidence).where(Evidence.id == evidence_id, Evidence.tenant_id == self.tenant_id)
        )
        if row is None:
            raise DomainError(404, "not_found", "证据不存在或无权访问")
        source = await self.db.scalar(
            select(Source).where(Source.id == row.source_id, Source.tenant_id == self.tenant_id)
        )
        if source is None:
            raise DomainError(404, "not_found", "来源不存在或无权访问")
        return EvidenceResponse(
            data=EvidenceRead(
                id=row.id,
                source_id=source.id,
                excerpt=row.excerpt,
                locator=row.locator_json,
                collected_at=row.created_at,
                validity_status=row.validity_status,
                url=source.canonical_url,
                title=source.title,
                origin=source.origin_type,
                permission_note=source.permission_note,
                search_result=SearchResultMetadata.model_validate(row.locator_json["search_result"])
                if row.locator_json.get("search_result") is not None
                else None,
            )
        )
