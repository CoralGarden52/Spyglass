from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.application.auth import TenantContext
from app.application.research import ResearchService
from app.domain.report_schemas import EvidenceResponse, ReportList, ReportResponse
from app.infrastructure.report_repository import ReportRepository


class ReportService:
    def __init__(self, db: AsyncSession, context: TenantContext):
        self.repository = ReportRepository(db, context)
        self.research = ResearchService(db, context)

    async def list(self, project_id: UUID) -> ReportList:
        await self.research.project(project_id)
        return await self.repository.list(project_id)

    async def get(self, report_id: UUID) -> ReportResponse:
        return await self.repository.report(report_id)

    async def evidence(self, evidence_id: UUID) -> EvidenceResponse:
        return await self.repository.evidence(evidence_id)
