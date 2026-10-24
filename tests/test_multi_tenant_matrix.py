# -*- coding: utf-8 -*-
"""
Test Suite: Multi-Tenant Matrix & Cross-Office Security Verification
فحص مصفوفة عزل المكاتب والتحقق الخادمي الصارم من منع هجمات التلاعب بالمعرفات (IDOR)
وصلاحيات SuperAdmin عبر كافة الكيانات:
(القضايا، المستندات، العملاء، الجلسات، الفواتير، الإعدادات، مسارات الإدارة العليا)
يتم تنفيذ هذا الاختبار بالكامل في بيئة معزولة على قاعدة بيانات اختبار مستقلة.
"""

import unittest
import asyncio
from datetime import datetime
from fastapi import HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database.models import (
    Base, LawOffices, AccessProfiles, LawCases, LawClients,
    LawDocuments, LawHearings, Invoices, InvoiceItems
)
from main import (
    case_details_page, edit_case, delete_client,
    get_hearing_details, delete_hearing, update_office
)
from routers.client_profile_route import client_profile_page
from routers.documents_route import get_document_details, download_document
from routers.accounting import get_invoice_details, delete_invoice
from routers.security_center import require_superadmin


class TestMultiTenantMatrix(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = create_engine("sqlite:///:memory:", echo=False)
        Base.metadata.create_all(cls.engine)
        cls.Session = sessionmaker(bind=cls.engine)

    def setUp(self):
        self.db = self.Session()
        for tbl in reversed(Base.metadata.sorted_tables):
            self.db.execute(tbl.delete())
        self.db.commit()

        # إنشاء مكتبين مستقلين
        self.off1 = LawOffices(id=1, name="مكتب الأمان الأول", is_active=1)
        self.off2 = LawOffices(id=2, name="مكتب العدالة الثاني", is_active=1)
        self.db.add_all([self.off1, self.off2])
        self.db.commit()

        # إنشاء مستخدمين في المكتبين
        self.user_off1 = AccessProfiles(
            id=101, name="محامي مكتب 1", username="lawyer1",
            phone="0511111111", email="lawyer1@test.com",
            office_id=1, role="مدير المكتب", is_superadmin=0
        )
        self.user_off2 = AccessProfiles(
            id=201, name="محامي مكتب 2", username="lawyer2",
            phone="0522222222", email="lawyer2@test.com",
            office_id=2, role="مدير المكتب", is_superadmin=0
        )
        self.db.add_all([self.user_off1, self.user_off2])
        self.db.commit()

        # كيانات تابعة للمكتب 2 (المستهدف بالحماية من اختراق مكتب 1)
        self.case_off2 = LawCases(id=2001, office_id=2, case_number="CASE-OFF2-001", title="قضية سرية لمكتب 2", is_deleted=0)
        self.client_off2 = LawClients(id=2001, office_id=2, name="عميل مهم لمكتب 2", is_deleted=0)
        self.db.add_all([self.case_off2, self.client_off2])
        self.db.commit()

        self.hearing_off2 = LawHearings(
            id=2001, office_id=2, case_id=2001,
            title="جلسة مرافعة مكتب 2",
            hearing_at="2026-11-01 10:00:00", hearing_time="10:00",
            court_name="المحكمة التجارية", is_deleted=0
        )
        self.doc_off2 = LawDocuments(
            id=2001, office_id=2, case_id=2001,
            document_type_key="general", name="وثيقة_سرية_مكتب2",
            file_path="static/uploads/documents/secret_off2.pdf"
        )
        self.inv_off2 = Invoices(
            id=2001, office_id=2, client_id=2001, case_id=2001,
            invoice_number="INV-OFF2-999", uuid="uuid-off2-999",
            issue_date="2026-10-24", grand_total=50000.0, is_deleted=0
        )
        self.db.add_all([self.hearing_off2, self.doc_off2, self.inv_off2])
        self.db.commit()

    def tearDown(self):
        self.db.close()

    # 1. القضايا (Cases)
    def test_case_details_cross_office_blocked(self):
        """التحقق من أن مستخدم مكتب 1 يُمنع من قراءة تفاصيل قضية مكتب 2"""
        class DummyRequest:
            pass

        res = asyncio.run(case_details_page(
            case_id=2001,
            request=DummyRequest(),
            db=self.db,
            user=self.user_off1
        ))
        # يعيد 404 (غير موجود لمكتبه) لحجب وجود القضية من الأصل
        self.assertEqual(res.status_code, 404)

    def test_case_edit_cross_office_prevented(self):
        """التحقق من أن مستخدم مكتب 1 لا يستطيع تعديل بيانات قضية تابعة لمكتب 2"""
        class DummyRequest:
            pass

        asyncio.run(edit_case(
            case_id=2001,
            request=DummyRequest(),
            title="محاولة اختراق تعديل عنوان قضية",
            case_number="HACKED-NUM",
            client_id=2001,
            lead_lawyer_id=None,
            case_type_key="commercial",
            status_key="in_progress",
            db=self.db,
            user=self.user_off1
        ))

        # التحقق من أن القضية في قاعدة البيانات لم تتغير بياناتها إطلاقاً
        case_in_db = self.db.query(LawCases).filter(LawCases.id == 2001).first()
        self.assertEqual(case_in_db.title, "قضية سرية لمكتب 2")
        self.assertEqual(case_in_db.case_number, "CASE-OFF2-001")

    # 2. العملاء (Clients)
    def test_client_profile_cross_office_blocked(self):
        """التحقق من منع مستخدم مكتب 1 من الوصول لملف عميل مكتب 2"""
        class DummyRequest:
            pass

        with self.assertRaises(HTTPException) as cm:
            asyncio.run(client_profile_page(
                client_id=2001,
                request=DummyRequest(),
                db=self.db,
                user=self.user_off1
            ))
        self.assertEqual(cm.exception.status_code, 404)

    def test_client_delete_cross_office_prevented(self):
        """التحقق من أن استدعاء حذف عميل مكتب 2 بواسطة مستخدم مكتب 1 لا يحذف العميل"""
        class DummyRequest:
            pass

        asyncio.run(delete_client(
            request=DummyRequest(),
            client_id=2001,
            db=self.db,
            user=self.user_off1
        ))
        client_in_db = self.db.query(LawClients).filter(LawClients.id == 2001).first()
        self.assertEqual(client_in_db.is_deleted, 0, "Client of office 2 must NOT be deleted by office 1")

    # 3. الجلسات (Hearings)
    def test_hearing_details_cross_office_blocked(self):
        """التحقق من منع استعراض جلسة مكتب 2 من قبل مستخدم مكتب 1"""
        with self.assertRaises(HTTPException) as cm:
            asyncio.run(get_hearing_details(
                hearing_id=2001,
                db=self.db,
                user=self.user_off1
            ))
        self.assertEqual(cm.exception.status_code, 404)

    def test_hearing_delete_cross_office_blocked(self):
        """التحقق من منع حذف جلسة مكتب 2 من قبل مستخدم مكتب 1"""
        res = asyncio.run(delete_hearing(
            hearing_id=2001,
            db=self.db,
            user=self.user_off1
        ))
        self.assertEqual(res.status_code, 303)
        hearing_in_db = self.db.query(LawHearings).filter(LawHearings.id == 2001).first()
        self.assertIsNotNone(hearing_in_db)
        self.assertEqual(hearing_in_db.is_deleted, 0)

    # 4. المستندات (Documents)
    def test_document_details_cross_office_blocked(self):
        """التحقق من منع قراءة بيانات وثيقة مكتب 2 عبر API"""
        with self.assertRaises(HTTPException) as cm:
            asyncio.run(get_document_details(
                doc_id=2001,
                db=self.db,
                user=self.user_off1
            ))
        self.assertEqual(cm.exception.status_code, 404)

    def test_document_download_cross_office_blocked(self):
        """التحقق من منع تنزيل ملف وثيقة مكتب 2 بكود 403 Forbidden"""
        with self.assertRaises(HTTPException) as cm:
            asyncio.run(download_document(
                filename="secret_off2.pdf",
                db=self.db,
                user=self.user_off1
            ))
        self.assertEqual(cm.exception.status_code, 403)

    # 5. الفواتير (Invoices)
    def test_invoice_details_cross_office_blocked(self):
        """التحقق من منع استعراض فاتورة مكتب 2 من قبل مستخدم مكتب 1"""
        res = asyncio.run(get_invoice_details(
            uuid="uuid-off2-999",
            db=self.db,
            user=self.user_off1
        ))
        self.assertEqual(res.status_code, 404)

    def test_invoice_delete_cross_office_blocked(self):
        """التحقق من منع حذف فاتورة مكتب 2 من قبل مستخدم مكتب 1"""
        res = asyncio.run(delete_invoice(
            uuid="uuid-off2-999",
            db=self.db,
            user=self.user_off1
        ))
        self.assertEqual(res.status_code, 404)
        inv_in_db = self.db.query(Invoices).filter(Invoices.id == 2001).first()
        self.assertEqual(inv_in_db.is_deleted, 0)

    # 6. الإعدادات وتعديل بيانات المكتب (Settings & Office Modification)
    def test_office_settings_modification_cross_office_blocked(self):
        """التحقق من منع مستخدم مكتب 1 من التعديل على بيانات مكتب 2 بتمرير office_id في الفورم"""
        class DummyRequest:
            pass

        with self.assertRaises(HTTPException) as cm:
            asyncio.run(update_office(
                request=DummyRequest(),
                office_id=2,  # محاولة التلاعب بمعرف المكتب
                name="مكتب مخترق",
                db=self.db,
                user=self.user_off1
            ))
        self.assertEqual(cm.exception.status_code, 403)
        off2_in_db = self.db.query(LawOffices).filter(LawOffices.id == 2).first()
        self.assertEqual(off2_in_db.name, "مكتب العدالة الثاني", "Office 2 name must remain untouched")

    # 7. صلاحيات SuperAdmin والتحقق الخادمي الصارم (Server-Side RBAC)
    def test_superadmin_authorization_enforced(self):
        """التحقق من أن المستخدم العادي غير المشرف محظور تماماً من مركز الأمن السيبراني وعمليات السوبر أدمن"""
        # محاولة طلب دالة التحقق من السوبر أدمن
        with self.assertRaises(HTTPException) as cm:
            require_superadmin(self.user_off1)
        self.assertEqual(cm.exception.status_code, 403)

        # التحقق من أن السوبر أدمن الفعلي يُسمح له
        superadmin_user = AccessProfiles(
            id=1, name="سوبر أدمن المنصة", username="platform_admin",
            phone="0500000000", email="superadmin@lawsaas.test",
            office_id=1, role="مدير المنصة", is_superadmin=1
        )
        verified = require_superadmin(superadmin_user)
        self.assertEqual(verified.id, 1)


if __name__ == "__main__":
    unittest.main()
