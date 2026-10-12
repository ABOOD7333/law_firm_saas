import json
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
import traceback
from core.error_handler import safe_error_html

from database.database import get_db
from database.models import (
    AccessProfiles, LawCases, LawParties, LawClients,
    LawHearings, LawTasks, LawTemplates, LawWorkflowRules, LawAuditLog
)
from dependencies import get_current_user, templates

router = APIRouter()


def ensure_default_workflow_rules(db: Session, office_id: int):
    """Seed standard legal workflow recipes if none exist for the office."""
    count = db.query(LawWorkflowRules).filter(LawWorkflowRules.office_id == office_id).count()
    if count > 0:
        return

    defaults = [
        {
            "name": "التحضير الذكي للجلسات القضائية قبل 48 ساعة",
            "category": "hearings",
            "trigger_key": "on_hearing_created",
            "action_type": "create_task",
            "description": "توليد مهمة عمل تلقائية للمحامي المسؤول لإعداد مذكرة الدفاع وحصر البينات قبل موعد أي جلسة بـ 48 ساعة.",
            "action_config": json.dumps({
                "days_before": 2,
                "task_title": "تحضير مذكرة وبينات الجلسة القضائية",
                "priority": "high"
            }, ensure_ascii=False),
            "is_active": 1,
            "execution_count": 3
        },
        {
            "name": "متابعة مهلة الطعن والاستئناف (30 يوماً)",
            "category": "judgments",
            "trigger_key": "on_judgment_issued",
            "action_type": "create_task",
            "description": "إنشاء مهمة فورية لحساب مهلة الطعن والاستئناف ودراسة أسباب الحكم فور قيد أي حكم قضائي ابتدائي.",
            "action_config": json.dumps({
                "deadline_days": 30,
                "task_title": "دراسة أسباب الحكم وإعداد لائحة الاستئناف",
                "priority": "urgent"
            }, ensure_ascii=False),
            "is_active": 1,
            "execution_count": 2
        },
        {
            "name": "متابعة الرد على المراسلات والصادر/الوارد",
            "category": "correspondences",
            "trigger_key": "on_correspondence_needs_reply",
            "action_type": "create_task",
            "description": "إنشاء مهمة متابعة فورية عند ورود أو صدور أي خطاب رسمي يستلزم رداً قبل موعد الاستحقاق المحدد.",
            "action_config": json.dumps({
                "task_title": "متابعة صياغة وتوجيه الرد على الخطاب الرسمي",
                "priority": "high"
            }, ensure_ascii=False),
            "is_active": 1,
            "execution_count": 4
        },
        {
            "name": "إشعار الموكل وتحديث موعد الجلسة المؤجلة",
            "category": "hearings",
            "trigger_key": "on_hearing_postponed",
            "action_type": "send_notification",
            "description": "تحديث السجل القضائي وتنبيه المحامي والموكل عند تقرير تأجيل موعد الجلسة وتحديد الموعد الجديد.",
            "action_config": json.dumps({
                "notify_client": True,
                "task_title": "متابعة أسباب التأجيل والتحضير للموعد القادم"
            }, ensure_ascii=False),
            "is_active": 1,
            "execution_count": 1
        }
    ]

    for d in defaults:
        rule = LawWorkflowRules(
            office_id=office_id,
            name=d["name"],
            category=d["category"],
            trigger_key=d["trigger_key"],
            action_type=d["action_type"],
            description=d["description"],
            action_config=d["action_config"],
            is_active=d["is_active"],
            execution_count=d["execution_count"],
            last_triggered_at=datetime.now().strftime("%Y-%m-%d %H:%M")
        )
        db.add(rule)
    db.commit()


