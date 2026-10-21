"""Persist ordered run events, node steps and tool calls."""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0006_run_events"
down_revision: str | None = "0005_langgraph_checkpoint"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    for name, columns, constraints in [
        (
            "run_events",
            [
                sa.Column("seq", sa.Integer(), nullable=False),
                sa.Column("type", sa.String(64), nullable=False),
                sa.Column("schema_version", sa.Integer(), nullable=False),
                sa.Column("payload_json", postgresql.JSONB(), nullable=False),
            ],
            [
                sa.UniqueConstraint("run_id", "seq"),
                sa.CheckConstraint("seq > 0", name="positive_seq"),
            ],
        ),
        (
            "run_steps",
            [
                sa.Column("node", sa.String(64), nullable=False),
                sa.Column("status", sa.String(24), nullable=False),
                sa.Column(
                    "started_at",
                    sa.DateTime(timezone=True),
                    server_default=sa.func.now(),
                    nullable=False,
                ),
                sa.Column("ended_at", sa.DateTime(timezone=True)),
                sa.Column("usage_json", postgresql.JSONB()),
                sa.Column("artifact_refs", postgresql.JSONB(), nullable=False),
            ],
            [
                sa.UniqueConstraint("tenant_id", "run_id", "id", name="uq_run_step_owner"),
                sa.CheckConstraint(
                    "status IN ('running','completed','failed','cancelled')", name="status"
                ),
            ],
        ),
        (
            "tool_calls",
            [
                sa.Column("step_id", sa.UUID()),
                sa.Column("tool_name", sa.String(64), nullable=False),
                sa.Column("args_redacted_json", postgresql.JSONB(), nullable=False),
                sa.Column("result_ref", postgresql.JSONB()),
                sa.Column("status", sa.String(24), nullable=False),
                sa.Column("error_code", sa.String(80)),
                sa.Column("idempotency_key", sa.String(128), nullable=False),
                sa.Column(
                    "started_at",
                    sa.DateTime(timezone=True),
                    server_default=sa.func.now(),
                    nullable=False,
                ),
                sa.Column("ended_at", sa.DateTime(timezone=True)),
                sa.Column("usage_json", postgresql.JSONB()),
            ],
            [
                sa.UniqueConstraint(
                    "tenant_id", "run_id", "idempotency_key", name="uq_tool_run_request"
                ),
                sa.ForeignKeyConstraint(
                    ["tenant_id", "run_id", "step_id"],
                    ["run_steps.tenant_id", "run_steps.run_id", "run_steps.id"],
                ),
                sa.CheckConstraint(
                    "status IN ('running','completed','failed','cancelled')", name="status"
                ),
            ],
        ),
    ]:
        op.create_table(
            name,
            sa.Column("id", sa.UUID(), primary_key=True),
            sa.Column("tenant_id", sa.UUID(), sa.ForeignKey("tenants.id"), nullable=False),
            sa.Column("run_id", sa.UUID(), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            *columns,
            sa.UniqueConstraint("tenant_id", "id"),
            sa.ForeignKeyConstraint(["tenant_id", "run_id"], ["runs.tenant_id", "runs.id"]),
            *constraints,
        )
        op.create_index(f"ix_{name}_run_id", name, ["run_id"])
        op.create_index(f"ix_{name}_tenant_id", name, ["tenant_id"])


def downgrade() -> None:
    for name in ("tool_calls", "run_steps", "run_events"):
        op.drop_table(name)
