"""
import hashlib
from datetime import datetime, timedelta
Security Helpers — LawSaaS
أدوات مساعدة للتحقق من أمان المدخلات والملفات المرفوعة.
"""

def validate_file_signature(content: bytes, extension: str) -> bool:
    """
    التحقق من صحة الملف بناءً على التوقيع الرقمي (Magic Bytes) وليس فقط الامتداد لمنع رفع ملفات خبيثة بامتدادات مزيفة.
    """
    if not content:
        return False
        
    ext = extension.lower().strip().replace(".", "")
    
    # التوقيعات الرقمية الشائعة (Magic Bytes)
    if ext == 'pdf':
        return content.startswith(b'%PDF')
    elif ext in ['jpg', 'jpeg']:
        return content.startswith(b'\xff\xd8\xff')
    elif ext == 'png':
        return content.startswith(b'\x89PNG\r\n\x1a\n')
    elif ext == 'gif':
        return content.startswith(b'GIF87a') or content.startswith(b'GIF89a')
    elif ext in ['docx', 'doc']:
        # تنسيق DOCX هو عبارة عن ملف ZIP مضغوط (يبدأ بـ PK\x03\x04)
        # تنسيق DOC القديم يبدأ بـ \xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1
        return content.startswith(b'PK\x03\x04') or content.startswith(b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1')
    elif ext == 'txt':
        # التحقق من أن الملف النصي لا يحتوي على أحرف ثنائية ملغية (Null Bytes) وهي سمة الملفات التنفيذية
        try:
            if b'\x00' in content:
                return False
            content.decode('utf-8')
            return True
        except UnicodeDecodeError:
            return False
            
    return False


def hash_session_token(token: str) -> str:
    """Return the one-way database representation of a bearer session token."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def login_lockout_active(user, db) -> bool:
    """Enforce a temporary, recoverable account lock instead of a permanent lockout."""
    locked_until = getattr(user, "locked_until", None)
    if not locked_until:
        return False
    now = datetime.utcnow()
    try:
        until = datetime.strptime(locked_until, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        user.locked_until = None
        user.failed_attempts = 0
        db.commit()
        return False
    if until > now:
        return True
    user.locked_until = None
    user.failed_attempts = 0
    db.commit()
    return False


def record_login_failure(user, db) -> bool:
    """Record an unsuccessful login and temporarily lock after repeated failures."""
    user.failed_attempts = (getattr(user, "failed_attempts", 0) or 0) + 1
    locked = user.failed_attempts >= 10
    if locked:
        user.failed_attempts = 0
        user.locked_until = (datetime.utcnow() + timedelta(minutes=15)).strftime("%Y-%m-%d %H:%M:%S")
    db.commit()
    return locked


def client_records_for_user(db, user):
    """Return only same-office client records explicitly bound to a portal user.

    For legacy rows, permit contact matching only when it identifies exactly one
    client record; ambiguous matches fail closed.
    """
    from sqlalchemy import or_
    from database.models import LawClients

    if not user.office_id:
        return []
    bound = db.query(LawClients).filter(
        LawClients.user_id == user.id,
        LawClients.office_id == user.office_id,
        LawClients.is_deleted == 0,
    ).all()
    if bound:
        return bound
    contacts = []
    if user.phone:
        contacts.append(LawClients.phone == user.phone)
    if user.email:
        contacts.append(LawClients.email == user.email)
    if not contacts:
        return []
    matches = db.query(LawClients).filter(
        LawClients.office_id == user.office_id,
        LawClients.is_deleted == 0,
        or_(*contacts),
    ).all()
    return matches if len(matches) == 1 else []
