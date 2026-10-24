"""
Unit tests for Cryptographic Immutable Audit Chain (Chain-of-Custody)
اختبارات وحدة سلسلة سجلات التدقيق المشفرة غير القابلة للتلاعب
"""
import unittest
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database.models import Base, LawAuditLog
from core.security_center.audit_chain import (
    GENESIS_HASH,
    get_latest_audit_hash,
    sign_audit_entry,
    verify_audit_chain,
    backfill_legacy_audit_logs,
    compute_entry_hash,
)
from core.audit import write_audit


class TestAuditChain(unittest.TestCase):
    def setUp(self):
        # Create an isolated in-memory SQLite database for testing
        self.engine = create_engine("sqlite:///:memory:", echo=False)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.db = self.Session()

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(self.engine)

    def test_01_empty_chain_returns_genesis(self):
        """التحقق من أن السلسلة الفارغة تعيد الهاش البدئي Genesis"""
        latest = get_latest_audit_hash(self.db)
        self.assertEqual(latest, GENESIS_HASH)

        report = verify_audit_chain(self.db)
        self.assertTrue(report["is_valid"])
        self.assertEqual(report["verified_count"], 0)

    def test_02_write_audit_automatically_signs_and_chains(self):
        """التحقق من أن write_audit توقع السجل وتربطه بالسلسلة تلقائياً"""
        write_audit(
            self.db,
            table_name="law_cases",
            action_name="CREATE",
            actor_user_id=1,
            actor_name="أحمد المحامي",
            office_id=10,
            record_key="CASE-2026-001",
            details="إنشاء قضية جديدة",
        )
        self.db.commit()

        entry = self.db.query(LawAuditLog).first()
        self.assertIsNotNone(entry)
        self.assertEqual(entry.prev_hash, GENESIS_HASH)
        self.assertIsNotNone(entry.entry_hash)
        self.assertEqual(len(entry.entry_hash), 64)  # SHA-256 hex digest length

        # إضافة سجل ثانٍ والتأكد من الترابط بالسلسلة
        write_audit(
            self.db,
            table_name="law_cases",
            action_name="UPDATE",
            actor_user_id=1,
            actor_name="أحمد المحامي",
            office_id=10,
            record_key="CASE-2026-001",
            details="تعديل جلسة القضية",
        )
        self.db.commit()

        entries = self.db.query(LawAuditLog).order_by(LawAuditLog.id.asc()).all()
        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[1].prev_hash, entries[0].entry_hash)

        # التحقق الرياضي الشامل
        report = verify_audit_chain(self.db)
        self.assertTrue(report["is_valid"])
        self.assertEqual(report["verified_count"], 2)
        self.assertEqual(report["status"], "secure")

    def test_03_detect_tampering_of_audit_record(self):
        """التحقق من كشف أي تلاعب بمحتوى السجل فورياً عبر HMAC"""
        write_audit(
            self.db,
            table_name="invoices",
            action_name="PAYMENT_RECEIVED",
            actor_user_id=2,
            actor_name="المحاسب",
            office_id=10,
            details="استلام مبلغ 50,000 ريال",
        )
        self.db.commit()

        rec = self.db.query(LawAuditLog).first()
        tampered_id = rec.id

        # محاكاة هجوم مباشر في قاعدة البيانات لتعديل تفاصيل السجل لإخفاء الاختلاس
        self.db.execute(
            Base.metadata.tables["law_audit_log"].update()
            .where(LawAuditLog.id == tampered_id)
            .values(details="استلام مبلغ 5,000 ريال فقط")
        )
        self.db.commit()

        report = verify_audit_chain(self.db)
        self.assertFalse(report["is_valid"])
        self.assertEqual(report["status"], "compromised")
        self.assertIn(tampered_id, report["tampered_ids"])

    def test_04_detect_deletion_and_broken_chain(self):
        """التحقق من كشف حذف أي سجل في السلسلة (Broken Chain)"""
        for i in range(1, 4):
            write_audit(
                self.db,
                table_name="law_documents",
                action_name=f"ACTION_{i}",
                actor_user_id=1,
                office_id=10,
                details=f"Document operation {i}",
            )
            self.db.commit()

        entries = self.db.query(LawAuditLog).order_by(LawAuditLog.id.asc()).all()
        self.assertEqual(len(entries), 3)

        # محاكاة حذف السجل الأوسط (رقم 2)
        middle_id = entries[1].id
        self.db.query(LawAuditLog).filter(LawAuditLog.id == middle_id).delete()
        self.db.commit()

        report = verify_audit_chain(self.db)
        self.assertFalse(report["is_valid"])
        self.assertEqual(report["status"], "compromised")
        self.assertIn(entries[2].id, report["broken_chain_ids"])

    def test_05_backfill_legacy_records(self):
        """التحقق من الترقية التلقائية وتوقيع السجلات السابقة غير الموقعة"""
        # إنشاء 3 سجلات قديمة بدون توقيع
        for i in range(1, 4):
            legacy = LawAuditLog(
                table_name="legacy_table",
                action_name="LEGACY_ACTION",
                actor_user_id=i,
                actor_name="User",
                office_id=1,
                created_at=datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
            )
            self.db.add(legacy)
        self.db.commit()

        # التأكد من أنها غير موقعة
        unsigned_before = self.db.query(LawAuditLog).filter(LawAuditLog.entry_hash.is_(None)).count()
        self.assertEqual(unsigned_before, 3)

        # تشغيل الترقية التلقائية Backfill
        signed_count = backfill_legacy_audit_logs(self.db)
        self.assertEqual(signed_count, 3)

        # التحقق من أن السلسلة أصبحت موقعة ومترابطة وسليمة 100%
        report = verify_audit_chain(self.db)
        self.assertTrue(report["is_valid"])
        self.assertEqual(report["verified_count"], 3)
        self.assertEqual(report["unsigned_count"], 0)


if __name__ == "__main__":
    unittest.main()
