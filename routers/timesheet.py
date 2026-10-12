from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from sqlalchemy.orm import Session
from datetime import datetime
import json
import traceback
from core.error_handler import safe_error_html

from database.database import get_db
from database.models import AccessProfiles, LawCases, LawTimesheets
from dependencies import get_current_user, templates, check_user_permission

router = APIRouter()

@router.get("/timesheet", response_class=HTMLResponse)
async def timesheet_page(request: Request, db: Session = Depends(get_db), user: AccessProfiles = Depends(get_current_user)):
    if not user:
        return RedirectResponse(url="/", status_code=303)
    if not check_user_permission(user, 'timesheet', 'view'):
        raise HTTPException(status_code=403, detail="غير مصرح لك بدخول قسم سجل الساعات")
    try:
        office_id = user.office_id
        cases = db.query(LawCases).filter(LawCases.office_id == office_id, LawCases.is_deleted == 0).order_by(LawCases.case_number.asc()).all()
        users = db.query(AccessProfiles).filter(AccessProfiles.office_id == office_id, AccessProfiles.is_active == 1).order_by(AccessProfiles.name.asc()).all()
        records = db.query(LawTimesheets).filter(
            LawTimesheets.office_id == office_id,
            LawTimesheets.is_deleted == 0
        ).order_by(LawTimesheets.created_at.desc(), LawTimesheets.id.desc()).all()

        # Users mapping for display
        users_map = {u.id: u.name for u in users}

        # KPIs calculations
        total_hours = sum((r.duration_hours or 0.0) for r in records)
        total_value = sum(((r.duration_hours or 0.0) * (r.billable_rate or 0.0)) for r in records)
        unbilled_records = [r for r in records if getattr(r, 'is_billed', 0) == 0]
        unbilled_hours = sum((r.duration_hours or 0.0) for r in unbilled_records)
        unbilled_value = sum(((r.duration_hours or 0.0) * (r.billable_rate or 0.0)) for r in unbilled_records)
        billed_records = [r for r in records if getattr(r, 'is_billed', 0) == 1]

        stats = {
            "total_hours": round(total_hours, 2),
            "total_value": total_value,
            "unbilled_hours": round(unbilled_hours, 2),
            "unbilled_value": unbilled_value,
            "total_count": len(records),
            "unbilled_count": len(unbilled_records),
            "billed_count": len(billed_records)
        }

        records_json = json.dumps([{
            "id": r.id,
            "case_id": r.case_id,
            "case_number": r.law_case.case_number if r.law_case else "",
            "case_title": r.law_case.title if r.law_case else "",
            "title": r.title,
            "duration_hours": r.duration_hours,
            "billable_rate": r.billable_rate,
            "total_amount": round((r.duration_hours or 0.0) * (r.billable_rate or 0.0), 2),
            "user_id": r.user_id,
            "user_name": users_map.get(r.user_id, "غير محدد"),
            "work_date": getattr(r, 'work_date', '') or (r.created_at or '')[:10],
            "is_billed": getattr(r, 'is_billed', 0) or 0,
            "notes": getattr(r, 'notes', '') or ""
        } for r in records], ensure_ascii=False)

        return templates.TemplateResponse(request=request, name="timesheet.html", context={
            "user": user,
            "active_page": "timesheet",
            "records": records,
            "cases": cases,
            "users": users,
            "users_map": users_map,
            "stats": stats,
            "records_json": records_json
        })
    except Exception as exc:
        return safe_error_html(exc, context="timesheet.py")

@router.get("/api/timesheets/{rec_id}")
async def timesheets_get(rec_id: int, db: Session = Depends(get_db), user: AccessProfiles = Depends(get_current_user)):
    if not user:
        return JSONResponse({"ok": False, "message": "غير مصرح"}, status_code=401)
    office_id = user.office_id
    r = db.query(LawTimesheets).filter(
        LawTimesheets.id == rec_id,
        LawTimesheets.office_id == office_id,
        LawTimesheets.is_deleted == 0
    ).first()
    if not r:
        return JSONResponse({"ok": False, "message": "السجل غير موجود"}, status_code=404)

    return JSONResponse({
        "ok": True,
        "data": {
            "id": r.id,
            "case_id": r.case_id,
            "case_number": r.law_case.case_number if r.law_case else "",
            "title": r.title,
            "duration_hours": r.duration_hours,
            "billable_rate": r.billable_rate,
            "user_id": r.user_id,
            "work_date": getattr(r, 'work_date', '') or (r.created_at or '')[:10],
            "is_billed": getattr(r, 'is_billed', 0) or 0,
            "notes": getattr(r, 'notes', '') or ""
        }
    })

