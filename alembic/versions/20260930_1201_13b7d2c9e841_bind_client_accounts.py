"""Bind client records to their portal accounts."""

from alembic import op
import sqlalchemy as sa


revision = "13b7d2c9e841"
down_revision = "7f31a20b6841"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("law_clients")}
    if "user_id" not in columns:
        op.add_column("law_clients", sa.Column("user_id", sa.Integer(), nullable=True))

    indexes = {index["name"] for index in inspector.get_indexes("law_clients")}
    if "ix_law_clients_user_id" not in indexes:
        op.create_index("ix_law_clients_user_id", "law_clients", ["user_id"])

    foreign_keys = {fk.get("name") for fk in inspector.get_foreign_keys("law_clients")}
    if "fk_law_clients_user_id_access_profiles" not in foreign_keys:
        if bind.dialect.name == "sqlite":
            with op.batch_alter_table("law_clients") as batch_op:
                batch_op.create_foreign_key(
                    "fk_law_clients_user_id_access_profiles",
                    "access_profiles",
                    ["user_id"],
                    ["id"],
                    ondelete="SET NULL",
                )
        else:
            op.create_foreign_key(
                "fk_law_clients_user_id_access_profiles",
                "law_clients",
                "access_profiles",
                ["user_id"],
                ["id"],
                ondelete="SET NULL",
            )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    foreign_keys = {fk.get("name") for fk in inspector.get_foreign_keys("law_clients")}
    if "fk_law_clients_user_id_access_profiles" in foreign_keys:
        if bind.dialect.name == "sqlite":
            with op.batch_alter_table("law_clients") as batch_op:
                batch_op.drop_constraint("fk_law_clients_user_id_access_profiles", type_="foreignkey")
        else:
            op.drop_constraint("fk_law_clients_user_id_access_profiles", "law_clients", type_="foreignkey")
    indexes = {index["name"] for index in inspector.get_indexes("law_clients")}
    if "ix_law_clients_user_id" in indexes:
        op.drop_index("ix_law_clients_user_id", table_name="law_clients")
    columns = {column["name"] for column in inspector.get_columns("law_clients")}
    if "user_id" in columns:
        op.drop_column("law_clients", "user_id")
