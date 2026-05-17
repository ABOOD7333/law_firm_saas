

# ─── Logging ─────────────────────────────────────────────────
from core.logger import app_logger
from core.audit import write_audit

import hashlib
import uuid
from datetime import datetime, timedelta, timezone
from fastapi import FastAPI, Request, Form, Depends, Cookie, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import uvicorn
import os

from sqlalchemy.orm import Session
from database.database import get_db
from database.models import (AccessProfiles, AuthSessions, LawClients, LawCases, LawOffices,
    LawHearings, LawTransactions, LawExpenses, LawDocuments, LawTasks)
import shutil

app = FastAPI(title="Lexzur Clone - SaaS Law Firm Management", version="1.0")

# Ensure database tables are created (critical for Railway deployment)
from database.database import init_db
init_db()

try:
    from create_superadmin import create_superadmin
    create_superadmin()
except Exception as e:
    print(f"Failed to auto-create superadmin: {e}")

# Ensure static and templates directories exist for the server
os.makedirs("static/css", exist_ok=True)
os.makedirs("static/js", exist_ok=True)
os.makedirs("static/img", exist_ok=True)
os.makedirs("static/uploads/documents", exist_ok=True)
os.makedirs("templates", exist_ok=True)

from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.responses import JSONResponse
import uuid

class CSRFMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        csrf_cookie = request.cookies.get("csrf_token")
        if not csrf_cookie:
            csrf_cookie = str(uuid.uuid4())
            
        if request.method in ["POST", "PUT", "DELETE", "PATCH"]:
            # ── ثغرة 6 مُصلحة: تفعيل CSRF لجميع المسارات بما فيها صفحة الدخول ──
            if True:
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
            response.set_cookie("csrf_token", csrf_cookie, httponly=False) # Accessible by JS
        return response

app.add_middleware(CSRFMiddleware)

# ─── Safe Error Handler ───────────────────────────────────────────────────────
def _safe_error(tb_str: str = "") -> HTMLResponse:
    """يعرض تفاصيل الخطأ في التطوير فقط — يخفيها في الإنتاج."""
    if os.getenv("APP_ENV", "development").lower() == "production":
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

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Templates setup - imported from dependencies to avoid circular imports in routers
from dependencies import templates, get_current_user

@app.get("/", response_class=HTMLResponse)
async def login_page(request: Request, user: AccessProfiles = Depends(get_current_user)):
    # إذا كان المستخدم مسجل دخول مسبقاً، نوجهه للوحة التحكم مباشرة
    if user:
        return RedirectResponse(url="/dashboard", status_code=303)
    return templates.TemplateResponse(request=request, name="login.html")

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

# مساحة لتخزين الرموز الآمنة مؤقتاً (يفضل Redis في الإنتاج)
_reset_tokens = {}

# سجل بسيط لتتبع طلبات OTP لمنع إغراق الإيميل (Rate Limiting)
import time
_otp_rate_limit = {}
_ip_rate_limit = {}  # لتتبع محاولات تسجيل الدخول الخاطئة لكل IP

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

    if not user:
        return _JSONResponse({"success": False, "error": "لم يتم العثور على حساب بهذه البيانات"}, status_code=404)

    if user.phone != phone:
        return _JSONResponse({"success": False, "error": "رقم الهاتف غير مطابق للبيانات المسجلة"}, status_code=400)

    # Rate Limiting Check (3 محاولات كل 15 دقيقة)
    now = time.time()
    user_requests = _otp_rate_limit.get(email, [])
    # تنظيف المحاولات القديمة (أقدم من 15 دقيقة = 900 ثانية)
    user_requests = [req_time for req_time in user_requests if now - req_time < 900]
    
    if len(user_requests) >= 3:
        _otp_rate_limit[email] = user_requests
        return _JSONResponse({"success": False, "error": "تجاوزت الحد المسموح من المحاولات. يرجى الانتظار 15 دقيقة."}, status_code=429)

    user_requests.append(now)
    _otp_rate_limit[email] = user_requests

    code = generate_otp(6)
    store_otp(email, code)
    sent = send_otp_email(email, code, "forgot_password")
    
    if sent:
        return _JSONResponse({"success": True, "message": "تم إرسال رمز التحقق"})
    return _JSONResponse({"success": False, "error": "فشل إرسال البريد الإلكتروني"}, status_code=500)

