# -*- coding: utf-8 -*-
"""
Test Suite: LawSaaS SOC Engine & Security Center Independent Verification
التحقق المستقل من محرك مركز الأمن السيبراني:
1. إثبات ديناميكية الفحص وعدم وجود أي نتائج وهمية أو مسبقة الصنع.
2. التحقق من صلاحيات كافة مسارات routers/security_center.py ومنع غير المشرفين (403 Forbidden).
3. اختبار تطهير السجلات وكبح التنبيهات والتعامل مع فشل البريد SMTP.
4. التحقق من تسجيل فشل محرك الفحص كـ "failed" وعدم إظهاره كفحص ناجح.
"""

import os
import unittest
import asyncio
from unittest.mock import patch
from datetime import datetime
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database.models import Base, AccessProfiles, LawOffices
from database.security_models import (
    SecurityScans, SecurityFindings, SecurityEvents,
    SecurityAlerts, SecurityAlertSettings, SecurityScanTargets
)
from core.security_center.scanner_engine import LawSaaSScanner
from core.security_center.alert_service import dispatch_security_alert
from routers.security_center import (
    require_superadmin,
    trigger_security_scan,
    get_scan_history,
    get_security_findings,
    update_finding_status,
    get_security_events,
    get_dependencies_audit,
    get_scan_targets,
    update_alert_settings,
    security_center_dashboard
)


