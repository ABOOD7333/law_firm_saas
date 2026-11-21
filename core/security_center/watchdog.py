"""
Autonomous Security Watchdog — LawSaaS Platform
الحارس الأمني الخلفي الدائم (Autonomous 24/7 Security Watchdog)

يقوم هذا الحارس بالعمل التلقائي في خلفية الخادم:
1. إجراء الفحص الأمني الشامل التلقائي (Automated Scheduled Scan) دورياً دون الحاجة لضغط زر.
2. مراقبة محاولات الهجوم المتكررة وتحليل أنماط التهديد.
3. إرسال تنبيهات بريدية فورية إذا تجاوزت الهجمات الحد الطبيعي.
4. تنظيف وحفظ السجلات بما يتوافق مع سياسات الأمان.
"""

import asyncio
import traceback
from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy.orm import Session

from database.database import SessionLocal
from database.security_models import SecurityScans, SecurityScanSchedules, SecurityEvents, SecurityAlertSettings
from core.security_center.scanner_engine import LawSaaSScanner, ScannerEngine
from core.security_center.alert_service import dispatch_security_alert


async def soc_autonomous_watchdog_loop():
    """حلقة المراقبة الأمنية المستمرة في الخلفية"""
    print("[SOC Watchdog] Autonomous Security Watchdog Daemon started successfully (24/7 Online).")
    
    # انتظار أولي بعد بدء تشغيل السيرفر بدقيقة واحدة قبل أول فحص
    await asyncio.sleep(60)

    while True:
        try:
            db = SessionLocal()
            try:
                # 1. التحقق من جدول مواعيد الفحص التلقائي
                schedule = db.query(SecurityScanSchedules).filter(
                    SecurityScanSchedules.scan_type == "full_audit",
                    SecurityScanSchedules.is_enabled == 1
                ).first()

                should_scan = False
                now = datetime.now()

                if not schedule:
                    # إنشاء جدول افتراضي يعمل تلقائياً كل 6 ساعات (4 مرات يومياً)
                    schedule = SecurityScanSchedules(
                        scan_type="full_audit",
                        frequency="every_6_hours",
                        is_enabled=1,
                        last_run_at=None,
                        next_run_at=(now + timedelta(hours=6)).strftime("%Y-%m-%d %H:%M:%S")
                    )
                    db.add(schedule)
                    db.commit()
                    db.refresh(schedule)
                    should_scan = True
                else:
                    if schedule.frequency != "every_6_hours":
                        schedule.frequency = "every_6_hours"
                        db.commit()

                    if not schedule.last_run_at:
                        should_scan = True
                    else:
                        try:
                            last_run = datetime.strptime(schedule.last_run_at, "%Y-%m-%d %H:%M:%S")
                            # فحص كل 6 ساعات (21,600 ثانية)
                            if (now - last_run).total_seconds() >= (6 * 3600):
                                should_scan = True
                        except Exception:
                            should_scan = True

                # 2. تشغيل الفحص الأمني التلقائي إذا حان موعده
                if should_scan:
                    print("[SOC Watchdog] Triggering scheduled autonomous security scan (Every 6 Hours)...")
                    engine = LawSaaSScanner(root_dir=".", db=db)
                    scan = engine.run_full_scan(trigger_type="scheduled_watchdog", triggered_by=None)
                    schedule.last_run_at = now.strftime("%Y-%m-%d %H:%M:%S")
                    schedule.next_run_at = (now + timedelta(hours=6)).strftime("%Y-%m-%d %H:%M:%S")
                    db.commit()
                    print(f"[SOC Watchdog] Autonomous scan completed. Findings: {scan.findings_count} (Critical: {scan.critical_count})")

                # 3. مراقبة وتيرة الهجمات خلال الساعة الأخيرة
                one_hour_ago = (now - timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")
                recent_attacks_count = db.query(SecurityEvents).filter(
                    SecurityEvents.created_at >= one_hour_ago,
                    SecurityEvents.severity.in_(["critical", "high"])
                ).count()

                if recent_attacks_count >= 10:
                    dispatch_security_alert(
                        db=db,
                        title="تصاعد ملحوظ في وتيرة الهجمات السيبرانية",
                        message=f"رصد درع الحماية النشط {recent_attacks_count} محاولات هجوم عالية الخطورة خلال الساعة الأخيرة.",
                        severity="critical",
                        category_or_type="attack_spike",
                        target_identifier="LawSaaS Edge IPS"
                    )

            finally:
                db.close()

        except Exception as e:
            print(f"[SOC Watchdog Warning] {e}\n{traceback.format_exc()}")

        # دورة الفحص تتكرر كل 30 دقيقة
        await asyncio.sleep(1800)
