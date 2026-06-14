from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from sqlalchemy.orm import Session
import traceback
from core.error_handler import safe_error_html

from database.database import get_db
from database.models import AccessProfiles, LawCases, LawTimesheets
from dependencies import get_current_user, templates, check_user_permission

router = APIRouter()


@router.get("/timesheet", response_class=HTMLResponse)
async def timesheet_page(request: Request, db: Session = Depends(get_db), user: AccessProfiles = Depends(get_current_user)):
    if not user: return RedirectResponse(url="/", status_code=303)
    if not check_user_permission(user, 'timesheet', 'view'):
        return HTMLResponse(content="<script>alert('غير مصرح لك بدخول قسم سجل الساعات'); window.location.href='/dashboard';</script>", status_code=403)
    try:
        import json
        office_id = user.office_id or 1
        cases = db.query(LawCases).filter(LawCases.office_id == office_id, LawCases.is_deleted == 0).all()
        users = db.query(AccessProfiles).filter(AccessProfiles.office_id == office_id, AccessProfiles.is_active == 1).all()
        records = db.query(LawTimesheets).filter(LawTimesheets.office_id == office_id).all()
        records_json = json.dumps([{
            "id": r.id, "case_id": r.case_id, "title": r.title,
            "duration_hours": r.duration_hours, "billable_rate": r.billable_rate, "user_id": r.user_id
        } for r in records], ensure_ascii=False)
        return templates.TemplateResponse(request=request, name="timesheet.html", context={
            "user": user, "active_page": "timesheet", "records": records, "cases": cases, "users": users, "records_json": records_json
        })
    except Exception as exc:
        return safe_error_html(exc, context="timesheet.py")

@router.post("/api/timesheets/save")
async def timesheets_save(request: Request, db: Session = Depends(get_db), user: AccessProfiles = Depends(get_current_user)):
    from fastapi.responses import JSONResponse
    if not user: return JSONResponse({"ok": False, "message": "غير مصرح"}, status_code=401)
    try:
        data = await request.json()
        rec_id = data.get("id")
        case_id = data.get("case_id")
        target_user_id = data.get("user_id") or user.id
        office_id = user.office_id or 1
        
        if rec_id:
            if not check_user_permission(user, 'timesheet', 'edit'):
                return JSONResponse({"ok": False, "message": "غير مصرح لك بتعديل الساعات"})
        else:
            if not check_user_permission(user, 'timesheet', 'add'):
                return JSONResponse({"ok": False, "message": "غير مصرح لك بإضافة الساعات"})

        # 1. Validate Case and Lawyer Permission
        if case_id:
            case = db.query(LawCases).filter(LawCases.id == int(case_id), LawCases.office_id == office_id).first()
            if not case:
                return JSONResponse({"ok": False, "message": "القضية المحددة غير موجودة أو لا تتبع لمكتبك"})
            if user.role in ['محامي', 'محامٍ'] and user.can_view_all_cases == 0 and case.lead_lawyer_id != user.id:
                return JSONResponse({"ok": False, "message": "غير مصرح لك بإضافة أو تعديل ساعات العمل لهذه القضية"})
        else:
            return JSONResponse({"ok": False, "message": "يجب تحديد قضية مرتبطة"})

        # 2. Validate target user belongs to same office
        assigned_user = db.query(AccessProfiles).filter(AccessProfiles.id == int(target_user_id), AccessProfiles.office_id == office_id).first()
        if not assigned_user:
            return JSONResponse({"ok": False, "message": "المستخدم المعين غير موجود في هذا المكتب"})

        if rec_id:
            r = db.query(LawTimesheets).filter(LawTimesheets.id == int(rec_id), LawTimesheets.office_id == office_id).first()
            if not r: return JSONResponse({"ok": False, "message": "السجل غير موجود"})
            r.case_id = case_id
            r.title = data.get("title")
            r.duration_hours = data.get("duration_hours", 0)
            r.billable_rate = data.get("billable_rate", 0)
            r.user_id = assigned_user.id
            db.commit()
            return JSONResponse({"ok": True, "message": "تم التعديل بنجاح"})
        else:
            new_r = LawTimesheets(
                office_id=office_id, case_id=case_id,
                title=data.get("title"), duration_hours=data.get("duration_hours", 0),
                billable_rate=data.get("billable_rate", 0), user_id=assigned_user.id
            )
            db.add(new_r); db.commit()
            return JSONResponse({"ok": True, "message": "تمت الإضافة بنجاح"})
    except Exception as e:
        db.rollback()
        return JSONResponse({"ok": False, "message": str(e)})

@router.delete("/api/timesheets/delete/{rec_id}")
async def timesheets_delete(rec_id: int, db: Session = Depends(get_db), user: AccessProfiles = Depends(get_current_user)):
    from fastapi.responses import JSONResponse
    if not user: return JSONResponse({"ok": False, "message": "غير مصرح"}, status_code=401)
    if not check_user_permission(user, 'timesheet', 'delete'):
        return JSONResponse({"ok": False, "message": "غير مصرح لك بحذف الساعات"})
    office_id = user.office_id or 1
    r = db.query(LawTimesheets).filter(LawTimesheets.id == rec_id, LawTimesheets.office_id == office_id).first()
    if r:
        # Check lawyer case visibility permission
        case = db.query(LawCases).filter(LawCases.id == r.case_id).first()
        if case and user.role in ['محامي', 'محامٍ'] and user.can_view_all_cases == 0 and case.lead_lawyer_id != user.id:
            return JSONResponse({"ok": False, "message": "غير مصرح لك بحذف ساعات العمل هذه"})
        db.delete(r); db.commit()
    return JSONResponse({"ok": True, "message": "تم الحذف"})

