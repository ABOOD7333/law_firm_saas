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
from database.database import get_db, init_db
from database.models import (AccessProfiles, AuthSessions, LawClients, LawCases, LawOffices,
    LawHearings, LawTransactions, LawExpenses, LawDocuments, LawTasks, PaymentRequest)
import shutil

app = FastAPI(title="Lexzur Clone - SaaS Law Firm Management", version="1.0")

# Ensure database tables are created (critical for Railway deployment)
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

        if request.url.path.startswith("/api/mobile"):

            return await call_next(request)



        csrf_cookie = request.cookies.get("csrf_token")

        if not csrf_cookie:

            csrf_cookie = str(uuid.uuid4())

            

        if request.method in ["POST", "PUT", "DELETE", "PATCH"]:

            # â”€â”€ ط«ط؛ط±ط© 6 ظ…ظڈطµظ„ط­ط©: طھظپط¹ظٹظ„ CSRF ظ„ط¬ظ…ظٹط¹ ط§ظ„ظ…ط³ط§ط±ط§طھ ط¨ظ…ط§ ظپظٹظ‡ط§ طµظپط­ط© ط§ظ„ط¯ط®ظˆظ„ â”€â”€

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



# â”€â”€â”€ Safe Error Handler â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def _safe_error(tb_str: str = "") -> HTMLResponse:

    """ظٹط¹ط±ط¶ طھظپط§طµظٹظ„ ط§ظ„ط®ط·ط£ ظپظٹ ط§ظ„طھط·ظˆظٹط± ظپظ‚ط· â€” ظٹط®ظپظٹظ‡ط§ ظپظٹ ط§ظ„ط¥ظ†طھط§ط¬."""

    if True: # SECURITY FIX: Never expose tracebacks

        return HTMLResponse(

            content="<div style='font-family:sans-serif;padding:40px;text-align:center;direction:rtl'>"

                    "<h2 style='color:#dc2626'>âڑ ï¸ڈ ط­ط¯ط« ط®ط·ط£ ط¯ط§ط®ظ„ظٹ</h2>"

                    "<p style='color:#64748b'>ظٹط±ط¬ظ‰ ط§ظ„ظ…ط­ط§ظˆظ„ط© ظ…ط±ط© ط£ط®ط±ظ‰ ط£ظˆ ط§ظ„طھظˆط§طµظ„ ظ…ط¹ ط§ظ„ط¯ط¹ظ… ط§ظ„ظپظ†ظٹ.</p>"

                    "</div>",

            status_code=500

        )

    return HTMLResponse(

        content=f"<pre dir='ltr' style='background:#1e1e1e;color:#f8f8f2;padding:20px;font-size:13px;overflow:auto'>{tb_str}</pre>",

        status_code=500

    )





import time

from fastapi.responses import JSONResponse



_ip_login_attempts = {}



class LoginRateLimitMiddleware(BaseHTTPMiddleware):

    async def dispatch(self, request: Request, call_next):

        if request.url.path in ["/api/login", "/api/superadmin-login"] and request.method == "POST":

            ip = request.client.host or "127.0.0.1"

            now = time.time()

            attempts, last_time = _ip_login_attempts.get(ip, (0, 0))

            if now - last_time < 300:

                if attempts >= 10:

                    return JSONResponse({"success": False, "error": "طھظ… ط­ط¸ط± ط§ظ„ظ€ IP ظ…ط¤ظ‚طھط§ظ‹ ط¨ط³ط¨ط¨ ظƒط«ط±ط© ط§ظ„ظ…ط­ط§ظˆظ„ط§طھ. ط§ظ†طھط¸ط± 5 ط¯ظ‚ط§ط¦ظ‚."}, status_code=429)

            else:

                attempts = 0

            _ip_login_attempts[ip] = (attempts + 1, now)

        return await call_next(request)



app.add_middleware(LoginRateLimitMiddleware)



from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(

    CORSMiddleware,

    allow_origins=["http://localhost", "http://localhost:7882", "https://web-production-80e9e.up.railway.app"],

    allow_origin_regex=r"https?://.*",

    allow_credentials=True,

    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],

    allow_headers=["*"],

    expose_headers=["*"],

)



# Mount static files

app.mount("/static", StaticFiles(directory="static"), name="static")



# Templates setup - imported from dependencies to avoid circular imports in routers

from dependencies import templates, get_current_user



@app.get("/", response_class=HTMLResponse)

async def login_page(request: Request, user: AccessProfiles = Depends(get_current_user)):

    # ط¥ط°ط§ ظƒط§ظ† ط§ظ„ظ…ط³طھط®ط¯ظ… ظ…ط³ط¬ظ„ ط¯ط®ظˆظ„ ظ…ط³ط¨ظ‚ط§ظ‹طŒ ظ†ظˆط¬ظ‡ظ‡ ظ„ظ„ظˆط­ط© ط§ظ„طھط­ظƒظ… ظ…ط¨ط§ط´ط±ط©

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



# ظ…ط³ط§ط­ط© ظ„طھط®ط²ظٹظ† ط§ظ„ط±ظ…ظˆط² ط§ظ„ط¢ظ…ظ†ط© ظ…ط¤ظ‚طھط§ظ‹ (ظٹظپط¶ظ„ Redis ظپظٹ ط§ظ„ط¥ظ†طھط§ط¬)

_reset_tokens = {}

_temp_2fa_sessions = {}



# ط³ط¬ظ„ ط¨ط³ظٹط· ظ„طھطھط¨ط¹ ط·ظ„ط¨ط§طھ OTP ظ„ظ…ظ†ط¹ ط¥ط؛ط±ط§ظ‚ ط§ظ„ط¥ظٹظ…ظٹظ„ (Rate Limiting)

import time

_otp_rate_limit = {}

_ip_rate_limit = {}  # ظ„طھطھط¨ط¹ ظ…ط­ط§ظˆظ„ط§طھ طھط³ط¬ظٹظ„ ط§ظ„ط¯ط®ظˆظ„ ط§ظ„ط®ط§ط·ط¦ط© ظ„ظƒظ„ IP



@app.post("/api/forgot-send-otp")

