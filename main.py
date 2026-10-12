# ——— Logging ——————————————————————————————————————————————————————
# ChromaDB sqlite3 version override for production environment (Docker / Railway)
try:
    __import__('pysqlite3')
    import sys
    sys.modules['sqlite3'] = sys.modules.pop('pysqlite3')
except ImportError:
    pass
from core.logger import app_logger
from core.audit import write_audit
from core.security import hash_session_token, login_lockout_active, record_login_failure

import hashlib
import uuid
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta, timezone
from fastapi import FastAPI, Request, Form, Depends, Cookie, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import uvicorn
import os

from sqlalchemy.orm import Session
from sqlalchemy import text
from database.database import get_db, init_db
from database.models import (AccessProfiles, AuthSessions, AuthVerificationTokens, LawClients, LawCases, LawOffices,
    LawHearings, LawTransactions, LawExpenses, LawDocuments, LawTasks, PaymentRequest, LawTimesheets)
import shutil

# --- PDF Generation & Arabic support ---
import arabic_reshaper
from bidi.algorithm import get_display
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from fastapi.responses import FileResponse
import urllib.request
import tempfile

app = FastAPI(title="LawSaaS Platform - Enterprise Legal Management", version="1.0")

# Ensure database tables are created (critical for Railway deployment)
init_db()

async def daily_scheduler():
    import asyncio
    from database.database import SessionLocal
    from core.workflow_engine import run_daily_limitation_checks
    from core.rate_limiter import cleanup_old_attempts
    while True:
        db = None
        try:
            print("[Scheduler] Running daily limitation checks...")
            db = SessionLocal()
            run_daily_limitation_checks(db)
            print("[Scheduler] Daily limitation checks completed.")
            # تنظيف سجلات Rate Limiting القديمة (أكثر من ساعة)
            cleanup_old_attempts(older_than_seconds=3600)
            print("[Scheduler] Rate limit cleanup completed.")
        except Exception as e:
            print(f"[Scheduler Error] {e}")
        finally:
            if db:
                db.close()
        # Run every 24 hours
        await asyncio.sleep(86400)

@app.on_event("startup")
async def startup_event():
    # Spawn daily scheduler background task
    import asyncio
    asyncio.create_task(daily_scheduler())

    # ─────────────────────────────────────────────────────────────────────
    # ChromaDB / Embedding model indexing — DISABLED on startup intentionally
    #
    # السبب: تحميل نموذج sentence-transformers (229MB) عند كل إعادة تشغيل
    # يستنفد RAM الخادم على Railway → crash loop لانهائي.
    #
    # الحل: البحث الهجين يعمل بـ BM25 المعجمي بشكل كامل وهو كافٍ.
    # إذا أردت تفعيل الجزء الدلالي مستقبلاً، قم بتشغيل سكربت الفهرسة
    # يدوياً محلياً ورفع قاعدة بيانات chromadb إلى Volume مخصص.
    # ─────────────────────────────────────────────────────────────────────
    print("[Startup] Server ready. Semantic indexing disabled to preserve RAM on Railway.")

try:

    from create_superadmin import create_superadmin

    create_superadmin()

except Exception as e:

    print(f"Failed to auto-create superadmin: {e}")

# إنشاء المجلدات الضرورية (مع تجاهل خطأ الصلاحيات - Dockerfile ينشئها مسبقاً)
def _safe_makedirs(path: str):
    """Create directory if possible; log a warning on PermissionError."""
    try:
        os.makedirs(path, exist_ok=True)
    except PermissionError:
        app_logger.warning(f"[startup] Cannot create '{path}' — already handled by Dockerfile (OK)")
    except OSError as exc:
        app_logger.warning(f"[startup] makedirs('{path}'): {exc}")

_safe_makedirs("static/css")
_safe_makedirs("static/js")
_safe_makedirs("static/img")
_safe_makedirs("static/uploads/documents")
_safe_makedirs("private_uploads/documents")
_safe_makedirs("templates")

from starlette.middleware.base import BaseHTTPMiddleware

from fastapi.responses import JSONResponse

import uuid

class CSRFMiddleware(BaseHTTPMiddleware):

    async def dispatch(self, request: Request, call_next):

        if request.url.path.startswith("/api/mobile") and (
            request.url.path in {"/api/mobile/login", "/api/mobile/login-2fa"}
            or request.headers.get("Authorization", "").startswith("Bearer ")
        ):

            return await call_next(request)

        csrf_cookie = request.cookies.get("csrf_token")

        if not csrf_cookie:

            csrf_cookie = str(uuid.uuid4())

        # إعفاء مسارات تسجيل الدخول وما قبل المصادقة من CSRF
        # (محمية بواسطة Rate Limiting ولا توجد جلسة نشطة لاختطافها)
        PRE_AUTH_PATHS = {
            "/",
            "/login",
            "/api/login",
            "/api/superadmin-login",
            "/api/forgot-send-otp",
            "/api/verify-forgot-otp",
            "/api/register-send-otp",
            "/api/verify-register-otp",
        }
        if request.url.path in PRE_AUTH_PATHS:
            response = await call_next(request)
            if not request.cookies.get("csrf_token"):
                is_secure = not (request.url.hostname in ["127.0.0.1", "localhost"])
                response.set_cookie("csrf_token", csrf_cookie, httponly=False, secure=is_secure, samesite="Lax")
            return response

        if request.method in ["POST", "PUT", "DELETE", "PATCH"]:

                # Security Fix: Only check the CSRF token in the form body (or header), avoid URL query parameters.

                csrf_header = request.headers.get("X-CSRF-Token")

                # For Form Submissions

                form_token = None

                content_type = request.headers.get("Content-Type", "")

                if "application/x-www-form-urlencoded" in content_type or "multipart/form-data" in content_type:

                    try:

                        # Replay body trick to avoid exhausting the stream for FastAPI

                        body_bytes = await request.body()

                        # Mock receive function

                        async def receive():

                            return {"type": "http.request", "body": body_bytes}

                        request._receive = receive

                        form = await request.form()

                        form_token = form.get("csrf_token")

                        # Reset again so the endpoint can read it

                        async def receive_again():

                            return {"type": "http.request", "body": body_bytes}

                        request._receive = receive_again

                    except:

                        pass

                submitted_token = csrf_header or form_token

                if not submitted_token or submitted_token != csrf_cookie:

                    return JSONResponse({"error": "CSRF token missing or invalid", "status": 403}, status_code=403)

        response = await call_next(request)

        if not request.cookies.get("csrf_token"):

            is_secure = not (request.url.hostname in ["127.0.0.1", "localhost"])

            response.set_cookie(

                "csrf_token",

                csrf_cookie,

                httponly=False,

                secure=is_secure,

                samesite="Lax"

            )

        return response

app.add_middleware(CSRFMiddleware)

# ─── Safe Error Handler ───────────────────────────────────────────────────────

def _safe_error(tb_str: str = "") -> HTMLResponse:

    """يعرض تفاصيل الخطأ في التطوير فقط — يخفيها في الإنتاج ويسجلها في السجلات."""

    if tb_str:
        app_logger.error(f"[SERVER_ERROR_TRACEBACK]\n{tb_str}")

    if True: # SECURITY FIX: Never expose tracebacks

        return HTMLResponse(

            content="<div style='font-family:sans-serif;padding:40px;text-align:center;direction:rtl'>"

                    "<h2 style='color:#dc2626'>⚠️ حدث خطأ داخلي</h2>"

                    "<p style='color:#64748b'>يرجى المحاولة مرة أخرى أو التواصل مع الدعم الفني.</p>"

                    "</div>",

            status_code=500

        )

    return HTMLResponse(

        content=f"<pre dir='ltr' style='background:#1e1e1e;color:#f8f8f2;padding:20px;font-size:13px;overflow:auto'>{tb_str}</pre>",

        status_code=500

    )

import time

from fastapi.responses import JSONResponse

from core.rate_limiter import record_attempt, is_rate_limited

class LoginRateLimitMiddleware(BaseHTTPMiddleware):

    async def dispatch(self, request: Request, call_next):

        if request.url.path in ["/", "/api/login", "/api/superadmin-login", "/api/mobile/login"] and request.method == "POST":

            ip = request.client.host or "127.0.0.1"

            if is_rate_limited(ip, "login", max_attempts=10, window_seconds=300):

                    return JSONResponse({"success": False, "error": "تم حظر الـ IP مؤقتاً بسبب كثرة المحاولات. انتظر 5 دقائق."}, status_code=429)

            record_attempt(ip, "login")

        return await call_next(request)

app.add_middleware(LoginRateLimitMiddleware)

from fastapi.middleware.cors import CORSMiddleware

# ── [SECURITY FIX CRIT-01] إصلاح ثغرة CORS Wildcard ──
# تم حذف allow_origin_regex=r"https?://.*" التي كانت تسمح لأي موقع بالوصول
_ALLOWED_ORIGINS = [
    "http://localhost",
    "http://localhost:8000",
    "http://localhost:7882",
    "http://127.0.0.1:8000",
    "https://web-production-80e9e.up.railway.app",
]

app.add_middleware(

    CORSMiddleware,

    allow_origins=_ALLOWED_ORIGINS,

    allow_credentials=True,

    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],

    allow_headers=["Content-Type", "Authorization", "X-CSRF-Token", "X-Requested-With"],

)

# ── [SECURITY FIX MED-06] إضافة Security HTTP Headers ──
class SecurityHeadersMiddleware(BaseHTTPMiddleware):

    async def dispatch(self, request: Request, call_next):

        response = await call_next(request)

        # منع Clickjacking
        response.headers["X-Frame-Options"] = "DENY"

        # منع MIME Sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"

        # تفعيل XSS Protection المدمج في المتصفح
        response.headers["X-XSS-Protection"] = "1; mode=block"

        # تقليل تسريب Referer
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # تقييد الصلاحيات المتصفحية
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"

        # إجبار HTTPS (للإنتاج)
        is_prod = request.url.hostname not in ["127.0.0.1", "localhost"]
        if is_prod:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

        # Content Security Policy
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com https://unpkg.com; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://cdn.jsdelivr.net https://cdnjs.cloudflare.com; "
            "font-src 'self' https://fonts.gstatic.com https://cdn.jsdelivr.net; "
            "img-src 'self' data: blob: https:; "
            "connect-src 'self'; "
            "frame-ancestors 'none';"
        )

        return response

app.add_middleware(SecurityHeadersMiddleware)

# Mount static files

class SafeStaticFiles(StaticFiles):
    async def get_response(self, path: str, scope):
        if path == "uploads" or path.startswith("uploads/"):
            return PlainTextResponse("Not found", status_code=404)
        return await super().get_response(path, scope)


app.mount("/static", SafeStaticFiles(directory="static"), name="static")

# Templates setup - imported from dependencies to avoid circular imports in routers

from dependencies import templates, get_current_user, check_user_permission

@app.get("/", response_class=HTMLResponse)
async def login_page(request: Request, user: AccessProfiles = Depends(get_current_user)):
    # إذا كان المستخدم مسجل دخول مسبقاً، نوجهه للوحة التحكم مباشرة
    if user:
        return RedirectResponse(url="/dashboard", status_code=303)
    return templates.TemplateResponse(request=request, name="login.html")


@app.get("/login", response_class=HTMLResponse)
async def login_page_alias(request: Request, user: AccessProfiles = Depends(get_current_user)):
    if user:
        return RedirectResponse(url="/dashboard", status_code=303)
    return templates.TemplateResponse(request=request, name="login.html")


@app.get("/api/health")
async def health_check(db: Session = Depends(get_db)):
    """Minimal health check; detailed diagnostics must stay private."""
    checks = {"server": "ok", "database": "ok"}
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        checks["database"] = "unavailable"
    return JSONResponse(checks)


@app.post("/api/setup")
async def setup_database(user: AccessProfiles = Depends(get_current_user)):
    """Privileged recovery endpoint; never expose database setup publicly."""
    if not user or getattr(user, "is_superadmin", 0) != 1:
        raise HTTPException(status_code=403, detail="غير مصرح")
    results = {"steps": []}
    
    # 1. إنشاء الجداول
    try:
        from database.database import engine
        from database.models import Base
        Base.metadata.create_all(bind=engine)
        results["steps"].append({"create_tables": "OK"})
    except Exception:
        results["steps"].append({"create_tables": "ERROR"})
        return JSONResponse(results, status_code=500)
    
    # 2. تهيئة البيانات الأساسية
    try:
        init_db()
        results["steps"].append({"init_db": "OK"})
    except Exception:
        results["steps"].append({"init_db": "ERROR"})
    
    # 3. التحقق من الجداول
    try:
        from database.database import SessionLocal
        from database.models import AccessProfiles
        with SessionLocal() as db:
            count = db.query(AccessProfiles).count()
            results["steps"].append({"verify_users": f"OK ({count} users)"})
    except Exception:
        results["steps"].append({"verify_users": "ERROR"})
    
    results["status"] = "completed"
    return JSONResponse(results)

@app.get("/forgot-password", response_class=HTMLResponse)

async def forgot_password_page(request: Request):

    return templates.TemplateResponse(request=request, name="forgot_password.html", context={})

@app.get("/register", response_class=HTMLResponse)

async def register_page(request: Request, user: AccessProfiles = Depends(get_current_user)):

    if user:

        return RedirectResponse(url="/dashboard", status_code=303)

    return templates.TemplateResponse(request=request, name="register.html", context={})

from email_service import generate_otp, store_otp, verify_otp, send_otp_email

from fastapi.responses import JSONResponse as _JSONResponse

import secrets

# سجل بسيط لتتبع طلبات OTP لمنع إغراق الإيميل (Rate Limiting)

import time

# Rate limiting is now handled by core.rate_limiter (database-backed)

@app.post("/api/forgot-send-otp")

async def api_forgot_send_otp(request: Request, db: Session = Depends(get_db)):

    """إرسال رمز OTP لاستعادة كلمة المرور بعد التحقق من تاريخ الميلاد"""

    data = await request.json()

    email = data.get("email", "").strip()

    phone = data.get("phone", "").strip()

    if not email or not phone:

        return _JSONResponse({"success": False, "error": "الرجاء إدخال البريد الإلكتروني ورقم الهاتف"}, status_code=400)

    user = db.query(AccessProfiles).filter(

        (AccessProfiles.email == email) | (AccessProfiles.username == email)

    ).first()

    # [SECURITY FIX MED-02] رسالة موحدة لمنع User Enumeration
    # لا نُفصح إذا كان المستخدم موجوداً أم لا، وإذا كان الهاتف مطابقاً أم لا
    _enum_error = _JSONResponse({
        "success": False,
        "error": "إذا كانت البيانات صحيحة، سيصلك رمز التحقق على بريدك الإلكتروني خلال دقائق."
    }, status_code=200)

    if not user:

        return _enum_error

    if user.phone != phone:

        return _enum_error

    # Rate Limiting Check (3 محاولات كل 15 دقيقة)

    if is_rate_limited(email, "otp", max_attempts=3, window_seconds=900):

        return _JSONResponse({"success": False, "error": "تجاوزت الحد المسموح من المحاولات. يرجى الانتظار 15 دقيقة."}, status_code=429)

    record_attempt(email, "otp")

    code = generate_otp(6)

    store_otp(email, code)

    sent = send_otp_email(email, code, "forgot_password")

    if sent:

        return _JSONResponse({"success": True, "message": "تم إرسال رمز التحقق"})

    return _JSONResponse({"success": False, "error": "فشل إرسال البريد الإلكتروني"}, status_code=500)

