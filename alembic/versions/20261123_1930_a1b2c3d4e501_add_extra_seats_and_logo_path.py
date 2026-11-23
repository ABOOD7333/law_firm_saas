"""add extra_seats and logo_path to law_offices

Revision ID: a1b2c3d4e501
Revises: c8f2a4e19001
Create Date: 2026-11-23 19:30:00.000000

الهدف:
  - إضافة حقل extra_seats لتسجيل المقعد الإضافي (0 أو 1 كحد أقصى) لكل مكتب.
  - إضافة حقل logo_path لتخزين مسار شعار المكتب الرسمي المرفوع.
  كلا الحقلين جزء من نظام باقات الاشتراكات (Single Extra Seat Add-on Rule).
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers
revision = 'a1b2c3d4e501'
down_revision = 'c8f2a4e19001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # إضافة عمود extra_seats: عدد صحيح، افتراضي 0، لا يقبل NULL
    with op.batch_alter_table('law_offices', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                'extra_seats',
                sa.Integer(),
                nullable=False,
                server_default=sa.text('0'),
                comment='مقعد إضافي: 0 = لا يوجد، 1 = تم شراء مقعد إضافي (الحد الأقصى 1)'
            )
        )
        batch_op.add_column(
            sa.Column(
                'logo_path',
                sa.Text(),
                nullable=True,
                comment='مسار ملف شعار المكتب المرفوع على الخادم'
            )
        )


def downgrade() -> None:
    with op.batch_alter_table('law_offices', schema=None) as batch_op:
        batch_op.drop_column('logo_path')
        batch_op.drop_column('extra_seats')
