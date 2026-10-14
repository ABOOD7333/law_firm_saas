"""Add law_incoming_cases table for reception interface.

Revision ID: e5a2c4d8f102
Revises: 13b7d2c9e841
Create Date: 2026-10-14 18:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = 'e5a2c4d8f102'
down_revision = '13b7d2c9e841'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = inspector.get_table_names()

    if 'law_incoming_cases' not in tables:
        op.create_table(
            'law_incoming_cases',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('office_id', sa.Integer(), sa.ForeignKey('law_offices.id', ondelete='CASCADE'), nullable=False),
            sa.Column('section_key', sa.Text(), nullable=False),
            sa.Column('internal_number', sa.Text(), nullable=False),
            sa.Column('client_id', sa.Integer(), sa.ForeignKey('law_clients.id', ondelete='SET NULL'), nullable=True),
            sa.Column('client_name', sa.Text(), nullable=True),
            sa.Column('case_id', sa.Integer(), sa.ForeignKey('law_cases.id', ondelete='SET NULL'), nullable=True),
            sa.Column('reception_date', sa.Text(), nullable=False),
            sa.Column('status_key', sa.Text(), nullable=False, server_default='under_review'),
            sa.Column('subject_description', sa.Text(), nullable=True),
            sa.Column('notes', sa.Text(), nullable=True),
            sa.Column('created_by_user_id', sa.Integer(), sa.ForeignKey('access_profiles.id', ondelete='SET NULL'), nullable=True),
            sa.Column('assigned_lawyer_id', sa.Integer(), sa.ForeignKey('access_profiles.id', ondelete='SET NULL'), nullable=True),
            sa.Column('police_station', sa.Text(), nullable=True),
            sa.Column('police_report_number', sa.Text(), nullable=True),
            sa.Column('document_date', sa.Text(), nullable=True),
            sa.Column('police_referral_status', sa.Text(), nullable=True),
            sa.Column('prosecution_name', sa.Text(), nullable=True),
            sa.Column('prosecution_file_number', sa.Text(), nullable=True),
            sa.Column('prosecution_decision_date', sa.Text(), nullable=True),
            sa.Column('court_name', sa.Text(), nullable=True),
            sa.Column('court_case_number', sa.Text(), nullable=True),
            sa.Column('case_year', sa.Text(), nullable=True),
            sa.Column('judicial_document_type', sa.Text(), nullable=True),
            sa.Column('client_capacity', sa.Text(), nullable=True),
            sa.Column('appeal_court_name', sa.Text(), nullable=True),
            sa.Column('appeal_case_number', sa.Text(), nullable=True),
            sa.Column('appeal_year', sa.Text(), nullable=True),
            sa.Column('primary_case_number', sa.Text(), nullable=True),
            sa.Column('primary_judgment_date', sa.Text(), nullable=True),
            sa.Column('enforcement_authority', sa.Text(), nullable=True),
            sa.Column('enforcement_file_number', sa.Text(), nullable=True),
            sa.Column('enforcement_document_type', sa.Text(), nullable=True),
            sa.Column('enforcement_parties', sa.Text(), nullable=True),
            sa.Column('enforcement_document_date', sa.Text(), nullable=True),
            sa.Column('attachments_json', sa.Text(), nullable=True),
            sa.Column('is_cancelled', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('cancellation_reason', sa.Text(), nullable=True),
            sa.Column('is_deleted', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('created_at', sa.Text(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
            sa.Column('updated_at', sa.Text(), nullable=True),
        )
        op.create_index('ix_law_incoming_cases_office_id', 'law_incoming_cases', ['office_id'])
        op.create_index('ix_law_incoming_cases_section_key', 'law_incoming_cases', ['section_key'])
        op.create_index('ix_law_incoming_cases_internal_number', 'law_incoming_cases', ['internal_number'])
        op.create_index('ix_law_incoming_cases_client_id', 'law_incoming_cases', ['client_id'])
        op.create_index('ix_law_incoming_cases_case_id', 'law_incoming_cases', ['case_id'])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if 'law_incoming_cases' in inspector.get_table_names():
        op.drop_table('law_incoming_cases')
