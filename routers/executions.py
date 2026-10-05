from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from sqlalchemy.orm import Session
import traceback
from core.error_handler import safe_error_html

from database.database import get_db
from database.models import AccessProfiles, LawCases, LawExecutions
from dependencies import get_current_user, templates, require_user_permission, check_user_permission, user_can_access_case

router = APIRouter()


@router.get("/execution", response_class=HTMLResponse)
async def execution_page(request: Request, db: Session = Depends(get_db), user: AccessProfiles = Depends(get_current_user)):
    if not user: return RedirectResponse(url="/", status_code=303)
    require_user_permission(user, "execution", "view")
    try:
        import json
        cases_query = db.query(LawCases).filter(LawCases.office_id == user.office_id, LawCases.is_deleted == 0)
        if user.role in {"محامي", "محامٍ"} and not user.can_view_all_cases:
            cases_query = cases_query.filter(LawCases.lead_lawyer_id == user.id)
        case_ids = [row.id for row in cases_query.with_entities(LawCases.id).all()]
        cases = cases_query.all()
        records = db.query(LawExecutions).filter(LawExecutions.office_id == user.office_id, LawExecutions.case_id.in_(case_ids)).all() if case_ids else []
        records_json = json.dumps([{
            "id": r.id, "case_id": r.case_id, "execution_number": r.execution_number,
            "authority_name": r.authority_name or "", "status_key": r.status_key, "request_date": r.request_date or ""
        } for r in records], ensure_ascii=False)
        return templates.TemplateResponse(request=request, name="execution.html", context={
            "user": user, "active_page": "execution", "records": records, "cases": cases, "records_json": records_json
        })
    except Exception as exc:
        return safe_error_html(exc, context="executions.py")

@router.post("/api/executions/save")
async def executions_save(request: Request, db: Session = Depends(get_db), user: AccessProfiles = Depends(get_current_user)):
    from fastapi.responses import JSONResponse
    if not user: return JSONResponse({"ok": False, "message": "غير مصرح"}, status_code=401)
    try:
        data = await request.json()
        rec_id = data.get("id")
        action = "edit" if rec_id else "add"
        if not user.office_id or not check_user_permission(user, "execution", action):
            return JSONResponse({"ok": False, "message": "غير مصرح"}, status_code=403)
        case_id = data.get("case_id")
        if not case_id or not user_can_access_case(db, user, int(case_id)):
            return JSONResponse({"ok": False, "message": "القضية غير متاحة"}, status_code=403)
        if rec_id:
            r = db.query(LawExecutions).filter(LawExecutions.id == int(rec_id), LawExecutions.office_id == user.office_id).first()
            if not r: return JSONResponse({"ok": False, "message": "السجل غير موجود"})
            if not user_can_access_case(db, user, r.case_id): return JSONResponse({"ok": False, "message": "السجل غير موجود"}, status_code=404)
            r.case_id = data.get("case_id")
            r.execution_number = data.get("execution_number")
            r.authority_name = data.get("authority_name")
            r.status_key = data.get("status_key")
            r.request_date = data.get("request_date") or None
            db.commit()
            return JSONResponse({"ok": True, "message": "تم التعديل بنجاح"})
        else:
            new_r = LawExecutions(
                office_id=user.office_id, case_id=case_id,
                execution_number=data.get("execution_number"), authority_name=data.get("authority_name"),
                status_key=data.get("status_key"), request_date=data.get("request_date") or None
            )
            db.add(new_r); db.commit()
            return JSONResponse({"ok": True, "message": "تمت الإضافة بنجاح"})
    except Exception as e:
        db.rollback()
        return JSONResponse({"ok": False, "message": "حدث خطأ داخلي"}, status_code=500)

@router.delete("/api/executions/delete/{rec_id}")
async def executions_delete(rec_id: int, db: Session = Depends(get_db), user: AccessProfiles = Depends(get_current_user)):
    from fastapi.responses import JSONResponse
    if not user: return JSONResponse({"ok": False, "message": "غير مصرح"}, status_code=401)
    require_user_permission(user, "execution", "delete")
    r = db.query(LawExecutions).filter(LawExecutions.id == rec_id, LawExecutions.office_id == user.office_id).first()
    if r and not user_can_access_case(db, user, r.case_id): return JSONResponse({"ok": False, "message": "السجل غير موجود"}, status_code=404)
    if r: db.delete(r); db.commit()
    return JSONResponse({"ok": True, "message": "تم الحذف"})