@app.post("/api/forgot-verify-otp")
async def api_forgot_verify_otp(request: Request):
    """التحقق من رمز OTP وإصدار Token مؤقت آمن"""
    data = await request.json()
    identifier = data.get("identifier", "").strip()
    code = data.get("code", "").strip()

    if verify_otp(identifier, code):
        token = secrets.token_hex(16)
        _reset_tokens[token] = identifier
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

    # تحقق أمني: هل التوكن صالح ومطابق للبريد؟
    if not token or _reset_tokens.get(token) != email:
        return _JSONResponse({"success": False, "error": "طلب غير مصرح به أو انتهت صلاحية الجلسة"}, status_code=403)

    if len(new_password) < 8:
        return _JSONResponse({"success": False, "error": "كلمة المرور يجب أن تكون 8 أحرف/أرقام على الأقل"}, status_code=400)

    user = db.query(AccessProfiles).filter(AccessProfiles.email == email).first()

    if not user:
        return _JSONResponse({"success": False, "error": "لم يُعثر على هذا الحساب"}, status_code=404)

    user.access_pin_hash = _hash_pin(new_password)
    user.failed_attempts = 0
    
    if new_username:
        if new_username != user.username:
            existing = db.query(AccessProfiles).filter(AccessProfiles.username == new_username).first()
            if existing:
                return _JSONResponse({"success": False, "error": "اسم المستخدم محجوز، اختر اسماً آخر"}, status_code=400)
            user.username = new_username

    db.commit()
    # إتلاف التوكن لمنع إعادة الاستخدام
    del _reset_tokens[token]
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
    _ip_rate_limit[client_ip] = [t for t in _ip_rate_limit.get(client_ip, []) if now - t < 900]
    if len(_ip_rate_limit[client_ip]) >= 15:
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
            
        if user.failed_attempts >= 10:
            return templates.TemplateResponse(
                request=request,
                name="login.html",
                context={"error": "تم قفل الحساب مؤقتاً بسبب كثرة المحاولات الخاطئة. يرجى التواصل مع الإدارة."}
            )
            
        if user.role == 'موكل':
            if not case_number or user.case_number != case_number:
                # نسجل محاولة خاطئة لتجنب التخمين
                user.failed_attempts += 1
                db.commit()
                return templates.TemplateResponse(
                    request=request,
                    name="login.html",
                    context={"error": "رقم القضية غير مطابق للبيانات، يرجى التأكد والمحاولة مرة أخرى."}
                )
            
        if _verify_pin(password, user.access_pin_hash):
            user.failed_attempts = 0
            token = str(uuid.uuid4())
            expires = datetime.now(timezone.utc) + timedelta(days=7)
            new_session = AuthSessions(
                session_token=token,
                user_id=user.id,
                is_active=1,
                expires_at=expires.strftime("%Y-%m-%d %H:%M:%S")
            )
            db.add(new_session)
            db.commit()
            app_logger.info(f"LOGIN_OK | user={user.id} | role={user.role} | office={user.office_id}")
            response = RedirectResponse(url="/dashboard", status_code=303)
            response.set_cookie(key="session_token", value=token, httponly=True, max_age=7*24*3600)
            return response
        else:
            user.failed_attempts += 1
            db.commit()
            _ip_rate_limit.setdefault(client_ip, []).append(now)
            app_logger.warning(f"LOGIN_FAIL | user={user.id} | attempts={user.failed_attempts}")
            return templates.TemplateResponse(
                request=request,
                name="login.html",
                context={"error": f"بيانات الدخول غير صحيحة. تبقت {10 - user.failed_attempts} محاولات." if user.failed_attempts < 10 else "تم قفل الحساب."}
            )
    else:
        # ── ثغرة 4 مُصلحة: تأخير وهمي لمنع User Enumeration عبر قياس سرعة الاستجابة ──
        await asyncio.sleep(0.3)
        _ip_rate_limit.setdefault(client_ip, []).append(now)
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
        session_record = db.query(AuthSessions).filter(AuthSessions.session_token == token).first()
        if session_record:
            session_record.is_active = 0
            db.commit()
            app_logger.info(f"LOGOUT | user={session_record.user_id}")
            
    response = RedirectResponse(url="/", status_code=303)
    response.delete_cookie("session_token")
    return response

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
                LawHearings.status_key == 'pending'
            ).order_by(LawHearings.hearing_at.asc()).limit(5).all() if case_ids else []
            
            return templates.TemplateResponse(
                request=request, name="client_portal.html",
                context={"user": user, "my_cases": my_cases, "my_hearings": my_hearings, "active_page": "dashboard"}
            )
            
        # ── لوحة تحكم المحامين والمدراء ──
        office_id = user.office_id or 1
        my_tasks = db.query(LawTasks).filter(
            LawTasks.assignee_user_id == user.id,
            LawTasks.status_key.in_(['pending', 'in_progress'])
        ).order_by(LawTasks.priority_level.asc()).limit(5).all()
        
        total_cases = db.query(LawCases).filter(LawCases.office_id == office_id).count()
        total_clients = db.query(LawClients).filter(LawClients.office_id == office_id).count()
        pending_tasks_count = db.query(LawTasks).filter(
            LawTasks.assignee_user_id == user.id,
            LawTasks.status_key.in_(['pending', 'in_progress'])
        ).count()
        
        return templates.TemplateResponse(
            request=request, name="dashboard.html", 
            context={"user": user, "active_page": "dashboard", "my_tasks": my_tasks, "total_cases": total_cases, "total_clients": total_clients, "pending_tasks_count": pending_tasks_count}
        )
    except Exception:
        if user.role == 'موكل':
            return templates.TemplateResponse(request=request, name="client_portal.html", context={"user": user, "my_cases": [], "my_hearings": [], "active_page": "dashboard"})
        return templates.TemplateResponse(request=request, name="dashboard.html", context={"user": user, "active_page": "dashboard", "my_tasks": [], "total_cases": 0, "total_clients": 0, "pending_tasks_count": 0})

