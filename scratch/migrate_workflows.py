import json
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from database.database import engine, SessionLocal
from database.models import Base, LawOffices, LawWorkflowRules

def migrate():
    print("[Migration] Ensuring all tables are created...")
    Base.metadata.create_all(bind=engine)
    
    db = SessionLocal()
    try:
        offices = db.query(LawOffices).all()
        print(f"[Migration] Found {len(offices)} offices. Checking default workflow rules...")
        
        default_rules = [
            {
                "name": "توليد مهام تحضير للمحامي تلقائياً قبل الجلسة بـ 48 ساعة",
                "trigger_key": "on_hearing_created",
                "action_type": "create_task",
                "action_config": json.dumps({
                    "task_title": "التحضير لجلسة: {hearing_title}",
                    "task_description": "تم توليد هذه المهمة تلقائياً للتحضير لجلسة المحاكمة في القضية: {case_title} والتي ستبدأ في {hearing_time}.",
                    "due_offset_hours": -48,
                    "priority_level": 3  # High priority
                }, ensure_ascii=False)
            },
            {
                "name": "إرسال إشعار تحذيري يومي عند قرب تاريخ تقادم قضية (أقل من 30 يوماً)",
                "trigger_key": "on_case_limitation_warning",
                "action_type": "create_task",
                "action_config": json.dumps({
                    "task_title": "تحذير تقادم: {case_title}",
                    "task_description": "تنبيه هام: تاريخ تقادم القضية هو {limitation_date}، المتبقي أقل من 30 يوماً. يرجى اتخاذ الإجراءات العاجلة.",
                    "priority_level": 3  # High priority
                }, ensure_ascii=False)
            }
        ]
        
        rules_added = 0
        for office in offices:
            for rule_def in default_rules:
                # Check if this rule already exists for this office
                exists = db.query(LawWorkflowRules).filter(
                    LawWorkflowRules.office_id == office.id,
                    LawWorkflowRules.trigger_key == rule_def["trigger_key"]
                ).first()
                
                if not exists:
                    new_rule = LawWorkflowRules(
                        office_id=office.id,
                        name=rule_def["name"],
                        trigger_key=rule_def["trigger_key"],
                        action_type=rule_def["action_type"],
                        action_config=rule_def["action_config"],
                        is_active=1
                    )
                    db.add(new_rule)
                    rules_added += 1
                    
        if rules_added > 0:
            db.commit()
            print(f"[Migration] Successfully added {rules_added} default workflow rules.")
        else:
            print("[Migration] All offices already have default workflow rules populated.")
            
    except Exception as e:
        db.rollback()
        print(f"[Migration Error] {e}")
        raise e
    finally:
        db.close()

if __name__ == "__main__":
    migrate()