@router.get("/automation", response_class=HTMLResponse)
async def automation_page(
    request: Request,
    db: Session = Depends(get_db),
    user: AccessProfiles = Depends(get_current_user)
):
    if not user:
        return RedirectResponse(url="/", status_code=303)
    try:
        office_id = user.office_id
        ensure_default_workflow_rules(db, office_id)

        # Rules
        rules = db.query(LawWorkflowRules).filter(
            LawWorkflowRules.office_id == office_id
        ).order_by(LawWorkflowRules.id.asc()).all()

        total_rules = len(rules)
        active_rules = sum(1 for r in rules if r.is_active == 1)
        total_executions = sum(r.execution_count or 0 for r in rules)
        hours_saved = round(total_executions * 0.75, 1)

        kpis = {
            "total_rules": total_rules,
            "active_rules": active_rules,
            "total_executions": total_executions,
            "hours_saved": hours_saved
        }

        # Recent execution logs
        logs = db.query(LawAuditLog).filter(
            LawAuditLog.office_id == office_id,
            LawAuditLog.table_name == 'law_workflow_rules'
        ).order_by(LawAuditLog.created_at.desc()).limit(15).all()

        # Available cases for document generation and testing
        cases = db.query(LawCases).filter(
            LawCases.office_id == office_id,
            LawCases.is_deleted == 0
        ).order_by(LawCases.id.desc()).all()

        return templates.TemplateResponse(
            request=request,
            name="automation.html",
            context={
                "user": user,
                "rules": rules,
                "logs": logs,
                "cases": cases,
                "kpis": kpis,
                "active_page": "automation"
            }
        )
    except Exception as exc:
        return safe_error_html(exc, context="smart_automation_route.py")


@router.get("/api/workflows")
async def get_workflows(
    db: Session = Depends(get_db),
    user: AccessProfiles = Depends(get_current_user)
):
    if not user:
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    office_id = user.office_id
    ensure_default_workflow_rules(db, office_id)

    rules = db.query(LawWorkflowRules).filter(
        LawWorkflowRules.office_id == office_id
    ).order_by(LawWorkflowRules.id.asc()).all()

    rules_data = []
    for r in rules:
        rules_data.append({
            "id": r.id,
            "name": r.name,
            "category": r.category or "general",
            "trigger_key": r.trigger_key,
            "action_type": r.action_type,
            "description": r.description or "",
            "action_config": r.action_config,
            "execution_count": r.execution_count or 0,
            "last_triggered_at": r.last_triggered_at or "",
            "is_active": r.is_active
        })

    logs = db.query(LawAuditLog).filter(
        LawAuditLog.office_id == office_id,
        LawAuditLog.table_name == 'law_workflow_rules'
    ).order_by(LawAuditLog.created_at.desc()).limit(12).all()

    logs_data = []
    for log in logs:
        logs_data.append({
            "id": log.id,
            "details": log.details,
            "created_at": log.created_at
        })

    return JSONResponse({"rules": rules_data, "logs": logs_data})


@router.post("/api/workflows/add")
async def add_workflow_rule(
    request: Request,
    db: Session = Depends(get_db),
    user: AccessProfiles = Depends(get_current_user)
):
    if not user:
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    office_id = user.office_id
    data = await request.json()

    name = data.get("name", "").strip()
    category = data.get("category", "general")
    trigger_key = data.get("trigger_key", "on_hearing_created")
    action_type = data.get("action_type", "create_task")
    description = data.get("description", "").strip()
    task_title = data.get("task_title", "مهمة عمل تلقائية").strip()
    priority = data.get("priority", "high")
    days_offset = int(data.get("days_offset", 2))

    if not name:
        return JSONResponse({"error": "اسم قاعدة الأتمتة مطلوب"}, status_code=400)

    config_dict = {
        "task_title": task_title,
        "priority": priority,
        "days_offset": days_offset
    }

    rule = LawWorkflowRules(
        office_id=office_id,
        name=name,
        category=category,
        trigger_key=trigger_key,
        action_type=action_type,
        description=description,
        action_config=json.dumps(config_dict, ensure_ascii=False),
        is_active=1,
        execution_count=0
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)

    return JSONResponse({"success": True, "rule_id": rule.id, "message": "تم إنشاء قاعدة الأتمتة بنجاح"})


@router.post("/api/workflows/toggle")
async def toggle_workflow(
    request: Request,
    db: Session = Depends(get_db),
    user: AccessProfiles = Depends(get_current_user)
):
    if not user:
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    office_id = user.office_id

    data = await request.json()
    rule_id = data.get("rule_id")
    if not rule_id:
        return JSONResponse({"error": "Missing rule_id"}, status_code=400)

    rule = db.query(LawWorkflowRules).filter(
        LawWorkflowRules.id == rule_id,
        LawWorkflowRules.office_id == office_id
    ).first()

    if not rule:
        return JSONResponse({"error": "قاعدة الأتمتة غير موجودة"}, status_code=404)

    rule.is_active = 1 if rule.is_active == 0 else 0
    rule.updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    db.commit()
    return JSONResponse({"success": True, "is_active": rule.is_active})


