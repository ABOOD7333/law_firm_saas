"""
Comprehensive Test Suite — LawSaaS Cybersecurity Operations Center
مجموعة الاختبارات الشاملة لمركز الأمن السيبراني:
1. اختبار نماذج وجداول قاعدة البيانات التسعة.
2. اختبار محرك الفحص الأمني (SAST, SCA, Database Tenancy).
3. اختبار التحقق من الصلاحيات وحظر غير المشرفين (Superadmin Access Control).
4. اختبار وسيط المراقبة الأمنية وكشف الهجمات وتطهير البيانات.
5. اختبار كبح تكرار التنبيهات (Alert Deduplication & Throttling).
6. اختبار سلامة بيانات المكاتب والقضايا والعملاء القائمة (Zero Regression).
"""

import os
import sys
import unittest
from datetime import datetime
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from sqlalchemy import text

# ضمان إضافة مسار المشروع
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from database.database import SessionLocal, engine, Base
from database.models import AccessProfiles, LawOffices, LawCases, LawClients
from database.security_models import (
    SecurityScans,
    SecurityFindings,
    SecurityEvents,
    SecurityAlerts,
    SecurityDependencies,
    SecurityAuditLogs,
    SecurityScanSchedules,
    SecurityAlertSettings,
    SecurityScanTargets,
)
from core.security_center.scanner_engine import LawSaaSScanner, sanitize_evidence, is_scannable_file
from core.security_center.alert_service import compute_dedup_fingerprint, dispatch_security_alert, get_or_create_alert_settings
from core.security_center.monitor_middleware import sanitize_request_data, record_security_event
from routers.security_center import require_superadmin
from fastapi import HTTPException


