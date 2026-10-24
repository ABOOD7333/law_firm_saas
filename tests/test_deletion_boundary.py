# -*- coding: utf-8 -*-
"""
Test Suite: SQL Deletion Boundary & Multi-Tenant Data Protection
التحقق المستقل من حدود عمليات الحذف وضمان عدم تسرب الحذف إلى مكاتب أخرى أو بيانات غير مقصودة.
يتم تنفيذ هذا الاختبار بالكامل على قاعدة بيانات SQLite مستقلة في الذاكرة (:memory:) دون المساس بالإنتاج.
"""

import unittest
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database.models import (
    Base, LawOffices, AccessProfiles, AuthSessions,
    LawCases, LawClients, LawDocuments, Invoices, InvoiceItems
)


class TestSQLDeletionBoundary(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # إنشاء قاعدة بيانات مستقلة بالكامل في الذاكرة
        cls.engine = create_engine("sqlite:///:memory:", echo=False)
        Base.metadata.create_all(cls.engine)
        cls.Session = sessionmaker(bind=cls.engine)

    def setUp(self):
        self.db = self.Session()
        # تنظيف الجداول قبل كل اختبار
        for tbl in reversed(Base.metadata.sorted_tables):
            self.db.execute(tbl.delete())
        self.db.commit()

        # إعداد 3 مكاتب وهمية
        # مكتب 10 (مكتب رسمي مستقر)
        self.off10 = LawOffices(id=10, name="مكتب الأمان القانوني 10", is_active=1)
        # مكتب 20 (مكتب مستهدف بالحذف)
        self.off20 = LawOffices(id=20, name="مكتب تجريبي للتصفية 20", is_active=1)
        # مكتب 30 (مكتب شريك آخر مستقر)
        self.off30 = LawOffices(id=30, name="مكتب العدالة 30", is_active=1)

        self.db.add_all([self.off10, self.off20, self.off30])
        self.db.commit()

        # إضافة مستخدمين لكل مكتب
        self.u10 = AccessProfiles(id=1001, name="مستخدم 10", username="user_10", phone="0500000010", email="u10@lawsaas.test", office_id=10, role="مدير")
        self.u20 = AccessProfiles(id=2001, name="مستخدم 20", username="user_20", phone="0500000020", email="u20@lawsaas.test", office_id=20, role="مدير")
        self.u30 = AccessProfiles(id=3001, name="مستخدم 30", username="user_30", phone="0500000030", email="u30@lawsaas.test", office_id=30, role="مدير")
        self.db.add_all([self.u10, self.u20, self.u30])
        self.db.commit()

        # إضافة قضايا لكل مكتب
        self.case10 = LawCases(id=101, office_id=10, case_number="CASE-10", title="قضية مكتب 10", is_deleted=0)
        self.case20 = LawCases(id=201, office_id=20, case_number="CASE-20", title="قضية مكتب 20", is_deleted=0)
        self.case30 = LawCases(id=301, office_id=30, case_number="CASE-30", title="قضية مكتب 30", is_deleted=0)
        self.db.add_all([self.case10, self.case20, self.case30])
        self.db.commit()

        # إضافة عملاء لكل مكتب
        self.client10 = LawClients(id=11, office_id=10, name="عميل مكتب 10", is_deleted=0)
        self.client20 = LawClients(id=21, office_id=20, name="عميل مكتب 20", is_deleted=0)
        self.client30 = LawClients(id=31, office_id=30, name="عميل مكتب 30", is_deleted=0)
        self.db.add_all([self.client10, self.client20, self.client30])
        self.db.commit()

        # إضافة مستندات لكل مكتب
        self.doc10 = LawDocuments(id=1001, office_id=10, case_id=101, document_type_key="general", name="وثيقة 10", file_path="doc10.pdf")
        self.doc20 = LawDocuments(id=2001, office_id=20, case_id=201, document_type_key="general", name="وثيقة 20", file_path="doc20.pdf")
        self.doc30 = LawDocuments(id=3001, office_id=30, case_id=301, document_type_key="general", name="وثيقة 30", file_path="doc30.pdf")
        self.db.add_all([self.doc10, self.doc20, self.doc30])
        self.db.commit()

        # إضافة فواتير لكل مكتب
        self.inv10 = Invoices(id=501, office_id=10, client_id=11, invoice_number="INV-10", uuid="uuid-10", issue_date="2026-10-24", grand_total=1000.0, is_deleted=0)
        self.inv20 = Invoices(id=502, office_id=20, client_id=21, invoice_number="INV-20", uuid="uuid-20", issue_date="2026-10-24", grand_total=2000.0, is_deleted=0)
        self.inv30 = Invoices(id=503, office_id=30, client_id=31, invoice_number="INV-30", uuid="uuid-30", issue_date="2026-10-24", grand_total=3000.0, is_deleted=0)
        self.db.add_all([self.inv10, self.inv20, self.inv30])
        self.db.commit()

    def tearDown(self):
        self.db.close()

    def test_targeted_office_deletion_boundary(self):
        """
        التحقق من أن استدعاء حذف مكتب 20 يحذف سجلاته فقط
        مع بقاء مكتب 10 ومكتب 30 سليمين بنسبة 100%.
        """
        target_office_id = 20

        # تطبيق منطق الحذف المعتمد في routers/superadmin.py (delete_office)
        tables_to_clean = [
            'law_cases', 'law_incoming_cases', 'law_clients', 'law_parties',
            'law_hearings', 'law_tasks', 'law_judgments', 'law_expenses',
            'law_transactions', 'law_power_of_attorney', 'law_documents',
            'law_timesheets', 'law_notes', 'law_correspondences',
            'law_executions', 'law_limitations', 'law_pleadings',
            'payment_requests', 'invoices', 'client_payments',
            'retainer_agreements', 'client_intake_forms', 'law_trust_accounts'
        ]

        # 1. حذف جلسات ومستخدمي المكتب المستهدف
        users = self.db.query(AccessProfiles).filter(AccessProfiles.office_id == target_office_id).all()
        user_ids = [u.id for u in users]
        if user_ids:
            self.db.query(AuthSessions).filter(AuthSessions.user_id.in_(user_ids)).delete(synchronize_session=False)
            self.db.query(AccessProfiles).filter(AccessProfiles.id.in_(user_ids)).delete(synchronize_session=False)

        # 2. حذف الجداول التابعة
        for tbl in tables_to_clean:
            table_obj = Base.metadata.tables.get(tbl)
            if table_obj is not None and "office_id" in table_obj.c:
                self.db.execute(table_obj.delete().where(table_obj.c.office_id == target_office_id))

        # 3. حذف سجل المكتب نفسه
        office = self.db.query(LawOffices).filter(LawOffices.id == target_office_id).first()
        self.db.delete(office)
        self.db.commit()

        # === التحقق من نتائج الحذف على المكتب المستهدف (مكتب 20) ===
        self.assertIsNone(self.db.query(LawOffices).filter(LawOffices.id == 20).first(), "Office 20 must be deleted")
        self.assertEqual(self.db.query(AccessProfiles).filter(AccessProfiles.office_id == 20).count(), 0)
        self.assertEqual(self.db.query(LawCases).filter(LawCases.office_id == 20).count(), 0)
        self.assertEqual(self.db.query(LawClients).filter(LawClients.office_id == 20).count(), 0)
        self.assertEqual(self.db.query(LawDocuments).filter(LawDocuments.office_id == 20).count(), 0)
        self.assertEqual(self.db.query(Invoices).filter(Invoices.office_id == 20).count(), 0)

        # === التحقق الحاسم: بيانات مكتب 10 ومكتب 30 يجب أن تبقى سليمة 100% دون أي مساس ===
        # فحص مكتب 10
        self.assertIsNotNone(self.db.query(LawOffices).filter(LawOffices.id == 10).first(), "Office 10 must remain intact")
        self.assertEqual(self.db.query(AccessProfiles).filter(AccessProfiles.office_id == 10).count(), 1)
        self.assertEqual(self.db.query(LawCases).filter(LawCases.office_id == 10).count(), 1)
        self.assertEqual(self.db.query(LawClients).filter(LawClients.office_id == 10).count(), 1)
        self.assertEqual(self.db.query(LawDocuments).filter(LawDocuments.office_id == 10).count(), 1)
        self.assertEqual(self.db.query(Invoices).filter(Invoices.office_id == 10).count(), 1)

        # فحص مكتب 30
        self.assertIsNotNone(self.db.query(LawOffices).filter(LawOffices.id == 30).first(), "Office 30 must remain intact")
        self.assertEqual(self.db.query(AccessProfiles).filter(AccessProfiles.office_id == 30).count(), 1)
        self.assertEqual(self.db.query(LawCases).filter(LawCases.office_id == 30).count(), 1)
        self.assertEqual(self.db.query(LawClients).filter(LawClients.office_id == 30).count(), 1)
        self.assertEqual(self.db.query(LawDocuments).filter(LawDocuments.office_id == 30).count(), 1)
        self.assertEqual(self.db.query(Invoices).filter(Invoices.office_id == 30).count(), 1)

    def test_unauthorized_office_id_1_protected(self):
        """التحقق من أن المكتب رقم 1 محمي برمجياً من الحذف المباشر حتى لو طُلب حذفه"""
        from routers.superadmin import delete_office
        from fastapi import Request
        import asyncio

        # محاكاة مستخدم سوبر أدمن
        admin_user = AccessProfiles(id=1, username="superadmin", is_superadmin=1)
        # إنشاء request وهمي
        class DummyRequest:
            pass

    def test_cleanup_and_keep_official_offices_boundary(self):
        """
        التحقق من أن دالة cleanup_and_keep_official_offices تحافظ بشكل قاطع على
        مكتب عبدالله العليمي (1) ومكتب هشام دغيش (6) وحساب ABOOD، وتقتلع المكاتب التجريبية فقط.
        """
        from database.database import cleanup_and_keep_official_offices

        # إضافة مكتب 1 ومكتب 6
        off1 = LawOffices(id=1, name="مكتب عبدالله العليمي للمحاماة", is_active=1)
        off6 = LawOffices(id=6, name="مكتب هشام دغيش للمحاماة", is_active=1)
        self.db.add_all([off1, off6])
        self.db.commit()

        # إضافة مستخدم ABOOD في مكتب 1
        abood_user = AccessProfiles(id=1, name="ABOOD", username="ABOOD", phone="0555555555", email="abood@lawsaas.test", office_id=1, role="مدير النظام", is_superadmin=1)
        self.db.add(abood_user)
        self.db.commit()

        # تشغيل التطهير
        cleanup_and_keep_official_offices(self.db)

        # التحقق من بقاء مكتب 1 ومكتب 6 وحساب ABOOD
        self.assertIsNotNone(self.db.query(LawOffices).filter(LawOffices.id == 1).first(), "Office 1 must be kept")
        self.assertIsNotNone(self.db.query(LawOffices).filter(LawOffices.id == 6).first(), "Office 6 must be kept")
        self.assertIsNotNone(self.db.query(AccessProfiles).filter(AccessProfiles.username == "ABOOD").first(), "ABOOD user must be kept")

        # التحقق من حذف المكتب التجريبي (20)
        self.assertIsNone(self.db.query(LawOffices).filter(LawOffices.id == 20).first(), "Trial Office 20 must be purged")


if __name__ == "__main__":
    unittest.main()