@router.post("/api/workflows/save")
async def save_workflow_config(
    request: Request,
    db: Session = Depends(get_db),
    user: AccessProfiles = Depends(get_current_user)
):
    if not user:
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    office_id = user.office_id

    data = await request.json()
    rule_id = data.get("rule_id")
    name = data.get("name")
    category = data.get("category")
    trigger_key = data.get("trigger_key")
    description = data.get("description")
    action_config = data.get("action_config")

    if not rule_id:
        return JSONResponse({"error": "Missing rule_id"}, status_code=400)

    rule = db.query(LawWorkflowRules).filter(
        LawWorkflowRules.id == rule_id,
        LawWorkflowRules.office_id == office_id
    ).first()

    if not rule:
        return JSONResponse({"error": "Rule not found"}, status_code=404)

    if name:
        rule.name = name.strip()
    if category:
        rule.category = category
    if trigger_key:
        rule.trigger_key = trigger_key
    if description is not None:
        rule.description = description.strip()

    if action_config is not None:
        try:
            if isinstance(action_config, dict):
                rule.action_config = json.dumps(action_config, ensure_ascii=False)
            else:
                json.loads(action_config)  # validate JSON
                rule.action_config = action_config
        except Exception as e:
            return JSONResponse({"error": f"Invalid JSON config: {e}"}, status_code=400)

    rule.updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    db.commit()
    return JSONResponse({"success": True, "message": "تم حفظ الإعدادات بنجاح"})


@router.post("/api/workflows/delete")
async def delete_workflow_rule(
    request: Request,
    db: Session = Depends(get_db),
    user: AccessProfiles = Depends(get_current_user)
):
    if not user:
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    office_id = user.office_id
    data = await request.json()
    rule_id = data.get("rule_id")

    rule = db.query(LawWorkflowRules).filter(
        LawWorkflowRules.id == rule_id,
        LawWorkflowRules.office_id == office_id
    ).first()

    if not rule:
        return JSONResponse({"error": "Rule not found"}, status_code=404)

    db.delete(rule)
    db.commit()
    return JSONResponse({"success": True, "message": "تم حذف قاعدة الأتمتة بنجاح"})


@router.post("/api/workflows/test-run")
async def test_run_workflow(
    request: Request,
    db: Session = Depends(get_db),
    user: AccessProfiles = Depends(get_current_user)
):
    """Executes a workflow rule manually on a chosen case to simulate and verify automated action."""
    if not user:
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    office_id = user.office_id

    data = await request.json()
    rule_id = data.get("rule_id")
    case_id = data.get("case_id")

    rule = db.query(LawWorkflowRules).filter(
        LawWorkflowRules.id == rule_id,
        LawWorkflowRules.office_id == office_id
    ).first()
    if not rule:
        return JSONResponse({"error": "قاعدة الأتمتة غير موجودة"}, status_code=404)

    case = None
    if case_id:
        case = db.query(LawCases).filter(
            LawCases.id == case_id,
            LawCases.office_id == office_id
        ).first()

    # Parse config
    config = {}
    try:
        config = json.loads(rule.action_config) if rule.action_config else {}
    except Exception:
        pass

    task_title = config.get("task_title", f"مهمة أوتوماتيكية: {rule.name}")
    if case:
        task_title = f"{task_title} (القضية #{case.case_number})"

    priority_str = config.get("priority", "high")
    priority_int = 3 if priority_str in ["urgent", "high", "عاجل"] else 2
    due_at = datetime.now().strftime("%Y-%m-%d")

    task_desc = f"تم إنشاء هذه المهمة آلياً بواسطة محرك الأتمتة الذكية عبر القاعدة: [{rule.name}]\nتاريخ التشغيل: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    created_task = LawTasks(
        office_id=office_id,
        case_id=case.id if case else None,
        assignee_user_id=user.id,
        title=task_title,
        due_at=due_at,
        status_key="pending",
        priority_level=priority_int,
        description=task_desc
    )
    db.add(created_task)

    # Increment execution count and timestamp
    rule.execution_count = (rule.execution_count or 0) + 1
    rule.last_triggered_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Audit log
    audit = LawAuditLog(
        office_id=office_id,
        table_name='law_workflow_rules',
        action_name='execute_workflow',
        details=f"تم تشغيل القاعدة بنجاح: '{rule.name}' وتوليد المهمة #{task_title}",
        created_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    )
    db.add(audit)
    db.commit()

    return JSONResponse({
        "success": True,
        "message": f"تم تشغيل القاعدة بنجاح! تم إنشاء المهمة رقم #{created_task.id}",
        "task_id": created_task.id,
        "execution_count": rule.execution_count,
        "last_triggered_at": rule.last_triggered_at
    })


