from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import Base


def run_constraints() -> tuple[Any, ...]:
    return (
        UniqueConstraint("tenant_id", "id"),
        ForeignKeyConstraint(["tenant_id", "run_id"], ["runs.tenant_id", "runs.id"]),
    )


class RunEntity(Base):
    __abstract__ = True
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id"), index=True)
    run_id: Mapped[UUID] = mapped_column(index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ResearchPlanRecord(RunEntity):
    __tablename__ = "research_plans"
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB)
    __table_args__ = run_constraints()


class Source(RunEntity):
    __tablename__ = "sources"
    canonical_url: Mapped[str] = mapped_column(Text)
    title: Mapped[str] = mapped_column(String(500))
    origin_type: Mapped[str] = mapped_column(String(32))
    content_hash: Mapped[str] = mapped_column(String(64))
    permission_note: Mapped[str] = mapped_column(Text)
    __table_args__ = (
        *run_constraints(),
        UniqueConstraint("tenant_id", "run_id", "content_hash", name="uq_source_run_content"),
    )


class Evidence(RunEntity):
    __tablename__ = "evidence"
    source_id: Mapped[UUID] = mapped_column()
    excerpt: Mapped[str] = mapped_column(Text)
    locator_json: Mapped[dict[str, Any]] = mapped_column(JSONB)
    category: Mapped[str] = mapped_column(String(20))
    validity_status: Mapped[str] = mapped_column(String(20), default="valid")
    __table_args__ = (
        *run_constraints(),
        ForeignKeyConstraint(["tenant_id", "source_id"], ["sources.tenant_id", "sources.id"]),
    )


class CompetitorProfile(RunEntity):
    __tablename__ = "competitors"
    canonical_name: Mapped[str] = mapped_column(String(200))
    profile_json: Mapped[dict[str, Any]] = mapped_column(JSONB)
    __table_args__ = run_constraints()


class ReviewSample(RunEntity):
    __tablename__ = "review_samples"
    evidence_id: Mapped[UUID] = mapped_column()
    source_id: Mapped[UUID] = mapped_column()
    fingerprint: Mapped[str] = mapped_column(String(64))
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB)
    __table_args__ = (
        *run_constraints(),
        UniqueConstraint("tenant_id", "run_id", "fingerprint", name="uq_review_run_fingerprint"),
        ForeignKeyConstraint(["tenant_id", "evidence_id"], ["evidence.tenant_id", "evidence.id"]),
        ForeignKeyConstraint(["tenant_id", "source_id"], ["sources.tenant_id", "sources.id"]),
    )


class AnalysisArtifact(RunEntity):
    __tablename__ = "analysis_artifacts"
    skill_id: Mapped[str] = mapped_column(String(64))
    skill_version: Mapped[str] = mapped_column(String(32))
    revision: Mapped[int] = mapped_column()
    status: Mapped[str] = mapped_column(String(32))
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB)
    digest: Mapped[str] = mapped_column(String(64))
    __table_args__ = (
        *run_constraints(),
        ForeignKeyConstraint(["skill_id", "skill_version"], ["skills.id", "skills.version"]),
        UniqueConstraint(
            "tenant_id", "run_id", "skill_id", "revision", name="uq_analysis_run_skill_revision"
        ),
    )


class Claim(RunEntity):
    __tablename__ = "claims"
    artifact_id: Mapped[UUID] = mapped_column()
    statement: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32))
    __table_args__ = (
        *run_constraints(),
        ForeignKeyConstraint(
            ["tenant_id", "artifact_id"], ["analysis_artifacts.tenant_id", "analysis_artifacts.id"]
        ),
    )


class ClaimEvidence(Base):
    __tablename__ = "claim_evidence"
    tenant_id: Mapped[UUID] = mapped_column(primary_key=True)
    claim_id: Mapped[UUID] = mapped_column(primary_key=True)
    evidence_id: Mapped[UUID] = mapped_column(primary_key=True)
    relation: Mapped[str] = mapped_column(String(20), default="supports")
    __table_args__ = (
        ForeignKeyConstraint(["tenant_id", "claim_id"], ["claims.tenant_id", "claims.id"]),
        ForeignKeyConstraint(["tenant_id", "evidence_id"], ["evidence.tenant_id", "evidence.id"]),
    )


class Report(RunEntity):
    __tablename__ = "reports"
    project_id: Mapped[UUID] = mapped_column()
    title: Mapped[str] = mapped_column(String(200))
    current_version: Mapped[int] = mapped_column(default=1)
    __table_args__ = (
        *run_constraints(),
        UniqueConstraint("tenant_id", "run_id", name="uq_report_run"),
        ForeignKeyConstraint(
            ["tenant_id", "project_id"], ["research_projects.tenant_id", "research_projects.id"]
        ),
    )


class ReportVersion(RunEntity):
    __tablename__ = "report_versions"
    report_id: Mapped[UUID] = mapped_column()
    version: Mapped[int] = mapped_column()
    content_json: Mapped[dict[str, Any]] = mapped_column(JSONB)
    __table_args__ = (
        *run_constraints(),
        UniqueConstraint("tenant_id", "report_id", "version", name="uq_report_version"),
        ForeignKeyConstraint(["tenant_id", "report_id"], ["reports.tenant_id", "reports.id"]),
    )


class RuntimeCall(RunEntity):
    __tablename__ = "runtime_calls"
    kind: Mapped[str] = mapped_column(String(16))
    name: Mapped[str] = mapped_column(String(80))
    prompt_version: Mapped[str | None] = mapped_column(String(80))
    input_hash: Mapped[str] = mapped_column(String(64))
    output_hash: Mapped[str | None] = mapped_column(String(64))
    model: Mapped[str | None] = mapped_column(String(200))
    usage_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(32))
    error_code: Mapped[str | None] = mapped_column(String(80))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    __table_args__ = run_constraints()


class QualityReview(RunEntity):
    __tablename__ = "quality_reviews"
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB)
    __table_args__ = run_constraints()
