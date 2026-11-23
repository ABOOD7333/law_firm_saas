"""
Email service module — LawSaaS
يقرأ إعدادات SMTP من متغيرات البيئة (.env)
يدعم إرسال رسائل التحقق (OTP)، إشعارات الفواتير، الجلسات، واشتراكات المنصة بشكل متزامن وغير متزامن.
"""
import smtplib
import os
import secrets
import hmac
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from typing import Optional
import asyncio

# تحميل ملف .env
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# In-memory OTP store: { email: { code, expires_at } }
_otp_store: dict = {}


def _load_smtp_config() -> dict:
    """
    يقرأ إعدادات SMTP من متغيرات البيئة أولاً (.env)
    """
    raw_password = os.getenv("SMTP_PASSWORD", "")
    # تنظيف المسافات من كلمة مرور تطبيقات جوجل (App Password)
    clean_password = raw_password.replace(" ", "") if raw_password else ""

    env_config = {
        "host":     os.getenv("SMTP_HOST", "smtp.gmail.com") or "smtp.gmail.com",
        "port":     int(os.getenv("SMTP_PORT", "587") or "587"),
        "username": os.getenv("SMTP_USERNAME", "").strip(),
        "password": clean_password,
        "sender":   os.getenv("SMTP_SENDER", "LawSaaS").strip() or "LawSaaS",
        "use_tls":  str(os.getenv("SMTP_USE_TLS", "true")).lower() in ("true", "1", "yes"),
    }

    return env_config


def send_email(to_email: str, subject: str, html_content: str, sender_name: Optional[str] = None) -> bool:
    """
    إرسال بريد إلكتروني حقيقي عبر SMTP بتنسيق HTML متكامل.
    """
    config = _load_smtp_config()
    username = config.get("username")
    password = config.get("password")

    if not username or not password:
        print("[EmailService] ⚠️ لا توجد بيانات SMTP كافية (username/password مفقودة).")
        return False

    display_name = sender_name or config.get("sender") or "LawSaaS"

    try:
        msg = MIMEMultipart("alternative")
        msg["From"] = f"{display_name} <{username}>"
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.attach(MIMEText(html_content, "html", "utf-8"))

        host = config.get("host", "smtp.gmail.com")
        port = config.get("port", 587)

        print(f"[EmailService] Connecting to SMTP {host}:{port} for {to_email}...")
        server = smtplib.SMTP(host, port, timeout=20)
        server.ehlo()
        if config.get("use_tls"):
            server.starttls()
            server.ehlo()

        server.login(username, password)
        server.send_message(msg)
        server.quit()

        print(f"[EmailService] ✅ Email sent successfully to: {to_email}")
        return True
    except Exception as e:
        print(f"[EmailService] ❌ Failed to send email to {to_email}: {e}")
        return False


