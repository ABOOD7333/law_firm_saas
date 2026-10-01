"""Bind client records to their portal accounts."""

from alembic import op
import sqlalchemy as sa


revision = "13b7d2c9e841"
down_revision = "7f31a20b6841"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("law_clients", sa.Column("user_id", sa.Integer(), nullable=True))
    op.create_index("ix_law_clients_user_id", "law_clients", ["user_id"])
    op.create_foreign_key(
        "fk_law_clients_user_id_access_profiles",
        "law_clients",
        "access_profiles",
        ["user_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_law_clients_user_id_access_profiles", "law_clients", type_="foreignkey")
    op.drop_index("ix_law_clients_user_id", table_name="law_clients")
    op.drop_column("law_clients", "user_id")
