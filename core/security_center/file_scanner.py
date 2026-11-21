"""
Advanced Malware & Document Exploit Scanner — LawSaaS Platform
نظام فحص المستندات ومنع الملفات الملغومة (Stream Malware & PDF Exploit Guard)

الميزات المتقدمة:
1. التحقق من التوقيع الرقمي السحري الحقيقي (Magic Bytes).
2. الفحص البنيوي لملفات الـ PDF لمنع ثغرات التنفيذ الآلي (/Launch, /JavaScript, /EmbeddedFiles).
3. فحص ملفات أوفيس (Word/DOCX) ضد الماكرو الخبيث و vbaProject.bin.
4. كشف وحظر الخداع بالامتدادات المزدوجة (Double Extension Tricks).
5. فحص وتنقية مسارات الحفظ لمنع تجاوز المسارات (Path Traversal Prevention).
6. تسجيل أي محاولة رفع ملف مشبوه تلقائياً في مركز العمليات الأمنية (SOC).
"""

import io
import os
import re
import zipfile
import logging
from typing import Tuple, Optional
from sqlalchemy.orm import Session
from database.database import SessionLocal
from database.security_models import SecurityEvents
from core.security_center.monitor_middleware import record_security_event
from core.security_center.alert_service import dispatch_security_alert

logger = logging.getLogger("law_firm.security.files")

# الامتدادات التنفيذية والخطيرة الممنوعة قطعاً
DANGEROUS_EXTENSIONS = {
    "exe", "bat", "cmd", "ps1", "sh", "vbs", "vbe", "js", "jse", "wsf", "wsh",
    "scr", "pif", "dll", "so", "bin", "com", "hta", "jar", "msi", "reg", "docm", "xlsm"
}

# الامتدادات المصرح بها رسمياً في منصة المحاماة
ALLOWED_EXTENSIONS = {
    "pdf", "doc", "docx", "jpg", "jpeg", "png", "txt"
}


def sanitize_filename(filename: str) -> str:
    """تنقية وتطهير اسم الملف وإزالة أي محاولات لتجاوز المسار"""
    base = os.path.basename(filename)
    # الاحتفاظ بالأحرف الآمنة فقط
    clean = "".join(c for c in base if c.isalnum() or c in " ._-")
    return clean or "unnamed_document"


def scan_uploaded_file(
    content: bytes,
    filename: str,
    db: Optional[Session] = None,
    client_ip: Optional[str] = None,
    endpoint: Optional[str] = None
) -> Tuple[bool, str]:
    """
    فحص شامل للملف المرفوع:
    يرجع (True, "آمن") إذا كان الملف نظيفاً،
    أو (False, "سبب الرفض") إذا تم رصد كود خبيث أو تلاعب.
    """
    if not content:
        return False, "الملف فارغ أو تالف"

    clean_fn = sanitize_filename(filename).lower()

    # 1. فحص الامتدادات المزدوجة (Double Extension Tricks e.g., legal.pdf.exe)
    parts = clean_fn.split(".")
    if len(parts) > 2:
        for p in parts[1:]:
            if p in DANGEROUS_EXTENSIONS:
                _record_threat(
                    threat_desc=f"محاولة رفع ملف بامتداد تنفيذي خبيث مزدوج ({filename})",
                    db=db, client_ip=client_ip, endpoint=endpoint
                )
                return False, f"تم حظر الملف لاحتوائه على امتداد تنفيذي غير مصرح به (. {p})"

    ext = parts[-1] if len(parts) > 1 else ""
    if ext not in ALLOWED_EXTENSIONS:
        return False, f"نوع الملف غير مسموح به ({ext})"

    # 2. فحص البصمة الثنائية الحقيقية (Magic Bytes)
    valid_magic, magic_err = _verify_magic_bytes(content, ext)
    if not valid_magic:
        _record_threat(
            threat_desc=f"تزييف امتداد الملف: البصمة الثنائية لا تطابق الامتداد المزعوم ({filename})",
            db=db, client_ip=client_ip, endpoint=endpoint
        )
        return False, magic_err

    # 3. فحص بنيوي متخصص لملفات الـ PDF
    if ext == "pdf":
        is_safe_pdf, pdf_reason = _scan_pdf_exploits(content)
        if not is_safe_pdf:
            _record_threat(
                threat_desc=f"رصد كود خبيث مدمج داخل ملف PDF ({filename}): {pdf_reason}",
                db=db, client_ip=client_ip, endpoint=endpoint
            )
            return False, f"تم حظر ملف الـ PDF: {pdf_reason}"

    # 4. فحص ملفات أوفيس DOCX ضد الماكرو الخبيث
    if ext in ("docx", "doc"):
        is_safe_docx, docx_reason = _scan_docx_macros(content)
        if not is_safe_docx:
            _record_threat(
                threat_desc=f"رصد كود ماكرو VBA خبيث مدمج في مستند Word ({filename})",
                db=db, client_ip=client_ip, endpoint=endpoint
            )
            return False, f"تم حظر المستند: {docx_reason}"

    # 5. فحص ملفات النصوص TXT ضد الرموز الثنائية غير الصالحة
    if ext == "txt":
        if b"\x00" in content:
            return False, "الملف النصي يحوي بايتات ثنائية ملغية (Null Bytes) تدل على أنه ملف تنفيذي متنكر"

    return True, "تم الفحص بنجاح: الملف آمن وسليم"


