"""Add mobile device and soft-delete support to older database schemas.

Revision ID: 68f108684a94
Revises: 001_initial
Create Date: 2026-05-30 22:01:27.230191+00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from database.models import Base


revision: str = "68f108684a94"
down_revision: Union[str, None] = "001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_COLUMN_DEFINITIONS = {
    "access_profiles": {
        "updated_at": sa.Text(),
        "is_deleted": sa.Integer(),
        "is_2fa_enabled": sa.Integer(),
    },
    "auth_sessions": {"refresh_token": sa.Text()},
    "law_clients": {"updated_at": sa.Text(), "is_deleted": sa.Integer()},
    "law_correspondences": {"updated_at": sa.Text(), "is_deleted": sa.Integer()},
    "law_documents": {"updated_at": sa.Text(), "is_deleted": sa.Integer()},
    "law_executions": {"updated_at": sa.Text(), "is_deleted": sa.Integer()},
    "law_expenses": {"updated_at": sa.Text(), "is_deleted": sa.Integer()},
    "law_hearings": {"updated_at": sa.Text(), "is_deleted": sa.Integer()},
    "law_judgments": {"updated_at": sa.Text(), "is_deleted": sa.Integer()},
    "law_legal_references": {"updated_at": sa.Text(), "is_deleted": sa.Integer()},
    "law_limitations": {"updated_at": sa.Text(), "is_deleted": sa.Integer()},
    "law_notes": {"updated_at": sa.Text(), "is_deleted": sa.Integer()},
    "law_offices": {
        "subscription_plan": sa.Text(),
    },
    "law_parties": {"updated_at": sa.Text(), "is_deleted": sa.Integer()},
    "law_pleadings": {"updated_at": sa.Text(), "is_deleted": sa.Integer()},
    "law_power_of_attorney": {"updated_at": sa.Text(), "is_deleted": sa.Integer()},
    "law_tasks": {"updated_at": sa.Text(), "is_deleted": sa.Integer()},
    "law_timesheets": {"updated_at": sa.Text(), "is_deleted": sa.Integer()},
    "law_transactions": {"updated_at": sa.Text(), "is_deleted": sa.Integer()},
}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # Supports both databases created by the old partial baseline and databases
    # that already received their schema from SQLAlchemy create_all().
    Base.metadata.create_all(bind=bind, checkfirst=True)
    inspector = sa.inspect(bind)

    for table_name, definitions in _COLUMN_DEFINITIONS.items():
        present = {column["name"] for column in inspector.get_columns(table_name)}
        for column_name, column_type in definitions.items():
            if column_name in present:
                continue
            kwargs = {"nullable": True}
            if column_name == "is_deleted":
                kwargs.update(nullable=False, server_default=sa.text("0"))
            elif column_name == "is_2fa_enabled":
                kwargs.update(nullable=False, server_default=sa.text("0"))
            elif column_name == "subscription_plan":
                kwargs.update(nullable=False, server_default=sa.text("'trial'"))
            op.add_column(table_name, sa.Column(column_name, column_type, **kwargs))
            present.add(column_name)

    indexes = {item["name"] for item in sa.inspect(bind).get_indexes("auth_sessions")}
    if "ix_auth_sessions_refresh_token" not in indexes:
        op.create_index(
            "ix_auth_sessions_refresh_token",
            "auth_sessions",
            ["refresh_token"],
            unique=True,
        )

    device_indexes = {item["name"] for item in sa.inspect(bind).get_indexes("law_user_devices")}
    if "ix_law_user_devices_device_id" not in device_indexes:
        op.create_index(
            "ix_law_user_devices_device_id",
            "law_user_devices",
            ["device_id"],
            unique=True,
        )


def downgrade() -> None:
    # This compatibility migration can encounter columns that existed before
    # it ran. A blanket downgrade could therefore delete user data/schema.
    # Keep it intentionally non-destructive; forward migrations are supported.
    pass
