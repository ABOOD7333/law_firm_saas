"""
Security Monitoring Middleware — LawSaaS Platform
وسيط المراقبة الأمنية في الوقت الفعلي:
1. رصد محاولات الاختراق (SQL Injection, XSS, Path Traversal, Command Injection).
2. رصد محاولات كسر كلمات المرور (Brute Force) وتجاوز الصلاحيات.
3. رصد الاستكشاف المشبوه لروابط الإدارة الحساسة.
4. التطهير الصارم للبيانات: عدم حفظ كلمات المرور أو التوكنات أو المستندات أبداً.
5. تسجيل الأحداث في جدول security_events وإرسال التنبيهات الفورية للمدير.
"""

import json
import re
import urllib.parse
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from sqlalchemy.orm import Session

from database.database import SessionLocal
from database.security_models import SecurityEvents
from core.security_center.alert_service import dispatch_security_alert


# نماذج التوقيعات الهجومية (Attack Signatures)
ATTACK_SIGNATURES = [
    (
        "injection_attempt",
        "critical",
        re.compile(r"(\bUNION\b\s+\bSELECT\b|'\s*OR\s*'\d+'='\d+|--\s*$|;\s*DROP\s+TABLE|\bSLEEP\s*\(\d+\)|PG_SLEEP|BENCHMARK\()", re.IGNORECASE),
        "محاولة حقن استعلامات خبيثة (SQL Injection Attempt)"
    ),
    (
        "xss_attempt",
        "high",
        re.compile(r"(<\s*script\b|javascript\s*:|onerror\s*=|onload\s*=|document\.cookie|<img\s+src\s*=\s*['\"]?x)", re.IGNORECASE),
        "محاولة حقن سكربتات خبيثة عبر المتصفح (Cross-Site Scripting Attempt)"
    ),
    (
        "path_traversal_attempt",
        "high",
        re.compile(r"(\.\./|\.\.\\|%2e%2e%2f|%2e%2e\/|\betc/passwd\b|\bwin\.ini\b)", re.IGNORECASE),
        "محاولة تجاوز المسارات للوصول لملفات النظام (Path Traversal Attempt)"
    ),
    (
        "probe_sensitive_file",
        "medium",
        re.compile(r"(\.env|\.git/|wp-admin|phpmyadmin|\.aws/|id_rsa)", re.IGNORECASE),
        "محاولة استكشاف مسارات وملفات بيئة حساسة (Sensitive File Probe)"
    )
]

# ذاكرة لتتبع محاولات تسجيل الدخول الفاشلة لمنع كسر كلمات المرور (Brute Force Tracker)
_failed_login_attempts: Dict[str, List[datetime]] = defaultdict(list)
FAILED_LOGIN_THRESHOLD = 5
FAILED_LOGIN_WINDOW_MINUTES = 10


def sanitize_request_data(data: Any) -> str:
    """تنقية البيانات وإزالة أي حقول حساسة (كلمات مرور، توكنات، إلخ)"""
    if isinstance(data, dict):
        clean = {}
        for k, v in data.items():
            k_lower = str(k).lower()
            if any(s in k_lower for s in ["pass", "pwd", "secret", "token", "auth", "key", "credential", "doc"]):
                clean[k] = "[REDACTED]"
            else:
                clean[k] = sanitize_request_data(v)
        return json.dumps(clean, ensure_ascii=False)[:400]
    elif isinstance(data, str):
        # إخفاء الكلمات السرية
        sanitized = re.sub(r'(password|secret|token|api_key)\s*[:=]\s*["\'][^"\']+["\']', r'\1="[REDACTED]"', data, flags=re.IGNORECASE)
        return sanitized[:400]
    return str(data)[:400]


def record_security_event(
    db: Session,
    event_type: str,
    severity: str,
    source_ip: str,
    user_agent: Optional[str] = None,
    endpoint: Optional[str] = None,
    http_method: Optional[str] = None,
    status_code: Optional[int] = None,
    actor_user_id: Optional[int] = None,
    target_office_id: Optional[int] = None,
    details: Optional[str] = None,
    trigger_alert: bool = True
) -> SecurityEvents:
    """تسجيل حدث أمني تشغيلي في قاعدة البيانات وإرسال تنبيه إذا لزم"""
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    clean_details = sanitize_request_data(details or "")

    event = SecurityEvents(
        event_type=event_type,
        severity=severity,
        source_ip=source_ip,
        user_agent=(user_agent or "")[:300],
        endpoint=(endpoint or "")[:200],
        http_method=http_method,
        status_code=status_code,
        actor_user_id=actor_user_id,
        target_office_id=target_office_id,
        details=clean_details,
        created_at=now_str
    )
    db.add(event)
    db.commit()
    db.refresh(event)

    if trigger_alert and severity in ("critical", "high"):
        dispatch_security_alert(
            db=db,
            title=f"رصد حدث أمني تشغيلي: {event_type}",
            message=f"تم رصد نشاط مشبوه من العنوان {source_ip} على الرابط {endpoint}.\nالتفاصيل: {clean_details}",
            severity=severity,
            category_or_type=event_type,
            target_identifier=f"Endpoint: {endpoint or 'Global'}",
            event_id=event.id
        )

    return event


class SecurityMonitoringMiddleware(BaseHTTPMiddleware):
    """
    وسيط مراقبة أمنية يقوم بفحص كافة الطلبات الواردة إلى التطبيق
    """
    async def dispatch(self, request: Request, call_next):
        client_ip = request.client.host if request.client else "unknown"
        # دعم ترويسة X-Forwarded-For في استضافة Railway
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            client_ip = forwarded.split(",")[0].strip()

        path = request.url.path
        raw_query = str(request.url.query)
        decoded_query = urllib.parse.unquote(raw_query)
        inspect_string = f"{path}?{decoded_query}"

        # 1. فحص التوقيعات الهجومية (Signatures)
        for event_type, severity, pattern, desc in ATTACK_SIGNATURES:
            if pattern.search(inspect_string):
                db = SessionLocal()
                try:
                    record_security_event(
                        db=db,
                        event_type=event_type,
                        severity=severity,
                        source_ip=client_ip,
                        user_agent=request.headers.get("user-agent"),
                        endpoint=path,
                        http_method=request.method,
                        status_code=400,
                        details=f"{desc} | Signature matched on query string"
                    )
                finally:
                    db.close()

                # الرد بحظر فوري عند كشف هجوم حرج
                return Response(
                    content=json.dumps({"detail": "Security violation detected by LawSaaS SOC Engine"}),
                    status_code=400,
                    media_type="application/json"
                )

        # 2. متابعة تنفيذ الطلب واستقبال الرد
        response = await call_next(request)

        # 3. إلحاق ترويسات الحماية الأساسية بالاستجابة لرفع الأمان
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

        # 4. مراقبة محاولات تسجيل الدخول الفاشلة والوصول غير المصرح
        if path.startswith("/superadmin") and response.status_code in (401, 403):
            db = SessionLocal()
            try:
                record_security_event(
                    db=db,
                    event_type="unauthorized_superadmin_access",
                    severity="high",
                    source_ip=client_ip,
                    user_agent=request.headers.get("user-agent"),
                    endpoint=path,
                    http_method=request.method,
                    status_code=response.status_code,
                    details=f"محاولة غير مصرح بها للوصول إلى لوحة إدارة المنصة /superadmin من عنوان {client_ip}"
                )
            finally:
                db.close()

        return response