def _verify_magic_bytes(content: bytes, ext: str) -> Tuple[bool, str]:
    """التحقق من تطابق بايتات البداية مع نوع الملف المزعوم"""
    if ext == "pdf":
        if not content.startswith(b"%PDF"):
            return False, "الملف ينتحل امتداد PDF بينما بصمته الثنائية لا تطابق ملفات PDF"
    elif ext in ("jpg", "jpeg"):
        if not content.startswith(b"\xff\xd8\xff"):
            return False, "الملف ينتحل امتداد صورة JPEG وبصمته الرقمية غير صحيحة"
    elif ext == "png":
        if not content.startswith(b"\x89PNG\r\n\x1a\n"):
            return False, "الملف ينتحل امتداد صورة PNG وبصمته الرقمية غير صحيحة"
    elif ext in ("docx", "doc"):
        if not (content.startswith(b"PK\x03\x04") or content.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1")):
            return False, "الملف ينتحل امتداد Word وبصمته الرقمية غير مطابقة"
    return True, ""


def _scan_pdf_exploits(content: bytes) -> Tuple[bool, str]:
    """فحص هيكل ملف الـ PDF لاكتشاف أوامر التشغيل والسكربتات التنفيذية"""
    # 1. منع أمر /Launch (أمر إطلاق برامج خارجية أو شل)
    if b"/Launch" in content:
        return False, "رصد أمر تشغيل برامج خارجية خبيث داخل المستند (/Launch)"

    # 2. فحص /JavaScript أو /JS
    if b"/JavaScript" in content or b"/JS" in content:
        # فحص وجود دوال خطيرة
        dangerous_js_terms = [b"eval", b"app.launchURL", b"this.exportDataObject", b"powershell", b"cmd.exe", b"wscript"]
        content_lower = content.lower()
        for term in dangerous_js_terms:
            if term in content_lower:
                return False, f"رصد كود تنفيذي مشبوه داخل الجافاسكريبت المدمج بالـ PDF ({term.decode('utf-8', errors='ignore')})"

    # 3. فحص الملفات المدمجة المشبوهة
    if b"/EmbeddedFiles" in content:
        # إذا وجد ملف تنفيذي مرفق داخل الـ PDF
        for bad_ext in [b".exe", b".bat", b".cmd", b".vbs", b".js", b".scr"]:
            if bad_ext in content.lower():
                return False, "رصد ملف تنفيذي مخفي بداخل مستند الـ PDF"

    return True, ""


def _scan_docx_macros(content: bytes) -> Tuple[bool, str]:
    """فحص ملفات DOCX المضغوطة لمنع شفرات الماكرو الخبيثة"""
    if content.startswith(b"PK\x03\x04"):
        try:
            with zipfile.ZipFile(io.BytesIO(content)) as zf:
                names = [n.lower() for n in zf.namelist()]
                # منع ملفات الماكرو التنفيذية داخل Word
                if any("vbaproject.bin" in n or "vba" in n for n in names):
                    return False, "المستند يحوي شفرة ماكرو تنفيذية (VBA Macro) محظورة أمنياً"
        except zipfile.BadZipFile:
            return False, "ملف DOCX تالف أو معطوب"
        except Exception as e:
            logger.warning(f"[FileScan] Error unzipping docx: {e}")
    return True, ""


def _record_threat(
    threat_desc: str,
    db: Optional[Session] = None,
    client_ip: Optional[str] = None,
    endpoint: Optional[str] = None
):
    """تسجيل محاولة رفع الملف الملغم في مركز العمليات الأمنية (SOC)"""
    logger.warning(f"[Threat Blocked] {threat_desc} from IP: {client_ip or 'unknown'}")
    local_db = db or SessionLocal()
    try:
        record_security_event(
            db=local_db,
            event_type="malicious_file_blocked",
            severity="high",
            source_ip=client_ip or "unknown",
            endpoint=endpoint or "/documents/upload",
            http_method="POST",
            status_code=400,
            details=threat_desc
        )
    except Exception as e:
        logger.error(f"[FileScan] Failed to record security event: {e}")
    finally:
        if not db:
            local_db.close()
