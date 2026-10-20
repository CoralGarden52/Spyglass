"""${message}"""
from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

revision = ${repr(up_revision)}
down_revision = ${repr(down_revision)}
branch_labels = ${repr(branch_labels)}
depends_on = ${repr(depends_on)}


def upgrade() -> None:
    ${upgrades if upgrades else "raise NotImplementedError('Migration requires implementation')"}


def downgrade() -> None:
    ${downgrades if downgrades else "raise NotImplementedError('Downgrade requires implementation')"}
