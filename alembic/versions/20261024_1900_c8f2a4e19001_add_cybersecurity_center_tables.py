"""add cybersecurity center tables

Revision ID: c8f2a4e19001
Revises: e5a2c4d8f102
Create Date: 2026-10-24 19:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'c8f2a4e19001'
down_revision: Union[str, None] = 'e5a2c4d8f102'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    # 1. security_scans
    if 'security_scans' not in existing_tables:
        op.create_table(
            'security_scans',
            sa.Column('id', sa.Integer(), nullable=False, primary_key=True),
            sa.Column('scan_type', sa.Text(), nullable=False),
            sa.Column('scan_scope', sa.Text(), nullable=False),
            sa.Column('status', sa.Text(), server_default=sa.text("'running'"), nullable=False),
            sa.Column('started_at', sa.Text(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
            sa.Column('completed_at', sa.Text(), nullable=True),
            sa.Column('files_scanned', sa.Integer(), server_default=sa.text('0'), nullable=False),
            sa.Column('components_scanned', sa.Integer(), server_default=sa.text('0'), nullable=False),
            sa.Column('findings_count', sa.Integer(), server_default=sa.text('0'), nullable=False),
            sa.Column('critical_count', sa.Integer(), server_default=sa.text('0'), nullable=False),
            sa.Column('high_count', sa.Integer(), server_default=sa.text('0'), nullable=False),
            sa.Column('medium_count', sa.Integer(), server_default=sa.text('0'), nullable=False),
            sa.Column('low_count', sa.Integer(), server_default=sa.text('0'), nullable=False),
            sa.Column('info_count', sa.Integer(), server_default=sa.text('0'), nullable=False),
            sa.Column('error_summary', sa.Text(), nullable=True),
            sa.Column('scanner_version', sa.Text(), server_default=sa.text("'LawSaaS-SecEngine-v1.0'"), nullable=False),
            sa.Column('triggered_by_user_id', sa.Integer(), nullable=True),
            sa.ForeignKeyConstraint(['triggered_by_user_id'], ['access_profiles.id'], ondelete='SET NULL'),
        )
        op.create_index('ix_security_scans_scan_type', 'security_scans', ['scan_type'])
        op.create_index('ix_security_scans_status', 'security_scans', ['status'])
        op.create_index('ix_security_scans_started_at', 'security_scans', ['started_at'])

    # 2. security_findings
    if 'security_findings' not in existing_tables:
        op.create_table(
            'security_findings',
            sa.Column('id', sa.Integer(), nullable=False, primary_key=True),
            sa.Column('scan_id', sa.Integer(), nullable=False),
            sa.Column('title', sa.Text(), nullable=False),
            sa.Column('description', sa.Text(), nullable=False),
            sa.Column('severity', sa.Text(), nullable=False),
            sa.Column('confidence', sa.Text(), server_default=sa.text("'confirmed'"), nullable=False),
            sa.Column('category', sa.Text(), nullable=False),
            sa.Column('affected_component', sa.Text(), nullable=False),
            sa.Column('affected_file', sa.Text(), nullable=True),
            sa.Column('affected_line', sa.Integer(), nullable=True),
            sa.Column('vulnerability_id', sa.Text(), nullable=True),
            sa.Column('evidence_summary', sa.Text(), nullable=True),
            sa.Column('remediation_recommendation', sa.Text(), nullable=True),
            sa.Column('first_detected_at', sa.Text(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
            sa.Column('last_detected_at', sa.Text(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
            sa.Column('status', sa.Text(), server_default=sa.text("'open'"), nullable=False),
            sa.Column('resolved_at', sa.Text(), nullable=True),
            sa.Column('verified_at', sa.Text(), nullable=True),
            sa.Column('resolution_notes', sa.Text(), nullable=True),
            sa.ForeignKeyConstraint(['scan_id'], ['security_scans.id'], ondelete='CASCADE'),
        )
        op.create_index('ix_security_findings_scan_id', 'security_findings', ['scan_id'])
        op.create_index('ix_security_findings_severity', 'security_findings', ['severity'])
        op.create_index('ix_security_findings_category', 'security_findings', ['category'])
        op.create_index('ix_security_findings_status', 'security_findings', ['status'])
        op.create_index('ix_security_findings_affected_file', 'security_findings', ['affected_file'])
        op.create_index('ix_security_findings_vulnerability_id', 'security_findings', ['vulnerability_id'])

    # 3. security_events
    if 'security_events' not in existing_tables:
        op.create_table(
            'security_events',
            sa.Column('id', sa.Integer(), nullable=False, primary_key=True),
            sa.Column('event_type', sa.Text(), nullable=False),
            sa.Column('severity', sa.Text(), nullable=False),
            sa.Column('source_ip', sa.Text(), nullable=True),
            sa.Column('user_agent', sa.Text(), nullable=True),
            sa.Column('endpoint', sa.Text(), nullable=True),
            sa.Column('http_method', sa.Text(), nullable=True),
            sa.Column('status_code', sa.Integer(), nullable=True),
            sa.Column('actor_user_id', sa.Integer(), nullable=True),
            sa.Column('target_office_id', sa.Integer(), nullable=True),
            sa.Column('details', sa.Text(), nullable=True),
            sa.Column('created_at', sa.Text(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
            sa.ForeignKeyConstraint(['actor_user_id'], ['access_profiles.id'], ondelete='SET NULL'),
            sa.ForeignKeyConstraint(['target_office_id'], ['law_offices.id'], ondelete='SET NULL'),
        )
        op.create_index('ix_security_events_event_type', 'security_events', ['event_type'])
        op.create_index('ix_security_events_severity', 'security_events', ['severity'])
        op.create_index('ix_security_events_source_ip', 'security_events', ['source_ip'])
        op.create_index('ix_security_events_endpoint', 'security_events', ['endpoint'])
        op.create_index('ix_security_events_created_at', 'security_events', ['created_at'])

    # 4. security_alerts
    if 'security_alerts' not in existing_tables:
        op.create_table(
            'security_alerts',
            sa.Column('id', sa.Integer(), nullable=False, primary_key=True),
            sa.Column('alert_title', sa.Text(), nullable=False),
            sa.Column('alert_message', sa.Text(), nullable=False),
            sa.Column('severity', sa.Text(), nullable=False),
            sa.Column('channel', sa.Text(), server_default=sa.text("'dashboard_and_email'"), nullable=False),
            sa.Column('finding_id', sa.Integer(), nullable=True),
            sa.Column('event_id', sa.Integer(), nullable=True),
            sa.Column('is_read', sa.Integer(), server_default=sa.text('0'), nullable=False),
            sa.Column('email_sent', sa.Integer(), server_default=sa.text('0'), nullable=False),
            sa.Column('email_sent_at', sa.Text(), nullable=True),
            sa.Column('email_error', sa.Text(), nullable=True),
            sa.Column('dedup_fingerprint', sa.Text(), nullable=False),
            sa.Column('created_at', sa.Text(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
            sa.ForeignKeyConstraint(['finding_id'], ['security_findings.id'], ondelete='SET NULL'),
            sa.ForeignKeyConstraint(['event_id'], ['security_events.id'], ondelete='SET NULL'),
        )
        op.create_index('ix_security_alerts_severity', 'security_alerts', ['severity'])
        op.create_index('ix_security_alerts_is_read', 'security_alerts', ['is_read'])
        op.create_index('ix_security_alerts_dedup_fingerprint', 'security_alerts', ['dedup_fingerprint'])
        op.create_index('ix_security_alerts_created_at', 'security_alerts', ['created_at'])

    # 5. security_dependencies
    if 'security_dependencies' not in existing_tables:
        op.create_table(
            'security_dependencies',
            sa.Column('id', sa.Integer(), nullable=False, primary_key=True),
            sa.Column('package_name', sa.Text(), nullable=False),
            sa.Column('installed_version', sa.Text(), nullable=True),
            sa.Column('manifest_version', sa.Text(), nullable=True),
            sa.Column('ecosystem', sa.Text(), server_default=sa.text("'PyPI'"), nullable=False),
            sa.Column('vulnerability_id', sa.Text(), nullable=True),
            sa.Column('severity', sa.Text(), server_default=sa.text("'none'"), nullable=False),
            sa.Column('fixed_version', sa.Text(), nullable=True),
            sa.Column('affected_version_range', sa.Text(), nullable=True),
            sa.Column('detected_at', sa.Text(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
            sa.Column('verification_status', sa.Text(), server_default=sa.text("'clean'"), nullable=False),
            sa.Column('advisory_url', sa.Text(), nullable=True),
        )
        op.create_index('ix_security_dependencies_package_name', 'security_dependencies', ['package_name'])
        op.create_index('ix_security_dependencies_vulnerability_id', 'security_dependencies', ['vulnerability_id'])

    # 6. security_audit_logs
    if 'security_audit_logs' not in existing_tables:
        op.create_table(
            'security_audit_logs',
            sa.Column('id', sa.Integer(), nullable=False, primary_key=True),
            sa.Column('actor_user_id', sa.Integer(), nullable=True),
            sa.Column('action', sa.Text(), nullable=False),
            sa.Column('target_type', sa.Text(), nullable=True),
            sa.Column('target_id', sa.Text(), nullable=True),
            sa.Column('details', sa.Text(), nullable=True),
            sa.Column('ip_address', sa.Text(), nullable=True),
            sa.Column('created_at', sa.Text(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
            sa.ForeignKeyConstraint(['actor_user_id'], ['access_profiles.id'], ondelete='SET NULL'),
        )
        op.create_index('ix_security_audit_logs_action', 'security_audit_logs', ['action'])
        op.create_index('ix_security_audit_logs_created_at', 'security_audit_logs', ['created_at'])

    # 7. security_scan_schedules
    if 'security_scan_schedules' not in existing_tables:
        op.create_table(
            'security_scan_schedules',
            sa.Column('id', sa.Integer(), nullable=False, primary_key=True),
            sa.Column('scan_type', sa.Text(), nullable=False),
            sa.Column('frequency', sa.Text(), server_default=sa.text("'daily'"), nullable=False),
            sa.Column('is_enabled', sa.Integer(), server_default=sa.text('1'), nullable=False),
            sa.Column('last_run_at', sa.Text(), nullable=True),
            sa.Column('next_run_at', sa.Text(), nullable=True),
            sa.Column('created_at', sa.Text(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
            sa.Column('updated_at', sa.Text(), nullable=True),
        )

    # 8. security_alert_settings
    if 'security_alert_settings' not in existing_tables:
        op.create_table(
            'security_alert_settings',
            sa.Column('id', sa.Integer(), nullable=False, primary_key=True),
            sa.Column('admin_email', sa.Text(), server_default=sa.text("''"), nullable=False),
            sa.Column('email_alerts_enabled', sa.Integer(), server_default=sa.text('1'), nullable=False),
            sa.Column('min_email_severity', sa.Text(), server_default=sa.text("'high'"), nullable=False),
            sa.Column('dedup_cooldown_minutes', sa.Integer(), server_default=sa.text('120'), nullable=False),
            sa.Column('max_alerts_per_hour', sa.Integer(), server_default=sa.text('10'), nullable=False),
            sa.Column('notify_on_failed_logins', sa.Integer(), server_default=sa.text('1'), nullable=False),
            sa.Column('notify_on_new_critical_vulnerability', sa.Integer(), server_default=sa.text('1'), nullable=False),
            sa.Column('updated_at', sa.Text(), nullable=True),
        )

    # 9. security_scan_targets
    if 'security_scan_targets' not in existing_tables:
        op.create_table(
            'security_scan_targets',
            sa.Column('id', sa.Integer(), nullable=False, primary_key=True),
            sa.Column('target_type', sa.Text(), nullable=False),
            sa.Column('target_path', sa.Text(), nullable=False),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('is_excluded', sa.Integer(), server_default=sa.text('0'), nullable=False),
            sa.Column('last_scanned_at', sa.Text(), nullable=True),
            sa.Column('scan_status', sa.Text(), server_default=sa.text("'pending'"), nullable=False),
            sa.Column('skip_reason', sa.Text(), nullable=True),
        )
        op.create_index('ix_security_scan_targets_target_path', 'security_scan_targets', ['target_path'])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    for t in [
        'security_scan_targets',
        'security_alert_settings',
        'security_scan_schedules',
        'security_audit_logs',
        'security_dependencies',
        'security_alerts',
        'security_events',
        'security_findings',
        'security_scans',
    ]:
        if t in existing_tables:
            op.drop_table(t)