@router.post("/api/timesheets/save")
async def timesheets_save(request: Request, db: Session = Depends(get_db), user: AccessProfiles = Depends(get_current_user)):
    if not user:
        return JSONResponse({"ok": False, "message": "غير مصرح"}, status_code=401)
    try:
        data = await request.json()
        rec_id = data.get("id")
        case_id = data.get("case_id")
        target_user_id = data.get("user_id") or user.id
        office_id = user.office_id
        
        if rec_id:
            if not check_user_permission(user, 'timesheet', 'edit'):
                return JSONResponse({"ok": False, "message": "غير مصرح لك بتعديل الساعات"})
        else:
            if not check_user_permission(user, 'timesheet', 'add'):
                return JSONResponse({"ok": False, "message": "غير مصرح لك بإضافة الساعات"})

        if case_id:
            case = db.query(LawCases).filter(LawCases.id == int(case_id), LawCases.office_id == office_id, LawCases.is_deleted == 0).first()
            if not case:
                return JSONResponse({"ok": False, "message": "القضية المحددة غير موجودة أو لا تتبع لمكتبك"})
            if user.role in ['محامي', 'محامٍ'] and getattr(user, 'can_view_all_cases', 1) == 0 and case.lead_lawyer_id != user.id:
                return JSONResponse({"ok": False, "message": "غير مصرح لك بإضافة أو تعديل ساعات العمل لهذه القضية"})
        else:
            return JSONResponse({"ok": False, "message": "يجب تحديد قضية مرتبطة بسجل الساعات"})

        assigned_user = db.query(AccessProfiles).filter(AccessProfiles.id == int(target_user_id), AccessProfiles.office_id == office_id).first()
        if not assigned_user:
            return JSONResponse({"ok": False, "message": "المستخدم المعين غير موجود في هذا المكتب"})

        title = str(data.get("title") or "").strip()
        if not title:
            return JSONResponse({"ok": False, "message": "بيان أو وصف المهمة مطلوب"})

        try:
            duration_hours = float(data.get("duration_hours") or 0.0)
            billable_rate = float(data.get("billable_rate") or 0.0)
        except (ValueError, TypeError):
            return JSONResponse({"ok": False, "message": "القيم العددية للساعات أو المعدل غير صالحة"})

        if duration_hours <= 0:
            return JSONResponse({"ok": False, "message": "يجب أن تكون الساعات المستغرقة أكبر من الصفر"})

        work_date = data.get("work_date") or datetime.now().strftime("%Y-%m-%d")
        is_billed = 1 if data.get("is_billed") in [1, True, "1", "true"] else 0
        notes = data.get("notes") or None

        if rec_id:
            r = db.query(LawTimesheets).filter(
                LawTimesheets.id == int(rec_id),
                LawTimesheets.office_id == office_id,
                LawTimesheets.is_deleted == 0
            ).first()
            if not r:
                return JSONResponse({"ok": False, "message": "السجل غير موجود"})
            r.case_id = int(case_id)
            r.title = title
            r.duration_hours = duration_hours
            r.billable_rate = billable_rate
            r.user_id = assigned_user.id
            r.work_date = work_date
            r.is_billed = is_billed
            r.notes = notes
            r.updated_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
            db.commit()
            return JSONResponse({"ok": True, "message": "تم تحديث سجل الساعات بنجاح", "id": r.id})
        else:
            new_r = LawTimesheets(
                office_id=office_id,
                case_id=int(case_id),
                title=title,
                duration_hours=duration_hours,
                billable_rate=billable_rate,
                user_id=assigned_user.id,
                work_date=work_date,
                is_billed=is_billed,
                notes=notes,
                is_deleted=0
            )
            db.add(new_r)
            db.commit()
            return JSONResponse({"ok": True, "message": "تم تسجيل ساعات العمل بنجاح", "id": new_r.id})
    except Exception as e:
        db.rollback()
        return JSONResponse({"ok": False, "message": f"حدث خطأ داخلي: {str(e)}"}, status_code=500)

@router.post("/api/timesheets/{rec_id}/toggle-billed")
async def timesheets_toggle_billed(rec_id: int, db: Session = Depends(get_db), user: AccessProfiles = Depends(get_current_user)):
    if not user:
        return JSONResponse({"ok": False, "message": "غير مصرح"}, status_code=401)
    r = db.query(LawTimesheets).filter(
        LawTimesheets.id == rec_id,
        LawTimesheets.office_id == user.office_id,
        LawTimesheets.is_deleted == 0
    ).first()
    if not r:
        return JSONResponse({"ok": False, "message": "السجل غير موجود"}, status_code=404)

    current_val = getattr(r, 'is_billed', 0) or 0
    new_val = 0 if current_val == 1 else 1
    r.is_billed = new_val
    db.commit()
    return JSONResponse({
        "ok": True,
        "message": "تم تحديث حالة الفوترة بنجاح",
        "is_billed": new_val
    })

@router.delete("/api/timesheets/delete/{rec_id}")
async def timesheets_delete(rec_id: int, db: Session = Depends(get_db), user: AccessProfiles = Depends(get_current_user)):
    if not user:
        return JSONResponse({"ok": False, "message": "غير مصرح"}, status_code=401)
    if not check_user_permission(user, 'timesheet', 'delete'):
        return JSONResponse({"ok": False, "message": "غير مصرح لك بحذف الساعات"})
    office_id = user.office_id
    r = db.query(LawTimesheets).filter(
        LawTimesheets.id == rec_id,
        LawTimesheets.office_id == office_id,
        LawTimesheets.is_deleted == 0
    ).first()
    if not r:
        return JSONResponse({"ok": False, "message": "السجل غير موجود"})

    case = db.query(LawCases).filter(LawCases.id == r.case_id).first()
    if case and user.role in ['محامي', 'محامٍ'] and getattr(user, 'can_view_all_cases', 1) == 0 and case.lead_lawyer_id != user.id:
        return JSONResponse({"ok": False, "message": "غير مصرح لك بحذف ساعات العمل هذه"})

    r.is_deleted = 1
    r.updated_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    db.commit()
    return JSONResponse({"ok": True, "message": "تم حذف سجل الساعات بنجاح"})