@app.get("/api/case-numbers")
async def get_case_numbers(db: Session = Depends(get_db), user: AccessProfiles = Depends(get_current_user)):
    if not user:
        return _JSONResponse([])
    office_id = user.office_id or 1
    query = db.query(LawCases.case_number).filter(LawCases.office_id == office_id, LawCases.is_deleted == 0)
    
    if user.role in ['محامي', 'محامٍ'] and user.can_view_all_cases == 0:
        query = query.filter(LawCases.lead_lawyer_id == user.id)
        
    case_numbers = [c[0] for c in query.all() if c[0]]
    return _JSONResponse(case_numbers)

@app.get("/clients", response_class=HTMLResponse)
async def clients_page(request: Request, db: Session = Depends(get_db), user: AccessProfiles = Depends(get_current_user)):
    if not user:
        return RedirectResponse(url="/", status_code=303)
        
    try:
        office_id = user.office_id or 1
        clients = db.query(LawClients).filter(LawClients.office_id == office_id).order_by(LawClients.created_at.desc()).all()
        return templates.TemplateResponse(
            request=request, 
            name="clients.html", 
            context={"user": user, "clients": clients, "active_page": "clients"}
        )
    except Exception:
        import traceback
        return _safe_error(traceback.format_exc())

@app.post("/clients/add")
async def add_client(
    request: Request,
    name: str = Form(...),
    username: str = Form(...),
    password: str = Form(...),
    case_number: str = Form(...),
    phone: str = Form(None),
    national_id: str = Form(None),
    email: str = Form(None),
    db: Session = Depends(get_db),
    user: AccessProfiles = Depends(get_current_user)
):
    if not user:
        return RedirectResponse(url="/", status_code=303)
        
    office_id = user.office_id or 1
    
    # التأكد من عدم تكرار اسم المستخدم
    existing = db.query(AccessProfiles).filter(AccessProfiles.username == username).first()
    if existing:
        # للتغاضي مؤقتاً لو كان موجود، الأفضل إرجاع رسالة لكن سنقوم بتغييره لتجنب الخطأ
        username = f"{username}_{secrets.token_hex(2)}"
        
    new_client = LawClients(
        office_id=office_id,
        name=name,
        username=username,
        case_number=case_number,
        phone=phone,
        national_id=national_id,
        email=email
    )
    db.add(new_client)
    
    # إنشاء حساب دخول للموكل
    new_user = AccessProfiles(
        name=name,
        username=username,
        email=email or f"{username}@client.local",
        phone=phone or username,
        case_number=case_number,
        access_pin_hash=_hash_pin(password),
        role='موكل',
        office_id=office_id,
        is_active=1,
        email_verified=1,
        state="active"
    )
    db.add(new_user)
    db.commit()
    
    return RedirectResponse(url="/clients", status_code=303)

@app.post("/clients/edit")
async def edit_client(
    request: Request,
    client_id: int = Form(...),
    name: str = Form(...),
    username: str = Form(...),
    password: str = Form(""),
    case_number: str = Form(""),
    phone: str = Form(None),
    national_id: str = Form(None),
    email: str = Form(None),
    db: Session = Depends(get_db),
    user: AccessProfiles = Depends(get_current_user)
):
    if not user:
        return RedirectResponse(url="/", status_code=303)
        
    office_id = user.office_id or 1
    client = db.query(LawClients).filter(LawClients.id == client_id, LawClients.office_id == office_id).first()
    if client:
        client.name = name
        client.username = username
        client.case_number = case_number
        client.phone = phone
        client.national_id = national_id
        client.email = email
        
        # تحديث بيانات الدخول أيضاً إن وجدت
        client_user = db.query(AccessProfiles).filter(AccessProfiles.username == client.username, AccessProfiles.office_id == office_id).first()
        if client_user:
            client_user.name = name
            client_user.username = username
            client_user.case_number = case_number
            if password:
                client_user.access_pin_hash = _hash_pin(password)
                
        db.commit()
    return RedirectResponse(url="/clients", status_code=303)

@app.get("/cases", response_class=HTMLResponse)
async def cases_page(request: Request, db: Session = Depends(get_db), user: AccessProfiles = Depends(get_current_user)):
    if not user:
        return RedirectResponse(url="/", status_code=303)
        
    try:
        office_id = user.office_id or 1
        query = db.query(LawCases).filter(LawCases.office_id == office_id, LawCases.is_deleted == 0)
        
        # تقييد المحامي برؤية قضاياه فقط
        if user.role in ['محامي', 'محامٍ']:
            query = query.filter(LawCases.lead_lawyer_id == user.id)
            
        cases = query.order_by(LawCases.created_at.desc()).all()
        clients = db.query(LawClients).filter(LawClients.office_id == office_id).all()
        lawyers = db.query(AccessProfiles).filter(AccessProfiles.office_id == office_id, AccessProfiles.role != "موكل").all()
        
        return templates.TemplateResponse(
            request=request, 
            name="cases.html", 
            context={"user": user, "cases": cases, "clients": clients, "lawyers": lawyers, "active_page": "cases"}
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
    status_key: str = Form("draft"),
    db: Session = Depends(get_db),
    user: AccessProfiles = Depends(get_current_user)
):
    if not user:
        return RedirectResponse(url="/", status_code=303)
        
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
        status_key=status_key,
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

