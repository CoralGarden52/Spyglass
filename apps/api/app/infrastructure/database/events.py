from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.knowledge import RunEntity, run_constraints


class RunEvent(RunEntity):
    __tablename__ = "run_events"
    seq: Mapped[int] = mapped_column()
    type: Mapped[str] = mapped_column(String(64))
    schema_version: Mapped[int] = mapped_column(default=1)
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSONB)
    __table_args__ = (
        *run_constraints(),
        UniqueConstraint("run_id", "seq"),
        CheckConstraint("seq > 0", name="positive_seq"),
    )


class RunStep(RunEntity):
    __tablename__ = "run_steps"
    node: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(24))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    usage_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    artifact_refs: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    __table_args__ = (
        *run_constraints(),
        UniqueConstraint("tenant_id", "run_id", "id", name="uq_run_step_owner"),
        CheckConstraint("status IN ('running','completed','failed','cancelled')", name="status"),
    )


class ToolCall(RunEntity):
    __tablename__ = "tool_calls"
    step_id: Mapped[UUID | None] = mapped_column()
    tool_name: Mapped[str] = mapped_column(String(64))
    args_redacted_json: Mapped[dict[str, Any]] = mapped_column(JSONB)
    result_ref: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(24))
    error_code: Mapped[str | None] = mapped_column(String(80))
    idempotency_key: Mapped[str] = mapped_column(String(128))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    usage_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    __table_args__ = (
        *run_constraints(),
        ForeignKeyConstraint(
            ["tenant_id", "run_id", "step_id"],
            ["run_steps.tenant_id", "run_steps.run_id", "run_steps.id"],
        ),
        UniqueConstraint("tenant_id", "run_id", "idempotency_key", name="uq_tool_run_request"),
        CheckConstraint("status IN ('running','completed','failed','cancelled')", name="status"),
    )
