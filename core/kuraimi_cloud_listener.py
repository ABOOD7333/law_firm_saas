"""
Kuraimi Cloud Mail Listener & Auto-Activation Service
======================================================
Connects directly to Apple iCloud IMAP (imap.mail.me.com:993) via SSL,
fetches official transaction/deposit emails from Al-Kuraimi Islamic Bank (حاسب / إيداع),
extracts transaction reference numbers and deposited amounts,
strictly validates them against pending PaymentRequests, and auto-activates the office subscription!
"""

import os
import re
import imaplib
import email
from email.header import decode_header
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import logging
from sqlalchemy.orm import Session

from database.models import PaymentRequest, LawOffices
from core.audit import write_audit

logger = logging.getLogger("kuraimi_listener")
logger.setLevel(logging.INFO)

# iCloud IMAP Settings
ICLOUD_IMAP_SERVER = os.getenv("ICLOUD_IMAP_SERVER", "imap.mail.me.com")
ICLOUD_IMAP_PORT = int(os.getenv("ICLOUD_IMAP_PORT", "993"))
ICLOUD_EMAIL = os.getenv("KURAIMI_ICLOUD_EMAIL", "lawsaas.platform@icloud.com")
ICLOUD_APP_PASSWORD = os.getenv("KURAIMI_ICLOUD_APP_PASSWORD", "euty-xcfr-vphl-norv")

# نقطة حاسب التابعة لصاحب المنصة
KURAIMI_HASEB_POINT = os.getenv("KURAIMI_HASEB_POINT", "2709660")


def clean_header_text(header_val: str) -> str:
    """فك تشفير الترويسات (Subject / From) المشفرة بـ MIME/Base64."""
    if not header_val:
        return ""
    decoded_fragments = decode_header(header_val)
    parts = []
    for fragment, charset in decoded_fragments:
        if isinstance(fragment, bytes):
            try:
                parts.append(fragment.decode(charset or "utf-8", errors="ignore"))
            except Exception:
                parts.append(fragment.decode("utf-8", errors="ignore"))
        else:
            parts.append(str(fragment))
    return "".join(parts)


def parse_kuraimi_email_body(text: str) -> Dict[str, Any]:
    """
    استخراج بيانات العملية من نص إشعار الكريمي:
    - رقم العملية المرجعي (Reference No / رقم القيد / رقم العملية)
    - المبلغ (Amount)
    - العملة (YER / SAR / USD)
    """
    clean_text = text.replace(",", "").replace("\xa0", " ")

    # أنماط استخراج رقم العملية (6 إلى 14 رقم)
    ref_match = re.search(r'(?:عملية|مرجع|حاسب|رقم|قيد|Ref(?:erence)?|Txn(?:Id)?)[^\d]{0,20}(\d{5,14})', clean_text, re.IGNORECASE)
    if not ref_match:
        # البحث عن أي رقم متسلسل واضح
        ref_match = re.search(r'\b(\d{6,12})\b', clean_text)
    ref_num = ref_match.group(1) if ref_match else None

    # أنماط استخراج المبلغ
    amount_match = re.search(r'(?:مبلغ|قيد|المبلغ|Amount)[^\d]{0,15}(\d+(?:\.\d{1,2})?)', clean_text, re.IGNORECASE)
    if not amount_match:
        amount_match = re.search(r'(\d+(?:\.\d{1,2})?)\s*(?:ر\.?ي|ريال|USD|\$|SAR|سعودي)', clean_text, re.IGNORECASE)
    amount = float(amount_match.group(1)) if amount_match else None

    # تحديد العملة
    currency = "USD"
    if re.search(r'ريال\s*يمني|ر\.?ي|YER', clean_text, re.IGNORECASE):
        currency = "YER"
    elif re.search(r'ريال\s*سعودي|ر\.?س|SAR', clean_text, re.IGNORECASE):
        currency = "SAR"
    elif re.search(r'دولار|USD|\$', clean_text, re.IGNORECASE):
        currency = "USD"

    return {
        "reference_number": ref_num,
        "amount": amount,
        "currency": currency,
        "raw_text": clean_text[:1000]
    }


def connect_to_icloud_imap() -> Optional[imaplib.IMAP4_SSL]:
    """الاتصال بسحابة iCloud عبر بروتوكول IMAP الآمن."""
    if not ICLOUD_EMAIL or not ICLOUD_APP_PASSWORD:
        logger.warning("iCloud email credentials missing, skipping IMAP listener.")
        return None
    try:
        mail = imaplib.IMAP4_SSL(ICLOUD_IMAP_SERVER, ICLOUD_IMAP_PORT)
        mail.login(ICLOUD_EMAIL, ICLOUD_APP_PASSWORD)
        return mail
    except Exception as e:
        logger.error(f"Failed to connect to iCloud IMAP: {e}")
        return None


