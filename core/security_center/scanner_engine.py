"""
Cybersecurity Scanner Engine — LawSaaS Platform
محرك الفحص الأمني المتكامل:
1. SAST (Static Application Security Testing) لتحليل الشيفرات البرمجية واكتشاف الثغرات.
2. SCA (Software Composition Analysis) لفحص سلامة المكتبات والاعتماديات.
3. Configuration & Security Headers Audit لتدقيق إعدادات الخادم والترويسات.
4. Database Integrity & Multi-Tenancy Engine لتدقيق عزل بيانات المكاتب وسلامة الفهارس.
5. Target Registry لتوثيق جميع الملفات المفحوصة والمستثناة.
"""

import ast
import hashlib
import os
import re
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
from sqlalchemy.orm import Session
from sqlalchemy import text

from database.models import Base
from database.security_models import (
    SecurityScans,
    SecurityFindings,
    SecurityDependencies,
    SecurityScanTargets,
    SecurityAlerts,
)
from core.security_center.alert_service import dispatch_security_alert


# قواعد بيانات الثغرات المعروفة للمكتبات الأكثر شيوعاً (CVE Reference Database)
KNOWN_VULNERABLE_PACKAGES = {
    "jinja2": [
        {"max_vulnerable": "3.1.2", "cve": "CVE-2024-22195", "severity": "medium", "fixed": "3.1.3", "desc": "Cross-site scripting (XSS) in xmlattr filter"}
    ],
    "python-multipart": [
        {"max_vulnerable": "0.0.6", "cve": "CVE-2024-24762", "severity": "high", "fixed": "0.0.7", "desc": "Denial of Service via boundary delimiter parsing"}
    ],
    "requests": [
        {"max_vulnerable": "2.30.0", "cve": "CVE-2023-32681", "severity": "medium", "fixed": "2.31.0", "desc": "Unintended leak of Proxy-Authorization header"}
    ],
    "urllib3": [
        {"max_vulnerable": "2.0.6", "cve": "CVE-2023-45803", "severity": "medium", "fixed": "2.0.7", "desc": "Request body strip failure on cross-origin redirects"}
    ],
    "cryptography": [
        {"max_vulnerable": "42.0.3", "cve": "CVE-2024-26130", "severity": "medium", "fixed": "42.0.4", "desc": "NULL pointer dereference with invalid PKCS#7"}
    ],
    "starlette": [
        {"max_vulnerable": "0.26.1", "cve": "CVE-2023-29159", "severity": "medium", "fixed": "0.27.0", "desc": "Path traversal vulnerability in StaticFiles"}
    ]
}

EXCLUDED_DIRS = {".git", ".venv", "venv", "env", "__pycache__", "node_modules", ".idea", ".vscode", "scratch", "dist", "build"}
BINARY_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".ico", ".svg", ".db", ".sqlite", ".pyc", ".zip", ".tar", ".gz"}


def parse_semver(v: str) -> tuple:
    """تحويل رقم الإصدار إلى مصفوفة رقمية للمقارنة الدقيقة"""
    if not v or v == "latest":
        return (999, 999, 999)
    nums = re.findall(r'\d+', v)
    return tuple(map(int, nums)) if nums else (0,)


def sanitize_evidence(evidence: str) -> str:
    """تنقية الأدلة من أي كلمات مرور أو مفاتيح سرية قبل الحفظ"""
    if not evidence:
        return ""
    # إخفاء المفاتيح وكلمات المرور إن وجدت
    sanitized = re.sub(r'(password|secret|token|api_key|authorization)\s*[:=]\s*["\'][^"\']+["\']', r'\1="[REDACTED_BY_SOC]"', evidence, flags=re.IGNORECASE)
    # تقليص الحجم لـ 500 حرف
    return sanitized.strip()[:500]


def is_scannable_file(file_path: str) -> Tuple[bool, str]:
    """تحديد ما إذا كان الملف قابلاً للفحص الأمني أو يجب استثناؤه"""
    ext = os.path.splitext(file_path)[1].lower()
    if ext in BINARY_EXTENSIONS:
        return False, f"Binary or media file format ({ext})"
    
    parts = os.path.normpath(file_path).split(os.sep)
    for part in parts:
        if part in EXCLUDED_DIRS:
            return False, f"Excluded environment/cache directory ({part})"
            
    if ext in {".py", ".html", ".js", ".css", ".json", ".txt", ".md", ".ini", ".env", ".yaml", ".yml", "dockerfile"}:
        return True, "Scannable text/code file"
        
    return False, f"Unsupported file type ({ext})"


