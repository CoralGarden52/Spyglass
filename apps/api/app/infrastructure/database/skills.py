from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import Base


class SkillVersion(Base):
    __tablename__ = "skills"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    version: Mapped[str] = mapped_column(String(32), primary_key=True)
    kind: Mapped[str] = mapped_column(String(20))
    manifest_checksum: Mapped[str] = mapped_column(String(64))
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSONB)
    instructions: Mapped[str] = mapped_column(Text)
    is_system_required: Mapped[bool] = mapped_column(Boolean)
    __table_args__ = (CheckConstraint("kind IN ('scenario','core','advanced')", name="kind"),)


class SkillConfig(Base):
    __tablename__ = "skill_configs"
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id"), primary_key=True)
    skill_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    skill_version: Mapped[str] = mapped_column(String(32))
    enabled: Mapped[bool] = mapped_column(Boolean)
    config_json: Mapped[dict[str, Any]] = mapped_column(JSONB)
    revision: Mapped[int] = mapped_column(Integer)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (
        ForeignKeyConstraint(["skill_id", "skill_version"], ["skills.id", "skills.version"]),
        CheckConstraint(
            "skill_id NOT IN ('product_capability','pricing_analysis',"
            "'user_sentiment','swot_analysis') OR enabled",
            name="required_enabled",
        ),
        CheckConstraint("revision > 0", name="positive_revision"),
    )


class SkillMutation(Base):
    __tablename__ = "skill_config_mutations"
    tenant_id: Mapped[UUID] = mapped_column(primary_key=True)
    user_id: Mapped[UUID] = mapped_column(primary_key=True)
    idempotency_key: Mapped[str] = mapped_column(String(128), primary_key=True)
    request_hash: Mapped[str] = mapped_column(String(64))
    response_json: Mapped[dict[str, Any]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "user_id"], ["tenant_members.tenant_id", "tenant_members.user_id"]
        ),
    )
