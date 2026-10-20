from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import Base


class Project(Base):
    __tablename__ = "research_projects"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id"))
    created_by: Mapped[UUID] = mapped_column()
    title: Mapped[str] = mapped_column(String(200))
    mode: Mapped[str] = mapped_column(String(20))
    scenario_skill_id: Mapped[str] = mapped_column(String(60))
    status: Mapped[str] = mapped_column(String(20), server_default="draft")
    idempotency_key: Mapped[str] = mapped_column(String(128))
    request_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        UniqueConstraint("tenant_id", "created_by", "idempotency_key", name="uq_project_request"),
        ForeignKeyConstraint(
            ["tenant_id", "created_by"], ["tenant_members.tenant_id", "tenant_members.user_id"]
        ),
        CheckConstraint("mode IN ('quick','standard','deep')", name="mode"),
        CheckConstraint(
            "status IN ('draft','running','completed','needs_review','failed','archived')",
            name="status",
        ),
        CheckConstraint(
            "scenario_skill_id IN ('general_analysis','ecommerce','internet_product',"
            "'hardware_iot','ai_llm','finance')",
            name="scenario",
        ),
        Index("ix_projects_tenant_created", "tenant_id", "created_at"),
    )


class Thread(Base):
    __tablename__ = "threads"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id"))
    project_id: Mapped[UUID] = mapped_column()
    created_by: Mapped[UUID] = mapped_column()
    title: Mapped[str] = mapped_column(String(200))
    idempotency_key: Mapped[str] = mapped_column(String(128))
    request_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        UniqueConstraint("tenant_id", "id", "project_id", name="uq_thread_tenant_id_project"),
        UniqueConstraint("tenant_id", "created_by", "idempotency_key", name="uq_thread_request"),
        ForeignKeyConstraint(
            ["tenant_id", "project_id"], ["research_projects.tenant_id", "research_projects.id"]
        ),
        ForeignKeyConstraint(
            ["tenant_id", "created_by"], ["tenant_members.tenant_id", "tenant_members.user_id"]
        ),
        Index("ix_threads_tenant_created", "tenant_id", "created_at"),
    )


class Run(Base):
    __tablename__ = "runs"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id"))
    project_id: Mapped[UUID] = mapped_column()
    thread_id: Mapped[UUID] = mapped_column()
    user_id: Mapped[UUID] = mapped_column()
    status: Mapped[str] = mapped_column(String(24), server_default="pending")
    skills_snapshot_json: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, server_default="[]")
    usage_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    idempotency_key: Mapped[str] = mapped_column(String(128))
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_code: Mapped[str | None] = mapped_column(String(80))
    request_hash: Mapped[str | None] = mapped_column(String(64))
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        UniqueConstraint("tenant_id", "thread_id", "id", name="uq_run_tenant_thread_id"),
        UniqueConstraint(
            "tenant_id", "user_id", "thread_id", "idempotency_key", name="uq_run_request"
        ),
        ForeignKeyConstraint(
            ["tenant_id", "thread_id", "project_id"],
            ["threads.tenant_id", "threads.id", "threads.project_id"],
        ),
        ForeignKeyConstraint(
            ["tenant_id", "user_id"], ["tenant_members.tenant_id", "tenant_members.user_id"]
        ),
        CheckConstraint(
            "status IN ('pending','running','waiting_approval','cancel_requested',"
            "'completed','failed','cancelled','needs_review')",
            name="status",
        ),
        Index(
            "uq_run_active_thread",
            "tenant_id",
            "thread_id",
            unique=True,
            postgresql_where=text(
                "status IN ('pending','running','waiting_approval','cancel_requested')"
            ),
        ),
        Index("ix_runs_tenant_requested", "tenant_id", "requested_at"),
    )


class Message(Base):
    __tablename__ = "messages"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id"))
    thread_id: Mapped[UUID] = mapped_column()
    run_id: Mapped[UUID | None] = mapped_column()
    role: Mapped[str] = mapped_column(String(20))
    content_json: Mapped[dict[str, Any]] = mapped_column(JSONB)
    sequence: Mapped[int] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (
        ForeignKeyConstraint(["tenant_id", "thread_id"], ["threads.tenant_id", "threads.id"]),
        ForeignKeyConstraint(
            ["tenant_id", "thread_id", "run_id"], ["runs.tenant_id", "runs.thread_id", "runs.id"]
        ),
        UniqueConstraint("tenant_id", "thread_id", "sequence"),
        CheckConstraint("role IN ('user','assistant','system','tool')", name="role"),
        CheckConstraint("sequence > 0", name="sequence"),
    )
