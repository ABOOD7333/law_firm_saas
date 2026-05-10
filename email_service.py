"""
Email service module — LawSaaS
يقرأ إعدادات SMTP من متغيرات البيئة (.env)
Used for OTP verification in forgot_password and register flows.
"""
import smtplib
import os
import random
import string
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta

# تحميل ملف .env
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# In-memory OTP store: { email: { code, expires_at } }
# ملاحظة: هذا يعمل على instance واحد فقط.
# للإنتاج متعدد الـ instances استخدم Redis.
_otp_store: dict = {}


def _load_smtp_config() -> dict:
    """
    يقرأ إعدادات SMTP من متغيرات البيئة أولاً،
    ثم يرجع لـ smtp.conf كـ fallback للتوافق مع الإصدارات القديمة.
    """
    # أولاً: من متغيرات البيئة (.env)
    env_config = {
        "host":     os.getenv("SMTP_HOST", "smtp.gmail.com") or "smtp.gmail.com",
        "port":     os.getenv("SMTP_PORT", "587") or "587",
        "username": os.getenv("SMTP_USERNAME", ""),
        "password": os.getenv("SMTP_PASSWORD", ""),
        "sender":   os.getenv("SMTP_SENDER", "") or os.getenv("SMTP_USERNAME", ""),
        "use_tls":  os.getenv("SMTP_USE_TLS", "true"),
    }

    if env_config["username"] and env_config["password"]:
        return env_config

    # Fallback: smtp.conf (للتوافق مع الإصدارات القديمة)
    config = {}
    conf_path = os.path.join(os.path.dirname(__file__), "smtp.conf")
    try:
        with open(conf_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, val = line.split("=", 1)
                    config[key.strip()] = val.strip()
        if config:
            print("[EmailService] ⚠️ يُنصح بنقل إعدادات SMTP إلى ملف .env")
    except Exception as e:
        print(f"[EmailService] Failed to load smtp.conf: {e}")

    return config


def generate_otp(length: int = 6) -> str:
    """يولد رمز OTP عشوائي من الأرقام."""
    return ''.join(random.choices(string.digits, k=length))


def store_otp(identifier: str, code: str, ttl_minutes: int = 10):
    """يحفظ رمز OTP لمعرف معين (email/phone) لمدة ttl_minutes."""
    _otp_store[identifier.lower()] = {
        "code": code,
        "expires_at": datetime.now() + timedelta(minutes=ttl_minutes)
    }


def verify_otp(identifier: str, code: str) -> bool:
    """يتحقق من صحة رمز OTP وصلاحيته الزمنية."""
    entry = _otp_store.get(identifier.lower())
    if not entry:
        return False
    if datetime.now() > entry["expires_at"]:
        del _otp_store[identifier.lower()]
        return False
    if entry["code"] == code:
        del _otp_store[identifier.lower()]
        return True
    return False


def send_otp_email(to_email: str, otp_code: str, purpose: str = "forgot_password") -> bool:
    """
    يرسل رمز OTP عبر البريد الإلكتروني.
    يعيد True عند النجاح، False عند الفشل.
    """
    config = _load_smtp_config()
    if not config or not config.get("username"):
        print("[EmailService] لا توجد إعدادات SMTP.")
        return False

    if purpose == "forgot_password":
        subject = "رمز استعادة كلمة المرور - LawSaaS"
        body_html = f"""
        <div dir="rtl" style="font-family: Arial, sans-serif; max-width: 500px; margin: auto; padding: 20px;">
            <h2 style="color: #0f172a;">🔐 استعادة كلمة المرور</h2>
            <p>مرحباً،</p>
            <p>تلقينا طلباً لاستعادة كلمة مرور حسابك في <strong>LawSaaS</strong>.</p>
            <p>رمز التحقق الخاص بك:</p>
            <div style="background: #eff6ff; border: 2px solid #3b82f6; border-radius: 12px; padding: 20px; text-align: center; margin: 20px 0;">
                <span style="font-size: 36px; font-weight: bold; letter-spacing: 12px; color: #1d4ed8;">{otp_code}</span>
            </div>
            <p style="color: #64748b; font-size: 14px;">⏰ صالح لمدة <strong>10 دقائق</strong> فقط.</p>
            <p style="color: #64748b; font-size: 14px;">إذا لم تطلب هذا الرمز، تجاهل هذا البريد.</p>
            <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 20px 0;">
            <p style="color: #94a3b8; font-size: 12px;">LawSaaS - نظام إدارة مكاتب المحاماة السحابي</p>
        </div>
        """
    else:  # register
        subject = "تأكيد إنشاء حسابك - LawSaaS"
        body_html = f"""
        <div dir="rtl" style="font-family: Arial, sans-serif; max-width: 500px; margin: auto; padding: 20px;">
            <h2 style="color: #0f172a;">🎉 مرحباً بك في LawSaaS</h2>
            <p>شكراً لتسجيلك! استخدم رمز التحقق التالي لتأكيد بريدك الإلكتروني:</p>
            <div style="background: #f0fdf4; border: 2px solid #22c55e; border-radius: 12px; padding: 20px; text-align: center; margin: 20px 0;">
                <span style="font-size: 36px; font-weight: bold; letter-spacing: 12px; color: #16a34a;">{otp_code}</span>
            </div>
            <p style="color: #64748b; font-size: 14px;">⏰ صالح لمدة <strong>10 دقائق</strong> فقط.</p>
            <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 20px 0;">
            <p style="color: #94a3b8; font-size: 12px;">LawSaaS - نظام إدارة مكاتب المحاماة السحابي</p>
        </div>
        """

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = config.get("sender", config.get("username", ""))
        msg["To"]      = to_email
        msg.attach(MIMEText(body_html, "html", "utf-8"))

        use_tls = config.get("use_tls", "true").lower() == "true"
        host     = config.get("host") or "smtp.gmail.com"
        port     = int(config.get("port") or 587)
        username = config.get("username", "")
        password = config.get("password", "")

        print(f"[EmailService] Connecting to SMTP: {host}:{port} with user: {username}")
        with smtplib.SMTP(host, port, timeout=10) as server:
            server.set_debuglevel(1)  # Enable debug output for the connection
            server.ehlo()
            if use_tls:
                server.starttls()
                server.ehlo()
            server.login(username, password)
            server.sendmail(msg["From"], [to_email], msg.as_string())

        print(f"[EmailService] ✅ OTP sent to {to_email}")
        return True

    except Exception as e:
        print(f"[EmailService] ❌ Failed to send email: {e}")
        return False