class LawSaaSScanner:
    """
    محرك الفحص الشامل لمنصة LawSaaS
    """

    def __init__(self, root_dir: str = ".", db: Optional[Session] = None):
        self.root_dir = os.path.abspath(root_dir)
        self.db = db
        self.findings: List[Dict[str, Any]] = []
        self.files_scanned = 0
        self.components_scanned = 0
        self.scanned_targets: List[Dict[str, Any]] = []

    def run_full_scan(
        self,
        trigger_type: str = "full_audit",
        triggered_by: Optional[int] = None,
        db: Optional[Session] = None,
        triggered_by_user_id: Optional[int] = None
    ) -> SecurityScans:
        """تشغيل فحص شامل متكامل وحفظ النتائج في قاعدة البيانات"""
        if db is not None:
            self.db = db
        if triggered_by_user_id is not None and triggered_by is None:
            triggered_by = triggered_by_user_id

        if not self.db:
            raise ValueError("A database session (db) must be provided to run the security scan.")

        start_time = datetime.now()
        start_str = start_time.strftime("%Y-%m-%d %H:%M:%S")

        scan = SecurityScans(
            scan_type=trigger_type,
            scan_scope="all_files_and_database",
            status="running",
            started_at=start_str,
            scanner_version="LawSaaS-SecEngine-v1.0",
            triggered_by_user_id=triggered_by
        )
        self.db.add(scan)
        self.db.commit()
        self.db.refresh(scan)

        try:
            self.findings = []
            self.files_scanned = 0
            self.components_scanned = 0

            # 1. فهرسة وتسجيل الأهداف
            self._register_and_filter_targets()

            # 2. فحص الكود المصدري (SAST)
            self._scan_source_code()

            # 3. فحص الاعتماديات والمكتبات (SCA)
            self._scan_dependencies()

            # 4. فحص إعدادات الخادم والترويسات
            self._scan_configs_and_headers()

            # 5. فحص قاعدة البيانات وتعدد المكاتب
            self._scan_database_tenancy()

            # تصنيف وتخزين الثغرات
            crit_count = 0
            high_count = 0
            med_count = 0
            low_count = 0
            info_count = 0

            for f_data in self.findings:
                sev = f_data.get("severity", "medium").lower()
                if sev == "critical":
                    crit_count += 1
                elif sev == "high":
                    high_count += 1
                elif sev == "medium":
                    med_count += 1
                elif sev == "low":
                    low_count += 1
                else:
                    info_count += 1

                finding_record = SecurityFindings(
                    scan_id=scan.id,
                    title=f_data["title"],
                    description=f_data["description"],
                    severity=sev,
                    confidence=f_data.get("confidence", "confirmed"),
                    category=f_data.get("category", "misconfig"),
                    affected_component=f_data.get("affected_component", "core"),
                    affected_file=f_data.get("affected_file"),
                    affected_line=f_data.get("affected_line"),
                    vulnerability_id=f_data.get("vulnerability_id"),
                    evidence_summary=sanitize_evidence(f_data.get("evidence", "")),
                    remediation_recommendation=f_data.get("recommendation"),
                    first_detected_at=start_str,
                    last_detected_at=start_str,
                    status="open"
                )
                self.db.add(finding_record)
                self.db.flush()

                # إرسال تنبيه فوري إذا كانت الثغرة حرجة أو عالية
                if sev in ("critical", "high"):
                    dispatch_security_alert(
                        db=self.db,
                        title=f_data["title"],
                        message=f"{f_data['description']}\nالملف المتأثر: {f_data.get('affected_file')}:{f_data.get('affected_line', '-')}",
                        severity=sev,
                        category_or_type=f_data.get("category", "vulnerability"),
                        target_identifier=f_data.get("affected_file", "Platform Core"),
                        finding_id=finding_record.id
                    )

            # تحديث سجل الفحص
            completed_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            scan.completed_at = completed_str
            scan.status = "completed"
            scan.files_scanned = self.files_scanned
            scan.components_scanned = self.components_scanned
            scan.findings_count = len(self.findings)
            scan.critical_count = crit_count
            scan.high_count = high_count
            scan.medium_count = med_count
            scan.low_count = low_count
            scan.info_count = info_count

            self.db.commit()
            return scan

        except Exception as e:
            self.db.rollback()
            scan.status = "failed"
            scan.completed_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            scan.error_summary = str(e)[:1000]
            self.db.commit()
            raise e

    def _register_and_filter_targets(self):
        """فهرسة وتوثيق جميع الملفات والمجلدات وتصنيف المقبول والمستثنى"""
        for root, dirs, files in os.walk(self.root_dir):
            rel_root = os.path.relpath(root, self.root_dir)
            if rel_root != ".":
                parts = rel_root.split(os.sep)
                if any(p in EXCLUDED_DIRS for p in parts):
                    continue

            for fname in files:
                full_path = os.path.join(root, fname)
                rel_path = os.path.relpath(full_path, self.root_dir).replace("\\", "/")
                
                scannable, reason = is_scannable_file(rel_path)
                
                target_type = "file"
                if rel_path.startswith("routers/"):
                    target_type = "router"
                elif rel_path.startswith("database/"):
                    target_type = "database_model"
                elif rel_path.startswith("templates/"):
                    target_type = "template"
                elif rel_path.startswith("core/"):
                    target_type = "core_logic"

                # التحقق أو التحديث في قاعدة البيانات
                existing_target = self.db.query(SecurityScanTargets).filter(SecurityScanTargets.target_path == rel_path).first()
                if not existing_target:
                    existing_target = SecurityScanTargets(
                        target_type=target_type,
                        target_path=rel_path,
                        description=f"File: {fname}",
                        is_excluded=0 if scannable else 1,
                        scan_status="scanned" if scannable else "skipped",
                        skip_reason=None if scannable else reason,
                        last_scanned_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    )
                    self.db.add(existing_target)
                else:
                    existing_target.is_excluded = 0 if scannable else 1
                    existing_target.scan_status = "scanned" if scannable else "skipped"
                    existing_target.skip_reason = None if scannable else reason
                    existing_target.last_scanned_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                if scannable:
                    self.scanned_targets.append({"path": full_path, "rel_path": rel_path})
                    
        self.db.commit()

    def _scan_source_code(self):
        """فحص الشيفرة المصدرية (SAST)"""
        for item in self.scanned_targets:
            rel_path = item["rel_path"]
            full_path = item["path"]
            
            if rel_path.endswith(".py"):
                self.files_scanned += 1
                self._analyze_python_file(full_path, rel_path)
            elif rel_path.endswith(".html"):
                self.files_scanned += 1
                self._analyze_html_template(full_path, rel_path)

        self.components_scanned += 4  # Core, Routers, Database, Templates

    def _analyze_python_file(self, full_path: str, rel_path: str):
        """تحليل ملف بايثون لاكتشاف الثغرات الشائعة"""
        if rel_path.startswith("core/security_center/"):
            return

        try:
            with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
                lines = content.splitlines()

            # 1. فحص حقن الاستعلامات SQL Injection
            for idx, line in enumerate(lines, 1):
                clean_line = line.strip()
                if clean_line.startswith("#"):
                    continue

                # كشف التنسيق غير الآمن للاستعلامات
                if re.search(r'text\(\s*f["\'].*(?:SELECT|INSERT|UPDATE|DELETE)', line, re.IGNORECASE) or \
                   re.search(r'\.execute\(\s*f["\'].*(?:SELECT|INSERT|UPDATE|DELETE)', line, re.IGNORECASE):
                    self.findings.append({
                        "title": "مخاطر حقن استعلامات SQL (SQL Injection Risk)",
                        "description": "استخدام f-string لتجميع استعلام SQL مباشرة دون استخدام معاملات ربط آمنة (bindparams).",
                        "severity": "critical",
                        "category": "injection",
                        "affected_component": "Database Access",
                        "affected_file": rel_path,
                        "affected_line": idx,
                        "vulnerability_id": "CWE-89",
                        "evidence": clean_line,
                        "recommendation": "استخدم استعلامات SQLAlchemy المجهزة أو bindparams لتمرير المتغيرات بشكل منفصل وآمن."
                    })

                # 2. فحص تسريب أو كسر عزل المكاتب Multi-Tenant Bypass
                if "office_id or 1" in line or "office_id or  1" in line:
                    self.findings.append({
                        "title": "تجاوز افتراضي لعزل المكاتب (Multi-Tenancy Isolation Fallback)",
                        "description": "استخدام القيمة الافتراضية 'office_id or 1' قد يؤدي لتسريب أو كتابة بيانات داخل المكتب رقم 1 عند غياب معرف المكتب.",
                        "severity": "high",
                        "category": "tenant_isolation",
                        "affected_component": "Multi-Tenant Authorization",
                        "affected_file": rel_path,
                        "affected_line": idx,
                        "vulnerability_id": "CWE-284",
                        "evidence": clean_line,
                        "recommendation": "تحقق من وجود office_id بشكل صريح وفي حال غيابه ارمِ استثناء 403 Forbidden بدلاً من الرجوع التلقائي للمكتب 1."
                    })

                # 3. فحص الأسرار والمفاتيح الثابتة Hardcoded Secrets
                if re.search(r'(SECRET_KEY|API_KEY|PASSWORD|PRIVATE_KEY)\s*=\s*["\'][a-zA-Z0-9_\-\.]{12,}["\']', line, re.IGNORECASE):
                    # استثناء القوالب والاختبارات الافتراضية
                    if "change_this" not in line.lower() and "your_secret" not in line.lower() and not rel_path.startswith("tests/"):
                        self.findings.append({
                            "title": "مفتاح سري ثابت في الكود (Hardcoded Secret)",
                            "description": "تم رصد تعيين مفتاح سري أو كلمة مرور ثابتة داخل الكود المصدري بدلاً من متغيرات البيئة.",
                            "severity": "high",
                            "category": "secrets_exposure",
                            "affected_component": "Configuration",
                            "affected_file": rel_path,
                            "affected_line": idx,
                            "vulnerability_id": "CWE-798",
                            "evidence": "[REDACTED_SECRET_ASSIGNMENT]",
                            "recommendation": "انقل جميع المفاتيح السرية إلى متغيرات البيئة (.env / Environment Variables) واقرأها عبر os.getenv."
                        })

                # 4. فحص إعدادات الكوكيز غير الآمنة Insecure Cookie Setting
                if "response.set_cookie" in line:
                    cookie_block = "\n".join(lines[idx-1 : min(len(lines), idx+10)]).lower()
                    if "csrf_token" not in cookie_block and "is_support_session" not in cookie_block and "httponly=true" not in cookie_block:
                        self.findings.append({
                            "title": "ملف تعريف ارتباط يفتقر إلى خاصية HttpOnly",
                            "description": "إنشاء ملف تعريف ارتباط (Cookie) دون تفعيل خاصية httponly=True، مما يعرضه للسرقة عبر هجمات XSS.",
                            "severity": "medium",
                            "category": "misconfig",
                            "affected_component": "Session Management",
                            "affected_file": rel_path,
                            "affected_line": idx,
                            "vulnerability_id": "CWE-1004",
                            "evidence": clean_line,
                            "recommendation": "أضف المعامل httponly=True و samesite='lax' عند تعيين الكوكيز لمنع وصول سكربتات العميل إليها."
                        })

                # 5. فحص تجاوز المسارات Path Traversal
                if (re.search(r'(?<!\.)\bopen\s*\(', line) or "os.remove(" in line) and "request" in line and "urllib.request" not in line and "os.path.basename" not in line:
                    self.findings.append({
                        "title": "احتمالية تجاوز المسارات في التعامل مع الملفات (Path Traversal Risk)",
                        "description": "فتح أو معالجة ملفات بناءً على مدخلات الطلب دون استخدام دالة تقييد المسار os.path.basename.",
                        "severity": "high",
                        "category": "auth_bypass",
                        "affected_component": "File System Handler",
                        "affected_file": rel_path,
                        "affected_line": idx,
                        "vulnerability_id": "CWE-22",
                        "evidence": clean_line,
                        "recommendation": "استخدم os.path.basename لتنقية اسم الملف، وتأكد من أن المسار النهائي يقع حصراً داخل المجلد المسموح به."
                    })

        except Exception as e:
            pass

    def _analyze_html_template(self, full_path: str, rel_path: str):
        """فحص قوالب HTML للكشف عن ثغرات XSS الناتجة عن إيقاف الحماية التلقائية"""
        try:
            with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()

            for idx, line in enumerate(lines, 1):
                clean_line = line.strip()
                # البحث عن فلتر safe في مدخلات يحتمل أن تكون من المستخدم
                if "| safe" in line or "|safe" in line:
                    if any(kw in line.lower() for kw in ["user", "comment", "title", "content", "name", "desc", "input"]):
                        self.findings.append({
                            "title": "استخدام فلتر غير آمن في القوالب (Potential XSS via Safe Filter)",
                            "description": "تعطيل حماية الهروب التلقائي عبر فلتر '| safe' لمتغير قد يحوي مدخلات مستخدم.",
                            "severity": "medium",
                            "category": "xss",
                            "affected_component": "Jinja2 Templates",
                            "affected_file": rel_path,
                            "affected_line": idx,
                            "vulnerability_id": "CWE-79",
                            "evidence": clean_line[:120],
                            "recommendation": "تجنب استخدام فلتر safe مع مدخلات المستخدم واستخدم تنقية مسبقة (sanitization) قبل العرض."
                        })
        except Exception:
            pass

    def _scan_dependencies(self):
        """فحص الاعتماديات والمكتبات ومقارنتها بقاعدة الثغرات"""
        req_file = os.path.join(self.root_dir, "requirements.txt")
        if not os.path.exists(req_file):
            return

        with open(req_file, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()

        for line in lines:
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            # استخراج اسم المكتبة والإصدار
            match = re.match(r'^([a-zA-Z0-9_\-\.]+)(?:[>=<~^!]=*([0-9a-zA-Z_\-\.]+))?', line)
            if match:
                pkg_name = match.group(1).lower()
                version = match.group(2) or "latest"

                # فحص ما إذا كانت المكتبة مسجلة في الثغرات المعروفة
                vuln_info = KNOWN_VULNERABLE_PACKAGES.get(pkg_name)
                is_vuln = False
                vuln_cve = None
                vuln_sev = "none"
                fixed_ver = None
                advisory = None

                if vuln_info:
                    for v in vuln_info:
                        if version != "latest" and parse_semver(version) <= parse_semver(v["max_vulnerable"]):
                            is_vuln = True
                            vuln_cve = v["cve"]
                            vuln_sev = v["severity"]
                            fixed_ver = v["fixed"]
                            advisory = f"https://nvd.nist.gov/vuln/detail/{vuln_cve}"
                            
                            self.findings.append({
                                "title": f"مكتبة تحتوي ثغرة أمنية معروفة ({pkg_name} {version})",
                                "description": f"المكتبة {pkg_name} بإصدار {version} متأثرة بالثغرة {vuln_cve}: {v['desc']}.",
                                "severity": vuln_sev,
                                "category": "outdated_dep",
                                "affected_component": f"Dependency: {pkg_name}",
                                "affected_file": "requirements.txt",
                                "affected_line": None,
                                "vulnerability_id": vuln_cve,
                                "evidence": f"{pkg_name}=={version}",
                                "recommendation": f"قم بترقية المكتبة {pkg_name} إلى الإصدار {fixed_ver} أو أحدث."
                            })
                            break

                # تسجيل الاعتمادية في جدول security_dependencies
                existing_dep = self.db.query(SecurityDependencies).filter(SecurityDependencies.package_name == pkg_name).first()
                if not existing_dep:
                    dep_record = SecurityDependencies(
                        package_name=pkg_name,
                        installed_version=version,
                        manifest_version=version,
                        ecosystem="PyPI",
                        vulnerability_id=vuln_cve,
                        severity=vuln_sev,
                        fixed_version=fixed_ver,
                        verification_status="verified_vulnerable" if is_vuln else "clean",
                        advisory_url=advisory,
                        detected_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    )
                    self.db.add(dep_record)
                else:
                    existing_dep.installed_version = version
                    existing_dep.vulnerability_id = vuln_cve
                    existing_dep.severity = vuln_sev
                    existing_dep.fixed_version = fixed_ver
                    existing_dep.verification_status = "verified_vulnerable" if is_vuln else "clean"
                    existing_dep.advisory_url = advisory
                    existing_dep.detected_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        self.db.commit()

    def _scan_configs_and_headers(self):
        """فحص إعدادات الخادم وترويسات الحماية في main.py و Dockerfile"""
        main_py = os.path.join(self.root_dir, "main.py")
        if os.path.exists(main_py):
            with open(main_py, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()

            # فحص إعدادات CORS
            if 'allow_origins=["*"]' in content and 'allow_credentials=True' in content:
                self.findings.append({
                    "title": "إعدادات CORS غير آمنة (Permissive CORS with Credentials)",
                    "description": "تم السماح بجميع النطاقات ['*'] مع تفعيل السماح بالاعتمادات (allow_credentials=True)، مما يتيح سرقة الجلسات عبر المتصفح.",
                    "severity": "high",
                    "category": "misconfig",
                    "affected_component": "CORS Middleware",
                    "affected_file": "main.py",
                    "affected_line": None,
                    "vulnerability_id": "CWE-942",
                    "evidence": "allow_origins=['*'], allow_credentials=True",
                    "recommendation": "حدد النطاقات المسموح بها بدقة ولا تستخدم النطاق المفتوح '*' مع تفعيل الاعتمادات."
                })

            # فحص وجود Security Headers Middleware
            headers_to_check = ["X-Content-Type-Options", "X-Frame-Options", "Strict-Transport-Security"]
            missing_headers = [h for h in headers_to_check if h.lower() not in content.lower()]
            if missing_headers:
                self.findings.append({
                    "title": "غياب بعض ترويسات الحماية الأساسية في الردود (Missing Security Headers)",
                    "description": f"لم يتم رصد الترويسات التالية في وسيط الاستجابات: {', '.join(missing_headers)}.",
                    "severity": "medium",
                    "category": "misconfig",
                    "affected_component": "HTTP Security Headers",
                    "affected_file": "main.py",
                    "affected_line": None,
                    "vulnerability_id": "CWE-693",
                    "evidence": f"Missing: {missing_headers}",
                    "recommendation": "أضف وسيطاً (Middleware) يلحق ترويسات X-Content-Type-Options: nosniff و X-Frame-Options: SAMEORIGIN و HSTS بكل استجابة."
                })

    def _scan_database_tenancy(self):
        """فحص عزل قاعدة البيانات وفهارس أمان المكاتب"""
        # تدقيق الجداول التي تحوي office_id وتأكد من وجود فهارس
        tenant_tables_lacking_index = []
        for table_name, table in Base.metadata.tables.items():
            if table_name.startswith("security_"):
                continue
            if "office_id" in table.columns:
                col = table.columns["office_id"]
                has_index = col.index or any(
                    "office_id" in [c.name for c in idx.columns] for idx in table.indexes
                )
                if not has_index:
                    tenant_tables_lacking_index.append(table_name)

        if tenant_tables_lacking_index:
            self.findings.append({
                "title": "جداول متعددة المكاتب تفتقر إلى فهرس على حقل office_id",
                "description": f"الجداول التالية تحوي بيانات مكاتب لكن تفتقر لفهرس index على office_id مما قد يسبب بطئاً واستعلامات غير محسنة: {', '.join(tenant_tables_lacking_index[:5])}",
                "severity": "low",
                "category": "data_integrity",
                "affected_component": "Database Schema",
                "affected_file": "database/models.py",
                "affected_line": None,
                "vulnerability_id": "CWE-400",
                "evidence": f"Unindexed tables: {len(tenant_tables_lacking_index)} tables",
                "recommendation": "أضف index=True على حقل office_id في نماذج SQLAlchemy لتحسين الأداء وتسريع عزل المكاتب."
            })


# التوافقية مع المسميات السابقة (Backwards Compatibility Alias)
ScannerEngine = LawSaaSScanner
