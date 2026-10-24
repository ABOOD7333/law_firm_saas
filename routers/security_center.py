"""
Cybersecurity Operations Center — API & Web Router
المسار البرمجي المخصص حصرياً لمدير المنصة الرئيسي (Superadmin).
يوفر لوحة التحكم المركزية، واجهات تشغيل الفحص، وإدارة الثغرات، ومراقبة الأحداث الحية، وضبط التنبيهات.
"""

from datetime import datetime
import json
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Request, status, Query, Form
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from sqlalchemy.orm import Session
from sqlalchemy import desc

from database.database import get_db
from database.models import AccessProfiles
from database.security_models import (
    SecurityScans,
    SecurityFindings,
    SecurityEvents,
    SecurityAlerts,
    SecurityDependencies,
    SecurityAuditLogs,
    SecurityScanTargets,
    SecurityAlertSettings,
)
from dependencies import get_current_user, templates
from core.security_center.scanner_engine import LawSaaSScanner
from core.security_center.alert_service import get_or_create_alert_settings
from core.security_center.remediation_engine import AutoRemediationEngine
from core.security_center.monitor_middleware import get_active_defense_status, unban_ip

router = APIRouter()


def require_superadmin(user: AccessProfiles = Depends(get_current_user)) -> AccessProfiles:
    """التحقق الصارم من أن المستخدم هو مدير المنصة الرئيسي حصراً"""
    if not user or getattr(user, "is_superadmin", 0) != 1:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="عذراً، هذا القسم مخصص حصرياً لمدير المنصة الرئيسي (Superadmin)."
        )
    return user


def log_admin_audit(
    db: Session,
    user_id: int,
    action: str,
    target_type: Optional[str] = None,
    target_id: Optional[str] = None,
    details: Optional[str] = None,
    ip_address: Optional[str] = None
):
    """توثيق عمليات مدير المنصة داخل مركز الأمن السيبراني"""
    log_entry = SecurityAuditLogs(
        actor_user_id=user_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        details=details,
        ip_address=ip_address,
        created_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    )
    db.add(log_entry)
    db.commit()


# =========================================================================
# 1. واجهة لوحة تحكم مركز الأمن السيبراني (HTML Dashboard)
# =========================================================================
@router.get("/superadmin/security", response_class=HTMLResponse)
async def security_center_dashboard(
    request: Request,
    db: Session = Depends(get_db),
    user: AccessProfiles = Depends(get_current_user)
):
    if not user or getattr(user, "is_superadmin", 0) != 1:
        return RedirectResponse(url="/dashboard", status_code=303)

    # جلب أحدث عملية فحص
    latest_scan = db.query(SecurityScans).order_by(SecurityScans.id.desc()).first()

    # جلب الإحصائيات العامة
    total_findings = db.query(SecurityFindings).filter(SecurityFindings.status == "open").count()
    critical_findings = db.query(SecurityFindings).filter(SecurityFindings.severity == "critical", SecurityFindings.status == "open").count()
    high_findings = db.query(SecurityFindings).filter(SecurityFindings.severity == "high", SecurityFindings.status == "open").count()
    medium_findings = db.query(SecurityFindings).filter(SecurityFindings.severity == "medium", SecurityFindings.status == "open").count()
    low_findings = db.query(SecurityFindings).filter(SecurityFindings.severity == "low", SecurityFindings.status == "open").count()

    # جلب إحصائيات الأحداث الأمنية في آخر 24 ساعة
    today_prefix = datetime.now().strftime("%Y-%m-%d")
    recent_events_count = db.query(SecurityEvents).filter(SecurityEvents.created_at.like(f"{today_prefix}%")).count()

    # أحدث 10 ثغرات مفتوحة
    findings = db.query(SecurityFindings).filter(SecurityFindings.status == "open").order_by(
        desc(SecurityFindings.severity == "critical"),
        desc(SecurityFindings.severity == "high"),
        SecurityFindings.id.desc()
    ).limit(15).all()

    # أحدث 10 أحداث أمنية
    recent_events = db.query(SecurityEvents).order_by(SecurityEvents.id.desc()).limit(10).all()

    # أحدث 10 تنبيهات
    recent_alerts = db.query(SecurityAlerts).order_by(SecurityAlerts.id.desc()).limit(10).all()

    # إعدادات التنبيه
    alert_settings = get_or_create_alert_settings(db, getattr(user, "email", ""))

    # توثيق فتح اللوحة
    log_admin_audit(
        db=db,
        user_id=user.id,
        action="view_security_dashboard",
        ip_address=request.client.host if request.client else None
    )

    return templates.TemplateResponse(
        "security_center.html",
        {
            "request": request,
            "user": user,
            "latest_scan": latest_scan,
            "total_findings": total_findings,
            "critical_findings": critical_findings,
            "high_findings": high_findings,
            "medium_findings": medium_findings,
            "low_findings": low_findings,
            "recent_events_count": recent_events_count,
            "findings": findings,
            "recent_events": recent_events,
            "recent_alerts": recent_alerts,
            "alert_settings": alert_settings
        }
    )