@app.post("/api/forgot-verify-otp")

async def api_forgot_verify_otp(request: Request, db: Session = Depends(get_db)):

    """التحقق من رمز OTP وإصدار Token مؤقت آمن"""

    data = await request.json()

    identifier = data.get("identifier", "").strip()

    code = data.get("code", "").strip()

    if verify_otp(identifier, code):

        user = db.query(AccessProfiles).filter(AccessProfiles.email == identifier).first()
        if not user:
            return _JSONResponse({"success": False, "error": "الرمز غير صحيح أو منتهي الصلاحية"}, status_code=400)
        token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        expires = datetime.now(timezone.utc) + timedelta(minutes=10)
        db.add(AuthVerificationTokens(
            user_id=user.id,
            token_hash=token_hash,
            token_type="password_reset",
            expires_at=expires.strftime("%Y-%m-%d %H:%M:%S"),
        ))
        db.commit()

        return _JSONResponse({"success": True, "token": token})

    return _JSONResponse({"success": False, "error": "الرمز غير صحيح أو منتهي الصلاحية"}, status_code=400)

@app.post("/api/reset-password-secure")

async def api_reset_password_secure(request: Request, db: Session = Depends(get_db)):

    """إعادة تعيين كلمة المرور بشكل آمن باستخدام التوكن"""

    data = await request.json()

    email = data.get("email", "").strip()

    new_username = data.get("new_username", "").strip()

    new_password = data.get("new_password", "").strip()

    token = data.get("token", "").strip()

    if not token or not email or len(new_password) < 12:

        return _JSONResponse({"success": False, "error": "بيانات التغيير غير صالحة؛ كلمة المرور يجب أن تكون 12 حرفاً على الأقل"}, status_code=400)

    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    reset_record = db.query(AuthVerificationTokens).filter(
        AuthVerificationTokens.token_hash == hashlib.sha256(token.encode()).hexdigest(),
        AuthVerificationTokens.token_type == "password_reset",
        AuthVerificationTokens.expires_at > now_str,
        AuthVerificationTokens.consumed_at.is_(None),
    ).first()
    if not reset_record:
        return _JSONResponse({"success": False, "error": "طلب غير مصرح به أو انتهت صلاحية الجلسة"}, status_code=403)

    user = db.query(AccessProfiles).filter(
        AccessProfiles.email == email,
        AccessProfiles.id == reset_record.user_id,
    ).first()

    if not user:

        return _JSONResponse({"success": False, "error": "لم يُعثر على هذا الحساب"}, status_code=404)

    user.access_pin_hash = _hash_pin(new_password)

    user.failed_attempts = 0
    user.locked_until = None

    if new_username:

        if new_username != user.username:

            existing = db.query(AccessProfiles).filter(AccessProfiles.username == new_username).first()

            if existing:

                return _JSONResponse({"success": False, "error": "اسم المستخدم محجوز، اختر اسماً آخر"}, status_code=400)

            user.username = new_username

    reset_record.consumed_at = now_str
    db.query(AuthSessions).filter(
        AuthSessions.user_id == user.id,
        AuthSessions.is_active == 1,
    ).update({"is_active": 0})
    db.commit()

    return _JSONResponse({"success": True, "message": "تم تغيير البيانات بنجاح"})

@app.post("/api/verify-otp")

async def api_verify_otp(request: Request, db: Session = Depends(get_db)):

    """التحقق من رمز OTP العام (للتسجيل)"""

    data = await request.json()

    identifier = data.get("identifier", "").strip()

    code = data.get("code", "").strip()

    if verify_otp(identifier, code):

        user = db.query(AccessProfiles).filter(AccessProfiles.email == identifier).first()

        if user:

            user.is_active = 1

            user.email_verified = 1

            db.commit()

        return _JSONResponse({"success": True})

    return _JSONResponse({"success": False, "error": "الرمز غير صحيح أو منتهي الصلاحية"}, status_code=400)