async def api_forgot_send_otp(request: Request, db: Session = Depends(get_db)):

    """ط¥ط±ط³ط§ظ„ ط±ظ…ط² OTP ظ„ط§ط³طھط¹ط§ط¯ط© ظƒظ„ظ…ط© ط§ظ„ظ…ط±ظˆط± ط¨ط¹ط¯ ط§ظ„طھط­ظ‚ظ‚ ظ…ظ† طھط§ط±ظٹط® ط§ظ„ظ…ظٹظ„ط§ط¯"""

    data = await request.json()

    email = data.get("email", "").strip()

    phone = data.get("phone", "").strip()



    if not email or not phone:

        return _JSONResponse({"success": False, "error": "ط§ظ„ط±ط¬ط§ط، ط¥ط¯ط®ط§ظ„ ط§ظ„ط¨ط±ظٹط¯ ط§ظ„ط¥ظ„ظƒطھط±ظˆظ†ظٹ ظˆط±ظ‚ظ… ط§ظ„ظ‡ط§طھظپ"}, status_code=400)



    user = db.query(AccessProfiles).filter(

        (AccessProfiles.email == email) | (AccessProfiles.username == email)

    ).first()



    if not user:

        return _JSONResponse({"success": False, "error": "ظ„ظ… ظٹطھظ… ط§ظ„ط¹ط«ظˆط± ط¹ظ„ظ‰ ط­ط³ط§ط¨ ط¨ظ‡ط°ظ‡ ط§ظ„ط¨ظٹط§ظ†ط§طھ"}, status_code=404)



    if user.phone != phone:

        return _JSONResponse({"success": False, "error": "ط±ظ‚ظ… ط§ظ„ظ‡ط§طھظپ ط؛ظٹط± ظ…ط·ط§ط¨ظ‚ ظ„ظ„ط¨ظٹط§ظ†ط§طھ ط§ظ„ظ…ط³ط¬ظ„ط©"}, status_code=400)



    # Rate Limiting Check (3 ظ…ط­ط§ظˆظ„ط§طھ ظƒظ„ 15 ط¯ظ‚ظٹظ‚ط©)

    now = time.time()

    user_requests = _otp_rate_limit.get(email, [])

    # طھظ†ط¸ظٹظپ ط§ظ„ظ…ط­ط§ظˆظ„ط§طھ ط§ظ„ظ‚ط¯ظٹظ…ط© (ط£ظ‚ط¯ظ… ظ…ظ† 15 ط¯ظ‚ظٹظ‚ط© = 900 ط«ط§ظ†ظٹط©)

    user_requests = [req_time for req_time in user_requests if now - req_time < 900]

    

    if len(user_requests) >= 3:

        _otp_rate_limit[email] = user_requests

        return _JSONResponse({"success": False, "error": "طھط¬ط§ظˆط²طھ ط§ظ„ط­ط¯ ط§ظ„ظ…ط³ظ…ظˆط­ ظ…ظ† ط§ظ„ظ…ط­ط§ظˆظ„ط§طھ. ظٹط±ط¬ظ‰ ط§ظ„ط§ظ†طھط¸ط§ط± 15 ط¯ظ‚ظٹظ‚ط©."}, status_code=429)



    user_requests.append(now)

    _otp_rate_limit[email] = user_requests



    code = generate_otp(6)

    store_otp(email, code)

    sent = send_otp_email(email, code, "forgot_password")

    

    if sent:

        return _JSONResponse({"success": True, "message": "طھظ… ط¥ط±ط³ط§ظ„ ط±ظ…ط² ط§ظ„طھط­ظ‚ظ‚"})

    return _JSONResponse({"success": False, "error": "ظپط´ظ„ ط¥ط±ط³ط§ظ„ ط§ظ„ط¨ط±ظٹط¯ ط§ظ„ط¥ظ„ظƒطھط±ظˆظ†ظٹ"}, status_code=500)



@app.post("/api/forgot-verify-otp")

async def api_forgot_verify_otp(request: Request):

    """ط§ظ„طھط­ظ‚ظ‚ ظ…ظ† ط±ظ…ط² OTP ظˆط¥طµط¯ط§ط± Token ظ…ط¤ظ‚طھ ط¢ظ…ظ†"""

    data = await request.json()

    identifier = data.get("identifier", "").strip()

    code = data.get("code", "").strip()



    if verify_otp(identifier, code):

        token = secrets.token_hex(16)

        _reset_tokens[token] = identifier

        return _JSONResponse({"success": True, "token": token})

    return _JSONResponse({"success": False, "error": "ط§ظ„ط±ظ…ط² ط؛ظٹط± طµط­ظٹط­ ط£ظˆ ظ…ظ†طھظ‡ظٹ ط§ظ„طµظ„ط§ط­ظٹط©"}, status_code=400)



@app.post("/api/reset-password-secure")

async def api_reset_password_secure(request: Request, db: Session = Depends(get_db)):

    """ط¥ط¹ط§ط¯ط© طھط¹ظٹظٹظ† ظƒظ„ظ…ط© ط§ظ„ظ…ط±ظˆط± ط¨ط´ظƒظ„ ط¢ظ…ظ† ط¨ط§ط³طھط®ط¯ط§ظ… ط§ظ„طھظˆظƒظ†"""

    data = await request.json()

    email = data.get("email", "").strip()

    new_username = data.get("new_username", "").strip()

    new_password = data.get("new_password", "").strip()

    token = data.get("token", "").strip()



    # طھط­ظ‚ظ‚ ط£ظ…ظ†ظٹ: ظ‡ظ„ ط§ظ„طھظˆظƒظ† طµط§ظ„ط­ ظˆظ…ط·ط§ط¨ظ‚ ظ„ظ„ط¨ط±ظٹط¯طں

    if not token or _reset_tokens.get(token) != email:

        return _JSONResponse({"success": False, "error": "ط·ظ„ط¨ ط؛ظٹط± ظ…طµط±ط­ ط¨ظ‡ ط£ظˆ ط§ظ†طھظ‡طھ طµظ„ط§ط­ظٹط© ط§ظ„ط¬ظ„ط³ط©"}, status_code=403)



    if len(new_password) < 8:

        return _JSONResponse({"success": False, "error": "ظƒظ„ظ…ط© ط§ظ„ظ…ط±ظˆط± ظٹط¬ط¨ ط£ظ† طھظƒظˆظ† 8 ط£ط­ط±ظپ/ط£ط±ظ‚ط§ظ… ط¹ظ„ظ‰ ط§ظ„ط£ظ‚ظ„"}, status_code=400)



    user = db.query(AccessProfiles).filter(AccessProfiles.email == email).first()



    if not user:

        return _JSONResponse({"success": False, "error": "ظ„ظ… ظٹظڈط¹ط«ط± ط¹ظ„ظ‰ ظ‡ط°ط§ ط§ظ„ط­ط³ط§ط¨"}, status_code=404)



    user.access_pin_hash = _hash_pin(new_password)

    user.failed_attempts = 0

    

    if new_username:

        if new_username != user.username:

            existing = db.query(AccessProfiles).filter(AccessProfiles.username == new_username).first()

            if existing:

                return _JSONResponse({"success": False, "error": "ط§ط³ظ… ط§ظ„ظ…ط³طھط®ط¯ظ… ظ…ط­ط¬ظˆط²طŒ ط§ط®طھط± ط§ط³ظ…ط§ظ‹ ط¢ط®ط±"}, status_code=400)

            user.username = new_username



    db.commit()

    # ط¥طھظ„ط§ظپ ط§ظ„طھظˆظƒظ† ظ„ظ…ظ†ط¹ ط¥ط¹ط§ط¯ط© ط§ظ„ط§ط³طھط®ط¯ط§ظ…

    del _reset_tokens[token]

    return _JSONResponse({"success": True, "message": "طھظ… طھط؛ظٹظٹط± ط§ظ„ط¨ظٹط§ظ†ط§طھ ط¨ظ†ط¬ط§ط­"})



