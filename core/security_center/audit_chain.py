"""
Cryptographic Immutable Audit Chain — LawSaaS Platform
سلسلة سجلات التدقيق غير القابلة للتلاعب المشفرة (Chain-of-Custody via HMAC-SHA256)

الميزات والمعايير الأمنية:
1. ارتباط تتابعي غير قابل للكسر: كل سجل تدقيق يحمل تجزئة السجل الذي قبله (prev_hash).
2. توقيع رياضي HMAC-SHA256: كل سجل موقع رقمياً بمفتاح مشتق من سر المنصة (HKDF-SHA256).
3. كشف فوري لأي تلاعب: أي تعديل على بيانات السجل (المستخدم، الحدث، التوقيت، القيم) يبطل التوقيع فوراً.
4. كشف فوري لأي حذف أو دس: أي حذف لسجل في المنتصف يكسر تتابع السلسلة (prev_hash mismatch).
5. تكامل كامل مع مركز العمليات السيبرانية SOC وفحص الـ 6 ساعات الدوري.
6. توافق رجعي (Backfill): توقيع وربط السجلات السابقة تلقائياً دون فقدان أي بيانات.
"""

import os
import hmac
import json
import hashlib
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime
from sqlalchemy.orm import Session
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes

from database.models import LawAuditLog

logger = logging.getLogger("law_firm.security.audit_chain")

# الهاش البدئي لتأسيس السلسلة (Genesis Block Hash)
GENESIS_HASH = "GENESIS_0000000000000000000000000000000000000000000000000000000000000000"

_cached_hmac_key: Optional[bytes] = None


def get_audit_hmac_key() -> bytes:
    """اشتقاق مفتاح HMAC-SHA256 محصن لسلسلة التدقيق عبر HKDF"""
    global _cached_hmac_key
    if _cached_hmac_key is not None:
        return _cached_hmac_key

    custom_key = os.getenv("AUDIT_CHAIN_KEY")
    if not custom_key:
        custom_key = os.getenv("SECRET_KEY", "lawsaas_ultra_secure_enterprise_key_2026")

    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=b"lawsaas-audit-chain-hmac-salt-2026",
        info=b"lawsaas-immutable-audit-chain-v1"
    )
    _cached_hmac_key = hkdf.derive(custom_key.encode("utf-8"))
    return _cached_hmac_key


def _build_canonical_payload(prev_hash: str, entry_data: Dict[str, Any]) -> str:
    """بناء حمولة نصية قياسية وموحدة لحساب التجزئة"""
    canonical_dict = {
        "action_name": str(entry_data.get("action_name") or ""),
        "actor_name": str(entry_data.get("actor_name") or ""),
        "actor_user_id": str(entry_data.get("actor_user_id") or ""),
        "created_at": str(entry_data.get("created_at") or ""),
        "details": str(entry_data.get("details") or ""),
        "device_context": str(entry_data.get("device_context") or ""),
        "entity_id": str(entry_data.get("entity_id") or ""),
        "entity_type": str(entry_data.get("entity_type") or ""),
        "new_values_json": str(entry_data.get("new_values_json") or ""),
        "office_id": str(entry_data.get("office_id") or ""),
        "old_values_json": str(entry_data.get("old_values_json") or ""),
        "prev_hash": str(prev_hash or GENESIS_HASH),
        "record_key": str(entry_data.get("record_key") or ""),
        "session_uuid": str(entry_data.get("session_uuid") or ""),
        "table_name": str(entry_data.get("table_name") or ""),
    }
    return json.dumps(canonical_dict, sort_keys=True, ensure_ascii=False)


def compute_entry_hash(prev_hash: str, entry_data: Dict[str, Any]) -> str:
    """حساب بصمة HMAC-SHA256 المشفرة لسجل التدقيق"""
    key = get_audit_hmac_key()
    payload = _build_canonical_payload(prev_hash, entry_data)
    digest = hmac.new(key, payload.encode("utf-8"), hashlib.sha256).hexdigest()
    return digest


def get_latest_audit_hash(db: Session) -> str:
    """استرجاع هاش آخر سجل موقع في السلسلة، أو الهاش البدئي إذا كانت السلسلة جديدة"""
    try:
        last_entry = (
            db.query(LawAuditLog)
            .filter(LawAuditLog.entry_hash.isnot(None))
            .order_by(LawAuditLog.id.desc())
            .first()
        )
        if last_entry and last_entry.entry_hash:
            return last_entry.entry_hash
    except Exception as exc:
        logger.error(f"Error fetching latest audit hash: {exc}")
    return GENESIS_HASH


def sign_audit_entry(entry: LawAuditLog, prev_hash: Optional[str] = None, db: Optional[Session] = None) -> str:
    """
    توقيع سجل تدقيق رقمياً وربطه بالسجل السابق بالسلسلة
    """
    if not prev_hash:
        if db:
            prev_hash = get_latest_audit_hash(db)
        else:
            prev_hash = GENESIS_HASH

    entry_data = {
        "action_name": entry.action_name,
        "actor_name": entry.actor_name,
        "actor_user_id": entry.actor_user_id,
        "created_at": entry.created_at,
        "details": entry.details,
        "device_context": entry.device_context,
        "entity_id": entry.entity_id,
        "entity_type": entry.entity_type,
        "new_values_json": entry.new_values_json,
        "office_id": entry.office_id,
        "old_values_json": entry.old_values_json,
        "record_key": entry.record_key,
        "session_uuid": entry.session_uuid,
        "table_name": entry.table_name,
    }

    digest = compute_entry_hash(prev_hash, entry_data)
    entry.prev_hash = prev_hash
    entry.entry_hash = digest
    return digest