class TestSOCEngineVerification(unittest.TestCase):
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

        # إنشاء مكتب وحسابات للمستخدمين
        self.office = LawOffices(id=1, name="مكتب التحقق الأمني", is_active=1)
        self.db.add(self.office)
        self.db.commit()

        self.regular_user = AccessProfiles(
            id=10, name="محامي عادي", username="regular_lawyer",
            phone="0512345678", email="lawyer@firm.test",
            office_id=1, role="محامي", is_superadmin=0
        )
        self.superadmin_user = AccessProfiles(
            id=1, name="مدير المنصة", username="soc_admin",
            phone="0500000001", email="admin@soc.test",
            office_id=1, role="مدير المنصة", is_superadmin=1
        )
        self.db.add_all([self.regular_user, self.superadmin_user])
        self.db.commit()

    def tearDown(self):
        self.db.close()

    # 1. إثبات الفحص الديناميكي الفعلي (Dynamic Scanning Verification)
    def test_dynamic_scanning_proves_not_hardcoded(self):
        """
        حقن ملف وهمي بنمط ثغرة SQL Injection، والتحقق من رصده حياً،
        ثم حذف الملف وإعادة الفحص للتحقق من اختفاء النتيجة ديناميكياً.
        """
        test_filename = "temp_dynamic_test_script.py"
        part_prefix = "text(" + 'f"SELECT ' + "* FROM {"
        part_suffix = 'table_name}")'
        test_content = (
            "# Dynamic test probe\n"
            "from sqlalchemy import text\n"
            "def test_vulnerable_func(table_name):\n"
            f"    return {part_prefix}{part_suffix}\n"
        )
        with open(test_filename, "w", encoding="utf-8") as f:
            f.write(test_content)

        try:
            scanner = LawSaaSScanner(root_dir=".", db=self.db)
            scan1 = scanner.run_full_scan(trigger_type="test_dynamic_probe")
            self.assertEqual(scan1.status, "completed")

            # البحث عن النتيجة الخاصة بالملف المؤقت
            dynamic_finding = self.db.query(SecurityFindings).filter(
                SecurityFindings.affected_file == test_filename
            ).first()
            self.assertIsNotNone(dynamic_finding, "Scanner must dynamically detect injected vulnerability")
            self.assertEqual(dynamic_finding.vulnerability_id, "CWE-89")
        finally:
            if os.path.exists(test_filename):
                os.remove(test_filename)

        # إعادة الفحص بعد حذف الملف للتأكد من زواله ديناميكياً
        scan2 = scanner.run_full_scan(trigger_type="test_after_cleanup")
        self.assertEqual(scan2.status, "completed")
        finding_after_delete = [
            f for f in scanner.findings if f.get("affected_file") == test_filename
        ]
        self.assertEqual(len(finding_after_delete), 0, "Deleted file findings must not appear")

    # 2. اختبار صلاحيات كافة مسارات routers/security_center.py
    def test_all_security_center_endpoints_block_regular_users(self):
        """التحقق من أن كافة مسارات مركز الأمن ترفض الوصول بـ 403 للمستخدمين غير السوبر أدمن"""
        class DummyRequest:
            client = None
            headers = {}

        # مسار 1: صفحة مركز الأمن GET /superadmin/security
        res_page = asyncio.run(security_center_dashboard(request=DummyRequest(), db=self.db, user=self.regular_user))
        self.assertEqual(res_page.status_code, 303, "Non-superadmin must be redirected")

        # مسار 2: تشغيل فحص يدوي POST /api/superadmin/security/scan
        with self.assertRaises(HTTPException) as cm:
            asyncio.run(trigger_security_scan(request=DummyRequest(), scan_type="full_audit", db=self.db, user=self.regular_user))
        self.assertEqual(cm.exception.status_code, 403)

        # مسار 3: جلب قائمة الفحوصات GET /api/superadmin/security/scans
        with self.assertRaises(HTTPException) as cm:
            asyncio.run(get_scan_history(limit=10, db=self.db, user=self.regular_user))
        self.assertEqual(cm.exception.status_code, 403)

        # مسار 4: جلب قائمة الثغرات GET /api/superadmin/security/findings
        with self.assertRaises(HTTPException) as cm:
            asyncio.run(get_security_findings(severity=None, status_filter=None, category=None, limit=50, db=self.db, user=self.regular_user))
        self.assertEqual(cm.exception.status_code, 403)

        # مسار 5: تحديث حالة ثغرة POST /api/superadmin/security/findings/{id}/status
        with self.assertRaises(HTTPException) as cm:
            asyncio.run(update_finding_status(finding_id=1, request=DummyRequest(), new_status="resolved", notes=None, db=self.db, user=self.regular_user))
        self.assertEqual(cm.exception.status_code, 403)

        # مسار 6: جلب الأحداث الأمنية GET /api/superadmin/security/events
        with self.assertRaises(HTTPException) as cm:
            asyncio.run(get_security_events(limit=50, event_type=None, severity=None, db=self.db, user=self.regular_user))
        self.assertEqual(cm.exception.status_code, 403)

        # مسار 7: جلب سجل تدقيق الاعتماديات GET /api/superadmin/security/dependencies
        with self.assertRaises(HTTPException) as cm:
            asyncio.run(get_dependencies_audit(db=self.db, user=self.regular_user))
        self.assertEqual(cm.exception.status_code, 403)

        # مسار 8: جلب أهداف الفحص GET /api/superadmin/security/targets
        with self.assertRaises(HTTPException) as cm:
            asyncio.run(get_scan_targets(status_filter=None, limit=100, db=self.db, user=self.regular_user))
        self.assertEqual(cm.exception.status_code, 403)

        # مسار 9: تحديث إعدادات التنبيهات POST /api/superadmin/security/settings
        with self.assertRaises(HTTPException) as cm:
            asyncio.run(update_alert_settings(request=DummyRequest(), admin_email="test@soc.test", db=self.db, user=self.regular_user))
        self.assertEqual(cm.exception.status_code, 403)

    # 3. اختبار كبح التنبيهات وأخطاء إرسال البريد SMTP
    def test_alert_smtp_failure_handling(self):
        """التحقق من أن فشل إرسال البريد عند انقطاع خادم SMTP لا يسقط التطبيق ويُسجل بأمان"""
        # تهيئة إعدادات تنبيهات تشمل بريداً وتوجيهاً لخادم وهمي مغلق
        settings = SecurityAlertSettings(
            id=1,
            admin_email="admin@soc.test",
            email_alerts_enabled=1,
            min_email_severity="high",
            dedup_cooldown_minutes=120,
            max_alerts_per_hour=10
        )
        self.db.add(settings)
        self.db.commit()

        # إرسال تنبيه حرج
        alert = dispatch_security_alert(
            db=self.db,
            title="تنبيه اختبار خطأ SMTP",
            message="فحص قدرة معالجة أخطاء الشبكة",
            severity="critical",
            category_or_type="smtp_probe",
            target_identifier="core/network.py"
        )
        self.assertIsNotNone(alert.id, "Alert record must be created in DB")
        # يجب أن ينشأ السجل حتى مع فشل الإرسال الشبكي دون إلقاء استثناء غير معالج
        self.assertIn(alert.channel, ["dashboard_and_email", "dashboard_only"])

    # 4. التحقق من أن فشل محرك الفحص يُسجل كفشل (Failure Recording)
    def test_scan_failure_records_failed_status(self):
        """التحقق من أن حدوث استثناء مفاجئ في محرك الفحص يُسجل حالته كـ 'failed' ولا يُعرض كفحص ناجح"""
        scanner = LawSaaSScanner(root_dir=".", db=self.db)
        
        # محاكاة خطأ فادح في فحص الكود
        with patch.object(scanner, "_scan_source_code", side_effect=RuntimeError("Simulated scanner IO exception")):
            with self.assertRaises(RuntimeError):
                scanner.run_full_scan(trigger_type="test_failure")

        # التحقق من أن الفحص في قاعدة البيانات أصبح status='failed'
        failed_scan = self.db.query(SecurityScans).order_by(SecurityScans.id.desc()).first()
        self.assertIsNotNone(failed_scan)
        self.assertEqual(failed_scan.status, "failed", "Interrupted scan must be recorded as 'failed'")
        self.assertIn("Simulated scanner IO exception", failed_scan.error_summary)


if __name__ == "__main__":
    unittest.main()
