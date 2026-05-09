from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from sqlalchemy.orm import Session
import traceback

from database.database import get_db
from database.models import AccessProfiles, LawCases, LawTimesheets
from dependencies import get_current_user, templates

router = APIRouter()


@router.get("/timesheet", response_class=HTMLResponse)
async def timesheet_page(request: Request, db: Session = Depends(get_db), user: AccessProfiles = Depends(get_current_user)):
    if not user: return RedirectResponse(url="/", status_code=303)
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
    except Exception:
        import traceback
        return HTMLResponse(content=f"<pre dir='ltr'>{traceback.format_exc()}</pre>", status_code=500)

@router.post("/api/timesheets/save")
async def timesheets_save(request: Request, db: Session = Depends(get_db), user: AccessProfiles = Depends(get_current_user)):
    from fastapi.responses import JSONResponse
    if not user: return JSONResponse({"ok": False, "message": "غير مصرح"}, status_code=401)
    try:
        data = await request.json()
        rec_id = data.get("id")
        if rec_id:
            r = db.query(LawTimesheets).filter(LawTimesheets.id == int(rec_id), LawTimesheets.office_id == (user.office_id or 1)).first()
            if not r: return JSONResponse({"ok": False, "message": "السجل غير موجود"})
            r.case_id = data.get("case_id")
            r.title = data.get("title")
            r.duration_hours = data.get("duration_hours", 0)
            r.billable_rate = data.get("billable_rate", 0)
            r.user_id = data.get("user_id") or user.id
            db.commit()
            return JSONResponse({"ok": True, "message": "تم التعديل بنجاح"})
        else:
            new_r = LawTimesheets(
                office_id=user.office_id or 1, case_id=data.get("case_id"),
                title=data.get("title"), duration_hours=data.get("duration_hours", 0),
                billable_rate=data.get("billable_rate", 0), user_id=data.get("user_id") or user.id
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
    r = db.query(LawTimesheets).filter(LawTimesheets.id == rec_id, LawTimesheets.office_id == (user.office_id or 1)).first()
    if r: db.delete(r); db.commit()
    return JSONResponse({"ok": True, "message": "تم الحذف"})