# =========================================================================
# 2. تشغيل واستعلام عمليات الفحص الأمني (Scans API)
# =========================================================================
@router.post("/api/superadmin/security/scan")
async def trigger_security_scan(
    request: Request,
    scan_type: str = Form("full_audit"),
    db: Session = Depends(get_db),
    user: AccessProfiles = Depends(require_superadmin)
):
    """بدء عملية فحص أمني شاملة للمنصة"""
    require_superadmin(user)
    try:
        scanner = LawSaaSScanner(root_dir=".", db=db)
        scan = scanner.run_full_scan(trigger_type=scan_type, triggered_by=user.id)

        log_admin_audit(
            db=db,
            user_id=user.id,
            action="trigger_security_scan",
            target_type="security_scan",
            target_id=str(scan.id),
            details=f"Type: {scan_type}, Findings: {scan.findings_count}, Files: {scan.files_scanned}",
            ip_address=request.client.host if request.client else None
        )

        return {
            "status": "success",
            "message": "تم إكمال الفحص الأمني بنجاح وتحديث كافة السجلات وقاعدة البيانات.",
            "scan": {
                "id": scan.id,
                "status": scan.status,
                "findings_count": scan.findings_count,
                "critical_count": scan.critical_count,
                "high_count": scan.high_count,
                "medium_count": scan.medium_count,
                "low_count": scan.low_count,
                "files_scanned": scan.files_scanned,
                "completed_at": scan.completed_at
            }
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "message": f"فشل تشغيل الفحص الأمني: {str(e)}"
            }
        )


@router.get("/api/superadmin/security/scans")
async def get_scan_history(
    limit: int = 10,
    db: Session = Depends(get_db),
    user: AccessProfiles = Depends(require_superadmin)
):
    """جلب سجل عمليات الفحص السابقة"""
    require_superadmin(user)
    scans = db.query(SecurityScans).order_by(SecurityScans.id.desc()).limit(limit).all()
    return [{
        "id": s.id,
        "scan_type": s.scan_type,
        "status": s.status,
        "started_at": s.started_at,
        "completed_at": s.completed_at,
        "files_scanned": s.files_scanned,
        "findings_count": s.findings_count,
        "critical_count": s.critical_count,
        "high_count": s.high_count,
        "medium_count": s.medium_count
    } for s in scans]


# =========================================================================
# 3. إدارة ومتابعة الثغرات والمشكلات الأمنية (Findings API)
# =========================================================================
@router.get("/api/superadmin/security/findings")
async def get_security_findings(
    severity: Optional[str] = None,
    status_filter: Optional[str] = "open",
    category: Optional[str] = None,
    limit: int = 50,
    db: Session = Depends(get_db),
    user: AccessProfiles = Depends(require_superadmin)
):
    """جلب قائمة الثغرات مع إمكانية الفلترة الدقيقة"""
    require_superadmin(user)
    query = db.query(SecurityFindings)
    if severity and severity != "all":
        query = query.filter(SecurityFindings.severity == severity.lower())
    if status_filter and status_filter != "all":
        query = query.filter(SecurityFindings.status == status_filter.lower())
    if category and category != "all":
        query = query.filter(SecurityFindings.category == category.lower())

    findings = query.order_by(SecurityFindings.id.desc()).limit(limit).all()
    return [{
        "id": f.id,
        "title": f.title,
        "description": f.description,
        "severity": f.severity,
        "category": f.category,
        "affected_component": f.affected_component,
        "affected_file": f.affected_file,
        "affected_line": f.affected_line,
        "vulnerability_id": f.vulnerability_id,
        "evidence_summary": f.evidence_summary,
        "remediation_recommendation": f.remediation_recommendation,
        "status": f.status,
        "first_detected_at": f.first_detected_at
    } for f in findings]


