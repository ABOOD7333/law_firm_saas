"""
Security Monitoring & Active Defense Middleware — LawSaaS Platform
وسيط المراقبة الأمنية والدرع الدفاعي التلقائي (Active IPS & Defense Shield)

الميزات المتقدمة:
1. درع حماية نشط (Active Defense) يعمل تلقائياً 24/7 دون أي تدخل بشري.
2. كشف متقدم لحقن SQL، والسكربتات XSS، وتجاوز المسارات Path Traversal، وحقن الأوامر.
3. فحص نصوص الاستعلام (Query String)، والترويسات (Headers)، ومحتوى الطلب (Request Body).
4. رصد أدوات الهجوم والفحص التلقائي (Scanner User-Agents: Sqlmap, Nikto, Nessus, Burp, etc.).
5. نظام الحظر التلقائي الذكي (Auto-Ban IPS): حظر عناوين IP المهاجمة تلقائياً عند تكرار الهجمات.
6. حماية تسجيل الدخول ومكافحة كسر كلمات المرور (Brute Force Protection).
7. تسجيل فوري للأحداث وإرسال التنبيهات مع التطهير الصارم للبيانات الحساسة.
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


# نماذج التوقيعات الهجومية المتقدمة (Attack Signatures)
ATTACK_SIGNATURES = [
    (
        "injection_attempt",
        "critical",
        re.compile(r"(\bUNION\b\s+\bSELECT\b|'\s*OR\s*'\d+'='\d+|--\s*$|;\s*DROP\s+TABLE|\bSLEEP\s*\(\d+\)|PG_SLEEP|BENCHMARK\(|\bWAITFOR\s+DELAY\b)", re.IGNORECASE),
        "محاولة حقن استعلامات خبيثة (SQL Injection Attempt)"
    ),
    (
        "xss_attempt",
        "high",
        re.compile(r"(<\s*script\b|javascript\s*:|onerror\s*=|onload\s*=|document\.cookie|<img\s+src\s*=\s*['\"]?x|<svg\s+onload)", re.IGNORECASE),
        "محاولة حقن سكربتات خبيثة عبر المتصفح (Cross-Site Scripting Attempt)"
    ),
    (
        "path_traversal_attempt",
        "high",
        re.compile(r"(\.\./|\.\.\\|%2e%2e%2f|%2e%2e\/|\betc/passwd\b|\bwin\.ini\b|/proc/self/)", re.IGNORECASE),
        "محاولة تجاوز المسارات للوصول لملفات النظام (Path Traversal Attempt)"
    ),
    (
        "cmd_injection_attempt",
        "critical",
        re.compile(r"(;\s*\bcat\s+/|\|\s*\bcat\s+/|;\s*powershell\b|;\s*cmd\.exe\b|`whoami`|\$\(whoami\))", re.IGNORECASE),
        "محاولة تنفيذ أوامر نظام التشغيل (Command Injection Attempt)"
    ),
    (
        "probe_sensitive_file",
        "medium",
        re.compile(r"(\.env|\.git/|wp-admin|phpmyadmin|\.aws/|id_rsa|\.ds_store|web\.config)", re.IGNORECASE),
        "محاولة استكشاف مسارات وملفات بيئة حساسة (Sensitive File Probe)"
    )
]

# بصمات أدوات الفحص والاختراق الآلية (Vulnerability Scanners)
SCANNER_USER_AGENTS = re.compile(
    r"(sqlmap|nikto|acunetix|nessus|dirbuster|gobuster|wpscan|masscan|zgrab|nmap|burpsuite|havij)",
    re.IGNORECASE
)

# نظام تتبع الحظر التلقائي في الذاكرة (Memory IPS State)
_banned_ips: Dict[str, Dict[str, Any]] = {}  # ip -> {"until": datetime, "reason": str, "strikes": int}
_ip_strikes: Dict[str, List[datetime]] = defaultdict(list)
_failed_login_attempts: Dict[str, List[datetime]] = defaultdict(list)

# إحصائيات الدرع التلقائي الحية
_active_defense_stats = {
    "total_inspected_requests": 0,
    "total_blocked_attacks": 0,
    "total_auto_banned_ips": 0,
    "started_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
}

FAILED_LOGIN_THRESHOLD = 5
FAILED_LOGIN_WINDOW_MINUTES = 10
ATTACK_STRIKE_THRESHOLD = 3
DEFAULT_BAN_MINUTES = 30


def is_ip_banned(ip: str) -> Tuple[bool, Optional[str], int]:
    """فحص هل العنوان محظور حالياً وكم دقيقة متبقية"""
    if ip in _banned_ips:
        ban_info = _banned_ips[ip]
        now = datetime.now()
        if now < ban_info["until"]:
            remaining_secs = int((ban_info["until"] - now).total_seconds())
            return True, ban_info["reason"], max(1, remaining_secs // 60)
        else:
            # انتهاء فترة الحظر
            del _banned_ips[ip]
    return False, None, 0


def auto_ban_ip(ip: str, minutes: int, reason: str, db: Optional[Session] = None):
    """حظر عنوان IP تلقائياً وتسجيل ذلك في النظام"""
    until = datetime.now() + timedelta(minutes=minutes)
    _banned_ips[ip] = {
        "until": until,
        "reason": reason,
        "banned_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    _active_defense_stats["total_auto_banned_ips"] += 1

    if db:
        try:
            record_security_event(
                db=db,
                event_type="ip_auto_banned",
                severity="critical",
                source_ip=ip,
                details=f"تم حظر العنوان تلقائياً لمدة {minutes} دقيقة بواسطة درع الحماية النشط. السبب: {reason}",
                trigger_alert=True
            )
        except Exception as e:
            print(f"[Active Defense Error] Failed to log ban event: {e}")


def unban_ip(ip: str) -> bool:
    """فك الحظر يدوياً عن عنوان IP بواسطة SuperAdmin"""
    if ip in _banned_ips:
        del _banned_ips[ip]
        if ip in _ip_strikes:
            del _ip_strikes[ip]
        return True
    return False


def get_active_defense_status() -> Dict[str, Any]:
    """استرجاع تقرير حالة الدرع التلقائي بالكامل"""
    # تنظيف المحظورين المنتهين
    now = datetime.now()
    expired = [ip for ip, data in _banned_ips.items() if now >= data["until"]]
    for ip in expired:
        del _banned_ips[ip]

    banned_list = []
    for ip, data in _banned_ips.items():
        rem_mins = int((data["until"] - now).total_seconds() // 60)
        banned_list.append({
            "ip": ip,
            "reason": data["reason"],
            "banned_at": data.get("banned_at", "N/A"),
            "remaining_minutes": max(1, rem_mins)
        })

    return {
        "shield_status": "ACTIVE_DEFENSE_ONLINE",
        "total_inspected_requests": _active_defense_stats["total_inspected_requests"],
        "total_blocked_attacks": _active_defense_stats["total_blocked_attacks"],
        "total_auto_banned_ips": _active_defense_stats["total_auto_banned_ips"],
        "currently_banned_count": len(_banned_ips),
        "banned_ips": banned_list,
        "started_at": _active_defense_stats["started_at"]
    }


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
    وسيط المراقبة الأمنية والدرع التلقائي الذكي (Autonomous Active Defense)
    """
    async def dispatch(self, request: Request, call_next):
        _active_defense_stats["total_inspected_requests"] += 1

        # استخراج عنوان العميل الحقيقي
        client_ip = request.client.host if request.client else "unknown"
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            client_ip = forwarded.split(",")[0].strip()

        # 1. فحص هل الـ IP محظور تلقائياً بواسطة الدرع
        is_banned, ban_reason, rem_mins = is_ip_banned(client_ip)
        if is_banned:
            _active_defense_stats["total_blocked_attacks"] += 1
            return Response(
                content=json.dumps({
                    "error": "Access Denied by LawSaaS Active Defense Shield",
                    "reason": ban_reason,
                    "retry_after_minutes": rem_mins
                }),
                status_code=403,
                media_type="application/json"
            )

        user_agent = request.headers.get("user-agent", "")
        path = request.url.path

        # 2. فحص أدوات الفحص والاختراق الآلية (Scanner Detection)
        if user_agent and SCANNER_USER_AGENTS.search(user_agent):
            _active_defense_stats["total_blocked_attacks"] += 1
            db = SessionLocal()
            try:
                auto_ban_ip(
                    ip=client_ip,
                    minutes=60,
                    reason=f"رصد أداة اختراق وفحص أمني مشبوهة: {user_agent[:100]}",
                    db=db
                )
            finally:
                db.close()

            return Response(
                content=json.dumps({"detail": "Malicious scanner probe detected and blocked by LawSaaS SOC"}),
                status_code=403,
                media_type="application/json"
            )

        # 3. فحص التوقيعات الهجومية في المسار والـ Query String
        raw_query = str(request.url.query)
        decoded_query = urllib.parse.unquote(raw_query)
        inspect_string = f"{path}?{decoded_query}"

        # 4. فحص محتوى الطلب (Body) في طلبات POST/PUT/PATCH إن وجد
        body_str = ""
        if request.method in ("POST", "PUT", "PATCH") and not path.startswith("/static/"):
            try:
                body_bytes = await request.body()
                body_str = body_bytes.decode("utf-8", errors="ignore")[:2000]
                # إعادة بناء receive حتى تتمكن الراوترات التالية من قراءة الـ body
                async def receive():
                    return {"type": "http.request", "body": body_bytes}
                request._receive = receive
            except Exception:
                pass

        full_inspect_payload = f"{inspect_string} {body_str}"

        # 5. مطابقة التوقيعات الهجومية
        for event_type, severity, pattern, desc in ATTACK_SIGNATURES:
            if pattern.search(full_inspect_payload):
                _active_defense_stats["total_blocked_attacks"] += 1
                now = datetime.now()
                _ip_strikes[client_ip].append(now)

                # تنظيف المخالفات القديمة لأكثر من ساعة
                _ip_strikes[client_ip] = [t for t in _ip_strikes[client_ip] if (now - t).total_seconds() < 3600]

                db = SessionLocal()
                try:
                    record_security_event(
                        db=db,
                        event_type=event_type,
                        severity=severity,
                        source_ip=client_ip,
                        user_agent=user_agent,
                        endpoint=path,
                        http_method=request.method,
                        status_code=400,
                        details=f"{desc} | Signature matched on payload: {sanitize_request_data(full_inspect_payload[:250])}"
                    )

                    # إذا تكررت المخالفات 3 مرات، يتم الحظر التلقائي فوراً
                    if len(_ip_strikes[client_ip]) >= ATTACK_STRIKE_THRESHOLD:
                        auto_ban_ip(
                            ip=client_ip,
                            minutes=DEFAULT_BAN_MINUTES,
                            reason=f"تكرار محاولات الهجوم والاختراق ({len(_ip_strikes[client_ip])} محاولات)",
                            db=db
                        )
                finally:
                    db.close()

                return Response(
                    content=json.dumps({"detail": "Security violation detected by LawSaaS Active Defense Shield"}),
                    status_code=400,
                    media_type="application/json"
                )

        # 6. تمرير الطلب واستقبال الرد
        response = await call_next(request)

        # 7. إلحاق ترويسات الحماية بالاستجابة
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

        # 8. رصد محاولات الدخول الفاشلة لمحاربة كسر كلمات المرور (Brute Force Protection)
        if path in ("/login", "/api/auth/login", "/auth/login") and response.status_code in (401, 403):
            now = datetime.now()
            _failed_login_attempts[client_ip].append(now)
            _failed_login_attempts[client_ip] = [
                t for t in _failed_login_attempts[client_ip]
                if (now - t).total_seconds() < (FAILED_LOGIN_WINDOW_MINUTES * 60)
            ]

            if len(_failed_login_attempts[client_ip]) >= FAILED_LOGIN_THRESHOLD:
                db = SessionLocal()
                try:
                    auto_ban_ip(
                        ip=client_ip,
                        minutes=DEFAULT_BAN_MINUTES,
                        reason=f"تجاوز الحد المسموح لمحاولات تسجيل الدخول الفاشلة ({len(_failed_login_attempts[client_ip])} محاولات)",
                        db=db
                    )
                finally:
                    db.close()

        # 9. رصد محاولات الوصول غير المصرح إلى /superadmin أو /security-center
        if (path.startswith("/superadmin") or path.startswith("/security-center")) and response.status_code in (401, 403):
            db = SessionLocal()
            try:
                record_security_event(
                    db=db,
                    event_type="unauthorized_superadmin_access",
                    severity="high",
                    source_ip=client_ip,
                    user_agent=user_agent,
                    endpoint=path,
                    http_method=request.method,
                    status_code=response.status_code,
                    details=f"محاولة غير مصرح بها للوصول إلى لوحة الإدارة العليا من العنوان {client_ip}"
                )
            finally:
                db.close()

        return response