def _verify_pin(pin: str, stored_hash: str) -> bool:

    import hmac, base64

    if not stored_hash or not pin:

        return False

    normalized = pin.translate(str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")).strip()

    try:

        if stored_hash.startswith('pbkdf2:sha256:'):

            parts = stored_hash.split('$')

            if len(parts) != 3:

                return False

            iterations = int(parts[0].split(':')[2])

            salt_b64 = parts[1] + '=' * (-len(parts[1]) % 4)

            key_b64 = parts[2] + '=' * (-len(parts[2]) % 4)

            salt = base64.b64decode(salt_b64)

            expected = base64.b64decode(key_b64)

            actual = hashlib.pbkdf2_hmac('sha256', normalized.encode('utf-8'), salt, iterations)

            return hmac.compare_digest(actual, expected)

        if len(stored_hash) == 64 and all(c in '0123456789abcdef' for c in stored_hash.lower()):

            expected_bytes = bytes.fromhex(stored_hash)

            actual_bytes = hashlib.sha256(normalized.encode('utf-8')).digest()

            return hmac.compare_digest(actual_bytes, expected_bytes)

    except Exception:

        pass

    return False

def _hash_pin(pin: str) -> str:

    import hashlib, os, base64

    salt = os.urandom(16)

    iterations = 260000

    actual = hashlib.pbkdf2_hmac('sha256', pin.encode('utf-8'), salt, iterations)

    salt_b64 = base64.b64encode(salt).decode('utf-8').rstrip('=')

    hash_b64 = base64.b64encode(actual).decode('utf-8').rstrip('=')

    return f"pbkdf2:sha256:{iterations}${salt_b64}${hash_b64}"

@app.post("/")

async def login_submit(

    request: Request,

    email: str = Form(...),

    password: str = Form(...),

    case_number: str = Form(None),

    db: Session = Depends(get_db)

):

    import asyncio

    import time

    client_ip = request.client.host if request.client else "unknown"

    now = time.time()

    if is_rate_limited(client_ip, "login_form", max_attempts=15, window_seconds=900):

        return templates.TemplateResponse(

            request=request, name="login.html",

            context={"error": "تم حظر عنوان الـ IP مؤقتاً بسبب كثرة المحاولات الخاطئة. يرجى الانتظار 15 دقيقة."}

        )

    user = db.query(AccessProfiles).filter(

        (AccessProfiles.email == email) |

        (AccessProfiles.phone == email) |

        (AccessProfiles.username == email)

    ).first()

    if user:

        if user.is_active == 0:

            return templates.TemplateResponse(

                request=request,

                name="login.html",

                context={"error": "هذا الحساب موقوف. يرجى مراجعة إدارة المكتب."}

            )

        # تحقق من حالة المكتب

        office = db.query(LawOffices).filter(LawOffices.id == user.office_id).first() if user.office_id else None

        if office and office.is_active == 0:

            return templates.TemplateResponse(

                request=request,

                name="login.html",

                context={"error": "مكتب المحاماة الخاص بك موقوف حالياً من قبل إدارة المنصة. يرجى التواصل مع الدعم الفني."}

            )

        if login_lockout_active(user, db):

            return templates.TemplateResponse(

                request=request,

                name="login.html",

                context={"error": "تم إيقاف تسجيل الدخول مؤقتاً بسبب كثرة المحاولات. حاول لاحقاً."}

            )

        if user.role == 'موكل':

            if not case_number or user.case_number != case_number:

                # نسجل محاولة خاطئة لتجنب التخمين

                record_login_failure(user, db)

                return templates.TemplateResponse(

                    request=request,

                    name="login.html",

                    context={"error": "رقم القضية غير مطابق للبيانات، يرجى التأكد والمحاولة مرة أخرى."}

                )

        if _verify_pin(password, user.access_pin_hash):

            user.failed_attempts = 0
            user.locked_until = None

            db.commit()

            # Check if 2FA is enabled for this user (1 indicates enabled)

            if getattr(user, "is_2fa_enabled", 0) == 1:
                temp_token = str(uuid.uuid4())
                
                # [SECURITY FIX MED-01] تخزين جلسة التحقق المؤقتة بقاعدة البيانات بدلاً من الذاكرة لبيئة stateless
                expires = datetime.now(timezone.utc) + timedelta(minutes=5)
                new_token = AuthVerificationTokens(
                    user_id=user.id,
                    token_hash=temp_token,
                    token_type="web_2fa_session",
                    expires_at=expires.strftime("%Y-%m-%d %H:%M:%S")
                )
                db.add(new_token)
                db.commit()

                otp_code = generate_otp(6)
                store_otp(user.email, otp_code)
                send_otp_email(user.email, otp_code, purpose="2fa")

                app_logger.info(f"LOGIN_2FA_TRIGGERED | user={user.id} | email={user.email}")

                response = RedirectResponse(url="/login-2fa", status_code=303)

                response.set_cookie(

                    key="temp_2fa_token",

                    value=temp_token,

                    httponly=True,

                    max_age=300, # Valid for 5 minutes

                    secure=not (request.url.hostname in ["127.0.0.1", "localhost"]),

                    samesite="Lax"

                )

                return response

            # [SECURITY FIX LOW-01] تدوير الجلسة بتعطيل الجلسات السابقة النشطة
            db.query(AuthSessions).filter(
                AuthSessions.user_id == user.id,
                AuthSessions.is_active == 1
            ).update({"is_active": 0})
            db.commit()

            token = str(uuid.uuid4())

            expires = datetime.now(timezone.utc) + timedelta(days=7)

            new_session = AuthSessions(

                session_token=hash_session_token(token),

                user_id=user.id,

                is_active=1,

                expires_at=expires.strftime("%Y-%m-%d %H:%M:%S")

            )

            db.add(new_session)

            db.commit()

            app_logger.info(f"LOGIN_OK | user={user.id} | role={user.role} | office={user.office_id}")

            is_secure = not (request.url.hostname in ["127.0.0.1", "localhost"])

            target_url = "/dashboard"
            if user.role == "موكل":
                target_url = "/client-portal"

            response = RedirectResponse(url=target_url, status_code=303)

            response.set_cookie(
                key="session_token",

                value=token,

                httponly=True,

                max_age=7*24*3600,

                secure=is_secure,

                samesite="Lax"

            )

            return response

        else:

            locked = record_login_failure(user, db)

            record_attempt(client_ip, "login_form")

            app_logger.warning(f"LOGIN_FAIL | user={user.id} | attempts={user.failed_attempts}")

            return templates.TemplateResponse(

                request=request,

                name="login.html",

                context={"error": "تم إيقاف تسجيل الدخول مؤقتاً. حاول بعد 15 دقيقة." if locked else "البريد الإلكتروني أو كلمة المرور غير صحيحة."}

            )

    else:

        # ── ثغرة 4 مُصلحة: تأخير وهمي لمنع User Enumeration عبر قياس سرعة الاستجابة ──

        await asyncio.sleep(0.3)

        record_attempt(client_ip, "login_form")

        app_logger.warning(f"LOGIN_FAIL | user_not_found | input={email[:20]}")

        return templates.TemplateResponse(

            request=request,

            name="login.html",

            context={"error": "البريد الإلكتروني أو كلمة المرور غير صحيحة."}

        )

@app.post("/logout")

async def logout(request: Request, db: Session = Depends(get_db)):

    token = request.cookies.get("session_token")

    if token:

        session_record = db.query(AuthSessions).filter(
            AuthSessions.session_token.in_([token, hash_session_token(token)])
        ).first()

        if session_record:

            session_record.is_active = 0

            db.commit()

            app_logger.info(f"LOGOUT | user={session_record.user_id}")

    response = RedirectResponse(url="/", status_code=303)

    response.delete_cookie("session_token")

    return response

@app.get("/login-2fa", response_class=HTMLResponse)

async def login_2fa_page(request: Request, db: Session = Depends(get_db)):

    temp_token = request.cookies.get("temp_2fa_token")
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    db_token = None
    if temp_token:
        db_token = db.query(AuthVerificationTokens).filter(
            AuthVerificationTokens.token_hash == temp_token,
            AuthVerificationTokens.token_type == "web_2fa_session",
            AuthVerificationTokens.expires_at > now_str,
            AuthVerificationTokens.consumed_at.is_(None)
        ).first()

        if not db_token:
            return RedirectResponse(url="/", status_code=303)

    return templates.TemplateResponse(request=request, name="login_2fa.html", context={})

@app.post("/login-2fa")

async def login_2fa_submit(

    request: Request,

    code: str = Form(...),

    db: Session = Depends(get_db)

):

    temp_token = request.cookies.get("temp_2fa_token")
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    db_token = None
    if temp_token:
        db_token = db.query(AuthVerificationTokens).filter(
            AuthVerificationTokens.token_hash == temp_token,
            AuthVerificationTokens.token_type == "web_2fa_session",
            AuthVerificationTokens.expires_at > now_str,
            AuthVerificationTokens.consumed_at.is_(None)
        ).first()

    if not db_token:

        return templates.TemplateResponse(request=request, name="login.html", context={"error": "انتهت صلاحية جلسة التحقق، يرجى تسجيل الدخول مجدداً."})

    user_id = db_token.user_id

    user = db.query(AccessProfiles).filter(AccessProfiles.id == user_id).first()

    if not user:

        return RedirectResponse(url="/", status_code=303)

    if verify_otp(user.email, code.strip()):

        # OTP is valid! Clean up temp session in DB
        db_token.consumed_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        db.commit()

        # [SECURITY FIX LOW-01] تدوير الجلسة بتعطيل الجلسات السابقة النشطة للمستخدم
        db.query(AuthSessions).filter(
            AuthSessions.user_id == user.id,
            AuthSessions.is_active == 1
        ).update({"is_active": 0})
        db.commit()

        # Issue real session token

        token = str(uuid.uuid4())

        expires = datetime.now(timezone.utc) + timedelta(days=7)

        new_session = AuthSessions(

            session_token=hash_session_token(token),

            user_id=user.id,

            is_active=1,

            expires_at=expires.strftime("%Y-%m-%d %H:%M:%S")

        )

        db.add(new_session)

        db.commit()

        app_logger.info(f"LOGIN_OK_2FA | user={user.id} | role={user.role} | office={user.office_id}")

        # Enforce secure cookies dynamically based on hostname

        is_secure = not (request.url.hostname in ["127.0.0.1", "localhost"])

        target_url = "/dashboard"
        if user.role == "موكل":
            target_url = "/client-portal"

        response = RedirectResponse(url=target_url, status_code=303)

        response.delete_cookie("temp_2fa_token")

        response.set_cookie(

            key="session_token",

            value=token,

            httponly=True,

            max_age=7*24*3600,

            secure=is_secure,

            samesite="Lax"

        )

        return response

    else:
        db_token.attempts += 1
        if db_token.attempts >= 5:
            db_token.consumed_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        db.commit()
        return templates.TemplateResponse(

            request=request,

            name="login_2fa.html",

            context={"error": "رمز التحقق الثنائي غير صحيح أو منتهي الصلاحية."}

        )

@app.post("/settings/toggle-2fa")

async def toggle_2fa(

    request: Request,

    enabled: int = Form(...),

    db: Session = Depends(get_db),

    user: AccessProfiles = Depends(get_current_user)

):

    if not user:

        return RedirectResponse(url="/", status_code=303)

    user.is_2fa_enabled = 1 if enabled == 1 else 0

    db.commit()

    return RedirectResponse(url="/settings", status_code=303)

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(request: Request, db: Session = Depends(get_db), user: AccessProfiles = Depends(get_current_user)):
    if not user:
        return RedirectResponse(url="/", status_code=303)
    try:
        # ── بوابة الموكلين (Client Portal) ──
        if user.role == 'موكل':
            client_records = db.query(LawClients).filter(
                (LawClients.phone == user.phone) | (LawClients.email == user.email)
            ).all()
            case_ids = [c.case_id for c in client_records if c.case_id]
            my_cases = db.query(LawCases).filter(LawCases.id.in_(case_ids), LawCases.is_deleted == 0).all() if case_ids else []
            my_hearings = db.query(LawHearings).filter(
                LawHearings.case_id.in_(case_ids),
                LawHearings.show_in_client_portal == 1,
                LawHearings.is_deleted == 0
            ).order_by(LawHearings.hearing_at.asc()).limit(5).all() if case_ids else []
            return templates.TemplateResponse(
                request=request, name="client_portal.html",
                context={"user": user, "my_cases": my_cases, "my_hearings": my_hearings, "active_page": "dashboard"}
            )

        # ── لوحة تحكم المحامين والمدراء التنفيذية (Enterprise Legal Dashboard) ──
        office_id = user.office_id
        is_restricted_lawyer = (user.role in ['محامي', 'محامٍ'] and getattr(user, 'can_view_all_cases', 1) == 0)

        # 1. القضايا (Cases Base Query)
        cases_query = db.query(LawCases).filter(LawCases.office_id == office_id, LawCases.is_deleted == 0)
        if is_restricted_lawyer:
            cases_query = cases_query.filter(LawCases.lead_lawyer_id == user.id)

        all_my_cases = cases_query.all()
        accessible_case_ids = [c.id for c in all_my_cases]
        total_cases = len(all_my_cases)

        # تفصيل حالات القضايا
        case_status_counts = {
            "open": sum(1 for c in all_my_cases if c.status_key in ['open', 'مفتوحة', 'جديدة', 'new']),
            "awaiting_hearing": sum(1 for c in all_my_cases if c.status_key in ['awaiting_hearing', 'بانتظار جلسة', 'قيد المرافعة']),
            "awaiting_judgment": sum(1 for c in all_my_cases if c.status_key in ['awaiting_judgment', 'بانتظار الحكم']),
            "closed": sum(1 for c in all_my_cases if c.status_key in ['closed', 'مغلقة', 'منتهية', 'judged'])
        }

        # 2. الجلسات القضائية القادمة (Upcoming Hearings)
        hearings_query = db.query(LawHearings).filter(
            LawHearings.office_id == office_id,
            LawHearings.is_deleted == 0
        )
        if is_restricted_lawyer:
            hearings_query = hearings_query.filter(LawHearings.case_id.in_(accessible_case_ids) if accessible_case_ids else LawHearings.case_id == -1)

        upcoming_hearings = hearings_query.filter(
            LawHearings.status_key.in_(['pending', 'قادمة'])
        ).order_by(LawHearings.hearing_at.asc()).limit(6).all()
        upcoming_hearings_count = hearings_query.filter(LawHearings.status_key.in_(['pending', 'قادمة'])).count()

        # 3. المهام المعلقة والأولويات (My Pending Tasks)
        tasks_query = db.query(LawTasks).filter(
            LawTasks.assignee_user_id == user.id,
            LawTasks.status_key.in_(['pending', 'in_progress'])
        )
        my_tasks = tasks_query.order_by(LawTasks.priority_level.asc(), LawTasks.due_at.asc()).limit(6).all()
        pending_tasks_count = tasks_query.count()

        # 4. المهل القضائية ومواعيد الطعن العاجلة (Urgent Limitations & Deadlines)
        from database.models import LawLimitations
        limitations_query = db.query(LawLimitations).filter(
            LawLimitations.office_id == office_id,
            LawLimitations.is_deleted == 0,
            LawLimitations.status_key == 'active'
        )
        if is_restricted_lawyer:
            limitations_query = limitations_query.filter(LawLimitations.case_id.in_(accessible_case_ids) if accessible_case_ids else LawLimitations.case_id == -1)

        urgent_limitations = limitations_query.order_by(LawLimitations.due_date.asc()).limit(4).all()
        active_limitations_count = limitations_query.count()

        # 5. إجمالي الموكلين والمستندات
        total_clients = db.query(LawClients).filter(LawClients.office_id == office_id).count()
        total_docs = db.query(LawDocuments).filter(LawDocuments.office_id == office_id, LawDocuments.is_deleted == 0).count()

        # 6. سجل آخر الأنشطة في المكتب (Recent Activity Stream)
        from database.models import LawAuditLog
        recent_activities = db.query(LawAuditLog).filter(
            LawAuditLog.office_id == office_id
        ).order_by(LawAuditLog.created_at.desc()).limit(5).all()

        return templates.TemplateResponse(
            request=request,
            name="dashboard.html",
            context={
                "user": user,
                "active_page": "dashboard",
                "total_cases": total_cases,
                "total_clients": total_clients,
                "total_docs": total_docs,
                "pending_tasks_count": pending_tasks_count,
                "upcoming_hearings_count": upcoming_hearings_count,
                "active_limitations_count": active_limitations_count,
                "case_status_counts": case_status_counts,
                "my_tasks": my_tasks,
                "upcoming_hearings": upcoming_hearings,
                "urgent_limitations": urgent_limitations,
                "recent_activities": recent_activities
            }
        )
    except Exception as e:
        import traceback
        print(f"[Dashboard Error] {traceback.format_exc()}")
        if user.role == 'موكل':
            return templates.TemplateResponse(request=request, name="client_portal.html", context={"user": user, "my_cases": [], "my_hearings": [], "active_page": "dashboard"})
        return templates.TemplateResponse(
            request=request,
            name="dashboard.html",
            context={
                "user": user,
                "active_page": "dashboard",
                "total_cases": 0,
                "total_clients": 0,
                "total_docs": 0,
                "pending_tasks_count": 0,
                "upcoming_hearings_count": 0,
                "active_limitations_count": 0,
                "case_status_counts": {"open": 0, "awaiting_hearing": 0, "awaiting_judgment": 0, "closed": 0},
                "my_tasks": [],
                "upcoming_hearings": [],
                "urgent_limitations": [],
                "recent_activities": []
            }
        )

@app.get("/api/case-numbers")

async def get_case_numbers(db: Session = Depends(get_db), user: AccessProfiles = Depends(get_current_user)):

    if not user:

        return _JSONResponse([])

    office_id = user.office_id

    query = db.query(LawCases.case_number).filter(LawCases.office_id == office_id, LawCases.is_deleted == 0)

    if user.role in ['محامي', 'محامٍ'] and user.can_view_all_cases == 0:

        query = query.filter(LawCases.lead_lawyer_id == user.id)

    case_numbers = [c[0] for c in query.all() if c[0]]

    return _JSONResponse(case_numbers)

@app.get("/clients", response_class=HTMLResponse)
async def clients_page(request: Request, db: Session = Depends(get_db), user: AccessProfiles = Depends(get_current_user)):
    if not user:
        return RedirectResponse(url="/", status_code=303)
    if not check_user_permission(user, 'clients', 'view'):
        raise HTTPException(status_code=403, detail="غير مصرح لك بدخول قسم الموكلين")

    try:
        office_id = user.office_id
        clients = db.query(LawClients).filter(
            LawClients.office_id == office_id,
            LawClients.is_deleted == 0
        ).order_by(LawClients.id.desc()).all()

        # جلب قضايا المكتب لربطها في نافذة إضافة الموكل
        cases = db.query(LawCases).filter(
            LawCases.office_id == office_id,
            LawCases.is_deleted == 0
        ).order_by(LawCases.case_number.asc()).all()

        # إحصائيات الموكلين
        total_clients = len(clients)
        companies_count = sum(1 for c in clients if getattr(c, 'client_type', 'individual') in ['company', 'شركة', 'مؤسسة'])
        individuals_count = total_clients - companies_count
        portal_active_count = sum(1 for c in clients if getattr(c, 'portal_access', 1) == 1 and c.user_id)

        stats = {
            "total": total_clients,
            "companies": companies_count,
            "individuals": individuals_count,
            "portal_active": portal_active_count
        }

        return templates.TemplateResponse(
            request=request,
            name="clients.html",
            context={
                "user": user,
                "clients": clients,
                "cases": cases,
                "stats": stats,
                "active_page": "clients"
            }
        )
    except Exception:
        import traceback
        return _safe_error(traceback.format_exc())

@app.post("/clients/add")
async def add_client(
    request: Request,
    name: str = Form(...),
    client_type: str = Form("individual"),
    username: str = Form(None),
    password: str = Form(None),
    case_id: Optional[int] = Form(None),
    case_number: Optional[str] = Form(None),
    phone: str = Form(None),
    alt_phone: str = Form(None),
    national_id: str = Form(None),
    cr_number: str = Form(None),
    legal_rep_name: str = Form(None),
    email: str = Form(None),
    city: str = Form(None),
    address: str = Form(None),
    notes: str = Form(None),
    portal_access: int = Form(1),
    db: Session = Depends(get_db),
    user: AccessProfiles = Depends(get_current_user)
):
    if not user:
        return RedirectResponse(url="/", status_code=303)
    if not check_user_permission(user, 'clients', 'add'):
        raise HTTPException(status_code=403, detail="غير مصرح لك بإضافة موكل")

    if not name.strip() or len(name) > 200:
        return HTMLResponse(content="اسم الموكل غير صالح.", status_code=400)
    if not user.office_id:
        raise HTTPException(status_code=403, detail="الحساب غير مرتبط بمكتب")
    office_id = user.office_id

    # معالجة القضية المرتبطة
    final_case_number = case_number
    if case_id:
        target_case = db.query(LawCases).filter(LawCases.id == case_id, LawCases.office_id == office_id).first()
        if target_case and not final_case_number:
            final_case_number = target_case.case_number

    # إنشاء اسم مستخدم تلقائي إذا لم يتم تحديده وكان مطلوباً الدخول للبوابة
    if not username or not username.strip():
        username = f"cli_{secrets.token_hex(4)}"
    else:
        username = username.strip()

    existing = db.query(AccessProfiles).filter(AccessProfiles.username == username).first()
    if existing:
        username = f"{username}_{secrets.token_hex(2)}"

    new_client = LawClients(
        office_id=office_id,
        name=name.strip(),
        client_type=client_type,
        case_id=case_id,
        case_number=final_case_number,
        phone=phone.strip() if phone else None,
        alt_phone=alt_phone.strip() if alt_phone else None,
        national_id=national_id.strip() if national_id else None,
        cr_number=cr_number.strip() if cr_number else None,
        legal_rep_name=legal_rep_name.strip() if legal_rep_name else None,
        email=email.strip() if email else None,
        city=city.strip() if city else None,
        address=address.strip() if address else None,
        notes=notes.strip() if notes else None,
        username=username,
        portal_access=portal_access
    )
    db.add(new_client)

    # إنشاء حساب دخول للموكل إذا كان مطلوباً
    if portal_access == 1:
        client_pass = password.strip() if password and len(password.strip()) >= 8 else secrets.token_urlsafe(10)
        target_email = email.strip() if email else f"{username}@client.local"
        existing_profile = None
        if target_email or phone:
            conds = []
            if target_email:
                conds.append(AccessProfiles.email == target_email)
            if phone and phone.strip():
                conds.append(AccessProfiles.phone == phone.strip())
            from sqlalchemy import or_
            existing_profile = db.query(AccessProfiles).filter(or_(*conds)).first()

        if existing_profile and existing_profile.role == 'موكل':
            new_client.user_id = existing_profile.id
        else:
            if db.query(AccessProfiles).filter(AccessProfiles.email == target_email).first():
                target_email = f"{username}_{secrets.token_hex(2)}@client.local"
            new_user = AccessProfiles(
                name=name.strip(),
                username=username,
                email=target_email,
                phone=phone.strip() if phone else username,
                case_number=final_case_number or "",
                access_pin_hash=_hash_pin(client_pass),
                role='موكل',
                office_id=office_id,
                is_active=1,
                email_verified=1,
                state="active"
            )
            db.add(new_user)
            db.flush()
            new_client.user_id = new_user.id

    db.commit()
    return RedirectResponse(url="/clients", status_code=303)

@app.post("/clients/edit")
async def edit_client(
    request: Request,
    client_id: int = Form(...),
    name: str = Form(...),
    client_type: str = Form("individual"),
    username: str = Form(None),
    password: str = Form(""),
    case_id: Optional[int] = Form(None),
    case_number: Optional[str] = Form(None),
    phone: str = Form(None),
    alt_phone: str = Form(None),
    national_id: str = Form(None),
    cr_number: str = Form(None),
    legal_rep_name: str = Form(None),
    email: str = Form(None),
    city: str = Form(None),
    address: str = Form(None),
    notes: str = Form(None),
    portal_access: int = Form(1),
    db: Session = Depends(get_db),
    user: AccessProfiles = Depends(get_current_user)
):
    if not user:
        return RedirectResponse(url="/", status_code=303)
    if not check_user_permission(user, 'clients', 'edit'):
        raise HTTPException(status_code=403, detail="غير مصرح لك بتعديل بيانات موكل")

    if not user.office_id:
        raise HTTPException(status_code=403, detail="الحساب غير مرتبط بمكتب")
    office_id = user.office_id

    client = db.query(LawClients).filter(LawClients.id == client_id, LawClients.office_id == office_id).first()
    if client:
        client.name = name.strip()
        client.client_type = client_type
        if case_id:
            client.case_id = case_id
        if case_number:
            client.case_number = case_number
        client.phone = phone.strip() if phone else None
        client.alt_phone = alt_phone.strip() if alt_phone else None
        client.national_id = national_id.strip() if national_id else None
        client.cr_number = cr_number.strip() if cr_number else None
        client.legal_rep_name = legal_rep_name.strip() if legal_rep_name else None
        client.email = email.strip() if email else None
        client.city = city.strip() if city else None
        client.address = address.strip() if address else None
        client.notes = notes.strip() if notes else None
        client.portal_access = portal_access

        # تحديث حساب المستخدم المرتبط
        if client.user_id:
            client_user = db.query(AccessProfiles).filter(AccessProfiles.id == client.user_id, AccessProfiles.office_id == office_id).first()
            if client_user:
                client_user.name = name.strip()
                if email:
                    client_user.email = email.strip()
                if phone:
                    client_user.phone = phone.strip()
                if password and len(password.strip()) >= 8:
                    client_user.access_pin_hash = _hash_pin(password.strip())
                client_user.is_active = portal_access
        db.commit()

    return RedirectResponse(url="/clients", status_code=303)


@app.post("/clients/delete")
async def delete_client(
    request: Request,
    client_id: int = Form(...),
    db: Session = Depends(get_db),
    user: AccessProfiles = Depends(get_current_user)
):
    """حذف موكل بأمان (Soft Delete)"""
    if not user:
        return RedirectResponse(url="/", status_code=303)
    if not check_user_permission(user, 'clients', 'delete'):
        raise HTTPException(status_code=403, detail="غير مصرح لك بحذف موكل")
    office_id = user.office_id

    client = db.query(LawClients).filter(LawClients.id == client_id, LawClients.office_id == office_id).first()
    if client:
        client.is_deleted = 1
        if client.user_id:
            client_user = db.query(AccessProfiles).filter(AccessProfiles.id == client.user_id, AccessProfiles.office_id == office_id).first()
            if client_user:
                client_user.is_active = 0
        db.commit()

    return RedirectResponse(url="/clients", status_code=303)

@app.get("/cases", response_class=HTMLResponse)

async def cases_page(request: Request, db: Session = Depends(get_db), user: AccessProfiles = Depends(get_current_user)):

    if not user:

        return RedirectResponse(url="/", status_code=303)

    if not check_user_permission(user, 'cases', 'view'):

        raise HTTPException(status_code=403, detail="غير مصرح لك بدخول قسم القضايا")

    try:

        office_id = user.office_id

        query = db.query(LawCases).filter(LawCases.office_id == office_id, LawCases.is_deleted == 0)

        # تقييد المحامي برؤية قضاياه فقط

        if user.role in ['محامي', 'محامٍ']:

            query = query.filter(LawCases.lead_lawyer_id == user.id)

        cases = query.order_by(LawCases.created_at.desc()).all()

        visible_case_ids = [case.id for case in cases]
        clients = db.query(LawClients).filter(
            LawClients.office_id == office_id,
            LawClients.case_id.in_(visible_case_ids) if visible_case_ids else LawClients.id == -1,
        ).all()

        lawyers = db.query(AccessProfiles).filter(AccessProfiles.office_id == office_id, AccessProfiles.role != "موكل").all()

        # جلب القيم المرجعية المخصصة للمكتب (إن وجدت)
        from database.models import LawReferenceData
        custom_ref_data = db.query(LawReferenceData).filter(LawReferenceData.office_id == office_id).all()
        custom_statuses = [r.ref_name for r in custom_ref_data if r.ref_type in ['case_status', 'حالة_قضية', 'status']]
        custom_levels = [r.ref_name for r in custom_ref_data if r.ref_type in ['litigation_level', 'درجة_تقاضي', 'litigation']]

        return templates.TemplateResponse(

            request=request,

            name="cases.html",

            context={
                "user": user, 
                "cases": cases, 
                "clients": clients, 
                "lawyers": lawyers, 
                "custom_statuses": custom_statuses,
                "custom_levels": custom_levels,
                "active_page": "cases"
            }

        )

    except Exception as e:

        import traceback

        return _safe_error(traceback.format_exc())

@app.post("/cases/add")

async def add_case(

    request: Request,

    title: str = Form(...),

    case_number: str = Form(...),

    client_id: int = Form(...),

    lead_lawyer_id: int = Form(None),

    case_type_key: str = Form("civil"),

    status_key: str = Form("new"),

    litigation_level_key: str = Form("first_instance"),

    court_name: str = Form(None),

    court_case_number: str = Form(None),

    judgment_number: str = Form(None),

    judgment_date: str = Form(None),

    appeal_status: str = Form(None),

    stage_start_date: str = Form(None),

    outcome_key: str = Form("not_determined"),

    db: Session = Depends(get_db),

    user: AccessProfiles = Depends(get_current_user)

):

    if not user:

        return RedirectResponse(url="/", status_code=303)

    if not check_user_permission(user, 'cases', 'add'):

        raise HTTPException(status_code=403, detail="غير مصرح لك بإضافة قضية")

    office = db.query(LawOffices).first()

    if not office:

        office = LawOffices(name="المكتب الرئيسي", status_key="active")

        db.add(office)

        db.commit()

        db.refresh(office)

    office_id = user.office_id if user.office_id else office.id

    new_case = LawCases(

        title=title,

        case_number=case_number,

        case_type_key=case_type_key,

        status_key=status_key,

        litigation_level_key=litigation_level_key,

        court_name=court_name,

        court_case_number=court_case_number,

        judgment_number=judgment_number,

        judgment_date=judgment_date,

        appeal_status=appeal_status,

        stage_start_date=stage_start_date,

        outcome_key=outcome_key,

        lead_lawyer_id=lead_lawyer_id,

        created_by_user_id=user.id,

        office_id=office_id

    )

    db.add(new_case)

    db.commit()

    db.refresh(new_case)

    client = db.query(LawClients).filter(LawClients.id == client_id, LawClients.office_id == office_id).first()

    if client:

        client.case_id = new_case.id

        client.case_number = new_case.case_number

        db.commit()

    return RedirectResponse(url="/cases", status_code=303)

@app.get("/cases/export_report", response_class=HTMLResponse)

async def export_case_report(

    request: Request,

    case_number: str = None,

    case_title: str = None,

    start_date: str = None,

    end_date: str = None,

    db: Session = Depends(get_db),

    user: AccessProfiles = Depends(get_current_user)

):

    if not user:

        return RedirectResponse(url="/", status_code=303)

    office_id = user.office_id

    query = db.query(LawCases).filter(LawCases.office_id == office_id, LawCases.is_deleted == 0)

    if user.role in ['محامي', 'محامٍ'] and user.can_view_all_cases == 0:

        query = query.filter(LawCases.lead_lawyer_id == user.id)

    if case_number:

        query = query.filter(LawCases.case_number.like(f"%{str(case_number).replace('%', '').replace('_', '')}%"))

    elif case_title:

        query = query.filter(LawCases.title.like(f"%{str(case_title).replace('%', '').replace('_', '')}%"))

    if start_date:

        query = query.filter(LawCases.created_at >= f"{start_date} 00:00:00")

    if end_date:

        query = query.filter(LawCases.created_at <= f"{end_date} 23:59:59")

    cases_result = query.all()

    cases_data = []

    for c in cases_result:

        h_query = db.query(LawHearings).filter(LawHearings.case_id == c.id)

        t_query = db.query(LawTasks).filter(LawTasks.case_id == c.id)

        d_query = db.query(LawDocuments).filter(LawDocuments.case_id == c.id)

        if start_date:

            h_query = h_query.filter(LawHearings.hearing_at >= f"{start_date}")

            t_query = t_query.filter(LawTasks.created_at >= f"{start_date} 00:00:00")

            d_query = d_query.filter(LawDocuments.created_at >= f"{start_date} 00:00:00")

        if end_date:

            h_query = h_query.filter(LawHearings.hearing_at <= f"{end_date} 23:59:59")

            t_query = t_query.filter(LawTasks.created_at <= f"{end_date} 23:59:59")

            d_query = d_query.filter(LawDocuments.created_at <= f"{end_date} 23:59:59")

        cases_data.append({

            "case": c,

            "hearings": h_query.all(),

            "tasks": t_query.all(),

            "documents": d_query.all()

        })

    office = db.query(LawOffices).filter(LawOffices.id == office_id).first()

    return templates.TemplateResponse(

        request=request,

        name="case_report.html",

        context={

            "user": user,

            "office": office,

            "cases_data": cases_data,

            "start_date": start_date,

            "end_date": end_date,

            "is_single": bool(case_number or case_title)

        }

    )

@app.get("/cases/{case_id}", response_class=HTMLResponse)

async def case_details_page(case_id: int, request: Request, db: Session = Depends(get_db), user: AccessProfiles = Depends(get_current_user)):

    if not user:

        return RedirectResponse(url="/", status_code=303)

    try:

        office_id = user.office_id

        case = db.query(LawCases).filter(LawCases.id == case_id, LawCases.office_id == office_id).first()

        if not case:

            return HTMLResponse(content="القضية غير موجودة أو لا تملك صلاحية الوصول لها", status_code=404)

        # منع المحامي من دخول قضية غير تابعة له

        if user.role in ['محامي', 'محامٍ'] and case.lead_lawyer_id != user.id:

            raise HTTPException(status_code=403, detail="غير مصرح لك بالدخول لهذه القضية")

        hearings = db.query(LawHearings).filter(LawHearings.case_id == case_id).order_by(LawHearings.hearing_at.desc()).all()

        lawyer = db.query(AccessProfiles).filter(AccessProfiles.id == case.lead_lawyer_id).first() if case.lead_lawyer_id else None

        clients = db.query(LawClients).filter(
            LawClients.office_id == office_id,
            LawClients.case_id == case.id,
        ).all()

        lawyers = db.query(AccessProfiles).filter(AccessProfiles.role.in_(['محامٍ', 'مدير', 'مدير المكتب']), AccessProfiles.office_id == office_id).all()

        documents = db.query(LawDocuments).filter(LawDocuments.case_id == case_id).order_by(LawDocuments.created_at.desc()).all()

        return templates.TemplateResponse(

            request=request,

            name="case_details.html",

            context={"user": user, "case": case, "hearings": hearings, "lawyer": lawyer, "clients": clients, "lawyers": lawyers, "documents": documents, "active_page": "cases"}

        )

    except Exception as e:

        import traceback

        return _safe_error(traceback.format_exc())

@app.post("/cases/{case_id}/edit")

async def edit_case(

    case_id: int,

    request: Request,

    title: str = Form(...),

    case_number: str = Form(...),

    client_id: int = Form(...),

    lead_lawyer_id: int = Form(None),

    case_type_key: str = Form(None),

    status_key: str = Form("new"),

    litigation_level_key: str = Form(None),

    court_name: str = Form(None),

    court_case_number: str = Form(None),

    judgment_number: str = Form(None),

    judgment_date: str = Form(None),

    appeal_status: str = Form(None),

    stage_start_date: str = Form(None),

    outcome_key: str = Form(None),

    db: Session = Depends(get_db),

    user: AccessProfiles = Depends(get_current_user)

):

    if not user:

        return RedirectResponse(url="/", status_code=303)

    if not check_user_permission(user, 'cases', 'edit'):

        raise HTTPException(status_code=403, detail="غير مصرح لك بتعديل قضية")

    office_id = user.office_id

    case = db.query(LawCases).filter(LawCases.id == case_id, LawCases.office_id == office_id).first()

    if user.role in ['محامي', 'محامٍ'] and case and case.lead_lawyer_id != user.id:

        raise HTTPException(status_code=403, detail="غير مصرح لك بتعديل هذه القضية")

    if case:

        case.title = title

        case.case_number = case_number

        case.lead_lawyer_id = lead_lawyer_id

        if case_type_key:
            case.case_type_key = case_type_key

        case.status_key = status_key

        if litigation_level_key:
            case.litigation_level_key = litigation_level_key

        if court_name is not None:
            case.court_name = court_name

        if court_case_number is not None:
            case.court_case_number = court_case_number

        if judgment_number is not None:
            case.judgment_number = judgment_number

        if judgment_date is not None:
            case.judgment_date = judgment_date

        if appeal_status is not None:
            case.appeal_status = appeal_status

        if stage_start_date is not None:
            case.stage_start_date = stage_start_date

        if outcome_key is not None:
            case.outcome_key = outcome_key

        db.commit()

        # Check if client was changed/updated

        client = db.query(LawClients).filter(LawClients.id == client_id, LawClients.office_id == office_id).first()

        if client and client.case_id != case.id:

            client.case_id = case.id

            client.case_number = case.case_number

            db.commit()

    return RedirectResponse(url=f"/cases/{case_id}", status_code=303)

@app.get("/hearings", response_class=HTMLResponse)

async def hearings_page(
    request: Request, 
    case_id: int = None,
    action: str = None,
    db: Session = Depends(get_db), 
    user: AccessProfiles = Depends(get_current_user)
):

    if not user:

        return RedirectResponse(url="/", status_code=303)

    if not check_user_permission(user, 'hearings', 'view'):

        raise HTTPException(status_code=403, detail="غير مصرح لك بدخول قسم الجلسات")

    try:

        office_id = user.office_id

        cases_query = db.query(LawCases).filter(LawCases.office_id == office_id, LawCases.is_deleted == 0)

        hearings_query = db.query(LawHearings).filter(LawHearings.office_id == office_id)

        if user.role in ['محامي', 'محامٍ']:

            cases_query = cases_query.filter(LawCases.lead_lawyer_id == user.id)

            # Fetch cases IDs to filter hearings

            lawyer_case_ids = [c.id for c in cases_query.all()]

            hearings_query = hearings_query.filter(LawHearings.case_id.in_(lawyer_case_ids) if lawyer_case_ids else LawHearings.case_id == -1)

        hearings = hearings_query.order_by(LawHearings.hearing_at.desc()).all()

        cases = cases_query.all()

        selected_case_id = case_id
        open_new_modal = (action == "new")

        # Serialized cases list for dynamic JS auto-fill
        cases_json = [
            {
                "id": c.id,
                "case_number": c.case_number,
                "title": c.title,
                "court_name": getattr(c, 'court_name', '') or '',
                "court_case_number": getattr(c, 'court_case_number', '') or '',
                "litigation_level_key": getattr(c, 'litigation_level_key', '') or '',
                "client_name": c.law_clients[0].name if c.law_clients else ''
            }
            for c in cases
        ]

        return templates.TemplateResponse(

            request=request,

            name="hearings.html",

            context={
                "user": user, 
                "hearings": hearings, 
                "cases": cases, 
                "cases_json": cases_json,
                "selected_case_id": selected_case_id,
                "open_new_modal": open_new_modal,
                "active_page": "hearings"
            }

        )

    except Exception as e:

        import traceback

        return _safe_error(traceback.format_exc())

@app.post("/hearings/add")

async def add_hearing(

    request: Request,

    case_id: int = Form(...),

    title: str = Form(...),

    hearing_at: str = Form(...),

    next_hearing_date: str = Form(None),

    status_key: str = Form("قادمة"),

    chamber_number: str = Form(None),

    floor_number: str = Form(None),

    show_in_client_portal: int = Form(1),

    attachment: UploadFile = File(None),

    redirect_to_case: str = Form(None),

    # New comprehensive hearing report fields
    report_number: str = Form(None),

    court_name: str = Form(None),

    court_case_number: str = Form(None),

    litigation_level: str = Form(None),

    hearing_time: str = Form(None),

    judge_name: str = Form(None),

    hearing_type: str = Form(None),

    attendees_json: str = Form(None),

    hearing_summary: str = Form(None),

    client_requests: str = Form(None),

    opponent_requests: str = Form(None),

    pleadings_submitted: str = Form(None),

    evidence_submitted: str = Form(None),

    internal_notes: str = Form(None),

    has_court_decision: int = Form(0),

    decision_type: str = Form(None),

    decision_text: str = Form(None),

    has_judgment: int = Form(0),

    judgment_number: str = Form(None),

    judgment_date: str = Form(None),

    post_hearing_actions: str = Form(None),

    has_next_hearing: int = Form(0),

    postponement_reason: str = Form(None),

    next_hearing_requirements: str = Form(None),

    attachments_json: str = Form(None),

    report_status: str = Form("approved"),

    action_type: str = Form("save"), # 'save', 'draft', 'save_and_add_another'

    db: Session = Depends(get_db),

    user: AccessProfiles = Depends(get_current_user)

):

    if not user:

        return RedirectResponse(url="/", status_code=303)

    if not check_user_permission(user, 'hearings', 'add'):

        raise HTTPException(status_code=403, detail="غير مصرح لك بإضافة جلسة")

    # Get user office or default to first

    office_id = user.office_id

    if not office_id:

        first_office = db.query(LawOffices).first()

        office_id = first_office.id if first_office else 1

    # Clean datetime format from HTML5 datetime-local (e.g. 2023-05-10T14:30)

    formatted_hearing_at = hearing_at.replace('T', ' ') if hearing_at else None

    if case_id:

        case = db.query(LawCases).filter(LawCases.id == case_id, LawCases.office_id == office_id).first()

        if not case: raise HTTPException(status_code=403, detail="غير مصرح")

    attachment_path = None
    if attachment and attachment.filename and "".join(c for c in attachment.filename if c.isalnum() or c in ' ._-'):
        import time, shutil
        upload_dir = "static/uploads/hearings"
        os.makedirs(upload_dir, exist_ok=True)
        safe_filename = f"{int(time.time())}_" + "".join(c for c in attachment.filename if c.isalnum() or c in ' ._-')
        attachment_path = f"{upload_dir}/{safe_filename}"
        with open(attachment_path, "wb") as buffer:
            shutil.copyfileobj(attachment.file, buffer)

    # Generate report_number if not provided
    if not report_number:
        import time
        report_number = f"REP-{case_id}-{int(time.time())}"

    effective_report_status = "draft" if action_type == "draft" else report_status

    new_hearing = LawHearings(

        case_id=case_id,

        office_id=office_id,

        title=title,

        hearing_at=formatted_hearing_at,

        next_hearing_date=next_hearing_date,

        status_key=status_key,

        chamber_number=chamber_number,

        floor_number=floor_number,

        show_in_client_portal=1 if str(show_in_client_portal) in ("1", "true", "True") else 0,

        attachment_path=attachment_path,

        report_number=report_number,

        court_name=court_name,

        court_case_number=court_case_number,

        litigation_level=litigation_level,

        hearing_time=hearing_time,

        judge_name=judge_name,

        hearing_type=hearing_type,

        attendees_json=attendees_json,

        hearing_summary=hearing_summary,

        client_requests=client_requests,

        opponent_requests=opponent_requests,

        pleadings_submitted=pleadings_submitted,

        evidence_submitted=evidence_submitted,

        internal_notes=internal_notes,

        has_court_decision=has_court_decision,

        decision_type=decision_type,

        decision_text=decision_text,

        has_judgment=has_judgment,

        judgment_number=judgment_number,

        judgment_date=judgment_date,

        post_hearing_actions=post_hearing_actions,

        has_next_hearing=has_next_hearing,

        postponement_reason=postponement_reason,

        next_hearing_requirements=next_hearing_requirements,

        attachments_json=attachments_json,

        report_status=effective_report_status

    )

    db.add(new_hearing)

    db.commit()

    # Trigger smart workflow rule on hearing creation
    try:
        from core.workflow_engine import trigger_event
        event_data = {
            "hearing_title": new_hearing.title,
            "hearing_at": new_hearing.hearing_at,
            "case_id": new_hearing.case_id
        }
        trigger_event(db, "on_hearing_created", event_data, office_id=office_id)
    except Exception as e:
        print(f"[Workflow Trigger Error] {e}")

    if action_type == "save_and_add_another":
        return RedirectResponse(url=f"/hearings?action=new&case_id={case_id}&msg=saved", status_code=303)

    if redirect_to_case == "true":

        return RedirectResponse(url=f"/cases/{case_id}", status_code=303)

    return RedirectResponse(url="/hearings?msg=saved", status_code=303)

def get_arabic_font():
    candidates = [
        r"C:\Windows\Fonts\arial.ttf",
        r"C:\Windows\Fonts\tahoma.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "static/fonts/Amiri-Regular.ttf"
    ]
    local_font_dir = os.path.join("static", "fonts")
    local_font_path = os.path.join(local_font_dir, "Amiri-Regular.ttf")
    if not any(os.path.exists(p) for p in candidates[:-1]) and not os.path.exists(local_font_path):
        os.makedirs(local_font_dir, exist_ok=True)
        try:
            url = "https://github.com/googlefonts/amiri/raw/main/Amiri-Regular.ttf"
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req) as response, open(local_font_path, 'wb') as out_file:
                out_file.write(response.read())
        except Exception as e:
            pass
    for p in candidates:
        if os.path.exists(p):
            return p
    return None