@router.post("/api/superadmin/security/findings/{finding_id}/status")
async def update_finding_status(
    finding_id: int,
    request: Request,
    new_status: str = Form(...),
    notes: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    user: AccessProfiles = Depends(require_superadmin)
):
    """تحديث حالة ثغرة (open, in_progress, resolved, false_positive, ignored)"""
    require_superadmin(user)
    finding = db.query(SecurityFindings).filter(SecurityFindings.id == finding_id).first()
    if not finding:
        raise HTTPException(status_code=404, detail="الثغرة المطلوبة غير موجودة.")

    old_status = finding.status
    finding.status = new_status
    if notes:
        finding.resolution_notes = notes
    if new_status == "resolved":
        finding.resolved_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    db.commit()

    log_admin_audit(
        db=db,
        user_id=user.id,
        action="update_finding_status",
        target_type="security_finding",
        target_id=str(finding.id),
        details=f"Changed status from {old_status} to {new_status}. Notes: {notes or '-'}",
        ip_address=request.client.host if request.client else None
    )

    return {"status": "success", "message": f"تم تحديث حالة الثغرة بنجاح إلى: {new_status}"}


# =========================================================================
# 4. مراقبة الأحداث الأمنية التشغيلية (Events API)
# =========================================================================
@router.get("/api/superadmin/security/events")
async def get_security_events(
    limit: int = 50,
    event_type: Optional[str] = None,
    severity: Optional[str] = None,
    db: Session = Depends(get_db),
    user: AccessProfiles = Depends(require_superadmin)
):
    """جلب سجل الأحداث الأمنية ومحاولات الهجوم المباشرة"""
    require_superadmin(user)
    query = db.query(SecurityEvents)
    if event_type and event_type != "all":
        query = query.filter(SecurityEvents.event_type == event_type)
    if severity and severity != "all":
        query = query.filter(SecurityEvents.severity == severity)

    events = query.order_by(SecurityEvents.id.desc()).limit(limit).all()
    return [{
        "id": e.id,
        "event_type": e.event_type,
        "severity": e.severity,
        "source_ip": e.source_ip,
        "endpoint": e.endpoint,
        "http_method": e.http_method,
        "status_code": e.status_code,
        "details": e.details,
        "created_at": e.created_at
    } for e in events]


# =========================================================================
# 5. تدقيق المكتبات والاعتماديات (Dependencies API)
# =========================================================================
@router.get("/api/superadmin/security/dependencies")
async def get_dependencies_audit(
    db: Session = Depends(get_db),
    user: AccessProfiles = Depends(require_superadmin)
):
    """جلب قائمة فحص المكتبات والاعتماديات في المنصة"""
    require_superadmin(user)
    deps = db.query(SecurityDependencies).order_by(
        desc(SecurityDependencies.verification_status == "verified_vulnerable"),
        SecurityDependencies.package_name.asc()
    ).all()
    return [{
        "id": d.id,
        "package_name": d.package_name,
        "installed_version": d.installed_version,
        "verification_status": d.verification_status,
        "vulnerability_id": d.vulnerability_id,
        "severity": d.severity,
        "fixed_version": d.fixed_version,
        "advisory_url": d.advisory_url,
        "detected_at": d.detected_at
    } for d in deps]


# =========================================================================
# 6. قائمة الملفات والأهداف المفحوصة (Targets API)
# =========================================================================
@router.get("/api/superadmin/security/targets")
async def get_scan_targets(
    status_filter: Optional[str] = None,
    limit: int = 100,
    db: Session = Depends(get_db),
    user: AccessProfiles = Depends(require_superadmin)
):
    """استعراض توثيق الملفات المفحوصة والمستثناة"""
    require_superadmin(user)
    query = db.query(SecurityScanTargets)
    if status_filter and status_filter != "all":
        query = query.filter(SecurityScanTargets.scan_status == status_filter)

    targets = query.order_by(SecurityScanTargets.id.asc()).limit(limit).all()
    return [{
        "id": t.id,
        "target_type": t.target_type,
        "target_path": t.target_path,
        "is_excluded": t.is_excluded,
        "scan_status": t.scan_status,
        "skip_reason": t.skip_reason,
        "last_scanned_at": t.last_scanned_at
    } for t in targets]