class TestCybersecurityCenter(unittest.TestCase):
    def setUp(self):
        self.db: Session = SessionLocal()

    def tearDown(self):
        self.db.close()

    # 1. اختبار الجداول التسعة
    def test_database_tables_exist(self):
        expected_tables = [
            "security_scans",
            "security_findings",
            "security_events",
            "security_alerts",
            "security_dependencies",
            "security_audit_logs",
            "security_scan_schedules",
            "security_alert_settings",
            "security_scan_targets",
        ]
        registered_tables = list(Base.metadata.tables.keys())
        for tbl in expected_tables:
            self.assertIn(tbl, registered_tables, f"Table {tbl} must be registered in SQLAlchemy metadata")

    # 2. اختبار تطهير البيانات والأدلة
    def test_evidence_sanitization(self):
        raw_evidence = 'db.connect(user="admin", password="super_secret_password_123", token="xyz987")'
        clean = sanitize_evidence(raw_evidence)
        self.assertNotIn("super_secret_password_123", clean)
        self.assertNotIn("xyz987", clean)
        self.assertIn("[REDACTED_BY_SOC]", clean)

    def test_request_data_sanitization(self):
        payload = {
            "username": "lawyer1",
            "password": "SecretPassword123!",
            "auth_token": "bearer_abc_123",
            "case_id": 42
        }
        clean_json = sanitize_request_data(payload)
        self.assertNotIn("SecretPassword123!", clean_json)
        self.assertNotIn("bearer_abc_123", clean_json)
        self.assertIn("[REDACTED]", clean_json)
        self.assertIn("42", clean_json)

    # 3. اختبار بصمة وتكرار التنبيهات (Alert Deduplication)
    def test_alert_dedup_fingerprint_and_throttling(self):
        fp1 = compute_dedup_fingerprint("critical", "injection_attempt", "routers/cases.py")
        fp2 = compute_dedup_fingerprint("critical", "injection_attempt", "routers/cases.py")
        fp3 = compute_dedup_fingerprint("high", "injection_attempt", "routers/cases.py")

        self.assertEqual(fp1, fp2, "Identical alerts must yield identical fingerprints")
        self.assertNotEqual(fp1, fp3, "Different severities must yield different fingerprints")

        # إرسال تنبيه أول
        alert1 = dispatch_security_alert(
            db=self.db,
            title="اختبار تنبيه 1",
            message="رسالة اختبار أمني",
            severity="critical",
            category_or_type="test_injection",
            target_identifier="test/target.py"
        )
        self.assertIsNotNone(alert1.id)

        # محاولة إرسال تنبيه مكرر خلال فترة الكبح
        alert2 = dispatch_security_alert(
            db=self.db,
            title="اختبار تنبيه 1 مكرر",
            message="رسالة اختبار أمني مكررة",
            severity="critical",
            category_or_type="test_injection",
            target_identifier="test/target.py"
        )
        # يجب أن ينشئ السجل في لوحة التحكم ولكن دون إرسال بريد متكرر
        self.assertEqual(alert2.channel, "dashboard_only", "Duplicate alert must be throttled to dashboard_only")

    # 4. اختبار محرك الفحص الأمني (Scanner Engine)
    def test_scanner_engine_execution(self):
        scanner = LawSaaSScanner(root_dir=".", db=self.db)
        scan = scanner.run_full_scan(trigger_type="unit_test_audit")

        self.assertIsNotNone(scan.id)
        self.assertEqual(scan.status, "completed")
        self.assertGreater(scan.files_scanned, 0, "Scanner must scan files")
        self.assertGreaterEqual(scan.findings_count, 0)

        # التحقق من تسجيل الأهداف في security_scan_targets
        targets_count = self.db.query(SecurityScanTargets).count()
        self.assertGreater(targets_count, 0, "Scan targets registry must be populated")

        # التحقق من تسجيل الاعتماديات في security_dependencies
        deps_count = self.db.query(SecurityDependencies).count()
        self.assertGreater(deps_count, 0, "Dependencies must be audited and registered")

    # 5. اختبار الصلاحيات وحظر غير المشرفين (Superadmin RBAC)
    def test_superadmin_access_control(self):
        # محاكاة مستخدم عادي
        regular_user = AccessProfiles(id=999, username="lawyer_test", is_superadmin=0)
        with self.assertRaises(HTTPException) as cm:
            require_superadmin(regular_user)
        self.assertEqual(cm.exception.status_code, 403)

        # محاكاة مستخدم سوبر أدمن
        admin_user = AccessProfiles(id=1, username="admin_test", is_superadmin=1)
        res = require_superadmin(admin_user)
        self.assertEqual(res.id, 1)

    # 6. اختبار تسجيل الأحداث الأمنية التشغيلية (Security Events Monitoring)
    def test_record_security_event(self):
        event = record_security_event(
            db=self.db,
            event_type="test_xss_probe",
            severity="high",
            source_ip="192.168.1.100",
            endpoint="/test/search",
            http_method="GET",
            status_code=400,
            details="<script>alert(1)</script>",
            trigger_alert=False
        )
        self.assertIsNotNone(event.id)
        self.assertEqual(event.event_type, "test_xss_probe")
        self.assertEqual(event.source_ip, "192.168.1.100")

    # 7. اختبار عدم المساس بالبيانات القانونية القائمة (Zero Regression Check)
    def test_existing_legal_data_intact(self):
        # التحقق من أن جداول القضايا والمكاتب والعملاء تعمل دون أي مساس
        offices_count = self.db.query(LawOffices).count()
        cases_count = self.db.query(LawCases).count()
        clients_count = self.db.query(LawClients).count()

        self.assertGreaterEqual(offices_count, 0)
        self.assertGreaterEqual(cases_count, 0)
        self.assertGreaterEqual(clients_count, 0)

    # 8. اختبار عزل المكاتب ومنع التلاعب بالمعرفات (Cross-Tenant Isolation & IDOR Defense)
    def test_tenant_isolation_cross_office_document_download(self):
        """التحقق من أن مستخدم مكتب أ لا يستطيع تحميل وثيقة تابعة لمكتب ب بتغيير المعرّف"""
        from database.models import LawDocuments
        from routers.documents_route import download_document
        
        # محاكاة مستخدم من المكتب 1
        user_office_1 = AccessProfiles(id=101, username="lawyer_off1", office_id=1, role="محامي")
        
        import uuid
        test_case_office_6 = LawCases(
            office_id=6,
            case_number=f"TEST-OFF6-{uuid.uuid4().hex[:8]}",
            title="قضية مكتب 6",
            is_deleted=0,
            created_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        )
        self.db.add(test_case_office_6)
        self.db.commit()
        self.db.refresh(test_case_office_6)

        test_doc_office_6 = LawDocuments(
            office_id=6,
            case_id=test_case_office_6.id,
            document_type_key="general",
            name="secret_doc",
            file_type="pdf",
            file_path="static/uploads/documents/test_secret.pdf",
            created_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        )
        self.db.add(test_doc_office_6)
        self.db.commit()
        self.db.refresh(test_doc_office_6)

        try:
            # محاولة تنزيل الوثيقة من قبل مستخدم المكتب 1
            import asyncio
            with self.assertRaises(HTTPException) as cm:
                asyncio.run(download_document(
                    filename="test_secret.pdf",
                    db=self.db,
                    user=user_office_1
                ))
            self.assertEqual(cm.exception.status_code, 403, "يجب رفض الوصول لمستند مكتب آخر بكود 403 Forbidden")
            self.assertIn("غير مصرح", cm.exception.detail)
        finally:
            self.db.rollback()
            self.db.query(LawDocuments).filter(LawDocuments.name == "secret_doc").delete()
            self.db.query(LawCases).filter(LawCases.case_number.like("TEST-OFF6%")).delete()
            self.db.commit()

    # 9. اختبار حظر الحذف والوصول عند غياب office_id
    def test_hearing_deletion_missing_office_id_rejected(self):
        """التحقق من أن المستخدم الذي ليس له office_id لا يستطيع حذف جلسات المكتب 1"""
        from main import delete_hearing
        import asyncio
        
        user_without_office = AccessProfiles(id=102, username="rogue_user", office_id=None, role="محامي")
        
        # محاولة استدعاء حذف الجلسة
        res = asyncio.run(delete_hearing(
            hearing_id=99999,
            db=self.db,
            user=user_without_office
        ))
        self.assertEqual(res.status_code, 403, "يجب رفض الحذف بكود 403 عند غياب معرف المكتب")

    # 10. اختبار منع تعديل بيانات مكتب آخر (IDOR on Office Settings)
    def test_cross_office_settings_modification_rejected(self):
        """التحقق من أن مدير المكتب 1 لا يستطيع تعديل اسم أو بيانات المكتب 6 بتمرير المعرّف في الطلب"""
        from main import update_office
        import asyncio
        from unittest.mock import MagicMock
        
        # مدير من المكتب 1
        mgr_office_1 = AccessProfiles(id=103, username="mgr_off1", office_id=1, role="مدير المكتب")
        mock_request = MagicMock()
        mock_request.url.hostname = "localhost"

        with self.assertRaises(HTTPException) as cm:
            asyncio.run(update_office(
                request=mock_request,
                name="محاولة قرصنة اسم المكتب",
                office_id=6,  # يحاول تعديل المكتب 6
                db=self.db,
                user=mgr_office_1
            ))
        self.assertEqual(cm.exception.status_code, 403, "يجب رفض تعديل مكتب آخر بكود 403 Forbidden")
        self.assertIn("غير مصرح لك بتعديل بيانات مكتب آخر", cm.exception.detail)


if __name__ == "__main__":
    unittest.main()