@app.get("/finance", response_class=HTMLResponse)
async def finance_page(
    request: Request,
    currency: str = "YER",
    db: Session = Depends(get_db),
    user: AccessProfiles = Depends(get_current_user)
):
    if not user:
        return RedirectResponse(url="/", status_code=303)

    if not check_user_permission(user, 'finance', 'view'):

        raise HTTPException(status_code=403, detail="غير مصرح لك بدخول قسم المالية")
    try:
        office_id = user.office_id
        transactions = db.query(LawTransactions).filter(
            LawTransactions.office_id == office_id,
            LawTransactions.is_deleted == 0
        ).order_by(LawTransactions.transaction_at.desc(), LawTransactions.id.desc()).all()

        expenses = db.query(LawExpenses).filter(
            LawExpenses.office_id == office_id,
            LawExpenses.is_deleted == 0
        ).order_by(LawExpenses.expense_at.desc(), LawExpenses.id.desc()).all()

        cases = db.query(LawCases).filter(LawCases.office_id == office_id, LawCases.is_deleted == 0).order_by(LawCases.case_number.asc()).all()
        clients = db.query(LawClients).filter(LawClients.office_id == office_id, LawClients.is_deleted == 0).order_by(LawClients.name.asc()).all()
        clients_map = {c.id: c.name for c in clients}

        # Attach client_name to transactions
        for t in transactions:
            t.client_name = clients_map.get(t.client_id, None) if t.client_id else None

        target_currency = currency.upper() if currency.upper() in ["YER", "SAR", "USD"] else "YER"
        
        yer_to_target = 1.0
        if target_currency == "SAR":
            yer_to_target = 1.0 / 141.0
        elif target_currency == "USD":
            yer_to_target = 1.0 / 535.0

        total_income_yer = sum((t.amount * (t.exchange_rate or 1.0)) for t in transactions)
        total_expenses_yer = sum((e.amount * (e.exchange_rate or 1.0)) for e in expenses)
        total_income = total_income_yer * yer_to_target
        total_expenses = total_expenses_yer * yer_to_target
        net_profit = total_income - total_expenses
        profit_margin = round((net_profit / total_income * 100), 1) if total_income > 0 else 0.0

        stats = {
            "total_income": total_income,
            "total_expenses": total_expenses,
            "net_profit": net_profit,
            "profit_margin": profit_margin,
            "transactions_count": len(transactions),
            "expenses_count": len(expenses)
        }

        return templates.TemplateResponse(
            request=request,
            name="finance.html",
            context={
                "user": user,
                "transactions": transactions,
                "expenses": expenses,
                "cases": cases,
                "clients": clients,
                "active_page": "finance",
                "stats": stats,
                "total_income": total_income,
                "total_expenses": total_expenses,
                "net_profit": net_profit,
                "target_currency": target_currency
            }
        )
    except Exception as e:
        import traceback
        return _safe_error(traceback.format_exc())