@app.post("/api/verify-otp")

async def api_verify_otp(request: Request, db: Session = Depends(get_db)):

    """ط§ظ„طھط­ظ‚ظ‚ ظ…ظ† ط±ظ…ط² OTP ط§ظ„ط¹ط§ظ… (ظ„ظ„طھط³ط¬ظٹظ„)"""

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

    return _JSONResponse({"success": False, "error": "ط§ظ„ط±ظ…ط² ط؛ظٹط± طµط­ظٹط­ ط£ظˆ ظ…ظ†طھظ‡ظٹ ط§ظ„طµظ„ط§ط­ظٹط©"}, status_code=400)



def _verify_pin(pin: str, stored_hash: str) -> bool:

    import hmac, base64

    if not stored_hash or not pin:

        return False

    normalized = pin.translate(str.maketrans("ظ ظ،ظ¢ظ£ظ¤ظ¥ظ¦ظ§ظ¨ظ©غ°غ±غ²غ³غ´غµغ¶غ·غ¸غ¹", "01234567890123456789")).strip()

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

            context={"error": "طھظ… ط­ط¸ط± ط¹ظ†ظˆط§ظ† ط§ظ„ظ€ IP ظ…ط¤ظ‚طھط§ظ‹ ط¨ط³ط¨ط¨ ظƒط«ط±ط© ط§ظ„ظ…ط­ط§ظˆظ„ط§طھ ط§ظ„ط®ط§ط·ط¦ط©. ظٹط±ط¬ظ‰ ط§ظ„ط§ظ†طھط¸ط§ط± 15 ط¯ظ‚ظٹظ‚ط©."}

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

                context={"error": "ظ‡ط°ط§ ط§ظ„ط­ط³ط§ط¨ ظ…ظˆظ‚ظˆظپ. ظٹط±ط¬ظ‰ ظ…ط±ط§ط¬ط¹ط© ط¥ط¯ط§ط±ط© ط§ظ„ظ…ظƒطھط¨."}

            )



        # طھط­ظ‚ظ‚ ظ…ظ† ط­ط§ظ„ط© ط§ظ„ظ…ظƒطھط¨

        office = db.query(LawOffices).filter(LawOffices.id == user.office_id).first() if user.office_id else None

        if office and office.is_active == 0:

            return templates.TemplateResponse(

                request=request,

                name="login.html",

                context={"error": "ظ…ظƒطھط¨ ط§ظ„ظ…ط­ط§ظ…ط§ط© ط§ظ„ط®ط§طµ ط¨ظƒ ظ…ظˆظ‚ظˆظپ ط­ط§ظ„ظٹط§ظ‹ ظ…ظ† ظ‚ط¨ظ„ ط¥ط¯ط§ط±ط© ط§ظ„ظ…ظ†طµط©. ظٹط±ط¬ظ‰ ط§ظ„طھظˆط§طµظ„ ظ…ط¹ ط§ظ„ط¯ط¹ظ… ط§ظ„ظپظ†ظٹ."}

            )

            

        if user.failed_attempts >= 10:

            return templates.TemplateResponse(

                request=request,

                name="login.html",

                context={"error": "طھظ… ظ‚ظپظ„ ط§ظ„ط­ط³ط§ط¨ ظ…ط¤ظ‚طھط§ظ‹ ط¨ط³ط¨ط¨ ظƒط«ط±ط© ط§ظ„ظ…ط­ط§ظˆظ„ط§طھ ط§ظ„ط®ط§ط·ط¦ط©. ظٹط±ط¬ظ‰ ط§ظ„طھظˆط§طµظ„ ظ…ط¹ ط§ظ„ط¥ط¯ط§ط±ط©."}

            )

            

        if user.role == 'ظ…ظˆظƒظ„':

            if not case_number or user.case_number != case_number:

                # ظ†ط³ط¬ظ„ ظ…ط­ط§ظˆظ„ط© ط®ط§ط·ط¦ط© ظ„طھط¬ظ†ط¨ ط§ظ„طھط®ظ…ظٹظ†

                user.failed_attempts += 1

                db.commit()

                return templates.TemplateResponse(

                    request=request,

                    name="login.html",

                    context={"error": "ط±ظ‚ظ… ط§ظ„ظ‚ط¶ظٹط© ط؛ظٹط± ظ…ط·ط§ط¨ظ‚ ظ„ظ„ط¨ظٹط§ظ†ط§طھطŒ ظٹط±ط¬ظ‰ ط§ظ„طھط£ظƒط¯ ظˆط§ظ„ظ…ط­ط§ظˆظ„ط© ظ…ط±ط© ط£ط®ط±ظ‰."}

                )

            

        if _verify_pin(password, user.access_pin_hash):

            user.failed_attempts = 0

            db.commit()

            

            # Check if 2FA is enabled for this user (1 indicates enabled)

            if getattr(user, "is_2fa_enabled", 0) == 1:

                temp_token = str(uuid.uuid4())

                _temp_2fa_sessions[temp_token] = user.id

                

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

            

            is_secure = not (request.url.hostname in ["127.0.0.1", "localhost"])

            response = RedirectResponse(url="/dashboard", status_code=303)

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

            user.failed_attempts += 1

            db.commit()

            _ip_rate_limit.setdefault(client_ip, []).append(now)

            app_logger.warning(f"LOGIN_FAIL | user={user.id} | attempts={user.failed_attempts}")

            return templates.TemplateResponse(

                request=request,

                name="login.html",

                context={"error": f"ط¨ظٹط§ظ†ط§طھ ط§ظ„ط¯ط®ظˆظ„ ط؛ظٹط± طµط­ظٹط­ط©. طھط¨ظ‚طھ {10 - user.failed_attempts} ظ…ط­ط§ظˆظ„ط§طھ." if user.failed_attempts < 10 else "طھظ… ظ‚ظپظ„ ط§ظ„ط­ط³ط§ط¨."}

            )

    else:

        # â”€â”€ ط«ط؛ط±ط© 4 ظ…ظڈطµظ„ط­ط©: طھط£ط®ظٹط± ظˆظ‡ظ…ظٹ ظ„ظ…ظ†ط¹ User Enumeration ط¹ط¨ط± ظ‚ظٹط§ط³ ط³ط±ط¹ط© ط§ظ„ط§ط³طھط¬ط§ط¨ط© â”€â”€

        await asyncio.sleep(0.3)

        _ip_rate_limit.setdefault(client_ip, []).append(now)

        app_logger.warning(f"LOGIN_FAIL | user_not_found | input={email[:20]}")

        return templates.TemplateResponse(

            request=request,

            name="login.html",

            context={"error": "ط§ظ„ط¨ط±ظٹط¯ ط§ظ„ط¥ظ„ظƒطھط±ظˆظ†ظٹ ط£ظˆ ظƒظ„ظ…ط© ط§ظ„ظ…ط±ظˆط± ط؛ظٹط± طµط­ظٹط­ط©."}

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



@app.get("/login-2fa", response_class=HTMLResponse)

async def login_2fa_page(request: Request):

    temp_token = request.cookies.get("temp_2fa_token")

    if not temp_token or temp_token not in _temp_2fa_sessions:

        return RedirectResponse(url="/", status_code=303)

    return templates.TemplateResponse(request=request, name="login_2fa.html", context={})



@app.post("/login-2fa")

async def login_2fa_submit(

    request: Request,

    code: str = Form(...),

    db: Session = Depends(get_db)

):

    temp_token = request.cookies.get("temp_2fa_token")

    if not temp_token or temp_token not in _temp_2fa_sessions:

        return templates.TemplateResponse(request=request, name="login.html", context={"error": "ط§ظ†طھظ‡طھ طµظ„ط§ط­ظٹط© ط¬ظ„ط³ط© ط§ظ„طھط­ظ‚ظ‚طŒ ظٹط±ط¬ظ‰ طھط³ط¬ظٹظ„ ط§ظ„ط¯ط®ظˆظ„ ظ…ط¬ط¯ط¯ط§ظ‹."})

        

    user_id = _temp_2fa_sessions[temp_token]

    user = db.query(AccessProfiles).filter(AccessProfiles.id == user_id).first()

    if not user:

        return RedirectResponse(url="/", status_code=303)

        

    if verify_otp(user.email, code.strip()):

        # OTP is valid! Clean up temp session

        del _temp_2fa_sessions[temp_token]

        

        # Issue real session token

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

        

        app_logger.info(f"LOGIN_OK_2FA | user={user.id} | role={user.role} | office={user.office_id}")

        

        # Enforce secure cookies dynamically based on hostname

        is_secure = not (request.url.hostname in ["127.0.0.1", "localhost"])

        

        response = RedirectResponse(url="/dashboard", status_code=303)

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

        return templates.TemplateResponse(

            request=request,

            name="login_2fa.html",

            context={"error": "ط±ظ…ط² ط§ظ„طھط­ظ‚ظ‚ ط§ظ„ط«ظ†ط§ط¦ظٹ ط؛ظٹط± طµط­ظٹط­ ط£ظˆ ظ…ظ†طھظ‡ظٹ ط§ظ„طµظ„ط§ط­ظٹط©."}

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

        # â”€â”€ ط¨ظˆط§ط¨ط© ط§ظ„ظ…ظˆظƒظ„ظٹظ† (Client Portal) â”€â”€

        if user.role == 'ظ…ظˆظƒظ„':

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

            

        # â”€â”€ ظ„ظˆط­ط© طھط­ظƒظ… ط§ظ„ظ…ط­ط§ظ…ظٹظ† ظˆط§ظ„ظ…ط¯ط±ط§ط، â”€â”€

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

        if user.role == 'ظ…ظˆظƒظ„':

            return templates.TemplateResponse(request=request, name="client_portal.html", context={"user": user, "my_cases": [], "my_hearings": [], "active_page": "dashboard"})

        return templates.TemplateResponse(request=request, name="dashboard.html", context={"user": user, "active_page": "dashboard", "my_tasks": [], "total_cases": 0, "total_clients": 0, "pending_tasks_count": 0})



@app.get("/api/case-numbers")

async def get_case_numbers(db: Session = Depends(get_db), user: AccessProfiles = Depends(get_current_user)):

    if not user:

        return _JSONResponse([])

    office_id = user.office_id or 1

    query = db.query(LawCases.case_number).filter(LawCases.office_id == office_id, LawCases.is_deleted == 0)

    

    if user.role in ['ظ…ط­ط§ظ…ظٹ', 'ظ…ط­ط§ظ…ظچ'] and user.can_view_all_cases == 0:

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

    

    # ط§ظ„طھط£ظƒط¯ ظ…ظ† ط¹ط¯ظ… طھظƒط±ط§ط± ط§ط³ظ… ط§ظ„ظ…ط³طھط®ط¯ظ…

    existing = db.query(AccessProfiles).filter(AccessProfiles.username == username).first()

    if existing:

        # ظ„ظ„طھط؛ط§ط¶ظٹ ظ…ط¤ظ‚طھط§ظ‹ ظ„ظˆ ظƒط§ظ† ظ…ظˆط¬ظˆط¯طŒ ط§ظ„ط£ظپط¶ظ„ ط¥ط±ط¬ط§ط¹ ط±ط³ط§ظ„ط© ظ„ظƒظ† ط³ظ†ظ‚ظˆظ… ط¨طھط؛ظٹظٹط±ظ‡ ظ„طھط¬ظ†ط¨ ط§ظ„ط®ط·ط£

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

    

    # ط¥ظ†ط´ط§ط، ط­ط³ط§ط¨ ط¯ط®ظˆظ„ ظ„ظ„ظ…ظˆظƒظ„

    new_user = AccessProfiles(

        name=name,

        username=username,

        email=email or f"{username}@client.local",

        phone=phone or username,

        case_number=case_number,

        access_pin_hash=_hash_pin(password),

        role='ظ…ظˆظƒظ„',

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

        

        # طھط­ط¯ظٹط« ط¨ظٹط§ظ†ط§طھ ط§ظ„ط¯ط®ظˆظ„ ط£ظٹط¶ط§ظ‹ ط¥ظ† ظˆط¬ط¯طھ

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

        

        # طھظ‚ظٹظٹط¯ ط§ظ„ظ…ط­ط§ظ…ظٹ ط¨ط±ط¤ظٹط© ظ‚ط¶ط§ظٹط§ظ‡ ظپظ‚ط·

        if user.role in ['ظ…ط­ط§ظ…ظٹ', 'ظ…ط­ط§ظ…ظچ']:

            query = query.filter(LawCases.lead_lawyer_id == user.id)

            

        cases = query.order_by(LawCases.created_at.desc()).all()

        clients = db.query(LawClients).filter(LawClients.office_id == office_id).all()

        lawyers = db.query(AccessProfiles).filter(AccessProfiles.office_id == office_id, AccessProfiles.role != "ظ…ظˆظƒظ„").all()

        

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

        office = LawOffices(name="ط§ظ„ظ…ظƒطھط¨ ط§ظ„ط±ط¦ظٹط³ظٹ", status_key="active")

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

        

    office_id = user.office_id or 1

    query = db.query(LawCases).filter(LawCases.office_id == office_id, LawCases.is_deleted == 0)

    

    if user.role in ['ظ…ط­ط§ظ…ظٹ', 'ظ…ط­ط§ظ…ظچ'] and user.can_view_all_cases == 0:

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

        office_id = user.office_id or 1

        case = db.query(LawCases).filter(LawCases.id == case_id, LawCases.office_id == office_id).first()

        if not case:

            return HTMLResponse(content="ط§ظ„ظ‚ط¶ظٹط© ط؛ظٹط± ظ…ظˆط¬ظˆط¯ط© ط£ظˆ ظ„ط§ طھظ…ظ„ظƒ طµظ„ط§ط­ظٹط© ط§ظ„ظˆطµظˆظ„ ظ„ظ‡ط§", status_code=404)

            

        # ظ…ظ†ط¹ ط§ظ„ظ…ط­ط§ظ…ظٹ ظ…ظ† ط¯ط®ظˆظ„ ظ‚ط¶ظٹط© ط؛ظٹط± طھط§ط¨ط¹ط© ظ„ظ‡

        if user.role in ['ظ…ط­ط§ظ…ظٹ', 'ظ…ط­ط§ظ…ظچ'] and case.lead_lawyer_id != user.id:

            return HTMLResponse(content="<script>alert('ط؛ظٹط± ظ…طµط±ط­ ظ„ظƒ ط¨ط§ظ„ط¯ط®ظˆظ„ ظ„ظ‡ط°ظ‡ ط§ظ„ظ‚ط¶ظٹط©'); window.location.href='/cases';</script>", status_code=403)

            

        hearings = db.query(LawHearings).filter(LawHearings.case_id == case_id).order_by(LawHearings.hearing_at.desc()).all()

        lawyer = db.query(AccessProfiles).filter(AccessProfiles.id == case.lead_lawyer_id).first() if case.lead_lawyer_id else None

        

        clients = db.query(LawClients).filter(LawClients.office_id == office_id).all()

        lawyers = db.query(AccessProfiles).filter(AccessProfiles.role.in_(['ظ…ط­ط§ظ…ظچ', 'ظ…ط¯ظٹط±', 'ظ…ط¯ظٹط± ط§ظ„ظ…ظƒطھط¨']), AccessProfiles.office_id == office_id).all()

        

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

    

    if user.role in ['ظ…ط­ط§ظ…ظٹ', 'ظ…ط­ط§ظ…ظچ'] and case and case.lead_lawyer_id != user.id:

        return HTMLResponse(content="<script>alert('ط؛ظٹط± ظ…طµط±ط­ ظ„ظƒ ط¨طھط¹ط¯ظٹظ„ ظ‡ط°ظ‡ ط§ظ„ظ‚ط¶ظٹط©'); window.history.back();</script>", status_code=403)

        

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



@app.get("/hearings", response_class=HTMLResponse)

async def hearings_page(request: Request, db: Session = Depends(get_db), user: AccessProfiles = Depends(get_current_user)):

    if not user:

        return RedirectResponse(url="/", status_code=303)

        

    try:

        office_id = user.office_id or 1

        

        cases_query = db.query(LawCases).filter(LawCases.office_id == office_id, LawCases.is_deleted == 0)

        hearings_query = db.query(LawHearings).filter(LawHearings.office_id == office_id)

        

        if user.role in ['ظ…ط­ط§ظ…ظٹ', 'ظ…ط­ط§ظ…ظچ']:

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

        if not case: return HTMLResponse(content="<script>alert('ط؛ظٹط± ظ…طµط±ط­'); window.history.back();</script>", status_code=403)

        

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

        if not case: return HTMLResponse(content="<script>alert('ط؛ظٹط± ظ…طµط±ط­'); window.history.back();</script>", status_code=403)

        

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

        if not case: return HTMLResponse(content="<script>alert('ط؛ظٹط± ظ…طµط±ط­'); window.history.back();</script>", status_code=403)

        

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

        # ظپظ‚ط· ظ…ط³طھط®ط¯ظ…ظˆ ظ†ظپط³ ط§ظ„ظ…ظƒطھط¨

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

        

    if user.role not in ['ظ…ط¯ظٹط±', 'ظ…ط¯ظٹط± ط§ظ„ظ…ظƒطھط¨', 'طµط§ط­ط¨ ط§ظ„ظ…ظƒطھط¨']:

        return HTMLResponse(content="<script>alert('ط؛ظٹط± ظ…طµط±ط­ ظ„ظƒ ط¨طھط¹ط¯ظٹظ„ ط¨ظٹط§ظ†ط§طھ ط§ظ„ظ…ظƒطھط¨'); window.history.back();</script>", status_code=403)

        

    office_id_to_update = office_id or user.office_id

    if office_id_to_update:

        office = db.query(LawOffices).filter(LawOffices.id == office_id_to_update).first()

        # ظ†طھط­ظ‚ظ‚ ط£ظ† ط§ظ„ظ…ط³طھط®ط¯ظ… ظٹظ†طھظ…ظٹ ظ„ظ‡ط°ط§ ط§ظ„ظ…ظƒطھط¨ ظ‚ط¨ظ„ ط§ظ„طھط¹ط¯ظٹظ„ (ط£ظˆ ط£ظ†ظ‡ ط³ظˆط¨ط± ط¢ط¯ظ…ظ†)

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

        

    if user.role not in ['ظ…ط¯ظٹط±', 'ظ…ط¯ظٹط± ط§ظ„ظ…ظƒطھط¨', 'طµط§ط­ط¨ ط§ظ„ظ…ظƒطھط¨']:

        return HTMLResponse(content="<script>alert('ظ„ظٹط³ ظ„ط¯ظٹظƒ طµظ„ط§ط­ظٹط© ظ„ط¥ط¶ط§ظپط© ظ…ط³طھط®ط¯ظ…ظٹظ†'); window.history.back();</script>", status_code=403)

        

    office_id = user.office_id or 1

    

    ALLOWED_OFFICE_ROLES = {'ظ…ط¯ظٹط±', 'ظ…ط­ط§ظ…ظٹ', 'ظ…ط­ط§ظ…ظچ', 'ط³ظƒط±طھظٹط±', 'ظ…ط­ط§ط³ط¨', 'ظ…ظˆظƒظ„'}

    if role not in ALLOWED_OFFICE_ROLES:

        return HTMLResponse(content="<script>alert('ط¯ظˆط± ط§ظ„ط¹ط¶ظˆ ط§ظ„ظ…ط®طھط§ط± ط؛ظٹط± طµط§ظ„ط­'); window.history.back();</script>", status_code=400)

    

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



# ط§ظ„ط£ط¯ظˆط§ط± ط§ظ„ظ…ط³ظ…ظˆط­ ظ„ظ‡ط§ ط¨ط¥ط¯ط§ط±ط© ط§ظ„ظ…ط³طھط®ط¯ظ…ظٹظ†

_ADMIN_ROLES = {'ظ…ط¯ظٹط±', 'ظ…ط¯ظٹط± ط§ظ„ظ…ظƒطھط¨', 'طµط§ط­ط¨ ط§ظ„ظ…ظƒطھط¨'}



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



    # ًں”´ طھط­ظ‚ظ‚ ظ…ظ† ط§ظ„طµظ„ط§ط­ظٹط© â€” ظپظ‚ط· ط§ظ„ط£ط¯ظˆط§ط± ط§ظ„ط¥ط¯ط§ط±ظٹط©

    if user.role not in _ADMIN_ROLES:

        app_logger.warning(

            f"SECURITY | edit_user blocked | actor={user.id} role={user.role} target={user_id}"

        )

        return RedirectResponse(url="/settings", status_code=303)



    office_id = user.office_id or 1



    # ًں”´ IDOR protection â€” ط§ظ„ظ‡ط¯ظپ ظٹط¬ط¨ ط£ظ† ظٹظƒظˆظ† ظپظٹ ظ†ظپط³ ط§ظ„ظ…ظƒطھط¨

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

        # طھط¹ط¯ظٹظ„ ط¹ط¶ظˆ ط¢ط®ط±

        ALLOWED_OFFICE_ROLES = {'ظ…ط¯ظٹط±', 'ظ…ط­ط§ظ…ظٹ', 'ظ…ط­ط§ظ…ظچ', 'ط³ظƒط±طھظٹط±', 'ظ…ط­ط§ط³ط¨', 'ظ…ظˆظƒظ„'}

        if role not in ALLOWED_OFFICE_ROLES:

            return HTMLResponse(content="<script>alert('ط¯ظˆط± ط§ظ„ط¹ط¶ظˆ ط§ظ„ظ…ط®طھط§ط± ط؛ظٹط± طµط§ظ„ط­'); window.history.back();</script>", status_code=400)

        target_user.name = name

        target_user.phone = phone

        target_user.email = email

        target_user.role = role

        target_user.is_active = is_active

        target_user.birth_date = birth_date

    else:

        # ط§ظ„ظ…ط¯ظٹط± ظٹط¹ط¯ظ‘ظ„ ظ†ظپط³ظ‡ â€” ظ„ط§ ظٹظڈط؛ظٹظ‘ط± ط¯ظˆط±ظ‡ ط£ظˆ ط­ط§ظ„ط© ظ†ط´ط§ط·ظ‡

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

        role        = (data.get("role") or "ظ…ظˆظƒظ„").strip()

        username    = (data.get("username") or "").strip()

        name        = (data.get("name") or "").strip()

        phone       = (data.get("phone") or "").strip()

        email       = (data.get("email") or "").strip().lower()

        birth_date  = (data.get("birth_date") or "").strip()

        access_pin  = (data.get("access_pin") or "").strip()

        lawyer_name = (data.get("lawyer_name") or "").strip()



        if not all([username, name, email, birth_date, access_pin]):

            return _J({"success": False, "error": "ط¬ظ…ظٹط¹ ط§ظ„ط­ظ‚ظˆظ„ ط§ظ„ط£ط³ط§ط³ظٹط© ظ…ط·ظ„ظˆط¨ط©"}, status_code=400)

            

        if len(access_pin) < 6:

            return _J({"success": False, "error": "ظƒظ„ظ…ط© ط§ظ„ظ…ط±ظˆط± ظٹط¬ط¨ ط£ظ† طھظƒظˆظ† 6 ط£ط­ط±ظپ/ط£ط±ظ‚ط§ظ… ط¹ظ„ظ‰ ط§ظ„ط£ظ‚ظ„"}, status_code=400)



        if db.query(AccessProfiles).filter(

            (AccessProfiles.email == email) | (AccessProfiles.username == username) | (AccessProfiles.phone == phone)

        ).first():

            return _J({"success": False, "error": "ط§ظ„ط¨ط±ظٹط¯ ط§ظ„ط¥ظ„ظƒطھط±ظˆظ†ظٹطŒ ط§ط³ظ… ط§ظ„ظ…ط³طھط®ط¯ظ…طŒ ط£ظˆ ط±ظ‚ظ… ط§ظ„ظ‡ط§طھظپ ظ…ط³ط¬ظ„ ظ…ط³ط¨ظ‚ط§ظ‹"}, status_code=409)



        # ط¥ط±ط³ط§ظ„ ط±ظ…ط² ط§ظ„طھط­ظ‚ظ‚ ط£ظˆظ„ط§ظ‹ ط¨ط¯ظˆظ† ط§ظ„ط­ظپط¸ ظپظٹ ظ‚ط§ط¹ط¯ط© ط§ظ„ط¨ظٹط§ظ†ط§طھ

        code = generate_otp(6)

        store_otp(email, code)

        is_sent = send_otp_email(email, code, "register")

        

        if not is_sent:

            return _J({"success": False, "error": "ظپط´ظ„ ط¥ط±ط³ط§ظ„ ط§ظ„ط¨ط±ظٹط¯ ط§ظ„ط¥ظ„ظƒطھط±ظˆظ†ظٹ. طھط£ظƒط¯ ظ…ظ† طµط­ط© ط§ظ„ط¥ط¹ط¯ط§ط¯ط§طھ."}, status_code=500)

            

        # ط­ظپط¸ ط§ظ„ط¨ظٹط§ظ†ط§طھ ظ…ط¤ظ‚طھط§ظ‹ ظپظٹ ط§ظ„ط°ط§ظƒط±ط© ط­طھظ‰ ظٹطھظ… ط§ظ„طھط­ظ‚ظ‚

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

        return _J({"success": True, "message": "طھظ… ط¥ط±ط³ط§ظ„ ط±ظ…ط² ط§ظ„طھط­ظ‚ظ‚"})

    except Exception as exc:

        app_logger.error(f"api_register_secure error: {exc}", exc_info=True)

        return _J({"success": False, "error": f"ط­ط¯ط« ط®ط·ط£ ط¯ط§ط®ظ„ظٹ: {str(exc)}"}, status_code=500)



@app.post("/api/verify-register-otp")

async def api_verify_register_otp(request: Request, db: Session = Depends(get_db)):

    from fastapi.responses import JSONResponse as _J

    try:

        data  = await request.json()

        email = (data.get("email") or "").strip().lower()

        code  = (data.get("code")  or "").strip()

        

        if not email or not code:

            return _J({"success": False, "error": "ط§ظ„ط¨ظٹط§ظ†ط§طھ ط؛ظٹط± ظ…ظƒطھظ…ظ„ط©"}, status_code=400)

            

        if not verify_otp(email, code):

            return _J({"success": False, "error": "ط±ظ…ط² ط§ظ„طھط­ظ‚ظ‚ ط؛ظٹط± طµط­ظٹط­ ط£ظˆ ظ…ظ†طھظ‡ظٹ ط§ظ„طµظ„ط§ط­ظٹط©"}, status_code=400)

            

        # ط§ط³طھط±ط¬ط§ط¹ ط§ظ„ط¨ظٹط§ظ†ط§طھ ط§ظ„ظ…ط¤ظ‚طھط©

        pending_user = _pending_registrations.get(email)

        if not pending_user:

            return _J({"success": False, "error": "ط§ظ†طھظ‡طھ طµظ„ط§ط­ظٹط© ط¬ظ„ط³ط© ط§ظ„طھط³ط¬ظٹظ„ ط£ظˆ ط£ظ†ظƒ طھط³طھط®ط¯ظ… ظ†ط§ظپط°ط© ظ…ط®طھظ„ظپط©طŒ ظٹط±ط¬ظ‰ ط¥ط¹ط§ط¯ط© طھط¹ط¨ط¦ط© ط§ظ„ط¨ظٹط§ظ†ط§طھ"}, status_code=400)

            

        # ط¥ظ†ط´ط§ط، ظ…ظƒطھط¨ ط¬ط¯ظٹط¯ (ظ…ط³ط§ط­ط© ط¹ظ…ظ„ ظ…ط¹ط²ظˆظ„ط©) ظ„ظƒظ„ ظ…ط³طھط®ط¯ظ… ظٹط³ط¬ظ„ ظ…ظ† ط§ظ„ط®ط§ط±ط¬

        from datetime import datetime, timezone, timedelta

        sub_end = (datetime.now(timezone.utc) + timedelta(days=14)).replace(tzinfo=None).strftime("%Y-%m-%d %H:%M:%S")

        office_name = f"ظ…ظƒطھط¨ {pending_user['name']}" if pending_user['role'] in ['طµط§ط­ط¨ ظ…ظƒطھط¨', 'ظ…ط­ط§ظ…ظٹ'] else f"ط­ط³ط§ط¨ {pending_user['name']}"

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

            role='ظ…ط¯ظٹط±',  # ط¥ط¹ط·ط§ط، طµظ„ط§ط­ظٹط§طھ ظ…ط¯ظٹط± ط§ظ„ظ…ظƒطھط¨ ظƒط§ظ…ظ„ط© ظ„ظƒظ„ ظ…ظ† ظٹط³ط¬ظ„ ظ…ظ† ط§ظ„ط®ط§ط±ط¬

            office_id=new_office.id,

            is_active=1,  # ظ…ظپط¹ظ„ ظ…ط¨ط§ط´ط±ط© ظ„ط£ظ†ظ‡ ط£ط«ط¨طھ ط¥ظٹظ…ظٹظ„ظ‡

            email_verified=1,

            state="draft",

            failed_attempts=0,

        )

        db.add(new_user)

        db.flush()



        write_audit(

            db, table_name="access_profiles", action_name="register",

            actor_user_id=new_user.id, actor_name=pending_user["name"], office_id=new_office.id,

            entity_type="user", entity_id=new_user.id, details=f"طھط³ط¬ظٹظ„ ط­ط³ط§ط¨ ط¬ط¯ظٹط¯ ظˆطھط£ظƒظٹط¯ ط§ظ„ط¨ط±ظٹط¯"

        )

        db.commit()

        

        # طھظ†ط¸ظٹظپ ط§ظ„ط°ط§ظƒط±ط©

        del _pending_registrations[email]

        

        app_logger.info(f"EMAIL_VERIFIED_AND_REGISTERED | user={new_user.id} | {email}")

        return _J({"success": True, "message": "طھظ… ط§ظ„طھط­ظ‚ظ‚ ظˆط¥ظ†ط´ط§ط، ط§ظ„ط­ط³ط§ط¨ ط¨ظ†ط¬ط§ط­"})

    except Exception as exc:

        db.rollback()

        app_logger.error(f"verify_register_otp error: {exc}", exc_info=True)

        return _J({"success": False, "error": f"ط­ط¯ط« ط®ط·ط£ ط¯ط§ط®ظ„ظٹ ط£ط«ظ†ط§ط، ط§ظ„ط­ظپط¸: {str(exc)}"}, status_code=500)





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

        if user.role in ['ظ…ط¯ظٹط±', 'ظ…ط¯ظٹط± ط§ظ„ظ…ظƒطھط¨', 'طµط§ط­ط¨ ط§ظ„ظ…ظƒطھط¨']:

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

        if not case: return HTMLResponse(content="<script>alert('ط؛ظٹط± ظ…طµط±ط­'); window.history.back();</script>", status_code=403)

        

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

            if not case: return HTMLResponse(content="<script>alert('ط؛ظٹط± ظ…طµط±ط­'); window.history.back();</script>", status_code=403)

            

        task.title = title

        task.description = description

        task.case_id = case_id

        task.assignee_user_id = assignee_user_id

        task.due_at = due_at

    if task:

        task.status_key = status_key

        db.commit()

    return RedirectResponse(url="/tasks", status_code=303)



@app.get("/activity", response_class=HTMLResponse)

async def activity_page(request: Request, db: Session = Depends(get_db), user: AccessProfiles = Depends(get_current_user)):

    if not user:

        return RedirectResponse(url="/", status_code=303)

    if user.role not in ['ظ…ط¯ظٹط±', 'ظ…ط¯ظٹط± ط§ظ„ظ…ظƒطھط¨', 'طµط§ط­ط¨ ط§ظ„ظ…ظƒطھط¨']:

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

                    'text': f"ظ‚ط¨ظ„ {assignee.name if assignee else 'ظ…ط­ط§ظ…ظچ'} ظ…ظ‡ظ…ط©: {task.title}",

                    'sub': f"ط§ظ„ظ‚ط¶ظٹط©: {task.law_case.title if task.law_case else 'ظ…ظ‡ظ…ط© ط¹ط§ظ…ط©'}",

                    'date': task.created_at[:16]

                })

            elif task.status_key == 'completed':

                activity_feed.append({

                    'type': 'task_done',

                    'icon': 'fa-check-double',

                    'color': '#10b981',

                    'text': f"ط£طھظ… {assignee.name if assignee else 'ظ…ط­ط§ظ…ظچ'} ظ…ظ‡ظ…ط©: {task.title}",

                    'sub': f"ط§ظ„ظ‚ط¶ظٹط©: {task.law_case.title if task.law_case else 'ظ…ظ‡ظ…ط© ط¹ط§ظ…ط©'}",

                    'date': task.created_at[:16]

                })

            elif task.status_key == 'pending' and task.assignee_user_id:

                activity_feed.append({

                    'type': 'task_assigned',

                    'icon': 'fa-user-tag',

                    'color': '#f59e0b',

                    'text': f"طھظ… ط¥ط³ظ†ط§ط¯ ظ…ظ‡ظ…ط© ط¥ظ„ظ‰ {assignee.name if assignee else 'ظ…ط­ط§ظ…ظچ'}: {task.title}",

                    'sub': f"ط§ظ„ظ‚ط¶ظٹط©: {task.law_case.title if task.law_case else 'ظ…ظ‡ظ…ط© ط¹ط§ظ…ط©'}",

                    'date': task.created_at[:16]

                })

        

        for doc in recent_docs:

            activity_feed.append({

                'type': 'doc_uploaded',

                'icon': 'fa-file-arrow-up',

                'color': '#8b5cf6',

                'text': f"ط±ظپط¹ ظ…ط³طھظ†ط¯: {doc.name}",

                'sub': f"ظ†ظˆط¹ظ‡: {'{ظ…ط°ظƒط±ط©' if doc.document_type_key == 'memo' else doc.document_type_key} â€“ ظ…ط±طھط¨ط· ط¨ط§ظ„ظ‚ط¶ظٹط© ط±ظ‚ظ… {doc.case_id}",

                'date': doc.created_at[:16]

            })

        

        activity_feed.sort(key=lambda x: x['date'], reverse=True)

        

        # Task stats per user

        team_stats = []

        for u in all_users:

            if u.role in ['ظ…ط­ط§ظ…ظچ', 'ظ…ط¯ظٹط±', 'ط¥ط¯ط§ط±ظٹ']:

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

