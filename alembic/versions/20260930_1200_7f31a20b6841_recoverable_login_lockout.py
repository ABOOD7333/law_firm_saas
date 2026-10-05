"""Add a recoverable login lockout timestamp."""

from alembic import op
import sqlalchemy as sa


revision = "7f31a20b6841"
down_revision = "68f108684a94"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    columns = {column["name"] for column in sa.inspect(bind).get_columns("access_profiles")}
    if "locked_until" not in columns:
        op.add_column("access_profiles", sa.Column("locked_until", sa.Text(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    columns = {column["name"] for column in sa.inspect(bind).get_columns("access_profiles")}
    if "locked_until" in columns:
        op.drop_column("access_profiles", "locked_until")
