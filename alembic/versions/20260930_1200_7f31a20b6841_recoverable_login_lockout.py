"""Add a recoverable login lockout timestamp."""

from alembic import op
import sqlalchemy as sa


revision = "7f31a20b6841"
down_revision = "68f108684a94"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("access_profiles", sa.Column("locked_until", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("access_profiles", "locked_until")
