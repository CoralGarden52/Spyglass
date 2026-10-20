"""Install the real vector extension; business entities follow in Slice 1."""

from alembic import op

revision = "0001_pgvector"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")


def downgrade() -> None:
    # No CASCADE: later evidence tables must be removed by their own migrations first.
    op.execute("DROP EXTENSION vector")
