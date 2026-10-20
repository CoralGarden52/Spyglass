"""Initialize the SDK-owned checkpoint schema before accepting concurrent Runs."""

from langgraph.checkpoint.postgres import PostgresSaver
from psycopg import connect
from psycopg.rows import dict_row
from sqlalchemy.engine import make_url

from alembic import op
from app.core.config import Settings

revision = "0005_langgraph_checkpoint"
down_revision = "0004_research_runtime"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if op.get_context().as_sql:
        raise RuntimeError(
            "LangGraph SDK initialization requires online migration; --sql is unsupported"
        )
    # SDK migrations include CREATE INDEX CONCURRENTLY and require autocommit.
    # A separate revision lets an interrupted SDK setup safely resume.
    with op.get_context().autocommit_block():
        op.execute("CREATE SCHEMA IF NOT EXISTS langgraph")
        url = make_url(Settings().database_url.get_secret_value()).set(drivername="postgresql")
        with connect(
            url.render_as_string(False),
            autocommit=True,
            prepare_threshold=0,
            row_factory=dict_row,
            options="-c search_path=langgraph",
            connect_timeout=5,
        ) as connection:
            PostgresSaver(connection).setup()


def downgrade() -> None:
    op.execute("DROP SCHEMA IF EXISTS langgraph CASCADE")