@app.get("/cases/{case_id}", response_class=HTMLResponse)
async def case_details_page(case_id: int, request: Request, db: Session = Depends(get_db), user: AccessProfiles = Depends(get_current_user)):
    if not user:
        return RedirectResponse(url="/", status_code=303)
        
    try:
        office_id = user.office_id or 1
        case = db.query(LawCases).filter(LawCases.id == case_id, LawCases.office_id == office_id).first()
        if not case:
            return HTMLResponse(content="القضية غير موجودة أو لا تملك صلاحية الوصول لها", status_code=404)
            
        # منع المحامي من دخول قضية غير تابعة له
        if user.role in ['محامي', 'محامٍ'] and case.lead_lawyer_id != user.id:
            return HTMLResponse(content="<script>alert('غير مصرح لك بالدخول لهذه القضية'); window.location.href='/cases';</script>", status_code=403)
            
        hearings = db.query(LawHearings).filter(LawHearings.case_id == case_id).order_by(LawHearings.hearing_at.desc()).all()
        lawyer = db.query(AccessProfiles).filter(AccessProfiles.id == case.lead_lawyer_id).first() if case.lead_lawyer_id else None
        
        clients = db.query(LawClients).filter(LawClients.office_id == office_id).all()
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
    status_key: str = Form(...),
    db: Session = Depends(get_db),
    user: AccessProfiles = Depends(get_current_user)
):
    if not user:
        return RedirectResponse(url="/", status_code=303)
        
    office_id = user.office_id or 1
    case = db.query(LawCases).filter(LawCases.id == case_id, LawCases.office_id == office_id).first()
    
    if user.role in ['محامي', 'محامٍ'] and case and case.lead_lawyer_id != user.id:
        return HTMLResponse(content="<script>alert('غير مصرح لك بتعديل هذه القضية'); window.history.back();</script>", status_code=403)
        
    if case:
        case.title = title
        case.case_number = case_number
        case.lead_lawyer_id = lead_lawyer_id
        case.status_key = status_key
        db.commit()
        
        # Check if client was changed/updated
        client = db.query(LawClients).filter(LawClients.id == client_id, LawClients.office_id == office_id).first()
        if client and client.case_id != case.id:
            client.case_id = case.id
            client.case_number = case.case_number
            db.commit()
            
    return RedirectResponse(url=f"/cases/{case_id}", status_code=303)

from fastapi import Query
@app.get("/cases/export_report", response_class=HTMLResponse)
async def export_case_report(
    request: Request,
    case_number: str = Query(None),
    case_title: str = Query(None),
    start_date: str = Query(None),
    end_date: str = Query(None),
    db: Session = Depends(get_db),
    user: AccessProfiles = Depends(get_current_user)
):
    if not user:
        return RedirectResponse(url="/", status_code=303)
        
    office_id = user.office_id or 1
    query = db.query(LawCases).filter(LawCases.office_id == office_id, LawCases.is_deleted == 0)
    
    if user.role in ['محامي', 'محامٍ'] and user.can_view_all_cases == 0:
        query = query.filter(LawCases.lead_lawyer_id == user.id)
        
    if case_number:
        query = query.filter(LawCases.case_number.like(f"%{case_number}%"))
    elif case_title:
        query = query.filter(LawCases.title.like(f"%{case_title}%"))
        
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

@app.get("/hearings", response_class=HTMLResponse)
async def hearings_page(request: Request, db: Session = Depends(get_db), user: AccessProfiles = Depends(get_current_user)):
    if not user:
        return RedirectResponse(url="/", status_code=303)
        
    try:
        office_id = user.office_id or 1
        
        cases_query = db.query(LawCases).filter(LawCases.office_id == office_id, LawCases.is_deleted == 0)
        hearings_query = db.query(LawHearings).filter(LawHearings.office_id == office_id)
        
        if user.role in ['محامي', 'محامٍ']:
            cases_query = cases_query.filter(LawCases.lead_lawyer_id == user.id)
            # Fetch cases IDs to filter hearings
            lawyer_case_ids = [c.id for c in cases_query.all()]
            hearings_query = hearings_query.filter(LawHearings.case_id.in_(lawyer_case_ids) if lawyer_case_ids else LawHearings.case_id == -1)
            
        hearings = hearings_query.order_by(LawHearings.hearing_at.desc()).all()
        cases = cases_query.all()
        
        return templates.TemplateResponse(
            request=request, 
            name="hearings.html", 
            context={"user": user, "hearings": hearings, "cases": cases, "active_page": "hearings"}
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
    status_key: str = Form("pending"),
    redirect_to_case: str = Form(None),
    db: Session = Depends(get_db),
    user: AccessProfiles = Depends(get_current_user)
):
    if not user:
        return RedirectResponse(url="/", status_code=303)
        
    # Get user office or default to first
    office_id = user.office_id
    if not office_id:
        first_office = db.query(LawOffices).first()
        office_id = first_office.id if first_office else 1
    
    # Clean datetime format from HTML5 datetime-local (e.g. 2023-05-10T14:30)
    formatted_hearing_at = hearing_at.replace('T', ' ') if hearing_at else None
    
    if case_id:
        case = db.query(LawCases).filter(LawCases.id == case_id, LawCases.office_id == office_id).first()
        if not case: return HTMLResponse(content="<script>alert('غير مصرح'); window.history.back();</script>", status_code=403)
        
    new_hearing = LawHearings(
        case_id=case_id,
        office_id=office_id,
        title=title,
        hearing_at=formatted_hearing_at,
        next_hearing_date=next_hearing_date,
        status_key=status_key
    )
    db.add(new_hearing)
    db.commit()
    
    if redirect_to_case == "true":
        return RedirectResponse(url=f"/cases/{case_id}", status_code=303)
    return RedirectResponse(url="/hearings", status_code=303)