@app.get("/finance/invoice/{transaction_id}/pdf")
async def export_invoice_pdf(
    transaction_id: int,
    db: Session = Depends(get_db),
    user: AccessProfiles = Depends(get_current_user)
):
    if not user:
        return RedirectResponse(url="/", status_code=303)
    office_id = user.office_id
    trans = db.query(LawTransactions).filter(
        LawTransactions.id == transaction_id,
        LawTransactions.office_id == office_id
    ).first()
    if not trans:
        raise HTTPException(status_code=404, detail="الفاتورة غير موجودة")

    case_title = "عام"
    client_name = "عميل عام"
    client_phone = "-"
    if trans.client_id:
        client = db.query(LawClients).filter(LawClients.id == trans.client_id, LawClients.office_id == office_id).first()
        if client:
            client_name = getattr(client, 'name', 'عميل عام')
            client_phone = getattr(client, 'phone', '-') or "-"
    if trans.case_id:
        case = db.query(LawCases).filter(LawCases.id == trans.case_id, LawCases.office_id == office_id).first()
        if case:
            case_title = case.title
            if client_name == "عميل عام" and getattr(case, 'client_id', None):
                client = db.query(LawClients).filter(LawClients.id == case.client_id, LawClients.office_id == office_id).first()
                if client:
                    client_name = getattr(client, 'name', 'عميل عام')
                    client_phone = getattr(client, 'phone', '-') or "-"

    temp_dir = tempfile.gettempdir()
    pdf_path = os.path.join(temp_dir, f"invoice_{transaction_id}.pdf")

    font_path = get_arabic_font()
    font_name = "ArabicFont"
    if font_path:
        try:
            pdfmetrics.registerFont(TTFont(font_name, font_path))
        except Exception:
            font_name = "Helvetica"
    else:
        font_name = "Helvetica"

    c = canvas.Canvas(pdf_path, pagesize=A4)
    W, H = A4

    def ar(text: str) -> str:
        if not text:
            return ""
        try:
            reshaped = arabic_reshaper.reshape(text)
            return get_display(reshaped)
        except Exception:
            return text

    # Header Band
    c.setFillColorRGB(0.05, 0.1, 0.2)
    c.rect(0, H - 100, W, 100, fill=1, stroke=0)
    c.setFillColorRGB(0.8, 0.6, 0.2)
    c.rect(0, H - 103, W, 3, fill=1, stroke=0)

    c.setFillColorRGB(1, 1, 1)
    c.setFont(font_name, 22)
    c.drawRightString(W - 40, H - 50, ar("سند قبض أتعاب"))
    c.setFont(font_name, 11)
    c.setFillColorRGB(0.8, 0.9, 1.0)
    c.drawRightString(W - 40, H - 75, ar("منصة LawSaaS لإدارة مكاتب المحاماة"))

    c.setFillColorRGB(1, 1, 1)
    c.setFont(font_name, 10)
    c.drawString(40, H - 45, ar(f"رقم السند: {trans.id}"))
    c.drawString(40, H - 65, ar(f"التاريخ: {trans.transaction_at[:10] if trans.transaction_at else ''}"))

    c.setFillColorRGB(0.1, 0.1, 0.1)

    # Details
    y = H - 150
    c.setFont(font_name, 12)
    c.setFillColorRGB(0.05, 0.1, 0.2)
    c.drawRightString(W - 40, y, ar("بيانات الطرف الأول (المكتب):"))
    c.setFillColorRGB(0.2, 0.2, 0.2)
    c.setFont(font_name, 10.5)
    lawyer_name_val = getattr(user, 'name', '') or getattr(user, 'lawyer_name', '') or "المحامي المسؤول"
    c.drawRightString(W - 50, y - 35, ar(f"المحامي المستلم: {lawyer_name_val}"))

    c.setFont(font_name, 12)
    c.setFillColorRGB(0.05, 0.1, 0.2)
    c.drawString(40, y, ar("بيانات الطرف الثاني (العميل):"))
    c.setFillColorRGB(0.2, 0.2, 0.2)
    c.setFont(font_name, 10.5)
    c.drawString(50, y - 20, ar(f"العميل: {client_name}"))
    c.drawString(50, y - 35, ar(f"الهاتف: {client_phone}"))

    y = y - 70
    c.setStrokeColorRGB(0.8, 0.8, 0.8)
    c.setLineWidth(1)
    c.line(40, y + 10, W - 40, y + 10)

    c.setFont(font_name, 11)
    c.setFillColorRGB(0.1, 0.1, 0.1)
    c.drawRightString(W - 40, y - 5, ar(f"القضية المرتبطة: {case_title}"))

    # Table
    y = y - 40
    c.setFillColorRGB(0.9, 0.9, 0.95)
    c.rect(40, y, W - 80, 25, fill=1, stroke=0)
    c.setFillColorRGB(0.05, 0.1, 0.2)
    c.setFont(font_name, 11)
    c.drawRightString(W - 50, y + 7, ar("البيان"))
    c.drawCentredString(W / 2, y + 7, ar("المبلغ المدفوع"))
    c.drawString(50, y + 7, ar("المعادل بالريال اليمني"))

    y = y - 30
    c.setFillColorRGB(0.98, 0.98, 0.98)
    c.rect(40, y - 5, W - 80, 25, fill=1, stroke=0)
    c.setFillColorRGB(0.1, 0.1, 0.1)
    c.setFont(font_name, 10.5)
    c.drawRightString(W - 50, y, ar(trans.title))
    c.drawCentredString(W / 2, y, ar(f"{trans.amount:,.2f} {trans.currency}"))
    
    eq_val = trans.amount * (trans.exchange_rate or 1.0)
    c.drawString(50, y, ar(f"{eq_val:,.2f} ر.ي"))

    y = y - 25
    c.setStrokeColorRGB(0.05, 0.1, 0.2)
    c.setLineWidth(1.5)
    c.line(40, y, W - 40, y)

    y = y - 30
    c.setFont(font_name, 12)
    c.setFillColorRGB(0.05, 0.1, 0.2)
    c.drawRightString(W - 40, y, ar("إجمالي المبلغ المدفوع:"))
    c.setFont(font_name, 14)
    c.setFillColorRGB(0.1, 0.6, 0.3)
    c.drawRightString(W - 180, y, ar(f"{trans.amount:,.2f} {trans.currency}"))

    # Signatures
    y = y - 100
    c.setFont(font_name, 11)
    c.setFillColorRGB(0.2, 0.2, 0.2)
    c.drawRightString(W - 80, y, ar("توقيع المحامي المستلم:"))
    c.drawString(80, y, ar("توقيع العميل المودع:"))

    y = y - 50
    c.setStrokeColorRGB(0.6, 0.6, 0.6)
    c.setLineWidth(0.5)
    c.line(W - 180, y, W - 40, y)
    c.line(40, y, 180, y)

    # Footer
    c.setFillColorRGB(0.05, 0.1, 0.2)
    c.rect(0, 0, W, 40, fill=1, stroke=0)
    c.setFillColorRGB(0.8, 0.6, 0.2)
    c.rect(0, 40, W, 2, fill=1, stroke=0)

    c.setFont(font_name, 9)
    c.setFillColorRGB(0.8, 0.9, 1.0)
    c.drawCentredString(W / 2, 15, ar("شكراً لثقتكم بنا - منصة LawSaaS لإدارة مكاتب المحاماة"))

    c.showPage()
    c.save()

    return FileResponse(pdf_path, media_type="application/pdf", filename=f"invoice_{transaction_id}.pdf")