# =========================================================================
# 7. إعدادات التنبيهات وحدود المخاطر (Alert Settings API)
# =========================================================================
@router.post("/api/superadmin/security/settings")
async def update_alert_settings(
    request: Request,
    admin_email: str = Form(...),
    email_alerts_enabled: int = Form(1),
    min_email_severity: str = Form("high"),
    dedup_cooldown_minutes: int = Form(120),
    max_alerts_per_hour: int = Form(10),
    notify_on_failed_logins: int = Form(1),
    notify_on_new_critical_vulnerability: int = Form(1),
    db: Session = Depends(get_db),
    user: AccessProfiles = Depends(require_superadmin)
):
    """تحديث إعدادات كبح وإرسال التنبيهات الأمنية"""
    require_superadmin(user)
    settings = get_or_create_alert_settings(db)
    settings.admin_email = admin_email.strip()
    settings.email_alerts_enabled = email_alerts_enabled
    settings.min_email_severity = min_email_severity.lower()
    settings.dedup_cooldown_minutes = dedup_cooldown_minutes
    settings.max_alerts_per_hour = max_alerts_per_hour
    settings.notify_on_failed_logins = notify_on_failed_logins
    settings.notify_on_new_critical_vulnerability = notify_on_new_critical_vulnerability
    settings.updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    db.commit()

    log_admin_audit(
        db=db,
        user_id=user.id,
        action="change_alert_settings",
        details=f"Updated alert settings for email: {admin_email}, Min severity: {min_email_severity}",
        ip_address=request.client.host if request.client else None
    )

    return {"status": "success", "message": "تم حفظ وتحديث إعدادات التنبيهات بنجاح."}


# =========================================================================
# 8. الإصلاح التلقائي والذاتي للثغرات (Autonomous Remediation API)
# =========================================================================
@router.get("/api/superadmin/security/findings/{finding_id}/preview-fix")
async def preview_finding_fix(
    finding_id: int,
    db: Session = Depends(get_db),
    user: AccessProfiles = Depends(require_superadmin)
):
    """معاينة الإصلاح الذاتي المقترح للملاحظة الأمنية"""
    require_superadmin(user)
    finding = db.query(SecurityFindings).filter(SecurityFindings.id == finding_id).first()
    if not finding:
        raise HTTPException(status_code=404, detail="Finding not found")

    engine = AutoRemediationEngine()
    preview = engine.preview_fix(finding)
    return preview


@router.post("/api/superadmin/security/findings/{finding_id}/auto-fix")
async def auto_fix_finding(
    request: Request,
    finding_id: int,
    db: Session = Depends(get_db),
    user: AccessProfiles = Depends(require_superadmin)
):
    """تطبيق الإصلاح الآلي التلقائي لملاحظة أمنية محددة"""
    require_superadmin(user)
    engine = AutoRemediationEngine()
    result = engine.apply_fix(finding_id=finding_id, db=db, actor_user_id=user.id)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "فشل تطبيق الإصلاح"))

    log_admin_audit(
        db=db,
        user_id=user.id,
        action="apply_auto_remediation",
        target_type="security_finding",
        target_id=str(finding_id),
        details=f"Applied auto-remediation for finding #{finding_id}: {result.get('summary')}",
        ip_address=request.client.host if request.client else None
    )
    return result


@router.post("/api/superadmin/security/auto-fix-all")
async def auto_fix_all_findings(
    request: Request,
    db: Session = Depends(get_db),
    user: AccessProfiles = Depends(require_superadmin)
):
    """إصلاح كافة الملاحظات القابلة للعلاج الآلي بنقرة واحدة"""
    require_superadmin(user)
    engine = AutoRemediationEngine()
    result = engine.remediate_all(db=db, actor_user_id=user.id)

    log_admin_audit(
        db=db,
        user_id=user.id,
        action="apply_all_auto_remediations",
        details=f"Remediated {result.get('remediated_count')} findings automatically. Skipped {result.get('skipped_count')}.",
        ip_address=request.client.host if request.client else None
    )
    return result


# =========================================================================
# 9. الدرع التلقائي الحي ومكافحة التسلل (Active Defense IPS API)
# =========================================================================
@router.get("/api/superadmin/security/active-defense/status")
async def get_defense_status(
    user: AccessProfiles = Depends(require_superadmin)
):
    """الحصول على حالة الدرع التلقائي الحي وقائمة العناوين المحظورة"""
    require_superadmin(user)
    return get_active_defense_status()


@router.post("/api/superadmin/security/active-defense/unban/{ip}")
async def unban_ip_endpoint(
    request: Request,
    ip: str,
    db: Session = Depends(get_db),
    user: AccessProfiles = Depends(require_superadmin)
):
    """فك الحظر يدوياً عن عنوان IP محظور"""
    require_superadmin(user)
    success = unban_ip(ip)
    if not success:
        raise HTTPException(status_code=404, detail="العنوان غير موجود في قائمة الحظر الحالية.")

    log_admin_audit(
        db=db,
        user_id=user.id,
        action="manual_ip_unban",
        target_type="ip_address",
        target_id=ip,
        details=f"SuperAdmin unbanned IP address {ip}",
        ip_address=request.client.host if request.client else None
    )
    return {"status": "success", "message": f"تم فك الحظر بنجاح عن العنوان {ip}"}
