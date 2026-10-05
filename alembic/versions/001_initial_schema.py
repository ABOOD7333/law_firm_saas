"""initial_schema

Revision ID: 001_initial
Revises: 
Create Date: 2026-05-07 00:00:00.000000

هذا الـ migration الأول يمثل الحالة الحالية للقاعدة (baseline).
لأن الجداول موجودة بالفعل في law_firm.db، هذا الملف يتحقق فقط
ولا يعيد إنشاء الجداول.
للبيئات الجديدة (PostgreSQL)، سيُنشئ كل الجداول من الصفر.
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from database.models import Base

revision: str = '001_initial'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create missing tables from the complete current model metadata. Existing
    # tables are left intact; later revisions add columns to legacy schemas.
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind, checkfirst=True)


def downgrade() -> None:
    # لا نحذف في baseline migration
    pass