@app.post("/finance/add_transaction")
async def add_transaction(
    request: Request,
    title: str = Form(...),
    amount: float = Form(...),
    transaction_at: str = Form(...),
    currency: str = Form("YER"),
    exchange_rate: float = Form(1.0),
    case_id: Optional[int] = Form(None),
    client_id: Optional[int] = Form(None),
    payment_method: Optional[str] = Form("تحويل بنكي"),
    reference_number: Optional[str] = Form(None),
    notes: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    user: AccessProfiles = Depends(get_current_user)
):
    if not user:
        return RedirectResponse(url="/", status_code=303)

    if not check_user_permission(user, 'finance', 'add'):
        raise HTTPException(status_code=403, detail="غير مصرح لك بإضافة إيرادات")

    office_id = user.office_id

    if case_id and case_id > 0:
        case = db.query(LawCases).filter(LawCases.id == case_id, LawCases.office_id == office_id, LawCases.is_deleted == 0).first()
        if not case: raise HTTPException(status_code=403, detail="القضية غير موجودة")
    else:
        case_id = None

    if client_id and client_id > 0:
        client = db.query(LawClients).filter(LawClients.id == client_id, LawClients.office_id == office_id, LawClients.is_deleted == 0).first()
        if not client: client_id = None
    else:
        client_id = None

    # Calculate stored exchange rate relative to YER base (الريال اليمني)
    stored_rate = 1.0
    if currency == 'USD':
        stored_rate = float(exchange_rate or 535.0)
    elif currency == 'SAR':
        stored_rate = float(exchange_rate or 141.0)
    else:
        stored_rate = 1.0

    new_trans = LawTransactions(
        case_id=case_id,
        client_id=client_id,
        office_id=office_id,
        title=title.strip(),
        amount=amount,
        currency=currency,
        exchange_rate=stored_rate,
        transaction_at=transaction_at,
        payment_method=payment_method or "تحويل بنكي",
        reference_number=reference_number or None,
        notes=notes or None,
        status_key="completed",
        is_deleted=0
    )
    db.add(new_trans)
    db.commit()
    return RedirectResponse(url="/finance", status_code=303)

@app.post("/finance/add_expense")
async def add_expense(
    request: Request,
    title: str = Form(...),
    amount: float = Form(...),
    expense_at: str = Form(...),
    currency: str = Form("YER"),
    exchange_rate: float = Form(1.0),
    case_id: Optional[int] = Form(None),
    expense_category: Optional[str] = Form("رسوم قضائية"),
    is_billable: Optional[int] = Form(1),
    payment_method: Optional[str] = Form("تحويل بنكي"),
    notes: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    user: AccessProfiles = Depends(get_current_user)
):
    if not user:
        return RedirectResponse(url="/", status_code=303)

    if not check_user_permission(user, 'finance', 'add'):
        raise HTTPException(status_code=403, detail="غير مصرح لك بإضافة مصروفات")

    office_id = user.office_id

    if case_id and case_id > 0:
        case = db.query(LawCases).filter(LawCases.id == case_id, LawCases.office_id == office_id, LawCases.is_deleted == 0).first()
        if not case: raise HTTPException(status_code=403, detail="القضية غير موجودة")
    else:
        case_id = None

    # Calculate stored exchange rate relative to YER base (الريال اليمني)
    stored_rate = 1.0
    if currency == 'USD':
        stored_rate = float(exchange_rate or 535.0)
    elif currency == 'SAR':
        stored_rate = float(exchange_rate or 141.0)
    else:
        stored_rate = 1.0

    new_expense = LawExpenses(
        case_id=case_id,
        office_id=office_id,
        title=title.strip(),
        amount=amount,
        currency=currency,
        exchange_rate=stored_rate,
        expense_at=expense_at,
        expense_category=expense_category or "رسوم قضائية",
        is_billable=1 if is_billable else 0,
        payment_method=payment_method or "تحويل بنكي",
        notes=notes or None,
        is_deleted=0
    )
    db.add(new_expense)
    db.commit()
    return RedirectResponse(url="/finance", status_code=303)

@app.post("/finance/delete_transaction/{id}")
async def delete_transaction(id: int, db: Session = Depends(get_db), user: AccessProfiles = Depends(get_current_user)):
    if not user: return RedirectResponse(url="/", status_code=303)
    if not check_user_permission(user, 'finance', 'delete'):
        raise HTTPException(status_code=403, detail="غير مصرح")
    t = db.query(LawTransactions).filter(LawTransactions.id == id, LawTransactions.office_id == user.office_id).first()
    if t:
        t.is_deleted = 1
        db.commit()
    return RedirectResponse(url="/finance", status_code=303)

@app.post("/finance/delete_expense/{id}")
async def delete_expense_finance(id: int, db: Session = Depends(get_db), user: AccessProfiles = Depends(get_current_user)):
    if not user: return RedirectResponse(url="/", status_code=303)
    if not check_user_permission(user, 'finance', 'delete'):
        raise HTTPException(status_code=403, detail="غير مصرح")
    e = db.query(LawExpenses).filter(LawExpenses.id == id, LawExpenses.office_id == user.office_id).first()
    if e:
        e.is_deleted = 1
        db.commit()
    return RedirectResponse(url="/finance", status_code=303)

@app.get("/settings", response_class=HTMLResponse)

async def settings_page(request: Request, db: Session = Depends(get_db), user: AccessProfiles = Depends(get_current_user)):

    if not user:

        return RedirectResponse(url="/", status_code=303)

    try:

        office_id = user.office_id

        # فقط مستخدمو نفس المكتب

        users = db.query(AccessProfiles).filter(AccessProfiles.office_id == office_id).all()

        office = db.query(LawOffices).filter(LawOffices.id == office_id).first()

        return templates.TemplateResponse(

            request=request,

            name="settings.html",

            context={"user": user, "users": users, "office": office, "active_page": "settings"}

        )

    except Exception as e:

        import traceback

        return _safe_error(traceback.format_exc())

@app.post("/settings/update_office")

async def update_office(

    request: Request,

    office_id: int = Form(None),

    name: str = Form(...),

    db: Session = Depends(get_db),

    user: AccessProfiles = Depends(get_current_user)

):

    if not user:

        return RedirectResponse(url="/", status_code=303)

    if user.role not in ['مدير', 'مدير المكتب', 'صاحب المكتب']:

        raise HTTPException(status_code=403, detail="غير مصرح لك بتعديل بيانات المكتب")

    office_id_to_update = office_id or user.office_id

    if office_id_to_update:

        office = db.query(LawOffices).filter(LawOffices.id == office_id_to_update).first()

        # نتحقق أن المستخدم ينتمي لهذا المكتب قبل التعديل (أو أنه سوبر آدمن)

        if office and (user.office_id == office.id or user.id == 1):

            office.name = name

            db.commit()

    else:

        office = LawOffices(name=name)

        db.add(office)

        db.commit()

    return RedirectResponse(url="/settings", status_code=303)

@app.post("/settings/add_user")

async def add_user(

    request: Request,

    name: str = Form(...),

    username: str = Form(...),

    phone: str = Form(...),

    email: str = Form(...),

    password: str = Form(...),

    role: str = Form(...),

    db: Session = Depends(get_db),

    user: AccessProfiles = Depends(get_current_user)

):

    if not user:

        return RedirectResponse(url="/", status_code=303)

    if user.role not in ['صاحب المكتب', 'صاحب مكتب', 'مدير المكتب', 'مدير مكتب']:

        raise HTTPException(status_code=403, detail="ليس لديك صلاحية لإضافة مستخدمين")

    if len(password) < 12 or not user.office_id:
        return HTMLResponse(content="كلمة المرور يجب أن تكون 12 حرفاً على الأقل والحساب مرتبطاً بمكتب.", status_code=400)
    office_id = user.office_id

    ALLOWED_OFFICE_ROLES = {'مدير', 'محامي', 'محامٍ', 'سكرتير', 'محاسب', 'موكل'}

    if role not in ALLOWED_OFFICE_ROLES:

        raise HTTPException(status_code=400, detail="دور العضو المختار غير صالح")

    new_user = AccessProfiles(

        name=name,

        username=username,

        phone=phone,

        email=email,

        access_pin_hash=_hash_pin(password),

        role=role,

        office_id=office_id,

        created_by=user.id,

        is_active=1

    )

    db.add(new_user)

    db.commit()

    return RedirectResponse(url="/settings", status_code=303)

# REMOVED DUPLICATE: @app.post("/clients/edit")

async def edit_client(

    request: Request,

    client_id: int = Form(...),

    name: str = Form(...),

    phone: str = Form(...),

    national_id: str = Form(None),

    db: Session = Depends(get_db),

    user: AccessProfiles = Depends(get_current_user)

):

    if not user: return RedirectResponse(url="/", status_code=303)

    office_id = user.office_id

    client = db.query(LawClients).filter(LawClients.id == client_id, LawClients.office_id == office_id).first()

    if client:

        client.name = name

        client.phone = phone

        client.national_id = national_id

        db.commit()

    return RedirectResponse(url="/clients", status_code=303)


@app.get("/api/hearings/{hearing_id}")
async def get_hearing_details(
    hearing_id: int,
    db: Session = Depends(get_db),
    user: AccessProfiles = Depends(get_current_user)
):
    if not user:
        raise HTTPException(status_code=401, detail="غير مصرح")
    office_id = user.office_id
    hearing = db.query(LawHearings).filter(LawHearings.id == hearing_id, LawHearings.office_id == office_id).first()
    if not hearing:
        raise HTTPException(status_code=404, detail="المحضر غير موجود")
    
    # Hide internal notes from non-authorized users (only admin and lawyers)
    can_view_internal = (user.role in ['صاحب المكتب', 'صاحب مكتب', 'مدير المكتب', 'مدير', 'محامي', 'محامٍ'])
    
    return {
        "id": hearing.id,
        "report_number": hearing.report_number or f"REP-{hearing.id}",
        "case_id": hearing.case_id,
        "case_number": hearing.law_case.case_number if hearing.law_case else "",
        "case_title": hearing.law_case.title if hearing.law_case else "",
        "title": hearing.title,
        "hearing_at": hearing.hearing_at,
        "hearing_time": hearing.hearing_time or "",
        "court_name": hearing.court_name or "",
        "court_case_number": hearing.court_case_number or "",
        "litigation_level": hearing.litigation_level or "",
        "judge_name": hearing.judge_name or "",
        "hearing_type": hearing.hearing_type or "",
        "status_key": hearing.status_key,
        "report_status": hearing.report_status or "approved",
        "attendees_json": hearing.attendees_json or "[]",
        "hearing_summary": hearing.hearing_summary or "",
        "client_requests": hearing.client_requests or "",
        "opponent_requests": hearing.opponent_requests or "",
        "pleadings_submitted": hearing.pleadings_submitted or "",
        "evidence_submitted": hearing.evidence_submitted or "",
        "internal_notes": (hearing.internal_notes or "") if can_view_internal else "",
        "has_court_decision": hearing.has_court_decision or 0,
        "decision_type": hearing.decision_type or "",
        "decision_text": hearing.decision_text or "",
        "has_judgment": hearing.has_judgment or 0,
        "judgment_number": hearing.judgment_number or "",
        "judgment_date": hearing.judgment_date or "",
        "post_hearing_actions": hearing.post_hearing_actions or "",
        "has_next_hearing": hearing.has_next_hearing or 0,
        "next_hearing_date": hearing.next_hearing_date or "",
        "postponement_reason": hearing.postponement_reason or "",
        "next_hearing_requirements": hearing.next_hearing_requirements or "",
        "attachments_json": hearing.attachments_json or "[]",
        "attachment_path": hearing.attachment_path or ""
    }

@app.post("/hearings/edit")

async def edit_hearing(

    request: Request,

    hearing_id: int = Form(...),

    title: str = Form(...),

    hearing_at: str = Form(...),

    next_hearing_date: str = Form(None),

    status_key: str = Form(...),

    chamber_number: str = Form(None),

    floor_number: str = Form(None),

    show_in_client_portal: int = Form(1),

    attachment: UploadFile = File(None),

    redirect_to_case: str = Form(None),

    case_id: int = Form(None),

    db: Session = Depends(get_db),

    user: AccessProfiles = Depends(get_current_user)

):

    if not user: return RedirectResponse(url="/", status_code=303)

    if not check_user_permission(user, 'hearings', 'edit'):

        raise HTTPException(status_code=403, detail="غير مصرح لك بتعديل جلسة")

    office_id = user.office_id

    hearing = db.query(LawHearings).filter(LawHearings.id == hearing_id, LawHearings.office_id == office_id).first()

    if hearing:

        hearing.title = title

        hearing.hearing_at = hearing_at.replace('T', ' ') if hearing_at else None

        hearing.next_hearing_date = next_hearing_date

        hearing.status_key = status_key

        hearing.chamber_number = chamber_number

        hearing.floor_number = floor_number

        hearing.show_in_client_portal = 1 if str(show_in_client_portal) in ("1", "true", "True") else 0

        if attachment and attachment.filename and "".join(c for c in attachment.filename if c.isalnum() or c in ' ._-'):
            import time, shutil
            upload_dir = "static/uploads/hearings"
            os.makedirs(upload_dir, exist_ok=True)
            safe_filename = f"{int(time.time())}_" + "".join(c for c in attachment.filename if c.isalnum() or c in ' ._-')
            attachment_path = f"{upload_dir}/{safe_filename}"
            with open(attachment_path, "wb") as buffer:
                shutil.copyfileobj(attachment.file, buffer)
            hearing.attachment_path = attachment_path

        db.commit()

    if redirect_to_case == "true" and case_id:

        return RedirectResponse(url=f"/cases/{case_id}", status_code=303)

    return RedirectResponse(url="/hearings", status_code=303)

# الأدوار المسموح لها بإدارة المستخدمين

_ADMIN_ROLES = {'صاحب المكتب', 'صاحب مكتب', 'مدير المكتب', 'مدير مكتب'}

@app.post("/settings/edit_user")

async def edit_user(

    request: Request,

    user_id: int = Form(...),

    name: str = Form(...),

    phone: str = Form(...),

    email: str = Form(...),

    role: str = Form(...),

    is_active: int = Form(1),

    birth_date: str = Form(None),

    db: Session = Depends(get_db),

    user: AccessProfiles = Depends(get_current_user)

):

    if not user:

        return RedirectResponse(url="/", status_code=303)

    # 🔴 تحقق من الصلاحية — فقط الأدوار الإدارية

    if user.role not in _ADMIN_ROLES:

        app_logger.warning(

            f"SECURITY | edit_user blocked | actor={user.id} role={user.role} target={user_id}"

        )

        return RedirectResponse(url="/settings", status_code=303)

    office_id = user.office_id

    # 🔴 IDOR protection — الهدف يجب أن يكون في نفس المكتب

    target_user = db.query(AccessProfiles).filter(

        AccessProfiles.id == user_id,

        AccessProfiles.office_id == office_id

    ).first()

    if not target_user:

        app_logger.warning(

            f"SECURITY | edit_user: user {user_id} not found in office {office_id} | actor={user.id}"

        )

        return RedirectResponse(url="/settings", status_code=303)

    old_vals = {"name": target_user.name, "phone": target_user.phone,

                "email": target_user.email, "role": target_user.role,

                "is_active": target_user.is_active, "birth_date": target_user.birth_date}

    if target_user.id != user.id:

        # تعديل عضو آخر

        ALLOWED_OFFICE_ROLES = {'مدير', 'محامي', 'محامٍ', 'سكرتير', 'محاسب', 'موكل'}

        if role not in ALLOWED_OFFICE_ROLES:

            raise HTTPException(status_code=400, detail="دور العضو المختار غير صالح")

        target_user.name = name

        target_user.phone = phone

        target_user.email = email

        target_user.role = role

        target_user.is_active = is_active

        target_user.birth_date = birth_date

    else:

        # المدير يعدّل نفسه — لا يُغيّر دوره أو حالة نشاطه

        target_user.name = name

        target_user.phone = phone

        target_user.email = email

        target_user.birth_date = birth_date

    write_audit(

        db,

        table_name="access_profiles",

        action_name="edit_user",

        actor_user_id=user.id,

        actor_name=user.name,

        office_id=office_id,

        entity_type="user",

        entity_id=target_user.id,

        record_key=str(target_user.id),

        old_values=old_vals,

        new_values={"name": name, "phone": phone, "email": email,

                    "role": role, "is_active": is_active},

    )

    db.commit()

    app_logger.info(f"edit_user | actor={user.id} | target={target_user.id} | office={office_id}")

    return RedirectResponse(url="/settings", status_code=303)

