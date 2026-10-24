"""
Alert Service — LawSaaS Cybersecurity Operations Center
خدمة إدارة وإرسال التنبيهات الأمنية لمدير المنصة الرئيسي مع كبح التكرار (Alert Throttling).
"""

import hashlib
import os
from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy.orm import Session
from database.security_models import SecurityAlerts, SecurityAlertSettings
import email_service


def compute_dedup_fingerprint(severity: str, category_or_type: str, target: str) -> str:
    """توليد بصمة رقمية فريدة لمنع تكرار إرسال التنبيه لنفس المشكلة"""
    raw = f"{severity.strip().lower()}:{category_or_type.strip().lower()}:{target.strip().lower()}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def get_or_create_alert_settings(db: Session, admin_fallback_email: str = "") -> SecurityAlertSettings:
    """جلب إعدادات التنبيه أو إنشاء الإعدادات الافتراضية"""
    settings = db.query(SecurityAlertSettings).first()
    if not settings:
        fallback = admin_fallback_email or os.getenv("SUPERADMIN_EMAIL", "") or os.getenv("SMTP_USERNAME", "")
        settings = SecurityAlertSettings(
            admin_email=fallback,
            email_alerts_enabled=1,
            min_email_severity="high",
            dedup_cooldown_minutes=120,
            max_alerts_per_hour=10,
            notify_on_failed_logins=1,
            notify_on_new_critical_vulnerability=1,
            updated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        )
        db.add(settings)
        db.commit()
        db.refresh(settings)
    return settings


def dispatch_security_alert(
    db: Session,
    title: str,
    message: str,
    severity: str,
    category_or_type: str,
    target_identifier: str,
    finding_id: Optional[int] = None,
    event_id: Optional[int] = None,
    admin_email: Optional[str] = None
) -> SecurityAlerts:
    """
    تسجيل التنبيه وإرساله بالبريد لمدير المنصة عند انطباق معايير الخطورة وكبح التكرار
    """
    fingerprint = compute_dedup_fingerprint(severity, category_or_type, target_identifier)
    settings = get_or_create_alert_settings(db, admin_email or "")

    now_dt = datetime.now()
    now_str = now_dt.strftime("%Y-%m-%d %H:%M:%S")

    # فحص كبح التكرار (Deduplication Check)
    cooldown_cutoff = (now_dt - timedelta(minutes=settings.dedup_cooldown_minutes)).strftime("%Y-%m-%d %H:%M:%S")
    recent_dup = (
        db.query(SecurityAlerts)
        .filter(
            SecurityAlerts.dedup_fingerprint == fingerprint,
            SecurityAlerts.created_at >= cooldown_cutoff
        )
        .first()
    )

    should_send_email = False
    if not recent_dup and settings.email_alerts_enabled == 1:
        # فحص مستوى الخطورة المطلوب للإرسال البريدي
        severity_rank = {"critical": 4, "high": 3, "medium": 2, "low": 1, "info": 0}
        min_rank = severity_rank.get(settings.min_email_severity.lower(), 3)
        current_rank = severity_rank.get(severity.lower(), 1)
        if current_rank >= min_rank:
            should_send_email = True

    # إنشاء سجل التنبيه
    alert = SecurityAlerts(
        alert_title=title,
        alert_message=message,
        severity=severity,
        channel="dashboard_and_email" if should_send_email else "dashboard_only",
        finding_id=finding_id,
        event_id=event_id,
        is_read=0,
        email_sent=0,
        dedup_fingerprint=fingerprint,
        created_at=now_str
    )
    db.add(alert)
    db.commit()
    db.refresh(alert)

    # إرسال البريد الإلكتروني في حال استيفاء الشروط
    if should_send_email:
        target_email = settings.admin_email or admin_email or os.getenv("SMTP_USERNAME")
        if target_email:
            try:
                subject = f"⚠️ [LawSaaS Security Alert] تنبيه أمني {severity.upper()}: {title}"
                html_body = f"""
                <div dir="rtl" style="font-family: Cairo, Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #e2e8f0; border-radius: 10px; background: #ffffff;">
                    <div style="background: {'#dc2626' if severity == 'critical' else '#ea580c' if severity == 'high' else '#2563eb'}; color: white; padding: 12px 20px; border-radius: 8px; text-align: center;">
                        <h2 style="margin: 0; font-size: 1.2rem;">مركز الأمن السيبراني — LawSaaS</h2>
                        <p style="margin: 4px 0 0; font-size: 0.9rem;">تنبيه أمني فوري: {severity.upper()}</p>
                    </div>
                    <div style="padding: 20px 10px;">
                        <h3 style="color: #0f172a; margin-top: 0;">{title}</h3>
                        <p style="color: #334155; line-height: 1.6; font-size: 0.95rem;">{message}</p>
                        <table style="width: 100%; border-collapse: collapse; margin-top: 15px; font-size: 0.9rem;">
                            <tr style="border-bottom: 1px solid #f1f5f9;">
                                <td style="padding: 8px; color: #64748b; font-weight: bold;">مستوى الخطورة:</td>
                                <td style="padding: 8px; font-weight: bold; color: {'#dc2626' if severity == 'critical' else '#ea580c'};">{severity.upper()}</td>
                            </tr>
                            <tr style="border-bottom: 1px solid #f1f5f9;">
                                <td style="padding: 8px; color: #64748b; font-weight: bold;">الهدف / المكون:</td>
                                <td style="padding: 8px; color: #0f172a;">{target_identifier}</td>
                            </tr>
                            <tr style="border-bottom: 1px solid #f1f5f9;">
                                <td style="padding: 8px; color: #64748b; font-weight: bold;">وقت الرصد:</td>
                                <td style="padding: 8px; color: #0f172a;">{now_str}</td>
                            </tr>
                        </table>
                        <div style="margin-top: 25px; text-align: center;">
                            <a href="/superadmin/security" style="background: #0f172a; color: white; padding: 10px 24px; border-radius: 6px; text-decoration: none; font-weight: bold; font-size: 0.9rem; display: inline-block;">
                                فتح مركز الأمن السيبراني
                            </a>
                        </div>
                    </div>
                    <div style="border-top: 1px solid #e2e8f0; padding-top: 12px; margin-top: 15px; font-size: 0.75rem; color: #94a3b8; text-align: center;">
                        تم إرسال هذا التنبيه الآلي المشفر حصرياً لمدير المنصة الرئيسي. لا يحتوي هذا البريد على كلمات مرور أو رموز سرية.
                    </div>
                </div>
                """
                # استخدام email_service الداخلي
                res = email_service.send_email_html(target_email, subject, html_body)
                if res.get("status") == "success":
                    alert.email_sent = 1
                    alert.email_sent_at = now_str
                else:
                    alert.email_sent = -1
                    alert.email_error = str(res.get("message", "Unknown email error"))[:500]
                db.commit()
            except Exception as e:
                alert.email_sent = -1
                alert.email_error = str(e)[:500]
                db.commit()

    return alert