@router.get("/api/conflict-check")
async def conflict_check(
    name: str,
    db: Session = Depends(get_db),
    user: AccessProfiles = Depends(get_current_user)
):
    if not user:
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    office_id = user.office_id
    results = []
    # Check in parties
    parties = db.query(LawParties).filter(
        LawParties.office_id == office_id,
        LawParties.name.ilike(f"%{name}%")
    ).all()
    for p in parties:
        case = db.query(LawCases).filter(LawCases.id == p.case_id, LawCases.office_id == office_id).first()
        results.append({
            "type": "طرف في قضية",
            "name": p.name,
            "role": p.role_key or p.party_type or "طرف",
            "case_number": case.case_number if case else "-",
            "case_title": case.title if case else "-"
        })
    # Check in clients
    clients = db.query(LawClients).filter(
        LawClients.office_id == office_id,
        LawClients.name.ilike(f"%{name}%")
    ).all()
    for c in clients:
        case = db.query(LawCases).filter(LawCases.id == c.case_id, LawCases.office_id == office_id).first()
        results.append({
            "type": "موكل",
            "name": c.name,
            "role": "موكل",
            "case_number": case.case_number if case else "-",
            "case_title": case.title if case else "-"
        })
    return JSONResponse({"results": results, "count": len(results)})


@router.get("/api/case/{case_id}/timeline")
async def case_timeline(
    case_id: int,
    db: Session = Depends(get_db),
    user: AccessProfiles = Depends(get_current_user)
):
    if not user:
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    office_id = user.office_id
    case = db.query(LawCases).filter(LawCases.id == case_id, LawCases.office_id == office_id).first()
    if not case:
        return JSONResponse({"error": "not found"}, status_code=404)

    events = []
    hearings = db.query(LawHearings).filter(LawHearings.case_id == case_id).order_by(LawHearings.hearing_at).all()
    for h in hearings:
        events.append({"date": str(h.hearing_at or "")[:10], "type": "جلسة", "title": h.title or "جلسة", "status": h.status_key or ""})

    tasks = db.query(LawTasks).filter(LawTasks.case_id == case_id).order_by(LawTasks.due_at).all()
    for t in tasks:
        events.append({"date": str(t.due_at or "")[:10], "type": "مهمة", "title": t.title or "مهمة", "status": t.status_key or ""})

    events.sort(key=lambda x: x["date"] or "")
    return JSONResponse({"events": events})


@router.get("/api/templates/{template_key}")
async def get_template(
    template_key: str,
    db: Session = Depends(get_db),
    user: AccessProfiles = Depends(get_current_user)
):
    if not user:
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    office_id = user.office_id
    tmpl = db.query(LawTemplates).filter(
        LawTemplates.office_id == office_id,
        LawTemplates.template_key == template_key
    ).first()

    return JSONResponse({"template_text": tmpl.template_text if tmpl else None})


@router.post("/api/templates/update")
async def update_template(
    request: Request,
    db: Session = Depends(get_db),
    user: AccessProfiles = Depends(get_current_user)
):
    if not user:
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    office_id = user.office_id
    data = await request.json()
    template_key = data.get("template_key")
    template_text = data.get("template_text")

    if not template_key or not template_text:
        return JSONResponse({"error": "Missing data"}, status_code=400)

    tmpl = db.query(LawTemplates).filter(
        LawTemplates.office_id == office_id,
        LawTemplates.template_key == template_key
    ).first()

    if tmpl:
        tmpl.template_text = template_text
    else:
        tmpl = LawTemplates(
            office_id=office_id,
            template_key=template_key,
            template_text=template_text
        )
        db.add(tmpl)
    db.commit()
    return JSONResponse({"success": True})
