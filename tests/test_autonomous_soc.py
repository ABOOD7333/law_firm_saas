"""
Unit & Integration Tests — Autonomous Security Operations Center & Remediation
اختبارات المنظومة الذكية لمركز الأمن السيبراني والإصلاح التلقائي والدرع النشط
"""

import os
import unittest
from datetime import datetime
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database.models import Base, AccessProfiles
from database.security_models import SecurityFindings, SecurityScans, SecurityAuditLogs, SecurityEvents
from core.security_center.remediation_engine import AutoRemediationEngine
from core.security_center.monitor_middleware import (
    _banned_ips, _ip_strikes, _failed_login_attempts,
    is_ip_banned, auto_ban_ip, unban_ip, get_active_defense_status
)
from main import app


class TestAutonomousSOC(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(cls.engine)
        cls.Session = sessionmaker(bind=cls.engine)
        cls.client = TestClient(app)

    def setUp(self):
        self.db = self.Session()
        # Reset memory state
        _banned_ips.clear()
        _ip_strikes.clear()
        _failed_login_attempts.clear()

    def tearDown(self):
        self.db.rollback()
        self.db.close()

    def test_remediation_engine_can_remediate(self):
        """التحقق من قدرة محرك الإصلاح على تحديد الملاحظات القابلة للعلاج"""
        engine = AutoRemediationEngine()

        # 1. Dependency update
        finding_dep = SecurityFindings(
            category="outdated_dep",
            title="مكتبة قديمة",
            affected_file="requirements.txt"
        )
        can_fix, fix_type = engine.can_remediate(finding_dep)
        self.assertTrue(can_fix)
        self.assertEqual(fix_type, "dependency_update")

        # 2. Add office index
        finding_idx = SecurityFindings(
            category="data_integrity",
            title="جداول تفتقر لفهرس office_id",
            affected_file="database/models.py"
        )
        can_fix, fix_type = engine.can_remediate(finding_idx)
        self.assertTrue(can_fix)
        self.assertEqual(fix_type, "add_office_index")

        # 3. Sanitize template
        finding_xss = SecurityFindings(
            category="xss",
            title="فلتر غير آمن",
            affected_file="templates/pleadings_print.html"
        )
        can_fix, fix_type = engine.can_remediate(finding_xss)
        self.assertTrue(can_fix)
        self.assertEqual(fix_type, "sanitize_template_safe")

        # 4. Unknown finding requires manual review
        finding_unknown = SecurityFindings(
            category="unknown_logic",
            title="منطق أعمال غير معتاد",
            affected_file="custom_logic.py"
        )
        can_fix, fix_type = engine.can_remediate(finding_unknown)
        self.assertFalse(can_fix)
        self.assertEqual(fix_type, "manual_review_required")

    def test_active_ips_auto_ban_and_unban(self):
        """التحقق من عمل نظام الحظر التلقائي وفك الحظر (IPS Auto-Ban & Unban)"""
        test_ip = "192.168.1.105"

        # في البداية ليس محظوراً
        is_banned, _, _ = is_ip_banned(test_ip)
        self.assertFalse(is_banned)

        # حظر العنوان
        auto_ban_ip(test_ip, minutes=30, reason="Test Malicious Scan", db=None)

        # التحقق من أن العنوان محظور الآن
        is_banned, reason, remaining = is_ip_banned(test_ip)
        self.assertTrue(is_banned)
        self.assertEqual(reason, "Test Malicious Scan")
        self.assertGreaterEqual(remaining, 1)

        # فحص تقرير الحالة الحية
        status = get_active_defense_status()
        self.assertEqual(status["shield_status"], "ACTIVE_DEFENSE_ONLINE")
        self.assertGreaterEqual(status["currently_banned_count"], 1)

        # فك الحظر يدوياً
        success = unban_ip(test_ip)
        self.assertTrue(success)
        is_banned, _, _ = is_ip_banned(test_ip)
        self.assertFalse(is_banned)

    def test_middleware_blocks_malicious_user_agent(self):
        """التحقق من اعتراض وحظر أدوات الفحص التلقائية المشبوهة (مثل sqlmap و nikto)"""
        response = self.client.get(
            "/",
            headers={"User-Agent": "sqlmap/1.6.4#stable (https://sqlmap.org)"}
        )
        # يجب أن يرد بحظر فوري 403
        self.assertEqual(response.status_code, 403)
        data = response.json()
        self.assertIn("Malicious scanner probe detected", data.get("detail", ""))

    def test_middleware_blocks_sql_injection_payload(self):
        """التحقق من اعتراض وحظر محاولات حقن SQL تلقائياً"""
        response = self.client.get("/?search=' UNION SELECT 1,2,3--")
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertIn("Security violation detected", data.get("detail", ""))

    def test_middleware_blocks_path_traversal_payload(self):
        """التحقق من اعتراض محاولات تجاوز المسارات Path Traversal"""
        response = self.client.get("/static/../../etc/passwd")
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertIn("Security violation detected", data.get("detail", ""))


if __name__ == "__main__":
    unittest.main()
