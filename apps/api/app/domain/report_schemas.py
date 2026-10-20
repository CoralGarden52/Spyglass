from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.agent.runtime.contracts import ReportDraft, ReviewResult
from app.domain.search import SearchResultMetadata, SearchSourceView


class ReportSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    run_id: UUID
    project_id: UUID
    title: str
    current_version: int
    created_at: datetime


class ArtifactView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    skill_id: str
    skill_version: str
    revision: int
    status: str
    digest: str
    payload: dict[str, Any]


class AuditView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    kind: str
    name: str
    prompt_version: str | None
    model: str | None
    usage_json: dict[str, Any] | None
    status: str
    error_code: str | None
    started_at: datetime
    ended_at: datetime


class ReportRead(ReportSummary):
    content: ReportDraft
    review_history: list[ReviewResult]
    artifact_history: list[ArtifactView]
    calls: list[AuditView]
    search_sources: list[SearchSourceView] = Field(default_factory=list)


class ReportList(BaseModel):
    schema_version: Literal[1] = 1
    data: list[ReportSummary]


class ReportResponse(BaseModel):
    schema_version: Literal[1] = 1
    data: ReportRead


class EvidenceRead(BaseModel):
    id: UUID
    source_id: UUID
    excerpt: str
    locator: dict[str, Any]
    collected_at: datetime
    validity_status: str
    url: str
    title: str
    origin: str
    permission_note: str
    search_result: SearchResultMetadata | None = None


class EvidenceResponse(BaseModel):
    schema_version: Literal[1] = 1
    data: EvidenceRead
