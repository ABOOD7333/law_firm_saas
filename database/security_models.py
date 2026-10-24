"""
Cybersecurity Operations Center — Database Models (LawSaaS Platform)
نماذج قاعدة بيانات مركز الأمن السيبراني المتكامل لمنصة LawSaaS.

جميع الجداول التسعة مبنية لدعم PostgreSQL للإنتاج و SQLite للتطوير المحلي،
مع فهارس دقيقة وعلاقات آمنة لحماية المنصة.
"""

from typing import Optional
from sqlalchemy import (
    Column,
    ForeignKey,
    Index,
    Integer,
    Text,
    DateTime,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database.models import Base


# 1. security_scans — لتسجيل عمليات الفحص الأمني
class SecurityScans(Base):
    __tablename__ = "security_scans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    scan_type: Mapped[str] = mapped_column(Text, nullable=False, index=True)  # sast_code, sca_dependencies, config_headers, db_integrity, full_audit
    scan_scope: Mapped[str] = mapped_column(Text, nullable=False)            # e.g. all_files, routers/, dependencies, database
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'running'"), index=True)  # running, completed, failed, cancelled
    
    started_at: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("CURRENT_TIMESTAMP"), index=True)
    completed_at: Mapped[Optional[str]] = mapped_column(Text)
    
    files_scanned: Mapped[int] = mapped_column(Integer, server_default=text("0"), nullable=False)
    components_scanned: Mapped[int] = mapped_column(Integer, server_default=text("0"), nullable=False)
    findings_count: Mapped[int] = mapped_column(Integer, server_default=text("0"), nullable=False)
    
    critical_count: Mapped[int] = mapped_column(Integer, server_default=text("0"), nullable=False)
    high_count: Mapped[int] = mapped_column(Integer, server_default=text("0"), nullable=False)
    medium_count: Mapped[int] = mapped_column(Integer, server_default=text("0"), nullable=False)
    low_count: Mapped[int] = mapped_column(Integer, server_default=text("0"), nullable=False)
    info_count: Mapped[int] = mapped_column(Integer, server_default=text("0"), nullable=False)
    
    error_summary: Mapped[Optional[str]] = mapped_column(Text)
    scanner_version: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'LawSaaS-SecEngine-v1.0'"))
    triggered_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("access_profiles.id", ondelete="SET NULL"), nullable=True)

    # Relationships
    findings: Mapped[list["SecurityFindings"]] = relationship("SecurityFindings", back_populates="scan", cascade="all, delete-orphan")


# 2. security_findings — لتسجيل الثغرات والمشكلات الأمنية المكتشفة
class SecurityFindings(Base):
    __tablename__ = "security_findings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    scan_id: Mapped[int] = mapped_column(ForeignKey("security_scans.id", ondelete="CASCADE"), nullable=False, index=True)
    
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(Text, nullable=False, index=True)      # critical, high, medium, low, info
    confidence: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'confirmed'"))  # confirmed, suspicious, informational
    category: Mapped[str] = mapped_column(Text, nullable=False, index=True)      # injection, auth_bypass, tenant_isolation, secrets_exposure, xss, ssrf, misconfig, outdated_dep, data_integrity
    
    affected_component: Mapped[str] = mapped_column(Text, nullable=False)        # Component/Module name
    affected_file: Mapped[Optional[str]] = mapped_column(Text, index=True)       # Relative path
    affected_line: Mapped[Optional[int]] = mapped_column(Integer)
    
    vulnerability_id: Mapped[Optional[str]] = mapped_column(Text, index=True)   # CWE, CVE, or Rule ID
    evidence_summary: Mapped[Optional[str]] = mapped_column(Text)                # Sanitized evidence snippet (no user/client secrets)
    remediation_recommendation: Mapped[Optional[str]] = mapped_column(Text)
    
    first_detected_at: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    last_detected_at: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'open'"), index=True)  # open, in_progress, resolved, false_positive, ignored
    resolved_at: Mapped[Optional[str]] = mapped_column(Text)
    verified_at: Mapped[Optional[str]] = mapped_column(Text)
    resolution_notes: Mapped[Optional[str]] = mapped_column(Text)

    # Relationships
    scan: Mapped["SecurityScans"] = relationship("SecurityScans", back_populates="findings")
    alerts: Mapped[list["SecurityAlerts"]] = relationship("SecurityAlerts", back_populates="finding")


# 3. security_events — لتسجيل الأحداث الأمنية التشغيلية أثناء استخدام المنصة
class SecurityEvents(Base):
    __tablename__ = "security_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_type: Mapped[str] = mapped_column(Text, nullable=False, index=True)    # failed_login, brute_force_suspect, unauthorized_access, privilege_escalation_attempt, suspicious_api_request, path_traversal_attempt, injection_attempt, file_policy_violation, sensitive_admin_change, security_exception
    severity: Mapped[str] = mapped_column(Text, nullable=False, index=True)      # critical, high, medium, low, info
    
    source_ip: Mapped[Optional[str]] = mapped_column(Text, index=True)
    user_agent: Mapped[Optional[str]] = mapped_column(Text)
    endpoint: Mapped[Optional[str]] = mapped_column(Text, index=True)
    http_method: Mapped[Optional[str]] = mapped_column(Text)
    status_code: Mapped[Optional[int]] = mapped_column(Integer)
    
    actor_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("access_profiles.id", ondelete="SET NULL"), nullable=True)
    target_office_id: Mapped[Optional[int]] = mapped_column(ForeignKey("law_offices.id", ondelete="SET NULL"), nullable=True)
    
    details: Mapped[Optional[str]] = mapped_column(Text)                         # Sanitized JSON or text metadata (NO passwords, NO session tokens)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("CURRENT_TIMESTAMP"), index=True)

    # Relationships
    alerts: Mapped[list["SecurityAlerts"]] = relationship("SecurityAlerts", back_populates="event")