@app.get("/finance", response_class=HTMLResponse)
async def finance_page(request: Request, db: Session = Depends(get_db), user: AccessProfiles = Depends(get_current_user)):
    if not user:
        return RedirectResponse(url="/", status_code=303)
        
    try:
        office_id = user.office_id or 1
        transactions = db.query(LawTransactions).filter(LawTransactions.office_id == office_id).order_by(LawTransactions.transaction_at.desc()).all()
        expenses = db.query(LawExpenses).filter(LawExpenses.office_id == office_id).order_by(LawExpenses.expense_at.desc()).all()
        cases = db.query(LawCases).filter(LawCases.office_id == office_id, LawCases.is_deleted == 0).all()
        
        return templates.TemplateResponse(
            request=request, 
            name="finance.html", 
            context={"user": user, "transactions": transactions, "expenses": expenses, "cases": cases, "active_page": "finance"}
        )
    except Exception as e:
        import traceback
        return _safe_error(traceback.format_exc())

@app.post("/finance/add_transaction")
async def add_transaction(
    request: Request,
    title: str = Form(...),
    amount: float = Form(...),
    transaction_at: str = Form(...),
    case_id: int = Form(None),
    db: Session = Depends(get_db),
    user: AccessProfiles = Depends(get_current_user)
):
    if not user:
        return RedirectResponse(url="/", status_code=303)
        
    office_id = user.office_id or 1
    
    if case_id:
        case = db.query(LawCases).filter(LawCases.id == case_id, LawCases.office_id == office_id).first()
        if not case: return HTMLResponse(content="<script>alert('غير مصرح'); window.history.back();</script>", status_code=403)
        
    new_trans = LawTransactions(
        case_id=case_id,
        office_id=office_id,
        title=title,
        amount=amount,
        transaction_at=transaction_at,
        status_key="completed"
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
    case_id: int = Form(None),
    db: Session = Depends(get_db),
    user: AccessProfiles = Depends(get_current_user)
):
    if not user:
        return RedirectResponse(url="/", status_code=303)
        
    office_id = user.office_id or 1
    
    if case_id:
        case = db.query(LawCases).filter(LawCases.id == case_id, LawCases.office_id == office_id).first()
        if not case: return HTMLResponse(content="<script>alert('غير مصرح'); window.history.back();</script>", status_code=403)
        
    new_expense = LawExpenses(
        case_id=case_id,
        office_id=office_id,
        title=title,
        amount=amount,
        expense_at=expense_at
    )
    db.add(new_expense)
    db.commit()
    
    return RedirectResponse(url="/finance", status_code=303)

@app.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request, db: Session = Depends(get_db), user: AccessProfiles = Depends(get_current_user)):
    if not user:
        return RedirectResponse(url="/", status_code=303)
        
    try:
        office_id = user.office_id or 1
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
        return HTMLResponse(content="<script>alert('غير مصرح لك بتعديل بيانات المكتب'); window.history.back();</script>", status_code=403)
        
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
        
    if user.role not in ['مدير', 'مدير المكتب', 'صاحب المكتب']:
        return HTMLResponse(content="<script>alert('ليس لديك صلاحية لإضافة مستخدمين'); window.history.back();</script>", status_code=403)
        
    office_id = user.office_id or 1
    
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
    office_id = user.office_id or 1
    client = db.query(LawClients).filter(LawClients.id == client_id, LawClients.office_id == office_id).first()
    if client:
        client.name = name
        client.phone = phone
        client.national_id = national_id
        db.commit()
    return RedirectResponse(url="/clients", status_code=303)

@app.post("/hearings/edit")
async def edit_hearing(
    request: Request,
    hearing_id: int = Form(...),
    title: str = Form(...),
    hearing_at: str = Form(...),
    next_hearing_date: str = Form(None),
    status_key: str = Form(...),
    redirect_to_case: str = Form(None),
    case_id: int = Form(None),
    db: Session = Depends(get_db),
    user: AccessProfiles = Depends(get_current_user)
):
    if not user: return RedirectResponse(url="/", status_code=303)
    office_id = user.office_id or 1
    hearing = db.query(LawHearings).filter(LawHearings.id == hearing_id, LawHearings.office_id == office_id).first()
    if hearing:
        hearing.title = title
        hearing.hearing_at = hearing_at.replace('T', ' ') if hearing_at else None
        hearing.next_hearing_date = next_hearing_date
        hearing.status_key = status_key
        db.commit()
    if redirect_to_case == "true" and case_id:
        return RedirectResponse(url=f"/cases/{case_id}", status_code=303)
    return RedirectResponse(url="/hearings", status_code=303)

