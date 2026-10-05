from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from sqlalchemy.orm import Session
import traceback
from core.error_handler import safe_error_html

from database.database import get_db
from database.models import (
    AccessProfiles, LawCases, LawParties, LawClients,
    LawHearings, LawTasks, LawTemplates
)
from dependencies import get_current_user, templates, check_user_permission

router = APIRouter()

def _require(user, action="view"):
    if not user or not user.office_id or not check_user_permission(user, "automation", action):
        raise HTTPException(status_code=403, detail="غير مصرح")


@router.get("/automation", response_class=HTMLResponse)
async def automation_page(
    request: Request,
    db: Session = Depends(get_db),
    user: AccessProfiles = Depends(get_current_user)
):
    if not user: return RedirectResponse(url="/", status_code=303)
    _require(user)
    try:
        cases = db.query(LawCases).filter(LawCases.office_id == user.office_id, LawCases.is_deleted == 0).all()
        return templates.TemplateResponse(request=request, name="automation.html",
            context={"user": user, "cases": cases, "active_page": "automation"})
    except Exception as exc:
        return safe_error_html(exc, context="smart_automation_route.py")

@router.get("/api/conflict-check")
async def conflict_check(
    name: str,
    db: Session = Depends(get_db),
    user: AccessProfiles = Depends(get_current_user)
):
    from fastapi.responses import JSONResponse
    if not user: return JSONResponse({"error":"unauthorized"}, status_code=401)
    _require(user)
    name = (name or "").strip()
    if len(name) < 2 or len(name) > 120:
        raise HTTPException(status_code=400, detail="أدخل اسمًا من حرفين إلى 120 حرفًا")
    office_id = user.office_id
    results = []
    # Check in parties
    parties = db.query(LawParties).filter(
        LawParties.office_id == office_id,
        LawParties.is_deleted == 0,
        LawParties.name.ilike(f"%{name}%")
    ).limit(100).all()
    for p in parties:
        case = db.query(LawCases).filter(LawCases.id == p.case_id, LawCases.office_id == office_id, LawCases.is_deleted == 0).first()
        results.append({
            "type": "طرف في قضية",
            "name": p.name,
            "role": p.role_key or "",
            "case_number": case.case_number if case else "-",
            "case_title": case.title if case else "-"
        })
    # Check in clients
    clients = db.query(LawClients).filter(
        LawClients.office_id == office_id,
        LawClients.is_deleted == 0,
        LawClients.name.ilike(f"%{name}%")
    ).limit(100).all()
    for c in clients:
        case = db.query(LawCases).filter(LawCases.id == c.case_id, LawCases.office_id == office_id, LawCases.is_deleted == 0).first()
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
    from fastapi.responses import JSONResponse
    if not user: return JSONResponse({"error":"unauthorized"}, status_code=401)
    _require(user)
    office_id = user.office_id
    query = db.query(LawCases).filter(LawCases.id == case_id, LawCases.office_id == office_id, LawCases.is_deleted == 0)
    if user.role == "محامٍ": query = query.filter(LawCases.lead_lawyer_id == user.id)
    case = query.first()
    if not case: return JSONResponse({"error":"not found"}, status_code=404)
    
    events = []
    # Hearings
    hearings = db.query(LawHearings).filter(LawHearings.case_id == case_id).order_by(LawHearings.hearing_at).all()
    for h in hearings:
        events.append({"date": str(h.hearing_at or "")[:10], "type": "جلسة", "title": h.title or "جلسة", "status": h.status_key or ""})
    # Tasks
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
    from fastapi.responses import JSONResponse
    if not user: return JSONResponse({"error": "unauthorized"}, status_code=401)
    _require(user)
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
    from fastapi.responses import JSONResponse
    if not user: return JSONResponse({"error": "unauthorized"}, status_code=401)
    _require(user, "edit")
    office_id = user.office_id
    data = await request.json()
    template_key = data.get("template_key")
    template_text = data.get("template_text")
    
    if not isinstance(template_key, str) or len(template_key) > 100 or not isinstance(template_text, str) or not template_text.strip():
        return JSONResponse({"error": "Missing data"}, status_code=400)
    if len(template_text) > 200_000:
        return JSONResponse({"error": "Template is too large"}, status_code=413)
        
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

@router.get("/api/workflows")
async def get_workflows(
    db: Session = Depends(get_db),
    user: AccessProfiles = Depends(get_current_user)
):
    from fastapi.responses import JSONResponse
    from database.models import LawWorkflowRules, LawAuditLog
    if not user: return JSONResponse({"error": "unauthorized"}, status_code=401)
    _require(user)
    office_id = user.office_id
    
    # Get rules
    rules = db.query(LawWorkflowRules).filter(LawWorkflowRules.office_id == office_id).all()
    rules_data = []
    for r in rules:
        rules_data.append({
            "id": r.id,
            "name": r.name,
            "trigger_key": r.trigger_key,
            "action_type": r.action_type,
            "action_config": r.action_config,
            "is_active": r.is_active
        })
        
    # Get recent execution logs
    logs = db.query(LawAuditLog).filter(
        LawAuditLog.office_id == office_id,
        LawAuditLog.table_name == 'law_workflow_rules',
        LawAuditLog.action_name == 'execute_workflow'
    ).order_by(LawAuditLog.created_at.desc()).limit(10).all()
    
    logs_data = []
    for log in logs:
        logs_data.append({
            "id": log.id,
            "details": log.details,
            "created_at": log.created_at
        })
        
    return JSONResponse({"rules": rules_data, "logs": logs_data})

@router.post("/api/workflows/toggle")
async def toggle_workflow(
    request: Request,
    db: Session = Depends(get_db),
    user: AccessProfiles = Depends(get_current_user)
):
    from fastapi.responses import JSONResponse
    from database.models import LawWorkflowRules
    if not user: return JSONResponse({"error": "unauthorized"}, status_code=401)
    _require(user, "edit")
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
        return JSONResponse({"error": "Rule not found"}, status_code=404)
        
    rule.is_active = 1 if rule.is_active == 0 else 0
    db.commit()
    return JSONResponse({"success": True, "is_active": rule.is_active})

@router.post("/api/workflows/save")
async def save_workflow_config(
    request: Request,
    db: Session = Depends(get_db),
    user: AccessProfiles = Depends(get_current_user)
):
    from fastapi.responses import JSONResponse
    from database.models import LawWorkflowRules
    import json
    if not user: return JSONResponse({"error": "unauthorized"}, status_code=401)
    _require(user, "edit")
    office_id = user.office_id
    
    data = await request.json()
    rule_id = data.get("rule_id")
    action_config = data.get("action_config")
    
    if not rule_id or action_config is None:
        return JSONResponse({"error": "Missing rule_id or action_config"}, status_code=400)
        
    rule = db.query(LawWorkflowRules).filter(
        LawWorkflowRules.id == rule_id,
        LawWorkflowRules.office_id == office_id
    ).first()
    
    if not rule:
        return JSONResponse({"error": "Rule not found"}, status_code=404)
        
    # Verify action_config is valid JSON
    try:
        if isinstance(action_config, dict):
            rule.action_config = json.dumps(action_config, ensure_ascii=False)
        else:
            if not isinstance(action_config, str) or len(action_config) > 20_000:
                return JSONResponse({"error": "Config is too large or invalid"}, status_code=400)
            json.loads(action_config) # test parse
            rule.action_config = action_config
    except Exception as e:
        return JSONResponse({"error": f"Invalid JSON config: {e}"}, status_code=400)
        
    db.commit()
    return JSONResponse({"success": True})