_pending_registrations = {}

@app.post("/api/register-secure")

async def api_register_secure(request: Request, db: Session = Depends(get_db)):

    from fastapi.responses import JSONResponse as _J

    try:

        data = await request.json()

        role        = (data.get("role") or "موكل").strip()

        username    = (data.get("username") or "").strip()

        name        = (data.get("name") or "").strip()

        phone       = (data.get("phone") or "").strip()

        email       = (data.get("email") or "").strip().lower()

        birth_date  = (data.get("birth_date") or "").strip()

        access_pin  = (data.get("access_pin") or "").strip()

        lawyer_name = (data.get("lawyer_name") or "").strip()

        if not all([username, name, email, birth_date, access_pin]):

            return _J({"success": False, "error": "جميع الحقول الأساسية مطلوبة"}, status_code=400)

        if len(access_pin) < 12:

            return _J({"success": False, "error": "كلمة المرور يجب أن تكون 12 حرفاً على الأقل"}, status_code=400)

        if db.query(AccessProfiles).filter(

            (AccessProfiles.email == email) | (AccessProfiles.username == username) | (AccessProfiles.phone == phone)

        ).first():

            return _J({"success": False, "error": "البريد الإلكتروني، اسم المستخدم، أو رقم الهاتف مسجل مسبقاً"}, status_code=409)

        # إرسال رمز التحقق أولاً بدون الحفظ في قاعدة البيانات

        code = generate_otp(6)

        store_otp(email, code)

        is_sent = send_otp_email(email, code, "register")

        if not is_sent:

            return _J({"success": False, "error": "فشل إرسال البريد الإلكتروني. تأكد من صحة الإعدادات."}, status_code=500)

        # حفظ البيانات مؤقتاً في الذاكرة حتى يتم التحقق

        _pending_registrations[email] = {

            "name": name,

            "username": username,

            "email": email,

            "phone": phone,

            "birth_date": birth_date,

            "lawyer_name": lawyer_name,

        "access_pin_hash": _hash_pin(access_pin),

            "role": role

        }

        app_logger.info(f"REGISTER_OTP_SENT | {email}")

        return _J({"success": True, "message": "تم إرسال رمز التحقق"})

    except Exception as exc:

        app_logger.error(f"api_register_secure error: {exc}", exc_info=True)

        return _J({"success": False, "error": "حدث خطأ داخلي. يرجى المحاولة مرة أخرى."}, status_code=500)

@app.post("/api/verify-register-otp")

async def api_verify_register_otp(request: Request, db: Session = Depends(get_db)):

    from fastapi.responses import JSONResponse as _J

    try:

        data  = await request.json()

        email = (data.get("email") or "").strip().lower()

        code  = (data.get("code")  or "").strip()

        if not email or not code:

            return _J({"success": False, "error": "البيانات غير مكتملة"}, status_code=400)

        if not verify_otp(email, code):

            return _J({"success": False, "error": "رمز التحقق غير صحيح أو منتهي الصلاحية"}, status_code=400)

        # استرجاع البيانات المؤقتة

        pending_user = _pending_registrations.get(email)

        if not pending_user:

            return _J({"success": False, "error": "انتهت صلاحية جلسة التسجيل أو أنك تستخدم نافذة مختلفة، يرجى إعادة تعبئة البيانات"}, status_code=400)

        # إنشاء مكتب جديد (مساحة عمل معزولة) لكل مستخدم يسجل من الخارج

        from datetime import datetime, timezone, timedelta

        sub_end = (datetime.now(timezone.utc) + timedelta(days=14)).replace(tzinfo=None).strftime("%Y-%m-%d %H:%M:%S")

        office_name = f"مكتب {pending_user['name']}" if pending_user['role'] in ['صاحب مكتب', 'محامي'] else f"حساب {pending_user['name']}"

        new_office = LawOffices(name=office_name, status_key="active", subscription_plan="trial", subscription_end=sub_end, is_active=1)

        db.add(new_office)

        db.flush()

        new_user = AccessProfiles(

            name=pending_user["name"],

            username=pending_user["username"],

            email=pending_user["email"],

            phone=pending_user["phone"],

            birth_date=pending_user["birth_date"],

            lawyer_name=None,

            access_pin_hash=pending_user["access_pin_hash"],

            role='مدير',  # إعطاء صلاحيات مدير المكتب كاملة لكل من يسجل من الخارج

            office_id=new_office.id,

            is_active=1,  # مفعل مباشرة لأنه أثبت إيميله

            email_verified=1,

            state="draft",

            failed_attempts=0,

        )

        db.add(new_user)

        db.flush()

        write_audit(

            db, table_name="access_profiles", action_name="register",

            actor_user_id=new_user.id, actor_name=pending_user["name"], office_id=new_office.id,

            entity_type="user", entity_id=new_user.id, details=f"تسجيل حساب جديد وتأكيد البريد"

        )

        db.commit()

        # تنظيف الذاكرة

        del _pending_registrations[email]

        app_logger.info(f"EMAIL_VERIFIED_AND_REGISTERED | user={new_user.id} | {email}")

        return _J({"success": True, "message": "تم التحقق وإنشاء الحساب بنجاح"})

    except Exception as exc:

        db.rollback()

        app_logger.error(f"verify_register_otp error: {exc}", exc_info=True)

        return _J({"success": False, "error": "حدث خطأ داخلي أثناء الحفظ."}, status_code=500)

# REMOVED DUPLICATE: @app.post("/documents/add")

async def add_document(

    request: Request,

    case_id: int = Form(...),

    name: str = Form(...),

    document_type_key: str = Form(...),

    doc_date: str = Form(None),

    notes: str = Form(None),

    file: UploadFile = File(None),

    db: Session = Depends(get_db),

    user: AccessProfiles = Depends(get_current_user)

):

    if not user: return RedirectResponse(url="/", status_code=303)

    file_path = None

    if file and "".join(c for c in file.filename if c.isalnum() or c in ' ._-'):

        import time

        safe_filename = f"{int(time.time())}_" + "".join(c for c in file.filename if c.isalnum() or c in ' ._-')

        file_path = f"static/uploads/documents/{safe_filename}"

        with open(file_path, "wb") as buffer:

            shutil.copyfileobj(file.file, buffer)

    office_id = user.office_id

    new_doc = LawDocuments(

        case_id=case_id,

        office_id=office_id,

        name=name,

        document_type_key=document_type_key,

        doc_date=doc_date,

        file_path=file_path,

        notes=notes

    )

    db.add(new_doc)

    db.commit()

    return RedirectResponse(url=f"/cases/{case_id}", status_code=303)

@app.get("/tasks", response_class=HTMLResponse)
async def tasks_page(
    request: Request,
    filter_type: Optional[str] = None,
    q: Optional[str] = None,
    case_id: Optional[int] = None,
    assignee_id: Optional[int] = None,
    db: Session = Depends(get_db),
    user: AccessProfiles = Depends(get_current_user)
):
    if not user:
        return RedirectResponse(url="/", status_code=303)
    try:
        from datetime import date as _date, datetime as _dt
        today_str = str(_date.today())
        office_id = user.office_id

        # Base query
        query = db.query(LawTasks).filter(
            LawTasks.office_id == office_id,
            LawTasks.is_deleted == 0
        )

        # Role restrictions: regular lawyers see own tasks or cases they lead
        if user.role not in ['مدير', 'مدير المكتب', 'صاحب المكتب', 'صاحب مكتب', 'مدير النظام']:
            query = query.filter(LawTasks.assignee_user_id == user.id)

        all_office_tasks = query.all()

        # Calculate live KPI Ribbon statistics
        total_tasks = len(all_office_tasks)
        overdue_tasks = sum(1 for t in all_office_tasks if t.due_at and t.due_at[:10] < today_str and t.status_key != 'completed')
        due_today_tasks = sum(1 for t in all_office_tasks if t.due_at and t.due_at[:10] == today_str and t.status_key != 'completed')
        completed_tasks = sum(1 for t in all_office_tasks if t.status_key == 'completed')
        completion_rate = round((completed_tasks / total_tasks * 100) if total_tasks > 0 else 0, 1)

        # Apply user filters
        filtered_tasks = all_office_tasks
        if filter_type == 'my':
            filtered_tasks = [t for t in filtered_tasks if t.assignee_user_id == user.id]
        elif filter_type == 'overdue':
            filtered_tasks = [t for t in filtered_tasks if t.due_at and t.due_at[:10] < today_str and t.status_key != 'completed']
        elif filter_type == 'today':
            filtered_tasks = [t for t in filtered_tasks if t.due_at and t.due_at[:10] == today_str and t.status_key != 'completed']
        elif filter_type == 'urgent':
            filtered_tasks = [t for t in filtered_tasks if t.priority_level == 1 and t.status_key != 'completed']
        elif filter_type == 'completed':
            filtered_tasks = [t for t in filtered_tasks if t.status_key == 'completed']

        if q:
            q_lower = q.lower()
            filtered_tasks = [t for t in filtered_tasks if (t.title and q_lower in t.title.lower()) or (t.description and q_lower in t.description.lower())]

        if case_id:
            filtered_tasks = [t for t in filtered_tasks if t.case_id == case_id]

        if assignee_id:
            filtered_tasks = [t for t in filtered_tasks if t.assignee_user_id == assignee_id]

        # Sorting: priority asc, due_at asc (safe against mixed int/str types)
        def _task_priority_weight(p):
            if p is None: return 2
            if isinstance(p, int): return p
            p_str = str(p).strip().lower()
            if p_str in ['1', 'عالية', 'عاجل', 'عاجلة', 'urgent', 'high']: return 1
            if p_str in ['2', 'متوسطة', 'medium', 'normal']: return 2
            if p_str in ['3', 'منخفضة', 'low']: return 3
            try: return int(p_str)
            except Exception: return 2

        filtered_tasks.sort(key=lambda t: (_task_priority_weight(t.priority_level), t.due_at or '9999-12-31'))

        cases = db.query(LawCases).filter(LawCases.office_id == office_id, LawCases.is_deleted == 0).order_by(LawCases.title.asc()).all()
        users = db.query(AccessProfiles).filter(AccessProfiles.office_id == office_id).order_by(AccessProfiles.name.asc()).all()

        return templates.TemplateResponse(
            request=request, name="tasks.html",
            context={
                "user": user,
                "tasks": filtered_tasks,
                "cases": cases,
                "users": users,
                "active_page": "tasks",
                "filter_type": filter_type or "all",
                "q": q or "",
                "today_str": today_str,
                "kpis": {
                    "total": total_tasks,
                    "overdue": overdue_tasks,
                    "today": due_today_tasks,
                    "completed": completed_tasks,
                    "rate": completion_rate
                }
            }
        )
    except Exception as e:
        import traceback
        return _safe_error(traceback.format_exc())

@app.get("/api/tasks/{task_id}")
async def get_task_api(
    task_id: int,
    db: Session = Depends(get_db),
    user: AccessProfiles = Depends(get_current_user)
):
    if not user:
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    task = db.query(LawTasks).filter(
        LawTasks.id == task_id,
        LawTasks.office_id == user.office_id,
        LawTasks.is_deleted == 0
    ).first()
    if not task:
        return JSONResponse({"error": "not found"}, status_code=404)
    return JSONResponse({
        "id": task.id,
        "title": task.title,
        "description": task.description or "",
        "case_id": task.case_id,
        "assignee_user_id": task.assignee_user_id,
        "due_at": task.due_at or "",
        "priority_level": task.priority_level,
        "status_key": task.status_key,
        "task_type": getattr(task, 'task_type', None) or "general",
        "estimated_hours": getattr(task, 'estimated_hours', 0.0) or 0.0,
        "actual_hours": getattr(task, 'actual_hours', 0.0) or 0.0,
        "is_billable": getattr(task, 'is_billable', 0) or 0,
        "checklist_json": getattr(task, 'checklist_json', None) or ""
    })

@app.post("/tasks/add")
async def add_task(
    request: Request,
    title: str = Form(...),
    description: Optional[str] = Form(None),
    case_id: Optional[int] = Form(None),
    assignee_user_id: Optional[int] = Form(None),
    due_at: Optional[str] = Form(None),
    priority_level: int = Form(2),
    task_type: Optional[str] = Form("general"),
    estimated_hours: Optional[float] = Form(0.0),
    is_billable: Optional[int] = Form(0),
    checklist_json: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    user: AccessProfiles = Depends(get_current_user)
):
    if not user: return RedirectResponse(url="/", status_code=303)
    office_id = user.office_id
    if case_id:
        case = db.query(LawCases).filter(LawCases.id == case_id, LawCases.office_id == office_id).first()
        if not case: raise HTTPException(status_code=403, detail="غير مصرح")

    task = LawTasks(
        title=title.strip(),
        description=description.strip() if description else None,
        case_id=case_id if case_id and case_id > 0 else None,
        office_id=office_id,
        assignee_user_id=assignee_user_id if assignee_user_id and assignee_user_id > 0 else None,
        due_at=due_at.strip() if due_at else None,
        priority_level=priority_level,
        status_key='pending',
        task_type=task_type or 'general',
        estimated_hours=estimated_hours or 0.0,
        actual_hours=0.0,
        is_billable=is_billable or 0,
        checklist_json=checklist_json
    )
    db.add(task)
    db.commit()
    db.refresh(task)

    if request.headers.get("accept") == "application/json":
        return JSONResponse({"ok": True, "task_id": task.id})
    return RedirectResponse(url="/tasks", status_code=303)