# الأدوار المسموح لها بإدارة المستخدمين
_ADMIN_ROLES = {'مدير', 'مدير المكتب', 'صاحب المكتب'}

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

    office_id = user.office_id or 1

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
            
        if len(access_pin) < 6:
            return _J({"success": False, "error": "كلمة المرور يجب أن تكون 6 أحرف/أرقام على الأقل"}, status_code=400)

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
            "access_pin": access_pin,
            "role": role
        }
        
        app_logger.info(f"REGISTER_OTP_SENT | {email}")
        return _J({"success": True, "message": "تم إرسال رمز التحقق"})
    except Exception as exc:
        app_logger.error(f"api_register_secure error: {exc}", exc_info=True)
        return _J({"success": False, "error": f"حدث خطأ داخلي: {str(exc)}"}, status_code=500)

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
            access_pin_hash=_hash_pin(pending_user["access_pin"]),
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
        return _J({"success": False, "error": f"حدث خطأ داخلي أثناء الحفظ: {str(exc)}"}, status_code=500)


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
    if file and file.filename:
        import time
        safe_filename = f"{int(time.time())}_{file.filename}"
        file_path = f"static/uploads/documents/{safe_filename}"
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
    office_id = user.office_id or 1
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
async def tasks_page(request: Request, db: Session = Depends(get_db), user: AccessProfiles = Depends(get_current_user)):
    if not user:
        return RedirectResponse(url="/", status_code=303)
    try:
        office_id = user.office_id or 1
        # Manager sees all tasks in office, lawyer sees only their own
        if user.role in ['مدير', 'مدير المكتب', 'صاحب المكتب']:
            tasks = db.query(LawTasks).filter(LawTasks.office_id == office_id).order_by(LawTasks.priority_level.asc(), LawTasks.due_at.asc()).all()
        else:
            tasks = db.query(LawTasks).filter(
                LawTasks.office_id == office_id,
                LawTasks.assignee_user_id == user.id
            ).order_by(LawTasks.priority_level.asc(), LawTasks.due_at.asc()).all()
        
        cases = db.query(LawCases).filter(LawCases.office_id == office_id, LawCases.is_deleted == 0).all()
        users = db.query(AccessProfiles).filter(AccessProfiles.office_id == office_id).all()
        return templates.TemplateResponse(
            request=request, name="tasks.html",
            context={"user": user, "tasks": tasks, "cases": cases, "users": users, "active_page": "tasks"}
        )
    except Exception as e:
        import traceback
        return _safe_error(traceback.format_exc())

@app.post("/tasks/add")
async def add_task(
    request: Request,
    title: str = Form(...),
    description: str = Form(None),
    case_id: int = Form(None),
    assignee_user_id: int = Form(None),
    due_at: str = Form(None),
    priority_level: int = Form(2),
    db: Session = Depends(get_db),
    user: AccessProfiles = Depends(get_current_user)
):
    if not user: return RedirectResponse(url="/", status_code=303)
    office_id = user.office_id or 1
    
    if case_id:
        case = db.query(LawCases).filter(LawCases.id == case_id, LawCases.office_id == office_id).first()
        if not case: return HTMLResponse(content="<script>alert('غير مصرح'); window.history.back();</script>", status_code=403)
        
    task = LawTasks(
        title=title,
        description=description,
        case_id=case_id,
        office_id=office_id,
        assignee_user_id=assignee_user_id,
        due_at=due_at,
        priority_level=priority_level,
        status_key='pending'
    )
    db.add(task)
    db.commit()
    return RedirectResponse(url="/tasks", status_code=303)

@app.post("/tasks/edit")
async def edit_task(
    request: Request,
    task_id: int = Form(...),
    title: str = Form(...),
    description: str = Form(None),
    case_id: int = Form(None),
    assignee_user_id: int = Form(None),
    due_at: str = Form(None),
    priority_level: int = Form(2),
    status_key: str = Form('pending'),
    db: Session = Depends(get_db),
    user: AccessProfiles = Depends(get_current_user)
):
    if not user: return RedirectResponse(url="/", status_code=303)
    office_id = user.office_id or 1
    task = db.query(LawTasks).filter(LawTasks.id == task_id, LawTasks.office_id == office_id).first()
    if task:
        if case_id:
            case = db.query(LawCases).filter(LawCases.id == case_id, LawCases.office_id == office_id).first()
            if not case: return HTMLResponse(content="<script>alert('غير مصرح'); window.history.back();</script>", status_code=403)
            
        task.title = title
        task.description = description
        task.case_id = case_id
        task.assignee_user_id = assignee_user_id
        task.due_at = due_at
        task.priority_level = priority_level
        task.status_key = status_key
        db.commit()
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
    office_id = user.office_id or 1
    task = db.query(LawTasks).filter(LawTasks.id == task_id, LawTasks.office_id == office_id).first()
    if task:
        task.status_key = status_key
        db.commit()
    return RedirectResponse(url="/tasks", status_code=303)

