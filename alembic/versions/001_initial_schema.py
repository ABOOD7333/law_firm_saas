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

revision: str = '001_initial'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # نستخدم checkfirst=True لتجنب الخطأ إذا كانت الجداول موجودة
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = inspector.get_table_names()

    if 'law_offices' not in existing_tables:
        op.create_table('law_offices',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('name', sa.Text(), nullable=False),
            sa.Column('owner_user_id', sa.Integer(), nullable=True),
            sa.Column('status_key', sa.Text(), nullable=False, server_default='active'),
            sa.Column('is_active', sa.Integer(), nullable=False, server_default='1'),
            sa.Column('is_deleted', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('created_at', sa.Text(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
            sa.PrimaryKeyConstraint('id'),
            sa.CheckConstraint('is_active IN (0, 1)'),
            sa.CheckConstraint('is_deleted IN (0, 1)'),
        )

    if 'access_profiles' not in existing_tables:
        op.create_table('access_profiles',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('name', sa.Text(), nullable=False),
            sa.Column('phone', sa.Text(), nullable=False),
            sa.Column('email', sa.Text(), nullable=False),
            sa.Column('email_verified', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('reset_verified', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('state', sa.Text(), nullable=False, server_default='draft'),
            sa.Column('protection_type', sa.Text(), nullable=False, server_default='ربط الجهاز الحالي'),
            sa.Column('preferred_theme', sa.Text(), nullable=False, server_default='light'),
            sa.Column('role', sa.Text(), nullable=False, server_default='محامٍ'),
            sa.Column('failed_attempts', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('created_at', sa.Text(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
            sa.Column('is_active', sa.Integer(), nullable=False, server_default='1'),
            sa.Column('can_view_all_cases', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('age', sa.Integer(), nullable=True),
            sa.Column('birth_date', sa.Text(), nullable=True),
            sa.Column('device_fingerprint', sa.Text(), nullable=True),
            sa.Column('device_name', sa.Text(), nullable=True),
            sa.Column('security_question', sa.Text(), nullable=True),
            sa.Column('last_login_at', sa.Text(), nullable=True),
            sa.Column('last_login_device', sa.Text(), nullable=True),
            sa.Column('access_pin_hash', sa.Text(), nullable=True),
            sa.Column('office_id', sa.Integer(), sa.ForeignKey('law_offices.id'), nullable=True),
            sa.Column('role_id', sa.Integer(), nullable=True),
            sa.Column('created_by', sa.Integer(), sa.ForeignKey('access_profiles.id'), nullable=True),
            sa.Column('linked_owner_id', sa.Integer(), nullable=True),
            sa.Column('job_title', sa.Text(), nullable=True),
            sa.Column('username', sa.Text(), nullable=True),
            sa.Column('lawyer_name', sa.Text(), nullable=True),
            sa.Column('case_number', sa.Text(), nullable=True),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('phone'),
            sa.UniqueConstraint('email'),
        )

    # نتوقف هنا — باقي الجداول في migrations لاحقة أو تُنشأ بـ create_all
    # للبيئات الجديدة استخدم: python -c "from database.database import init_db; init_db()"


def downgrade() -> None:
    # لا نحذف في baseline migration
    pass
