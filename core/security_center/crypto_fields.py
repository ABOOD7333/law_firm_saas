"""
Field-Level Encryption at Rest (AES-256-GCM) — LawSaaS Platform
منظومة التشفير العسكري للبيانات الحساسة على مستوى الحقول في قاعدة البيانات

الميزات:
1. تشفير متقدم بموجب معايير NIST باستخدام AES-256-GCM (Authenticated Encryption).
2. اشتقاق مفاتيح التشفير عبر HKDF-SHA256 لمنع كشف المفاتيح.
3. Nonce عشوائي فريد 96-bit لكل عملية تشفير لمنع هجمات تحليل الأنماط.
4. توافقية تامة بأثر رجعي (Backward Compatibility): قراءة السجلات السابقة غير المشفرة بسلاسة، وتشفيرها التلقائي عند الحفظ.
5. نوع مخصص في SQLAlchemy (EncryptedString / EncryptedText) يعمل بشفافية كاملة مع الـ ORM.
"""

import os
import base64
import logging
from typing import Optional
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes
from sqlalchemy.types import TypeDecorator, Text
from sqlalchemy import text

logger = logging.getLogger("law_firm.security.crypto")

PREFIX = "enc:v1:"
NONCE_LENGTH = 12  # 96 bits recommended for AES-GCM

_cached_aesgcm: Optional[AESGCM] = None


def get_encryption_key() -> bytes:
    """اشتقاق مفتاح تشفير 256 بت آمن"""
    custom_key = os.getenv("FIELD_ENCRYPTION_KEY")
    if custom_key:
        if len(custom_key) == 64:
            try:
                return bytes.fromhex(custom_key)
            except Exception:
                pass
        try:
            decoded = base64.b64decode(custom_key)
            if len(decoded) == 32:
                return decoded
        except Exception:
            pass
        secret_bytes = custom_key.encode("utf-8")
    else:
        system_secret = os.getenv("SECRET_KEY", "lawsaas_ultra_secure_enterprise_key_2026")
        secret_bytes = system_secret.encode("utf-8")

    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=b"lawsaas-field-level-encryption-salt-2026",
        info=b"lawsaas-db-field-encryption-v1"
    )
    return hkdf.derive(secret_bytes)


def get_cipher() -> AESGCM:
    """الحصول على كائن التشفير AESGCM"""
    global _cached_aesgcm
    if _cached_aesgcm is None:
        key = get_encryption_key()
        _cached_aesgcm = AESGCM(key)
    return _cached_aesgcm


def encrypt_field(plaintext: Optional[str]) -> Optional[str]:
    """تشفير نص وتخزينه بصيغة enc:v1:<Base64>"""
    if plaintext is None:
        return None
    val_str = str(plaintext)
    if not val_str:
        return ""
    # إذا كانت القيمة مشفرة مسبقاً، نتركها كما هي
    if val_str.startswith(PREFIX):
        return val_str

    try:
        cipher = get_cipher()
        nonce = os.urandom(NONCE_LENGTH)
        raw_bytes = val_str.encode("utf-8")
        ciphertext = cipher.encrypt(nonce, raw_bytes, None)
        encoded = base64.b64encode(nonce + ciphertext).decode("ascii")
        return f"{PREFIX}{encoded}"
    except Exception as e:
        logger.error(f"[Crypto] Failed to encrypt field: {e}")
        return val_str


def decrypt_field(stored_value: Optional[str]) -> Optional[str]:
    """فك تشفير النص، أو إرجاعه كما هو إذا كان نصاً غير مشفر"""
    if stored_value is None:
        return None
    val_str = str(stored_value)
    if not val_str:
        return ""
    # إذا لم تكن القيمة مشفرة بالبادئة enc:v1:، فهي نص قديم غير مشفر ونرجعه كما هو
    if not val_str.startswith(PREFIX):
        return val_str

    try:
        cipher = get_cipher()
        payload = val_str[len(PREFIX):]
        raw = base64.b64decode(payload)
        if len(raw) < NONCE_LENGTH:
            return val_str
        nonce = raw[:NONCE_LENGTH]
        ciphertext = raw[NONCE_LENGTH:]
        decrypted_bytes = cipher.decrypt(nonce, ciphertext, None)
        return decrypted_bytes.decode("utf-8")
    except Exception as e:
        logger.warning(f"[Crypto] Failed to decrypt field (may use different key): {e}")
        return val_str


class EncryptedString(TypeDecorator):
    """
    نوع حقل في SQLAlchemy يقوم بالتشفير الشفاف بـ AES-256-GCM.
    عند الإدخال في قاعدة البيانات يُشفر النص تلقائياً،
    وعند استدعائه في البايثون يُفك تشفيره تلقائياً.
    """
    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return encrypt_field(str(value))

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return decrypt_field(str(value))


class EncryptedText(EncryptedString):
    """نوع حقل للنصوص الطويلة المشفرة بـ AES-256-GCM"""
    pass


def migrate_and_encrypt_existing_records(db) -> dict:
    """
    فحص وترحيل السجلات القديمة لتشفيرها بالكامل بأثر رجعي.
    """
    stats = {"clients_encrypted": 0, "reps_encrypted": 0, "trust_accounts_encrypted": 0}
    try:
        # 1. تشفير جدول law_clients
        clients = db.execute(text("SELECT id, national_id, cr_number, tax_number FROM law_clients")).fetchall()
        for row in clients:
            c_id, nid, cr, tax = row
            updates = {}
            if nid and not str(nid).startswith(PREFIX):
                updates["national_id"] = encrypt_field(nid)
            if cr and not str(cr).startswith(PREFIX):
                updates["cr_number"] = encrypt_field(cr)
            if tax and not str(tax).startswith(PREFIX):
                updates["tax_number"] = encrypt_field(tax)

            if updates:
                set_clauses = ", ".join([f"{k} = :{k}" for k in updates.keys()])
                updates["id"] = c_id
                db.execute(text(f"UPDATE law_clients SET {set_clauses} WHERE id = :id"), updates)
                stats["clients_encrypted"] += 1

        # 2. تشفير جدول law_client_representatives
        reps = db.execute(text("SELECT id, national_id FROM law_client_representatives")).fetchall()
        for row in reps:
            r_id, nid = row
            if nid and not str(nid).startswith(PREFIX):
                enc_nid = encrypt_field(nid)
                db.execute(text("UPDATE law_client_representatives SET national_id = :nid WHERE id = :id"), {"nid": enc_nid, "id": r_id})
                stats["reps_encrypted"] += 1

        # 3. تشفير جدول law_trust_accounts
        trusts = db.execute(text("SELECT id, iban FROM law_trust_accounts")).fetchall()
        for row in trusts:
            t_id, iban = row
            if iban and not str(iban).startswith(PREFIX):
                enc_iban = encrypt_field(iban)
                db.execute(text("UPDATE law_trust_accounts SET iban = :iban WHERE id = :id"), {"iban": enc_iban, "id": t_id})
                stats["trust_accounts_encrypted"] += 1

        db.commit()
    except Exception as e:
        logger.error(f"[Crypto Migration] Error during field encryption migration: {e}")
        db.rollback()

    return stats
