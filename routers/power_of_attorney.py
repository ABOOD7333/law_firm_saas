from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from sqlalchemy.orm import Session
import traceback
from core.error_handler import safe_error_html

from database.database import get_db
from database.models import AccessProfiles, LawCases, LawPowerOfAttorney
from dependencies import get_current_user, templates, require_user_permission, check_user_permission, user_can_access_case

router = APIRouter()


@router.get("/power_of_attorney", response_class=HTMLResponse)
async def poa_page(request: Request, db: Session = Depends(get_db), user: AccessProfiles = Depends(get_current_user)):
    if not user: return RedirectResponse(url="/", status_code=303)
    require_user_permission(user, "power_of_attorney", "view")
    try:
        import json
        from datetime import datetime
        cases_query = db.query(LawCases).filter(LawCases.office_id == user.office_id, LawCases.is_deleted == 0)
        if user.role in {"محامي", "محامٍ"} and not user.can_view_all_cases:
            cases_query = cases_query.filter(LawCases.lead_lawyer_id == user.id)
        case_ids = [row.id for row in cases_query.with_entities(LawCases.id).all()]
        cases = cases_query.all()
        records = db.query(LawPowerOfAttorney).filter(LawPowerOfAttorney.office_id == user.office_id, LawPowerOfAttorney.case_id.in_(case_ids)).all() if case_ids else []
        records_json = json.dumps([{
            "id": r.id, "case_id": r.case_id, "principal_name": r.principal_name,
            "agency_number": r.agency_number, "issue_date": r.issue_date or "",
            "expiry_date": r.expiry_date or "", "notes": r.notes or ""
        } for r in records], ensure_ascii=False)
        today = datetime.now().strftime("%Y-%m-%d")
        return templates.TemplateResponse(request=request, name="power_of_attorney.html", context={
            "user": user, "active_page": "power_of_attorney", "records": records, "cases": cases, "records_json": records_json, "today": today
        })
    except Exception as exc:
        return safe_error_html(exc, context="power_of_attorney.py")

@router.post("/api/poa/save")
async def poa_save(request: Request, db: Session = Depends(get_db), user: AccessProfiles = Depends(get_current_user)):
    from fastapi.responses import JSONResponse
    if not user: return JSONResponse({"ok": False, "message": "غير مصرح"}, status_code=401)
    try:
        data = await request.json()
        rec_id = data.get("id")
        action = "edit" if rec_id else "add"
        if not user.office_id or not check_user_permission(user, "power_of_attorney", action):
            return JSONResponse({"ok": False, "message": "غير مصرح"}, status_code=403)
        case_id = data.get("case_id")
        if not case_id or not user_can_access_case(db, user, int(case_id)):
            return JSONResponse({"ok": False, "message": "القضية غير متاحة"}, status_code=403)
        if rec_id:
            r = db.query(LawPowerOfAttorney).filter(LawPowerOfAttorney.id == int(rec_id), LawPowerOfAttorney.office_id == user.office_id).first()
            if not r: return JSONResponse({"ok": False, "message": "السجل غير موجود"})
            if not user_can_access_case(db, user, r.case_id): return JSONResponse({"ok": False, "message": "السجل غير موجود"}, status_code=404)
            r.case_id = data.get("case_id")
            r.principal_name = data.get("principal_name")
            r.agency_number = data.get("agency_number")
            r.issue_date = data.get("issue_date") or None
            r.expiry_date = data.get("expiry_date") or None
            r.notes = data.get("notes") or None
            db.commit()
            return JSONResponse({"ok": True, "message": "تم التعديل بنجاح"})
        else:
            new_r = LawPowerOfAttorney(
                office_id=user.office_id, case_id=case_id,
                principal_name=data.get("principal_name"), agency_number=data.get("agency_number"),
                issue_date=data.get("issue_date") or None, expiry_date=data.get("expiry_date") or None,
                notes=data.get("notes") or None
            )
            db.add(new_r); db.commit()
            return JSONResponse({"ok": True, "message": "تمت الإضافة بنجاح"})
    except Exception as e:
        db.rollback()
        return JSONResponse({"ok": False, "message": "حدث خطأ داخلي"}, status_code=500)

@router.delete("/api/poa/delete/{rec_id}")
async def poa_delete(rec_id: int, db: Session = Depends(get_db), user: AccessProfiles = Depends(get_current_user)):
    from fastapi.responses import JSONResponse
    if not user: return JSONResponse({"ok": False, "message": "غير مصرح"}, status_code=401)
    require_user_permission(user, "power_of_attorney", "delete")
    r = db.query(LawPowerOfAttorney).filter(LawPowerOfAttorney.id == rec_id, LawPowerOfAttorney.office_id == user.office_id).first()
    if r and not user_can_access_case(db, user, r.case_id): return JSONResponse({"ok": False, "message": "السجل غير موجود"}, status_code=404)
    if r: db.delete(r); db.commit()
    return JSONResponse({"ok": True, "message": "تم الحذف"})