def verify_audit_chain(db: Session, max_records: Optional[int] = None) -> Dict[str, Any]:
    """
    فحص رياضي شامل لسلامة سلسلة سجلات التدقيق بالكامل:
    1. التحقق من التوقيع الرقمي لكل سجل (HMAC Integrity).
    2. التحقق من ترابط السلسلة وعدم انقطاعها (Chain Continuity).
    """
    try:
        query = (
            db.query(LawAuditLog)
            .filter(LawAuditLog.entry_hash.isnot(None))
            .order_by(LawAuditLog.id.asc())
        )
        if max_records:
            # التحقق من آخر N سجلات إذا طُلب ذلك
            signed_count = query.count()
            if signed_count > max_records:
                offset = signed_count - max_records
                query = query.offset(offset).limit(max_records)

        records: List[LawAuditLog] = query.all()
        unsigned_count = db.query(LawAuditLog).filter(LawAuditLog.entry_hash.is_(None)).count()

        if not records:
            return {
                "is_valid": True,
                "status": "empty",
                "verified_count": 0,
                "unsigned_count": unsigned_count,
                "message": "لا توجد سجلات تدقيق موقعة بعد في السلسلة.",
                "tampered_ids": [],
                "broken_chain_ids": [],
                "latest_hash": GENESIS_HASH,
            }

        expected_prev_hash: Optional[str] = None
        tampered_ids: List[int] = []
        broken_chain_ids: List[int] = []

        for idx, rec in enumerate(records):
            entry_data = {
                "action_name": rec.action_name,
                "actor_name": rec.actor_name,
                "actor_user_id": rec.actor_user_id,
                "created_at": rec.created_at,
                "details": rec.details,
                "device_context": rec.device_context,
                "entity_id": rec.entity_id,
                "entity_type": rec.entity_type,
                "new_values_json": rec.new_values_json,
                "office_id": rec.office_id,
                "old_values_json": rec.old_values_json,
                "record_key": rec.record_key,
                "session_uuid": rec.session_uuid,
                "table_name": rec.table_name,
            }

            # 1. التحقق من التوقيع الرقمي للمحتوى
            recomputed_hash = compute_entry_hash(rec.prev_hash or GENESIS_HASH, entry_data)
            if recomputed_hash != rec.entry_hash:
                tampered_ids.append(rec.id)
                logger.error(f"[Audit Chain TAMPERED] Record ID {rec.id} content was modified!")

            # 2. التحقق من ترابط السلسلة (prev_hash)
            if expected_prev_hash is not None and rec.prev_hash != expected_prev_hash:
                broken_chain_ids.append(rec.id)
                logger.error(
                    f"[Audit Chain BROKEN] Record ID {rec.id} expected prev_hash "
                    f"'{expected_prev_hash[:12]}...', got '{str(rec.prev_hash)[:12]}...'"
                )

            expected_prev_hash = rec.entry_hash

        is_clean = len(tampered_ids) == 0 and len(broken_chain_ids) == 0

        status_str = "secure" if is_clean else "compromised"
        if is_clean:
            message = f"سلسلة التدقيق سليمة تماماً 100%. تم التحقق من {len(records)} سجل دون أي تلاعب."
        else:
            message = (
                f"تحذير أمني: تم رصد عدم تطابق في سلسلة التدقيق! "
                f"سجلات معدلة: {len(tampered_ids)}، انقطاعات في السلسلة: {len(broken_chain_ids)}."
            )

        return {
            "is_valid": is_clean,
            "status": status_str,
            "verified_count": len(records),
            "unsigned_count": unsigned_count,
            "message": message,
            "tampered_ids": tampered_ids,
            "broken_chain_ids": broken_chain_ids,
            "latest_hash": records[-1].entry_hash if records else GENESIS_HASH,
        }

    except Exception as exc:
        logger.error(f"Failed to verify audit chain: {exc}", exc_info=True)
        return {
            "is_valid": False,
            "status": "error",
            "verified_count": 0,
            "unsigned_count": 0,
            "message": f"حدث خطأ أثناء فحص سلسلة التدقيق: {str(exc)}",
            "tampered_ids": [],
            "broken_chain_ids": [],
            "latest_hash": GENESIS_HASH,
        }


def backfill_legacy_audit_logs(db: Session) -> int:
    """
    توقيع وربط السجلات السابقة غير الموقعة في السلسلة المشفرة تلقائياً
    """
    try:
        unsigned_records = (
            db.query(LawAuditLog)
            .filter(LawAuditLog.entry_hash.is_(None))
            .order_by(LawAuditLog.id.asc())
            .all()
        )
        if not unsigned_records:
            return 0

        current_prev_hash = get_latest_audit_hash(db)
        count = 0

        for rec in unsigned_records:
            current_prev_hash = sign_audit_entry(rec, prev_hash=current_prev_hash)
            count += 1

        db.commit()
        logger.info(f"[Audit Chain] Successfully backfilled and signed {count} legacy audit records.")
        return count
    except Exception as exc:
        db.rollback()
        logger.error(f"[Audit Chain] Backfill failed: {exc}", exc_info=True)
        return 0