from routers import rag_router

app.include_router(ai_assistant_router.router)

app.include_router(rag_router.router)

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

    write_audit(db, "payment_requests", "submit_payment", user.id, user.name, new_req.id, "office", office.id, f"Submitted payment request for {plan}")
    
    return _J({"success": True, "message": "تم إرسال السند بنجاح"})

@app.get("/ai-assistant")

async def ai_assistant_page(request: Request, db: Session = Depends(get_db)):

    user = get_current_user(request, db)

    if not user:

        return RedirectResponse("/login", status_code=302)

    return templates.TemplateResponse("ai_assistant.html", {"request": request, "user": user})



@app.get("/knowledge-admin")

async def knowledge_admin_page(request: Request, db: Session = Depends(get_db)):

    user = get_current_user(request, db)

    if not user or user.role != 'محامي':
        return RedirectResponse("/login", status_code=302)

    return templates.TemplateResponse("knowledge_admin.html", {"request": request, "user": user})

@app.post("/debug-login-test")
async def debug_login_test(request: Request, db: Session = Depends(get_db)):
    import traceback
    try:
        form = await request.form()
        email = str(form.get("email", "ABOOD"))
        password = str(form.get("password", "admin123456"))
        user = db.query(AccessProfiles).filter(
            (AccessProfiles.email == email) |
            (AccessProfiles.username == email)
        ).first()
        if not user:
            return JSONResponse({"error": "user_not_found"})
        pin_ok = _verify_pin(password, user.access_pin_hash) if user.access_pin_hash else False
        return JSONResponse({
            "user_id": user.id,
            "username": user.username,
            "role": user.role,
            "is_active": user.is_active,
            "pin_ok": pin_ok,
            "status": "ok"
        })
    except Exception as e:
        return JSONResponse({"error": str(e), "trace": traceback.format_exc()}, status_code=200)

