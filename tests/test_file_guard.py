"""
Unit Tests for Advanced File & Document Exploit Scanner
اختبارات فحص الملفات ومنع المستندات الملغومة وثغرات الـ PDF والماكرو
"""

import unittest
import io
import zipfile
from database.database import SessionLocal
from database.security_models import SecurityEvents
from core.security_center.file_scanner import scan_uploaded_file


class TestFileExploitScanner(unittest.TestCase):
    def setUp(self):
        self.db = SessionLocal()

    def tearDown(self):
        self.db.close()

    def test_clean_pdf_allowed(self):
        """اختبار قبول ملف PDF سليم وطبيعي"""
        clean_pdf = b"%PDF-1.4\n1 0 obj\n<< /Title (Legal Contract 2026) >>\nendobj\ntrailer\n<< /Root 1 0 R >>\n%%EOF"
        is_safe, msg = scan_uploaded_file(clean_pdf, "contract.pdf", db=self.db)
        self.assertTrue(is_safe, f"Clean PDF should pass: {msg}")

    def test_pdf_launch_exploit_blocked(self):
        """اختبار حظر ملف PDF يحوي أمر تشغيل خارجي خبيث (/Launch)"""
        malicious_pdf = b"%PDF-1.4\n1 0 obj\n<< /Type /Action /S /Launch /F (powershell.exe -enc ...) >>\nendobj\n%%EOF"
        is_safe, msg = scan_uploaded_file(malicious_pdf, "court_order.pdf", db=self.db, client_ip="192.168.1.50")
        self.assertFalse(is_safe)
        self.assertIn("/Launch", msg)

        # التحقق من تسجيل الحدث الأمني في مركز العمليات
        event = self.db.query(SecurityEvents).filter(
            SecurityEvents.event_type == "malicious_file_blocked",
            SecurityEvents.source_ip == "192.168.1.50"
        ).first()
        self.assertIsNotNone(event)
        self.assertIn("/Launch", event.details)

        # تنظيف
        self.db.delete(event)
        self.db.commit()

    def test_pdf_embedded_js_eval_blocked(self):
        """اختبار حظر ملف PDF يحوي كود جافاسكريبت تنفيذي مشبوه"""
        malicious_pdf = b"%PDF-1.4\n<< /JavaScript << /JS (eval(unescape('...'))) >> >>\n%%EOF"
        is_safe, msg = scan_uploaded_file(malicious_pdf, "pleading.pdf", db=self.db)
        self.assertFalse(is_safe)
        self.assertIn("جافاسكريبت", msg)

    def test_clean_docx_allowed(self):
        """اختبار قبول ملف DOCX سليم خالي من الماكرو"""
        bio = io.BytesIO()
        with zipfile.ZipFile(bio, "w") as zf:
            zf.writestr("word/document.xml", "<w:document><w:body><w:p><w:t>عقد اتفاق قانوني</w:t></w:p></w:body></w:document>")
        content = bio.getvalue()

        is_safe, msg = scan_uploaded_file(content, "agreement.docx", db=self.db)
        self.assertTrue(is_safe, f"Clean DOCX should pass: {msg}")

    def test_docx_vba_macro_blocked(self):
        """اختبار حظر مستند Word يحوي شفرة ماكرو VBA خبيثة"""
        bio = io.BytesIO()
        with zipfile.ZipFile(bio, "w") as zf:
            zf.writestr("word/document.xml", "<w:document></w:document>")
            zf.writestr("word/vbaProject.bin", b"DANGEROUS_VBA_MACRO_PAYLOAD")
        content = bio.getvalue()

        is_safe, msg = scan_uploaded_file(content, "invoice_macro.docx", db=self.db)
        self.assertFalse(is_safe)
        self.assertIn("ماكرو", msg)

    def test_double_extension_blocked(self):
        """اختبار حظر محاولات الخداع بالامتدادات المزدوجة"""
        fake_content = b"%PDF-1.4\nClean looking content\n%%EOF"
        is_safe, msg = scan_uploaded_file(fake_content, "contract.pdf.exe", db=self.db)
        self.assertFalse(is_safe)
        self.assertIn("تنفيذي", msg)

    def test_mismatched_magic_bytes_blocked(self):
        """اختبار كشف التلاعب عند تغيير امتداد ملف تنفيذي إلى .pdf"""
        fake_pdf = b"MZ\x90\x00\x03\x00\x00\x00" # Windows PE executable magic bytes
        is_safe, msg = scan_uploaded_file(fake_pdf, "deed.pdf", db=self.db)
        self.assertFalse(is_safe)
        self.assertIn("بصمته", msg)


if __name__ == "__main__":
    unittest.main()
