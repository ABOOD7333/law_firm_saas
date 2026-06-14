import json
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from database.models import (
    LawWorkflowRules, LawTasks, LawCases, LawHearings,
    LawLimitations, LawAuditLog, LawNotificationLog, AccessProfiles
)

def parse_date(date_str: str) -> datetime:
    if not date_str:
        return None
    date_str = date_str.replace('T', ' ')
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d", "%d/%m/%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(date_str.strip(), fmt)
        except ValueError:
            continue
    return None

def trigger_event(db: Session, trigger_key: str, event_data: dict, office_id: int):
    """
    Executes all active rules matching a specific trigger key.
    """
    try:
        rules = db.query(LawWorkflowRules).filter(
            LawWorkflowRules.office_id == office_id,
            LawWorkflowRules.trigger_key == trigger_key,
            LawWorkflowRules.is_active == 1
        ).all()
        
        for rule in rules:
            try:
                config = json.loads(rule.action_config)
            except Exception as e:
                print(f"[WorkflowEngine] Error parsing rule config for rule {rule.id}: {e}")
                continue
                
            if rule.action_type == "create_task":
                if trigger_key == "on_hearing_created":
                    # event_data should contain: hearing_title, hearing_at, case_id
                    hearing_title = event_data.get("hearing_title", "")
                    hearing_at_str = event_data.get("hearing_at", "")
                    case_id = event_data.get("case_id")
                    
                    if not case_id or not hearing_at_str:
                        continue
                        
                    case = db.query(LawCases).filter(LawCases.id == case_id).first()
                    case_title = case.title if case else "قضية غير معروفة"
                    
                    hearing_time = parse_date(hearing_at_str)
                    if not hearing_time:
                        continue
                        
                    # Calculate due date: subtract hours from config
                    offset_hours = config.get("due_offset_hours", -48)
                    due_time = hearing_time + timedelta(hours=offset_hours)
                    due_time_str = due_time.strftime("%Y-%m-%d %H:%M:%S")
                    
                    # Format text
                    task_title = config.get("task_title", "التحضير للجلسة: {hearing_title}").format(
                        hearing_title=hearing_title,
                        case_title=case_title,
                        hearing_time=hearing_at_str
                    )
                    task_desc = config.get("task_description", "").format(
                        hearing_title=hearing_title,
                        case_title=case_title,
                        hearing_time=hearing_at_str
                    )
                    
                    # Create the task
                    new_task = LawTasks(
                        case_id=case_id,
                        office_id=office_id,
                        title=task_title,
                        description=task_desc,
                        due_at=due_time_str,
                        assignee_user_id=case.lead_lawyer_id if case else None,
                        status_key="pending",
                        priority_level=config.get("priority_level", 3)
                    )
                    db.add(new_task)
                    
                    # Log execution in LawAuditLog
                    audit = LawAuditLog(
                        table_name="law_workflow_rules",
                        action_name="execute_workflow",
                        record_key=str(rule.id),
                        actor_name="WorkflowEngine",
                        details=f"توليد مهمة تلقائية: {task_title} للقضية: {case_title}",
                        office_id=office_id
                    )
                    db.add(audit)
                    db.commit()
                    print(f"[WorkflowEngine] Created automated preparation task for hearing: {hearing_title}")
                    
    except Exception as e:
        print(f"[WorkflowEngine Error] {e}")

def run_daily_limitation_checks(db: Session):
    """
    Scans all offices for active on_case_limitation_warning rules and checks active limitations.
    Runs as a daily background process.
    """
    try:
        # Get active limitation warning rules
        rules = db.query(LawWorkflowRules).filter(
            LawWorkflowRules.trigger_key == "on_case_limitation_warning",
            LawWorkflowRules.is_active == 1
        ).all()
        
        today = datetime.now()
        
        for rule in rules:
            office_id = rule.office_id
            try:
                config = json.loads(rule.action_config)
            except Exception as e:
                print(f"[WorkflowEngine] Error parsing config for rule {rule.id}: {e}")
                continue
                
            # Fetch active, non-deleted limitations for this office
            limitations = db.query(LawLimitations).filter(
                LawLimitations.office_id == office_id,
                LawLimitations.status_key == "active",
                LawLimitations.is_deleted == 0
            ).all()
            
            for lim in limitations:
                due_time = parse_date(lim.due_date)
                if not due_time:
                    continue
                    
                days_left = (due_time - today).days
                
                # Warning trigger condition: remaining days < 30 and hasn't passed yet
                if 0 <= days_left < 30:
                    # Check if warning task already exists to prevent duplicate warning spam
                    warning_tag = f"تحذير تقادم #${lim.id}"
                    existing_task = db.query(LawTasks).filter(
                        LawTasks.office_id == office_id,
                        LawTasks.title.like(f"{warning_tag}%"),
                        LawTasks.is_deleted == 0
                    ).first()
                    
                    if existing_task:
                        # Warning already created
                        continue
                        
                    case = db.query(LawCases).filter(LawCases.id == lim.case_id).first()
                    case_title = case.title if case else "قضية غير معروفة"
                    
                    # Format text
                    task_title = f"{warning_tag}: {case_title}"
                    task_desc = config.get("task_description", "").format(
                        case_title=case_title,
                        limitation_date=lim.due_date
                    )
                    if not task_desc:
                        task_desc = f"تنبيه: متبقي {days_left} يوماً على تاريخ تقادم القضية ({case_title}) في {lim.due_date}."
                        
                    # Create warning task
                    new_task = LawTasks(
                        case_id=lim.case_id,
                        office_id=office_id,
                        title=task_title,
                        description=task_desc,
                        due_at=(today + timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S"),
                        assignee_user_id=case.lead_lawyer_id if case else None,
                        status_key="pending",
                        priority_level=config.get("priority_level", 3)  # High Priority
                    )
                    db.add(new_task)
                    
                    # Notify assigned lawyer and all managers/admins
                    notify_users = []
                    # 1. Lead lawyer
                    if case and case.lead_lawyer_id:
                        notify_users.append(case.lead_lawyer_id)
                        
                    # 2. Office Managers/Admins/Owners
                    managers = db.query(AccessProfiles).filter(
                        AccessProfiles.office_id == office_id,
                        AccessProfiles.role.in_(["مدير", "صاحب المكتب", "مدير النظام", "مدير المكتب"]),
                        AccessProfiles.is_active == 1,
                        AccessProfiles.is_deleted == 0
                    ).all()
                    for m in managers:
                        if m.id not in notify_users:
                            notify_users.append(m.id)
                            
                    # Add notifications
                    for user_id in notify_users:
                        notif = LawNotificationLog(
                            user_id=user_id,
                            title="تحذير: قرب تاريخ تقادم قضية",
                            content=f"تنبيه هام: القضية '{case_title}' تقترب من تاريخ التقادم في {lim.due_date} (المتبقي أقل من 30 يوماً).",
                            is_read=0
                        )
                        db.add(notif)
                        
                    # Log execution in LawAuditLog
                    audit = LawAuditLog(
                        table_name="law_workflow_rules",
                        action_name="execute_workflow",
                        record_key=str(rule.id),
                        actor_name="WorkflowEngine",
                        details=f"توليد تحذير تقادم: {task_title} للقضية: {case_title}",
                        office_id=office_id
                    )
                    db.add(audit)
                    db.commit()
                    print(f"[WorkflowEngine] Generated warning task & alerts for limitation ID {lim.id}")
                    
    except Exception as e:
        print(f"[WorkflowEngine Daily Task Error] {e}")
