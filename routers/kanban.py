from fastapi import APIRouter, Request, Depends, HTTPException, Body
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from database.database import get_db
from database.models import AccessProfiles, LawTasks, LawCases, LawClients, LawOffices
from dependencies import templates, get_current_user, check_user_permission

router = APIRouter(prefix="/kanban", tags=["Kanban"])

def get_authorized_user(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        raise HTTPException(status_code=303, headers={"Location": "/"})
    if user.role == "موكل":
        raise HTTPException(status_code=303, headers={"Location": "/client-portal"})
    return user

@router.get("", response_class=HTMLResponse)
async def kanban_board(request: Request, db: Session = Depends(get_db), user: AccessProfiles = Depends(get_authorized_user)):
    if not check_user_permission(user, 'tasks', 'view'):
        return HTMLResponse("<script>alert('غير مصرح لك'); window.location.href='/dashboard';</script>")
    
    # We will fetch data via API in the template
    return templates.TemplateResponse("kanban/board.html", {
        "request": request,
        "user": user,
        "active_page": "kanban"
    })

@router.get("/api/tasks")
async def get_tasks(db: Session = Depends(get_db), user: AccessProfiles = Depends(get_authorized_user)):
    if not check_user_permission(user, 'tasks', 'view'):
        return JSONResponse({"ok": False, "error": "غير مصرح لك"}, status_code=403)
        
    tasks = db.query(LawTasks).filter(
        LawTasks.office_id == user.office_id,
        LawTasks.is_deleted == 0
    ).order_by(LawTasks.kanban_order.asc(), LawTasks.id.desc()).all()
    
    # Enrich with case info and assignee info
    assignees_ids = list(set([t.assignee_user_id for t in tasks if t.assignee_user_id]))
    cases_ids = list(set([t.case_id for t in tasks if t.case_id]))
    
    assignees = {}
    if assignees_ids:
        users = db.query(AccessProfiles).filter(AccessProfiles.id.in_(assignees_ids)).all()
        assignees = {u.id: {"name": u.name, "avatar": u.name[0] if u.name else "?"} for u in users}
        
    cases_map = {}
    if cases_ids:
        cases = db.query(LawCases).filter(LawCases.id.in_(cases_ids)).all()
        cases_map = {c.id: {"case_number": c.case_number, "title": c.title} for c in cases}
        
    data = []
    for t in tasks:
        data.append({
            "id": t.id,
            "title": t.title,
            "description": t.description,
            "status_key": t.status_key,
            "priority_level": t.priority_level,
            "due_at": t.due_at,
            "kanban_order": t.kanban_order,
            "assignee": assignees.get(t.assignee_user_id, None),
            "case": cases_map.get(t.case_id, None)
        })
        
    return JSONResponse({"ok": True, "tasks": data})

@router.patch("/api/tasks/{task_id}/move")
async def move_task(
    task_id: int, 
    data: dict = Body(...), 
    db: Session = Depends(get_db), 
    user: AccessProfiles = Depends(get_authorized_user)
):
    if not check_user_permission(user, 'tasks', 'edit'):
        return JSONResponse({"ok": False, "error": "غير مصرح لك"}, status_code=403)
        
    task = db.query(LawTasks).filter(
        LawTasks.id == task_id, 
        LawTasks.office_id == user.office_id
    ).first()
    
    if not task:
        return JSONResponse({"ok": False, "error": "المهمة غير موجودة"}, status_code=404)
        
    new_status = data.get("status_key")
    new_order = data.get("kanban_order", 0)
    
    if new_status:
        task.status_key = new_status
    if new_order is not None:
        task.kanban_order = new_order
        
    db.commit()
    return JSONResponse({"ok": True})

@router.post("/api/tasks/reorder")
async def reorder_tasks(
    data: dict = Body(...), 
    db: Session = Depends(get_db), 
    user: AccessProfiles = Depends(get_authorized_user)
):
    if not check_user_permission(user, 'tasks', 'edit'):
        return JSONResponse({"ok": False, "error": "غير مصرح لك"}, status_code=403)
        
    updates = data.get("updates", [])
    # updates: [{"id": 1, "order": 0, "status": "pending"}, ...]
    
    for update in updates:
        t_id = update.get("id")
        t_order = update.get("order")
        t_status = update.get("status")
        
        db.query(LawTasks).filter(
            LawTasks.id == t_id, 
            LawTasks.office_id == user.office_id
        ).update({
            LawTasks.kanban_order: t_order,
            LawTasks.status_key: t_status
        }, synchronize_session=False)
        
    db.commit()
    return JSONResponse({"ok": True})

@router.get("/api/cases")
async def get_cases(db: Session = Depends(get_db), user: AccessProfiles = Depends(get_authorized_user)):
    if not check_user_permission(user, 'cases', 'view'):
        return JSONResponse({"ok": False, "error": "غير مصرح لك"}, status_code=403)
        
    cases = db.query(LawCases).filter(
        LawCases.office_id == user.office_id,
        LawCases.is_deleted == 0
    ).order_by(LawCases.updated_at.desc(), LawCases.id.desc()).all()
    
    data = []
    for c in cases:
        data.append({
            "id": c.id,
            "case_number": c.case_number,
            "title": c.title,
            "status_key": c.status_key,
            "open_date": c.open_date,
            "estimated_fee": c.estimated_fee
        })
        
    return JSONResponse({"ok": True, "cases": data})

@router.patch("/api/cases/{case_id}/move")
async def move_case(
    case_id: int, 
    data: dict = Body(...), 
    db: Session = Depends(get_db), 
    user: AccessProfiles = Depends(get_authorized_user)
):
    if not check_user_permission(user, 'cases', 'edit'):
        return JSONResponse({"ok": False, "error": "غير مصرح لك"}, status_code=403)
        
    case = db.query(LawCases).filter(
        LawCases.id == case_id, 
        LawCases.office_id == user.office_id
    ).first()
    
    if not case:
        return JSONResponse({"ok": False, "error": "القضية غير موجودة"}, status_code=404)
        
    new_status = data.get("status_key")
    if new_status:
        case.status_key = new_status
        case.updated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        db.commit()
        
    return JSONResponse({"ok": True})