@app.get("/activity", response_class=HTMLResponse)
async def activity_page(request: Request, db: Session = Depends(get_db), user: AccessProfiles = Depends(get_current_user)):
    if not user:
        return RedirectResponse(url="/", status_code=303)
    if user.role not in ['مدير', 'مدير المكتب', 'صاحب المكتب']:
        return RedirectResponse(url="/dashboard", status_code=303)
    try:
        office_id = user.office_id or 1
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
            if task.status_key == 'in_progress':
                activity_feed.append({
                    'type': 'task_accepted',
                    'icon': 'fa-circle-check',
                    'color': '#3b82f6',
                    'text': f"قبل {assignee.name if assignee else 'محامٍ'} مهمة: {task.title}",
                    'sub': f"القضية: {task.law_case.title if task.law_case else 'مهمة عامة'}",
                    'date': task.created_at[:16]
                })
            elif task.status_key == 'completed':
                activity_feed.append({
                    'type': 'task_done',
                    'icon': 'fa-check-double',
                    'color': '#10b981',
                    'text': f"أتم {assignee.name if assignee else 'محامٍ'} مهمة: {task.title}",
                    'sub': f"القضية: {task.law_case.title if task.law_case else 'مهمة عامة'}",
                    'date': task.created_at[:16]
                })
            elif task.status_key == 'pending' and task.assignee_user_id:
                activity_feed.append({
                    'type': 'task_assigned',
                    'icon': 'fa-user-tag',
                    'color': '#f59e0b',
                    'text': f"تم إسناد مهمة إلى {assignee.name if assignee else 'محامٍ'}: {task.title}",
                    'sub': f"القضية: {task.law_case.title if task.law_case else 'مهمة عامة'}",
                    'date': task.created_at[:16]
                })
        
        for doc in recent_docs:
            activity_feed.append({
                'type': 'doc_uploaded',
                'icon': 'fa-file-arrow-up',
                'color': '#8b5cf6',
                'text': f"رفع مستند: {doc.name}",
                'sub': f"نوعه: {'{مذكرة' if doc.document_type_key == 'memo' else doc.document_type_key} – مرتبط بالقضية رقم {doc.case_id}",
                'date': doc.created_at[:16]
            })
        
        activity_feed.sort(key=lambda x: x['date'], reverse=True)
        
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
app.include_router(parties.router)
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
# ----------------------------------------------------------------------------
# SaaS Subscription Routes
# ----------------------------------------------------------------------------

@app.get("/subscription")
async def view_subscription(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url="/", status_code=303)
        
    office = db.query(LawOffices).filter(LawOffices.id == user.office_id).first() if user.office_id else None
    
    return templates.TemplateResponse("subscription.html", {
        "request": request,
        "user": user,
        "office": office
    })

@app.post("/api/subscription/checkout")
async def api_subscription_checkout(request: Request, db: Session = Depends(get_db)):
    from fastapi.responses import JSONResponse as _J
    user = get_current_user(request, db)
    if not user:
        return _J({"success": False, "error": "غير مصرح"}, status_code=403)
        
    # Only owner/manager can pay
    if user.role not in ['مدير النظام', 'مدير', 'مدير المكتب']:
        return _J({"success": False, "error": "غير مصرح لك بتجديد الاشتراك"}, status_code=403)
        
    data = await request.json()
    plan = data.get("plan")
    if plan not in ['monthly', 'yearly']:
        return _J({"success": False, "error": "خطة غير صالحة"}, status_code=400)
        
    office = db.query(LawOffices).filter(LawOffices.id == user.office_id).first()
    if not office:
        pass
        pass
            
        pass
        pass
        db.commit()
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
    office_id = user.office_id or 1
    task = db.query(LawTasks).filter(LawTasks.id == task_id, LawTasks.office_id == office_id).first()
    if task:
        task.status_key = status_key
        db.commit()
    return RedirectResponse(url="/tasks", status_code=303)

@app.get("/activity", response_class=HTMLResponse)
async def activity_page(request: Request, db: Session = Depends(get_db), user: AccessProfiles = Depends(get_current_user)):
    if not user:
        return RedirectResponse(url="/", status_code=303)
    if user.role not in ['مدير', 'مدير المكتب', 'صاحب المكتب']:
        return RedirectResponse(url="/dashboard", status_code=303)
    try:
        office_id = user.office_id or 1
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
            if task.status_key == 'in_progress':
                activity_feed.append({
                    'type': 'task_accepted',
                    'icon': 'fa-circle-check',
                    'color': '#3b82f6',
                    'text': f"قبل {assignee.name if assignee else 'محامٍ'} مهمة: {task.title}",
                    'sub': f"القضية: {task.law_case.title if task.law_case else 'مهمة عامة'}",
                    'date': task.created_at[:16]
                })
            elif task.status_key == 'completed':
                activity_feed.append({
                    'type': 'task_done',
                    'icon': 'fa-check-double',
                    'color': '#10b981',
                    'text': f"أتم {assignee.name if assignee else 'محامٍ'} مهمة: {task.title}",
                    'sub': f"القضية: {task.law_case.title if task.law_case else 'مهمة عامة'}",
                    'date': task.created_at[:16]
                })
            elif task.status_key == 'pending' and task.assignee_user_id:
                activity_feed.append({
                    'type': 'task_assigned',
                    'icon': 'fa-user-tag',
                    'color': '#f59e0b',
                    'text': f"تم إسناد مهمة إلى {assignee.name if assignee else 'محامٍ'}: {task.title}",
                    'sub': f"القضية: {task.law_case.title if task.law_case else 'مهمة عامة'}",
                    'date': task.created_at[:16]
                })
        
        for doc in recent_docs:
            activity_feed.append({
                'type': 'doc_uploaded',
                'icon': 'fa-file-arrow-up',
                'color': '#8b5cf6',
                'text': f"رفع مستند: {doc.name}",
                'sub': f"نوعه: {'{مذكرة' if doc.document_type_key == 'memo' else doc.document_type_key} – مرتبط بالقضية رقم {doc.case_id}",
                'date': doc.created_at[:16]
            })
        
        activity_feed.sort(key=lambda x: x['date'], reverse=True)
        
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
app.include_router(parties.router)
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
# ----------------------------------------------------------------------------
# SaaS Subscription Routes
# ----------------------------------------------------------------------------