async def send_email_async(to_email: str, subject: str, html_content: str, sender_name: Optional[str] = None) -> bool:
    """
    إرسال بريد إلكتروني في الخلفية دون تعطيل استجابة الخادم (Non-blocking Asynchronous).
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.get_event_loop()

    return await loop.run_in_executor(None, send_email, to_email, subject, html_content, sender_name)


def generate_otp(length: int = 6) -> str:
    """يولد رمز OTP عشوائي من الأرقام."""
    if not 4 <= length <= 8:
        raise ValueError("OTP length must be between 4 and 8 digits")
    return f"{secrets.randbelow(10 ** length):0{length}d}"


def store_otp(identifier: str, code: str, ttl_minutes: int = 10, purpose: str = None, **kwargs):
    """يحفظ رمز OTP لمعرف معين (email/phone) لمدة ttl_minutes."""
    _otp_store[identifier.lower()] = {
        "code": code,
        "expires_at": datetime.now() + timedelta(minutes=ttl_minutes),
        "attempts": 0,
    }


def verify_otp(identifier: str, code: str, purpose: str = None, **kwargs) -> bool:
    """يتحقق من صحة رمز OTP وصلاحيته الزمنية."""
    entry = _otp_store.get(identifier.lower())
    if not entry:
        return False
    if datetime.now() > entry["expires_at"]:
        del _otp_store[identifier.lower()]
        return False
    if hmac.compare_digest(str(entry["code"]), str(code)):
        del _otp_store[identifier.lower()]
        return True
    entry["attempts"] += 1
    if entry["attempts"] >= 5:
        del _otp_store[identifier.lower()]
    return False


def send_otp_email(to_email: str, otp_code: str, purpose: str = "forgot_password") -> bool:
    """
    يرسل رمز OTP عبر البريد الإلكتروني.
    """
    if purpose == "forgot_password":
        subject = "رمز استعادة كلمة المرور - LawSaaS"
        body_html = f"""
        <div dir="rtl" style="font-family: Arial, sans-serif; max-width: 500px; margin: auto; padding: 20px; background: #ffffff; border-radius: 12px; border: 1px solid #e2e8f0;">
            <h2 style="color: #0f172a; text-align: center;">🔐 استعادة كلمة المرور</h2>
            <p style="color: #334155; font-size: 15px;">مرحباً،</p>
            <p style="color: #334155; font-size: 15px;">تلقينا طلباً لاستعادة كلمة مرور حسابك في <strong>LawSaaS</strong>.</p>
            <div style="background: #eff6ff; border: 2px dashed #3b82f6; border-radius: 12px; padding: 18px; text-align: center; margin: 20px 0;">
                <span style="font-size: 32px; font-weight: bold; letter-spacing: 10px; color: #1d4ed8; font-family: monospace;">{otp_code}</span>
            </div>
            <p style="color: #64748b; font-size: 13px; text-align: center;">⏰ الرمز صالح لمدة <strong>10 دقائق</strong> فقط.</p>
            <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 20px 0;">
            <p style="color: #94a3b8; font-size: 12px; text-align: center;">LawSaaS - نظام إدارة مكاتب المحاماة السحابي</p>
        </div>
        """
    elif purpose == "2fa":
        subject = "رمز التحقق الثنائي (2FA) - LawSaaS"
        body_html = f"""
        <div dir="rtl" style="font-family: Arial, sans-serif; max-width: 500px; margin: auto; padding: 20px; background: #ffffff; border-radius: 12px; border: 1px solid #e2e8f0;">
            <h2 style="color: #0f172a; text-align: center;">🔐 رمز التحقق الثنائي (2FA)</h2>
            <p style="color: #334155; font-size: 15px;">مرحباً،</p>
            <p style="color: #334155; font-size: 15px;">يرجى استخدام الرمز التالي لتأكيد الدخول إلى حسابك في <strong>LawSaaS</strong>:</p>
            <div style="background: #eff6ff; border: 2px dashed #3b82f6; border-radius: 12px; padding: 18px; text-align: center; margin: 20px 0;">
                <span style="font-size: 32px; font-weight: bold; letter-spacing: 10px; color: #1d4ed8; font-family: monospace;">{otp_code}</span>
            </div>
            <p style="color: #64748b; font-size: 13px; text-align: center;">⏰ صالح لمدة <strong>10 دقائق</strong> فقط.</p>
            <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 20px 0;">
            <p style="color: #94a3b8; font-size: 12px; text-align: center;">LawSaaS - نظام إدارة مكاتب المحاماة السحابي</p>
        </div>
        """
    else:  # register
        subject = "تأكيد إنشاء حسابك - LawSaaS"
        body_html = f"""
        <div dir="rtl" style="font-family: Arial, sans-serif; max-width: 500px; margin: auto; padding: 20px; background: #ffffff; border-radius: 12px; border: 1px solid #e2e8f0;">
            <h2 style="color: #059669; text-align: center;">🎉 مرحباً بك في LawSaaS</h2>
            <p style="color: #334155; font-size: 15px;">شكراً لانضمامك! استخدم رمز التحقق التالي لتفعيل بريدك الإلكتروني:</p>
            <div style="background: #f0fdf4; border: 2px dashed #22c55e; border-radius: 12px; padding: 18px; text-align: center; margin: 20px 0;">
                <span style="font-size: 32px; font-weight: bold; letter-spacing: 10px; color: #15803d; font-family: monospace;">{otp_code}</span>
            </div>
            <p style="color: #64748b; font-size: 13px; text-align: center;">⏰ الرمز صالح لمدة <strong>10 دقائق</strong> فقط.</p>
            <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 20px 0;">
            <p style="color: #94a3b8; font-size: 12px; text-align: center;">LawSaaS - نظام إدارة مكاتب المحاماة السحابي</p>
        </div>
        """

    return send_email(to_email, subject, body_html)