def fetch_latest_kuraimi_emails(limit: int = 15) -> List[Dict[str, Any]]:
    """جلب وتحليل أحدث رسائل واردة من بنك الكريمي."""
    mail = connect_to_icloud_imap()
    if not mail:
        return []

    results = []
    try:
        mail.select("INBOX")
        # البحث عن كافة الرسائل أو الرسائل الحديثة
        status, data = mail.search(None, "ALL")
        if status != "OK" or not data or not data[0]:
            mail.logout()
            return []

        msg_ids = data[0].split()
        # نأخذ أحدث الرسائل
        latest_ids = msg_ids[-limit:] if len(msg_ids) > limit else msg_ids

        for msg_id in reversed(latest_ids):
            res, msg_data = mail.fetch(msg_id, "(RFC822)")
            if res != "OK":
                continue
            for response_part in msg_data:
                if isinstance(response_part, tuple):
                    raw_email = response_part[1]
                    msg = email.message_from_bytes(raw_email)
                    subject = clean_header_text(msg.get("Subject", ""))
                    sender = clean_header_text(msg.get("From", ""))

                    # استخراج نص الرسالة
                    body = ""
                    if msg.is_multipart():
                        for part in msg.walk():
                            content_type = part.get_content_type()
                            content_disposition = str(part.get("Content-Disposition"))
                            if content_type in ["text/plain", "text/html"] and "attachment" not in content_disposition:
                                payload = part.get_payload(decode=True)
                                if payload:
                                    body += payload.decode("utf-8", errors="ignore") + " "
                    else:
                        payload = msg.get_payload(decode=True)
                        if payload:
                            body = payload.decode("utf-8", errors="ignore")

                    parsed = parse_kuraimi_email_body(f"{subject} {body}")
                    parsed["subject"] = subject
                    parsed["sender"] = sender
                    parsed["date"] = msg.get("Date", "")
                    results.append(parsed)

        mail.logout()
    except Exception as e:
        logger.error(f"Error fetching emails from iCloud: {e}")
        try:
            mail.logout()
        except Exception:
            pass

    return results


def verify_and_activate_pending_requests(db: Session) -> List[Dict[str, Any]]:
    """
    فحص جميع طلبات الدفع المعلقة (pending) ومطابقتها مع إشعارات إيميل iCloud.
    إذا تم التطابق مع مرجع العملية والمبلغ:
    1. تفعيل المكتب فوراً وتحديث تاريخ انتهاء الاشتراك لمدة 30 يوماً أو 365 يوماً.
    2. اعتماد طلب الدفع PaymentRequest وتحويله إلى approved.
    3. تسجيل عملية التدقيق (write_audit).
    """
    pending_requests = db.query(PaymentRequest).filter(PaymentRequest.status == "pending").all()
    if not pending_requests:
        return []

    emails = fetch_latest_kuraimi_emails(limit=25)
    activated = []

    for req in pending_requests:
        client_ref = (req.transfer_ref or "").strip()
        if not client_ref:
            continue

        for em in emails:
            bank_ref = (em.get("reference_number") or "").strip()
            # التحقق من تطابق رقم المرجع
            if client_ref == bank_ref or client_ref in em.get("raw_text", "") or bank_ref in client_ref:
                # التحقق الصارم من المبلغ (إن وُجد في الإيميل)
                email_amount = em.get("amount")
                if email_amount and req.amount:
                    # سماح تفاوت 0.5% لتفادي فروقات التحويل الصغيرة جداً
                    if abs(email_amount - req.amount) > 1.0 and email_amount < req.amount:
                        logger.warning(f"PaymentRequest #{req.id} amount mismatch: expected {req.amount}, got {email_amount}")
                        continue

                # تم التطابق بنجاح تام! تفعيل الاشتراك:
                office = db.query(LawOffices).filter(LawOffices.id == req.office_id).first()
                if office:
                    days_to_add = 365 if req.plan in ("yearly", "enterprise") else 30
                    new_end_date = datetime.utcnow() + timedelta(days=days_to_add)
                    
                    office.subscription_plan = req.plan
                    office.subscription_end = new_end_date.strftime("%Y-%m-%d %H:%M:%S")
                    office.status_key = "active"
                    office.is_active = 1

                    req.status = "approved"
                    req.reviewed_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
                    req.admin_notes = f"تم الاعتماد والتفعيل التلقائي سحابياً عبر إشعار بنك الكريمي (iCloud). مرجع: {bank_ref}"

                    db.commit()

                    write_audit(
                        db,
                        table_name="payment_requests",
                        action_name="auto_approve_kuraimi_cloud",
                        actor_user_id=req.user_id,
                        actor_name="Kuraimi Cloud Auto-Activator",
                        office_id=office.id,
                        entity_type="payment_request",
                        entity_id=req.id,
                        details=f"Auto-activated {req.plan} for office {office.name} via matching ref {bank_ref}"
                    )

                    activated.append({
                        "request_id": req.id,
                        "office_id": office.id,
                        "office_name": office.name,
                        "plan": req.plan,
                        "ref": bank_ref
                    })
                    break

    return activated