# 4. security_alerts — لتسجيل التنبيهات الموجهة إلى مدير المنصة الرئيسي
class SecurityAlerts(Base):
    __tablename__ = "security_alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    alert_title: Mapped[str] = mapped_column(Text, nullable=False)
    alert_message: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(Text, nullable=False, index=True)      # critical, high, medium, low
    channel: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'dashboard_and_email'"))  # dashboard_and_email, dashboard_only, email_only
    
    finding_id: Mapped[Optional[int]] = mapped_column(ForeignKey("security_findings.id", ondelete="SET NULL"), nullable=True)
    event_id: Mapped[Optional[int]] = mapped_column(ForeignKey("security_events.id", ondelete="SET NULL"), nullable=True)
    
    is_read: Mapped[int] = mapped_column(Integer, server_default=text("0"), nullable=False, index=True)  # 0: unread, 1: read
    email_sent: Mapped[int] = mapped_column(Integer, server_default=text("0"), nullable=False)          # 0: not sent, 1: sent, -1: failed
    email_sent_at: Mapped[Optional[str]] = mapped_column(Text)
    email_error: Mapped[Optional[str]] = mapped_column(Text)
    
    dedup_fingerprint: Mapped[str] = mapped_column(Text, nullable=False, index=True)  # Hash to prevent duplicate email spamming
    created_at: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("CURRENT_TIMESTAMP"), index=True)

    # Relationships
    finding: Mapped[Optional["SecurityFindings"]] = relationship("SecurityFindings", back_populates="alerts")
    event: Mapped[Optional["SecurityEvents"]] = relationship("SecurityEvents", back_populates="alerts")


# 5. security_dependencies — لتسجيل فحص المكتبات والاعتماديات
class SecurityDependencies(Base):
    __tablename__ = "security_dependencies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    package_name: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    installed_version: Mapped[Optional[str]] = mapped_column(Text)
    manifest_version: Mapped[Optional[str]] = mapped_column(Text)
    ecosystem: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'PyPI'"))
    
    vulnerability_id: Mapped[Optional[str]] = mapped_column(Text, index=True)   # CVE or GHSA
    severity: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'none'"))  # critical, high, medium, low, none
    fixed_version: Mapped[Optional[str]] = mapped_column(Text)
    affected_version_range: Mapped[Optional[str]] = mapped_column(Text)
    
    detected_at: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    verification_status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'clean'"))  # verified_vulnerable, clean, unverified, ignored
    advisory_url: Mapped[Optional[str]] = mapped_column(Text)


# 6. security_audit_logs — لتسجيل عمليات مدير المنصة داخل مركز الأمن
class SecurityAuditLogs(Base):
    __tablename__ = "security_audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    actor_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("access_profiles.id", ondelete="SET NULL"), nullable=True)
    
    action: Mapped[str] = mapped_column(Text, nullable=False, index=True)        # start_scan, view_finding, update_finding_status, change_alert_settings, schedule_scan, retest_finding
    target_type: Mapped[Optional[str]] = mapped_column(Text)
    target_id: Mapped[Optional[str]] = mapped_column(Text)
    details: Mapped[Optional[str]] = mapped_column(Text)                         # JSON or audit description
    ip_address: Mapped[Optional[str]] = mapped_column(Text)
    
    created_at: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("CURRENT_TIMESTAMP"), index=True)


# 7. security_scan_schedules — لإدارة جدولة الفحوص الدورية
class SecurityScanSchedules(Base):
    __tablename__ = "security_scan_schedules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    scan_type: Mapped[str] = mapped_column(Text, nullable=False)                 # full_audit, sast_code, sca_dependencies, config_headers, db_integrity
    frequency: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'daily'"))  # daily, weekly, monthly, manual_only
    is_enabled: Mapped[int] = mapped_column(Integer, server_default=text("1"), nullable=False)
    
    last_run_at: Mapped[Optional[str]] = mapped_column(Text)
    next_run_at: Mapped[Optional[str]] = mapped_column(Text)
    
    created_at: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    updated_at: Mapped[Optional[str]] = mapped_column(Text)


# 8. security_alert_settings — لحفظ إعدادات التنبيهات وحدود المخاطر
class SecurityAlertSettings(Base):
    __tablename__ = "security_alert_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    admin_email: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("''"))
    email_alerts_enabled: Mapped[int] = mapped_column(Integer, server_default=text("1"), nullable=False)
    min_email_severity: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'high'"))  # critical, high, medium, low
    
    dedup_cooldown_minutes: Mapped[int] = mapped_column(Integer, server_default=text("120"), nullable=False)
    max_alerts_per_hour: Mapped[int] = mapped_column(Integer, server_default=text("10"), nullable=False)
    notify_on_failed_logins: Mapped[int] = mapped_column(Integer, server_default=text("1"), nullable=False)
    notify_on_new_critical_vulnerability: Mapped[int] = mapped_column(Integer, server_default=text("1"), nullable=False)
    
    updated_at: Mapped[Optional[str]] = mapped_column(Text)


# 9. security_scan_targets — لتحديد الملفات والمكونات التي يغطيها الفحص
class SecurityScanTargets(Base):
    __tablename__ = "security_scan_targets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    target_type: Mapped[str] = mapped_column(Text, nullable=False)               # file, directory, database_table, config, route_group
    target_path: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text)
    is_excluded: Mapped[int] = mapped_column(Integer, server_default=text("0"), nullable=False)
    
    last_scanned_at: Mapped[Optional[str]] = mapped_column(Text)
    scan_status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'pending'"))  # scanned, skipped, failed, pending
    skip_reason: Mapped[Optional[str]] = mapped_column(Text)
