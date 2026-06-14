import sys
import os
import json
from datetime import datetime, timedelta

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from database.database import SessionLocal
from database.models import LawCases, LawOffices, LawTasks, LawHearings, LawLimitations, LawNotificationLog
from core.workflow_engine import trigger_event, run_daily_limitation_checks

def test_workflow_engine():
    db = SessionLocal()
    try:
        print("[Test] Starting Workflow Engine verification...")
        
        # 1. Fetch office
        office = db.query(LawOffices).first()
        if not office:
            print("[Test Fail] No office found in the database. Run migrate first.")
            return
            
        office_id = office.id
        print(f"[Test] Using Office ID: {office_id}")
        
        # 2. Find or create a test case
        case = db.query(LawCases).filter(LawCases.office_id == office_id).first()
        if not case:
            print("[Test] Creating a mock case...")
            case = LawCases(
                office_id=office_id,
                case_number="TEST-CASE-999",
                title="قضية اختبار الأتمتة",
                status_key="active"
            )
            db.add(case)
            db.commit()
            db.refresh(case)
            
        case_id = case.id
        print(f"[Test] Using Case ID: {case_id}, Number: {case.case_number}")
        
        # 3. Test Hearing Created Event (Trigger: on_hearing_created)
        print("[Test] Simulating hearing creation...")
        test_hearing_title = "جلسة المرافعة الختامية الكبرى"
        # Set hearing date to 5 days from now
        hearing_time = datetime.now() + timedelta(days=5)
        hearing_at_str = hearing_time.strftime("%Y-%m-%d %H:%M:%S")
        
        event_data = {
            "hearing_title": test_hearing_title,
            "hearing_at": hearing_at_str,
            "case_id": case_id
        }
        
        # Count tasks before trigger
        initial_tasks_count = db.query(LawTasks).filter(LawTasks.case_id == case_id).count()
        
        trigger_event(db, "on_hearing_created", event_data, office_id)
        
        # Check if preparation task was generated
        new_tasks = db.query(LawTasks).filter(
            LawTasks.case_id == case_id,
            LawTasks.title.like("%التحضير لجلسة%")
        ).all()
        
        if len(new_tasks) > initial_tasks_count:
            latest_task = new_tasks[-1]
            print(f"[Test Pass] Automated preparation task created: '{latest_task.title}'")
            print(f"            Description: {latest_task.description}")
            print(f"            Due Date: {latest_task.due_at}")
            
            # Verify that due date is indeed 48 hours before hearing
            expected_due = hearing_time - timedelta(hours=48)
            actual_due = datetime.strptime(latest_task.due_at, "%Y-%m-%d %H:%M:%S")
            diff = abs((expected_due - actual_due).total_seconds())
            if diff < 10:
                print("[Test Pass] Due date subtracted 48 hours correctly!")
            else:
                print(f"[Test Fail] Due date mismatch. Expected: {expected_due}, Actual: {actual_due}")
        else:
            print("[Test Fail] No automated task created for hearing!")
            
        # 4. Test Case Limitation Check (Trigger: on_case_limitation_warning)
        print("[Test] Creating a mock case limitation due in 15 days...")
        # Create a mock limitation
        mock_lim = LawLimitations(
            case_id=case_id,
            office_id=office_id,
            title="تقادم دعوى التعويض العقاري",
            limitation_type_key="due_date",
            due_date=(datetime.now() + timedelta(days=15)).strftime("%Y-%m-%d %H:%M:%S"),
            status_key="active"
        )
        db.add(mock_lim)
        db.commit()
        db.refresh(mock_lim)
        
        print(f"[Test] Limitation ID: {mock_lim.id} created, due: {mock_lim.due_date}")
        
        # Run daily checker
        print("[Test] Running daily checks...")
        notif_count_before = db.query(LawNotificationLog).count()
        run_daily_limitation_checks(db)
        
        # Verify warning task created
        warning_task = db.query(LawTasks).filter(
            LawTasks.case_id == case_id,
            LawTasks.title.like(f"%تحذير تقادم #${mock_lim.id}%")
        ).first()
        
        if warning_task:
            print(f"[Test Pass] Limitation warning task created: '{warning_task.title}'")
            print(f"            Description: {warning_task.description}")
        else:
            print("[Test Fail] Warning task not created!")
            
        # Verify notifications created
        notif_count_after = db.query(LawNotificationLog).count()
        if notif_count_after > notif_count_before:
            print(f"[Test Pass] Created {notif_count_after - notif_count_before} notifications for lawyers/managers.")
        else:
            print("[Test Fail] No notifications created!")
            
        # Test Duplicate Prevention
        print("[Test] Running daily checks again to verify no duplicate alerts are generated...")
        tasks_count_before = db.query(LawTasks).filter(LawTasks.case_id == case_id).count()
        run_daily_limitation_checks(db)
        tasks_count_after = db.query(LawTasks).filter(LawTasks.case_id == case_id).count()
        
        if tasks_count_before == tasks_count_after:
            print("[Test Pass] Duplicate prevention worked perfectly! No extra task generated.")
        else:
            print(f"[Test Fail] Duplicate alert generated! Task count increased by {tasks_count_after - tasks_count_before}")
            
        # Cleanup mock test data to keep database clean
        print("[Test] Cleaning up mock data...")
        db.delete(mock_lim)
        if warning_task:
            db.delete(warning_task)
        for t in new_tasks:
            db.delete(t)
        db.commit()
        print("[Test] Cleanup completed.")
        
    except Exception as e:
        db.rollback()
        print(f"[Test Error] {e}")
    finally:
        db.close()

if __name__ == "__main__":
    test_workflow_engine()