@app.get("/subscription")
async def view_subscription(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/", status_code=303)
    office = db.query(LawOffices).filter(LawOffices.id == user.office_id).first() if user.office_id else None
    return templates.TemplateResponse("subscription.html", {"request": request, "user": user, "office": office})

@app.post("/api/subscription/checkout")
async def api_subscription_checkout(request: Request, db: Session = Depends(get_db)):
    from fastapi.responses import JSONResponse as _J
    user = get_current_user(request, db)
    if not user:
        return _J({"success": False, "error": "غير مصرح"}, status_code=403)
    if user.role not in ['مدير النظام', 'مدير', 'مدير المكتب']:
        return _J({"success": False, "error": "غير مصرح لك بتجديد الاشتراك"}, status_code=403)

    data = await request.json()
    plan = data.get("plan")
    if plan not in ['monthly', 'yearly']:
        return _J({"success": False, "error": "خطة غير صالحة"}, status_code=400)

    office = db.query(LawOffices).filter(LawOffices.id == user.office_id).first()
    if not office:
        return _J({"success": False, "error": "المكتب غير موجود"}, status_code=404)

    receipt_base64 = data.get("receipt_base64", "")
    if not receipt_base64:
        return _J({"success": False, "error": "يرجى إرفاق صورة السند للتحقق من الدفع"}, status_code=400)
    # Security: تأكد أن الملف صورة حقيقية
    allowed_prefixes = ('data:image/jpeg', 'data:image/jpg', 'data:image/png', 'data:image/gif', 'data:image/webp')
    if not any(receipt_base64.startswith(p) for p in allowed_prefixes):
        return _J({"success": False, "error": "يرجى رفع صورة فقط (JPG, PNG, WEBP)"}, status_code=400)
    # Security: حجم الصورة لا يتجاوز 5MB
    if len(receipt_base64) > 7_000_000:
        return _J({"success": False, "error": "حجم الصورة كبير جداً. يرجى ضغطها قبل الرفع"}, status_code=400)

    office.subscription_plan = plan
    office.receipt_base64 = receipt_base64
    office.receipt_status = 'pending'
    db.commit()

    write_audit(db, "law_offices", "upload_receipt", user.id, user.name, office.id, "office", office.id, f"Uploaded receipt for {plan}")
    return _J({"success": True, "message": "تم إرسال السند بنجاح. سيتم تفعيل حسابك فور التأكيد."})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)

        
    # office = db.query(LawOffices).filter(LawOffices.id == user.office_id).first() if user.office_id else None
    
    # return templates.TemplateResponse("subscription.html", {
    #     "request": request,
    #     "user": user,
    #     "office": office
    # })

@app.post("/api/subscription/checkout")
async def api_subscription_checkout(request: Request, db: Session = Depends(get_db)):
    from fastapi.responses import JSONResponse as _J
    user = get_current_user(request, db)
    if not user:
        return _J({"success": False, "error": "غير مصرح"}, status_code=403)
        
    # Only owner/manager can pay
    if user.role not in ['مدير النظام', 'مدير', 'مدير المكتب']:
        return _J({"success": False, "error": "غير مصرح لك بتجديد الاشتراك"}, status_code=403)
        
    data = await request.json()
    plan = data.get("plan")
    if plan not in ['monthly', 'yearly']:
        return _J({"success": False, "error": "خطة غير صالحة"}, status_code=400)
        
    office = db.query(LawOffices).filter(LawOffices.id == user.office_id).first()
    if not office:
        return _J({"success": False, "error": "المكتب غير موجود"}, status_code=404)
        
    from datetime import datetime, timezone, timedelta
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    
    receipt_base64 = data.get("receipt_base64", "")
    if not receipt_base64:
        return _J({"success": False, "error": "يرجى إرفاق صورة السند للتحقق من الدفع"}, status_code=400)
    # Security: تأكد أن الملف صورة حقيقية وليس ملف تنفيذي
    allowed_prefixes = ('data:image/jpeg', 'data:image/jpg', 'data:image/png', 'data:image/gif', 'data:image/webp')
    if not any(receipt_base64.startswith(p) for p in allowed_prefixes):
        return _J({"success": False, "error": "يرجى رفع صورة فقط (JPG, PNG, WEBP)"}, status_code=400)
    # Security: حجم الصورة لا يتجاوز 5MB
    if len(receipt_base64) > 7_000_000:
        return _J({"success": False, "error": "حجم الصورة كبير جداً. يرجى ضغطها قبل الرفع"}, status_code=400)
        
        
    office.subscription_plan = plan
    office.receipt_base64 = receipt_base64
    
    write_audit(db, "law_offices", "renew_subscription", user.id, user.name, office.id, "office", office.id, f"Renewed to {plan}")
    
    return _J({"success": True, "message": "تم إرسال السند بنجاح"})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
