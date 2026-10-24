"""
Unit Tests for Field-Level Encryption at Rest (AES-256-GCM)
اختبارات التشفير العسكري للحقول الحساسة
"""

import unittest
import os
import uuid
from sqlalchemy import text
from database.database import SessionLocal, engine, Base
from database.models import LawClients, LawClientRepresentatives, LawTrustAccounts, LawOffices
from core.security_center.crypto_fields import (
    encrypt_field,
    decrypt_field,
    migrate_and_encrypt_existing_records,
    PREFIX
)


class TestFieldLevelEncryption(unittest.TestCase):
    def setUp(self):
        self.db = SessionLocal()
        # Create test office
        self.office = self.db.query(LawOffices).first()
        if not self.office:
            self.office = LawOffices(name="Crypto Test HQ")
            self.db.add(self.office)
            self.db.commit()
            self.db.refresh(self.office)

    def tearDown(self):
        self.db.close()

    def test_direct_encrypt_decrypt(self):
        """اختبار التشفير وفك التشفير المباشر"""
        test_id = "1098765432"
        enc = encrypt_field(test_id)
        self.assertIsNotNone(enc)
        self.assertTrue(enc.startswith(PREFIX))
        self.assertNotEqual(enc, test_id)

        # فك التشفير
        dec = decrypt_field(enc)
        self.assertEqual(dec, test_id)

    def test_distinct_nonces(self):
        """التأكد من أن نفس القيمة تشفر بنصوص مختلفة لمنع تحليل الأنماط"""
        test_id = "1098765432"
        enc1 = encrypt_field(test_id)
        enc2 = encrypt_field(test_id)
        self.assertNotEqual(enc1, enc2)
        # كلاهما يفك تشفيره لنفس القيمة الأصلية
        self.assertEqual(decrypt_field(enc1), test_id)
        self.assertEqual(decrypt_field(enc2), test_id)

    def test_backward_compatibility_plaintext(self):
        """التأكد من قراءة البيانات السابقة غير المشفرة دون أخطاء"""
        plain = "2099887766"
        # نص عادي بدون البادئة enc:v1:
        res = decrypt_field(plain)
        self.assertEqual(res, plain)

    def test_sqlalchemy_orm_transparency(self):
        """اختبار شفافية الـ ORM: التخزين مشفر في القاعدة والاستدعاء مفكوك في الكود"""
        unique_nid = f"NID-{uuid.uuid4().hex[:8]}"
        client = LawClients(
            office_id=self.office.id,
            name="شركة التشفير المتقدم المحدودة",
            national_id=unique_nid,
            cr_number="CR-1010998877",
            tax_number="TAX-3001234567"
        )
        self.db.add(client)
        self.db.commit()
        self.db.refresh(client)

        # 1. الاستعلام المباشر عبر الـ ORM يعطي النص الأصلي شفافياً
        fetched = self.db.query(LawClients).filter(LawClients.id == client.id).first()
        self.assertEqual(fetched.national_id, unique_nid)
        self.assertEqual(fetched.cr_number, "CR-1010998877")
        self.assertEqual(fetched.tax_number, "TAX-3001234567")

        # 2. الاستعلام الخام عبر SQL يثبت أن المخزن في القرص مشفر بالبادئة enc:v1:
        raw_row = self.db.execute(
            text("SELECT national_id, cr_number, tax_number FROM law_clients WHERE id = :id"),
            {"id": client.id}
        ).fetchone()

        raw_nid, raw_cr, raw_tax = raw_row
        self.assertTrue(raw_nid.startswith(PREFIX), f"Raw DB should be encrypted: {raw_nid}")
        self.assertTrue(raw_cr.startswith(PREFIX), f"Raw DB should be encrypted: {raw_cr}")
        self.assertTrue(raw_tax.startswith(PREFIX), f"Raw DB should be encrypted: {raw_tax}")

        # تنظيف
        self.db.delete(client)
        self.db.commit()

    def test_migration_utility(self):
        """اختبار أداة ترحيل وتشفير السجلات السابقة"""
        # إدخال سجل بنص خام مباشر دون تشفير
        self.db.execute(
            text("INSERT INTO law_clients (name, office_id, national_id, created_at, is_deleted) VALUES ('عميل قديم', :off, 'RAW_PLAINTEXT_ID_123', '2026-01-01', 0)"),
            {"off": self.office.id}
        )
        self.db.commit()

        # تشغيل سكربت الترحيل
        stats = migrate_and_encrypt_existing_records(self.db)
        self.assertGreaterEqual(stats["clients_encrypted"], 1)

        # التحقق من أن السجل أصبح مشفراً في القاعدة
        row = self.db.execute(text("SELECT national_id FROM law_clients WHERE name = 'عميل قديم'")).fetchone()
        self.assertTrue(row[0].startswith(PREFIX))
        self.assertEqual(decrypt_field(row[0]), "RAW_PLAINTEXT_ID_123")

        # تنظيف
        self.db.execute(text("DELETE FROM law_clients WHERE name = 'عميل قديم'"))
        self.db.commit()


if __name__ == "__main__":
    unittest.main()