@app.post("/tasks/edit")
async def edit_task(
    request: Request,
    task_id: int = Form(...),
    title: str = Form(...),
    description: Optional[str] = Form(None),
    case_id: Optional[int] = Form(None),
    assignee_user_id: Optional[int] = Form(None),
    due_at: Optional[str] = Form(None),
    priority_level: int = Form(2),
    status_key: str = Form('pending'),
    task_type: Optional[str] = Form("general"),
    estimated_hours: Optional[float] = Form(0.0),
    actual_hours: Optional[float] = Form(0.0),
    is_billable: Optional[int] = Form(0),
    checklist_json: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    user: AccessProfiles = Depends(get_current_user)
):
    if not user: return RedirectResponse(url="/", status_code=303)
    office_id = user.office_id
    task = db.query(LawTasks).filter(LawTasks.id == task_id, LawTasks.office_id == office_id, LawTasks.is_deleted == 0).first()
    if task:
        from datetime import datetime as _dt
        if case_id:
            case = db.query(LawCases).filter(LawCases.id == case_id, LawCases.office_id == office_id).first()
            if not case: raise HTTPException(status_code=403, detail="غير مصرح")
        task.title = title.strip()
        task.description = description.strip() if description else None
        task.case_id = case_id if case_id and case_id > 0 else None
        task.assignee_user_id = assignee_user_id if assignee_user_id and assignee_user_id > 0 else None
        task.due_at = due_at.strip() if due_at else None
        task.priority_level = priority_level
        if status_key == 'completed' and task.status_key != 'completed':
            task.completed_at = str(_dt.now())[:19]
        task.status_key = status_key
        task.task_type = task_type or 'general'
        task.estimated_hours = estimated_hours or 0.0
        task.actual_hours = actual_hours or 0.0
        task.is_billable = is_billable or 0
        task.checklist_json = checklist_json
        db.commit()

    if request.headers.get("accept") == "application/json":
        return JSONResponse({"ok": True, "task_id": task_id})
    return RedirectResponse(url="/tasks", status_code=303)

@app.post("/tasks/update_status")
async def update_task_status(
    request: Request,
    task_id: int = Form(...),
    status_key: str = Form(...),
    db: Session = Depends(get_db),
    user: AccessProfiles = Depends(get_current_user)
):
    if not user: return RedirectResponse(url="/", status_code=303)
    office_id = user.office_id
    task = db.query(LawTasks).filter(LawTasks.id == task_id, LawTasks.office_id == office_id, LawTasks.is_deleted == 0).first()
    if task:
        from datetime import datetime as _dt
        task.status_key = status_key
        if status_key == 'completed':
            task.completed_at = str(_dt.now())[:19]
        db.commit()

    if request.headers.get("accept") == "application/json":
        return JSONResponse({"ok": True, "task_id": task_id, "status_key": status_key})
    return RedirectResponse(url="/tasks", status_code=303)

@app.post("/tasks/delete")
async def delete_task(
    request: Request,
    task_id: int = Form(...),
    db: Session = Depends(get_db),
    user: AccessProfiles = Depends(get_current_user)
):
    if not user: return RedirectResponse(url="/", status_code=303)
    office_id = user.office_id
    task = db.query(LawTasks).filter(LawTasks.id == task_id, LawTasks.office_id == office_id).first()
    if task:
        task.is_deleted = 1
        db.commit()

    if request.headers.get("accept") == "application/json":
        return JSONResponse({"ok": True, "deleted_id": task_id})
    return RedirectResponse(url="/tasks", status_code=303)

@app.post("/tasks/convert-timesheet")
async def convert_task_to_timesheet(
    request: Request,
    task_id: int = Form(...),
    hours: float = Form(1.0),
    hourly_rate: Optional[float] = Form(0.0),
    notes: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    user: AccessProfiles = Depends(get_current_user)
):
    if not user: return RedirectResponse(url="/", status_code=303)
    office_id = user.office_id
    task = db.query(LawTasks).filter(LawTasks.id == task_id, LawTasks.office_id == office_id, LawTasks.is_deleted == 0).first()
    if not task or not task.case_id:
        raise HTTPException(status_code=400, detail="المهمة غير مرتبطة بقضية محددة لتحويلها إلى سجل أتعاب")

    entry = LawTimesheets(
        case_id=task.case_id,
        office_id=office_id,
        user_id=user.id,
        title=notes or f"إنجاز مهمة: {task.title}",
        duration_hours=hours,
        billable_rate=hourly_rate or 0.0
    )
    db.add(entry)
    task.actual_hours = hours
    db.commit()

    if request.headers.get("accept") == "application/json":
        return JSONResponse({"ok": True, "timesheet_id": entry.id})
    return RedirectResponse(url=f"/cases/{task.case_id}", status_code=303)

@app.get("/activity", response_class=HTMLResponse)

async def activity_page(request: Request, db: Session = Depends(get_db), user: AccessProfiles = Depends(get_current_user)):

    if not user:

        return RedirectResponse(url="/", status_code=303)

    if user.role not in ['مدير', 'مدير المكتب', 'صاحب المكتب']:

        return RedirectResponse(url="/dashboard", status_code=303)

    try:

        office_id = user.office_id

        # Recent task activity - all tasks with their assignees

        all_tasks = db.query(LawTasks).filter(LawTasks.office_id == office_id).order_by(LawTasks.created_at.desc()).limit(50).all()

        all_users = db.query(AccessProfiles).filter(AccessProfiles.office_id == office_id).all()

        users_map = {u.id: u for u in all_users}

        # Recent documents uploaded

        recent_docs = db.query(LawDocuments).filter(LawDocuments.office_id == office_id).order_by(LawDocuments.created_at.desc()).limit(20).all()

        # Build activity feed: merge tasks+docs ordered by date

        activity_feed = []

        for task in all_tasks:

            assignee = users_map.get(task.assignee_user_id)
            task_date = str(task.created_at)[:16] if task.created_at else ''

            if task.status_key == 'in_progress':

                activity_feed.append({

                    'type': 'task_accepted',

                    'icon': 'fa-circle-check',

                    'color': '#3b82f6',

                    'text': f"قبل {assignee.name if assignee else 'محامٍ'} مهمة: {task.title}",

                    'sub': f"القضية: {task.law_case.title if task.law_case else 'مهمة عامة'}",

                    'date': task_date

                })

            elif task.status_key == 'completed':

                activity_feed.append({

                    'type': 'task_done',

                    'icon': 'fa-check-double',

                    'color': '#10b981',

                    'text': f"أتم {assignee.name if assignee else 'محامٍ'} مهمة: {task.title}",

                    'sub': f"القضية: {task.law_case.title if task.law_case else 'مهمة عامة'}",

                    'date': task_date

                })

            elif task.status_key == 'pending' and task.assignee_user_id:

                activity_feed.append({

                    'type': 'task_assigned',

                    'icon': 'fa-user-tag',

                    'color': '#f59e0b',

                    'text': f"تم إسناد مهمة إلى {assignee.name if assignee else 'محامٍ'}: {task.title}",

                    'sub': f"القضية: {task.law_case.title if task.law_case else 'مهمة عامة'}",

                    'date': task_date

                })

        for doc in recent_docs:

            doc_date = str(doc.created_at)[:16] if doc.created_at else ''

            activity_feed.append({

                'type': 'doc_uploaded',

                'icon': 'fa-file-arrow-up',

                'color': '#8b5cf6',

                'text': f"رفع مستند: {doc.name}",

                'sub': f"نوعه: {'مذكرة' if doc.document_type_key == 'memo' else doc.document_type_key} – مرتبط بالقضية رقم {doc.case_id}",

                'date': doc_date

            })

        activity_feed.sort(key=lambda x: x.get('date', ''), reverse=True)

        # Task stats per user

        team_stats = []

        for u in all_users:

            if u.role in ['محامٍ', 'مدير', 'إداري']:

                user_tasks = [t for t in all_tasks if t.assignee_user_id == u.id]

                team_stats.append({

                    'user': u,

                    'pending': len([t for t in user_tasks if t.status_key == 'pending']),

                    'in_progress': len([t for t in user_tasks if t.status_key == 'in_progress']),

                    'completed': len([t for t in user_tasks if t.status_key == 'completed']),

                    'total': len(user_tasks)

                })

        return templates.TemplateResponse(

            request=request, name="activity.html",

            context={"user": user, "activity_feed": activity_feed, "team_stats": team_stats, "active_page": "activity"}

        )

    except Exception:

        import traceback

        return _safe_error(traceback.format_exc())

# ============ ROUTERS INTEGRATION ============

from routers import parties

from routers import pleadings

from routers import judgments

from routers import smart_search_route

from routers import calendar_route

from routers import reports_route

from routers import notes

from routers import correspondences

from routers import documents_route

from routers import api_case_recipients

from routers import smart_automation_route

from routers import timeline_route

from routers import team_management

from routers import reference_data

from routers import login_log___sessions

from routers import legal_references

from routers import limitations

from routers import timesheet

from routers import expenses

from routers import executions

from routers import power_of_attorney

from routers import advanced_operations

from routers import superadmin

from routers import mobile_api, mobile_sync, mobile_biometrics

app.include_router(parties.router)

app.include_router(mobile_api.router)

app.include_router(mobile_sync.router)

app.include_router(mobile_biometrics.router)

app.include_router(pleadings.router)

app.include_router(judgments.router)

app.include_router(smart_search_route.router)

app.include_router(calendar_route.router)

app.include_router(reports_route.router)

app.include_router(notes.router)

app.include_router(correspondences.router)

app.include_router(documents_route.router)

app.include_router(api_case_recipients.router)

app.include_router(smart_automation_route.router)

app.include_router(timeline_route.router)

app.include_router(team_management.router)

app.include_router(reference_data.router)

app.include_router(login_log___sessions.router)

app.include_router(legal_references.router)

app.include_router(limitations.router)

app.include_router(timesheet.router)

app.include_router(expenses.router)

app.include_router(executions.router)

app.include_router(power_of_attorney.router)

app.include_router(advanced_operations.router)

app.include_router(superadmin.router)

# المساعد الذكي القانوني اليمني

from routers import ai_assistant as ai_assistant_router

app.include_router(ai_assistant_router.router)

try:
    from routers import rag_router
    app.include_router(rag_router.router)
except ImportError as e:
    print(f"[RAG] تحذير: تعذر تحميل RAG Engine ({e}). سيعمل النظام بدون ميزة تحليل المستندات.")

# لوحة الكانبان (Kanban Boards)
from routers import kanban as kanban_router
app.include_router(kanban_router.router)

# محلل العقود الذكي
from routers import contract_analyzer as contract_analyzer_router
app.include_router(contract_analyzer_router.router)

# نظام الفوترة الإلكترونية والمحاسبة (ZATCA)
from routers import accounting as accounting_router
app.include_router(accounting_router.router)

# استقطاب الموكلين والتوقيع الإلكتروني (Smart Intake & E-Signature)
from routers import intake as intake_router
app.include_router(intake_router.router)

# بوابة الموكلين الذكية (Client Portal)
from routers import client_portal as client_portal_router
app.include_router(client_portal_router.router)

# ----------------------------------------------------------------------------

# SaaS Subscription Routes

# ----------------------------------------------------------------------------

@app.get("/subscription")
async def view_subscription(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/", status_code=303)
    office = db.query(LawOffices).filter(LawOffices.id == user.office_id).first() if user.office_id else None

    payment_requests = []
    pending_request = False
    if office:
        payment_requests = db.query(PaymentRequest).filter(PaymentRequest.office_id == office.id).order_by(PaymentRequest.id.desc()).all()
        if any(r.status == "pending" for r in payment_requests):
            pending_request = True

    return templates.TemplateResponse("subscription.html", {
        "request": request,
        "user": user,
        "office": office,
        "payment_requests": payment_requests,
        "pending_request": pending_request
    })

@app.post("/api/subscription/checkout")
async def api_subscription_checkout(request: Request, db: Session = Depends(get_db)):
    from fastapi.responses import JSONResponse as _J
    user = get_current_user(request, db)
    if not user:
        return _J({"success": False, "error": "غير مصرح"}, status_code=403)

    if user.role not in ['مدير النظام', 'مدير', 'مدير المكتب', 'صاحب مكتب']:
        return _J({"success": False, "error": "غير مصرح لك بتجديد الاشتراك"}, status_code=403)

    data = await request.json()
    plan = data.get("plan")
    amount = data.get("amount")
    transfer_ref = data.get("transfer_ref")
    receipt_base64 = data.get("receipt_base64", "")

    if plan not in ['monthly', 'yearly']:
        return _J({"success": False, "error": "خطة غير صالحة"}, status_code=400)

    office = db.query(LawOffices).filter(LawOffices.id == user.office_id).first()
    if not office:
        return _J({"success": False, "error": "المكتب غير موجود"}, status_code=404)

    if not receipt_base64 or not transfer_ref:
        return _J({"success": False, "error": "يرجى إرفاق صورة السند ورقم المرجع"}, status_code=400)

    allowed_prefixes = ('data:image/jpeg', 'data:image/jpg', 'data:image/png', 'data:image/gif', 'data:image/webp')
    if not any(receipt_base64.startswith(p) for p in allowed_prefixes):
        return _J({"success": False, "error": "يرجى رفع صورة فقط (JPG, PNG, WEBP)"}, status_code=400)

    if len(receipt_base64) > 7_000_000:
        return _J({"success": False, "error": "حجم الصورة كبير جداً. يرجى ضغطها قبل الرفع"}, status_code=400)

    existing_pending = db.query(PaymentRequest).filter(
        PaymentRequest.office_id == office.id,
        PaymentRequest.status == 'pending'
    ).first()

    if existing_pending:
        return _J({"success": False, "error": "يوجد لديك طلب دفع قيد المراجعة بالفعل."})

    new_req = PaymentRequest(
        office_id=office.id,
        user_id=user.id,
        plan=plan,
        amount=amount,
        transfer_ref=transfer_ref,
        receipt_base64=receipt_base64,
        status='pending'
    )
    db.add(new_req)
    db.commit()

    try:
        from email_service import send_email_async
        import asyncio
        html_content = f"""
        <div dir="rtl" style="font-family: Arial, sans-serif;">
            <h2 style="color: #5c2d91;">طلب دفع جديد 💰</h2>
            <p><strong>المكتب:</strong> {office.name}</p>
            <p><strong>المبلغ:</strong> ${amount} ({plan})</p>
            <p><strong>المرجع:</strong> {transfer_ref}</p>
            <p>يرجى الدخول إلى لوحة تحكم SuperAdmin لمراجعة الإيصال وتفعيل الحساب.</p>
        </div>
        """
        asyncio.create_task(send_email_async("aboodalalimi@icloud.com", f"💰 طلب دفع جديد - {office.name}", html_content))
    except Exception as e:
        pass

    write_audit(
        db,
        table_name="payment_requests",
        action_name="submit_payment",
        actor_user_id=user.id,
        actor_name=user.name,
        office_id=office.id,
        entity_type="payment_request",
        entity_id=new_req.id,
        details=f"Submitted payment request for {plan}"
    )

    return _J({"success": True, "message": "تم إرسال السند بنجاح"})

@app.get("/ai-assistant")
async def ai_assistant_page(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse("/", status_code=302)
    return templates.TemplateResponse("ai_assistant.html", {"request": request, "user": user})

@app.get("/knowledge-admin")
async def knowledge_admin_page(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user or user.role in ['موكل']:
        return RedirectResponse("/", status_code=302)
    return templates.TemplateResponse("knowledge_admin.html", {"request": request, "user": user})

# [SECURITY FIX CRITICAL] تم حذف endpoint التشخيصي /debug-login-test
# كان هذا الـ endpoint يُتيح اختبار كلمات المرور وعرض بيانات المستخدمين دون مصادقة.
# لا تُضف أي endpoints تشخيصية مشابهة في بيئة الإنتاج.
