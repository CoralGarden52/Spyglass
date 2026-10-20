from uuid import UUID

from fastapi import APIRouter

from app.application.reports import ReportService
from app.core.dependencies import Context, Database
from app.domain.report_schemas import EvidenceResponse, ReportList, ReportResponse

router = APIRouter(prefix="/api/v1", tags=["research-results"])


@router.get("/research/{project_id}/reports", response_model=ReportList)
async def list_reports(project_id: UUID, db: Database, context: Context) -> ReportList:
    return await ReportService(db, context).list(project_id)


@router.get("/reports/{report_id}", response_model=ReportResponse)
async def report(report_id: UUID, db: Database, context: Context) -> ReportResponse:
    return await ReportService(db, context).get(report_id)


@router.get("/evidence/{evidence_id}", response_model=EvidenceResponse)
async def evidence(evidence_id: UUID, db: Database, context: Context) -> EvidenceResponse:
    return await ReportService(db, context).evidence(evidence_id)
