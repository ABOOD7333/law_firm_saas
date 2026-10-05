from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from sqlalchemy.orm import Session
import traceback
from core.error_handler import safe_error_html

from database.database import get_db
from database.models import AccessProfiles, LawCases, LawLegalReferences
from dependencies import get_current_user, templates, require_user_permission, check_user_permission, user_can_access_case

router = APIRouter()


@router.get("/legal_references", response_class=HTMLResponse)
async def legal_references_page(request: Request, db: Session = Depends(get_db), user: AccessProfiles = Depends(get_current_user)):
    if not user: return RedirectResponse(url="/", status_code=303)
    require_user_permission(user, "legal_references", "view")
    try:
        import json
        cases_query = db.query(LawCases).filter(LawCases.office_id == user.office_id, LawCases.is_deleted == 0)
        if user.role in {"محامي", "محامٍ"} and not user.can_view_all_cases:
            cases_query = cases_query.filter(LawCases.lead_lawyer_id == user.id)
        case_ids = [row.id for row in cases_query.with_entities(LawCases.id).all()]
        cases = cases_query.all()
        records = db.query(LawLegalReferences).filter(LawLegalReferences.office_id == user.office_id, LawLegalReferences.case_id.in_(case_ids)).all() if case_ids else []
        
        records_json = json.dumps([{
            "id": r.id, "case_id": r.case_id, "title": r.title, "reference_url": r.reference_url or ""
        } for r in records], ensure_ascii=False)
        
        return templates.TemplateResponse(request=request, name="legal_references.html", context={
            "user": user, "active_page": "legal_references", "records": records, "cases": cases, "records_json": records_json
        })
    except Exception as exc:
        return safe_error_html(exc, context="legal_references.py")

@router.post("/api/legal_references/save")
async def legal_references_save(request: Request, db: Session = Depends(get_db), user: AccessProfiles = Depends(get_current_user)):
    from fastapi.responses import JSONResponse
    if not user: return JSONResponse({"ok": False, "message": "غير مصرح"}, status_code=401)
    try:
        data = await request.json()
        rec_id = data.get("id")
        action = "edit" if rec_id else "add"
        if not user.office_id or not check_user_permission(user, "legal_references", action):
            return JSONResponse({"ok": False, "message": "غير مصرح"}, status_code=403)
        case_id = data.get("case_id")
        if not case_id or not user_can_access_case(db, user, int(case_id)):
            return JSONResponse({"ok": False, "message": "القضية غير متاحة"}, status_code=403)
        if rec_id:
            r = db.query(LawLegalReferences).filter(LawLegalReferences.id == int(rec_id), LawLegalReferences.office_id == user.office_id).first()
            if not r: return JSONResponse({"ok": False, "message": "السجل غير موجود"})
            if not user_can_access_case(db, user, r.case_id): return JSONResponse({"ok": False, "message": "السجل غير موجود"}, status_code=404)
            r.case_id = case_id
            r.title = data.get("title")
            r.reference_url = data.get("reference_url")
            db.commit()
            return JSONResponse({"ok": True, "message": "تم التعديل بنجاح"})
        else:
            new_r = LawLegalReferences(
                office_id=user.office_id,
                case_id=case_id,
                title=data.get("title"),
                reference_url=data.get("reference_url")
            )
            db.add(new_r); db.commit()
            return JSONResponse({"ok": True, "message": "تمت الإضافة بنجاح"})
    except Exception as e:
        db.rollback()
        return JSONResponse({"ok": False, "message": "حدث خطأ داخلي"}, status_code=500)

@router.delete("/api/legal_references/delete/{rec_id}")
async def legal_references_delete(rec_id: int, db: Session = Depends(get_db), user: AccessProfiles = Depends(get_current_user)):
    from fastapi.responses import JSONResponse
    if not user: return JSONResponse({"ok": False, "message": "غير مصرح"}, status_code=401)
    require_user_permission(user, "legal_references", "delete")
    r = db.query(LawLegalReferences).filter(LawLegalReferences.id == rec_id, LawLegalReferences.office_id == user.office_id).first()
    if not r: return JSONResponse({"ok": False, "message": "السجل غير موجود"})
    if not user_can_access_case(db, user, r.case_id): return JSONResponse({"ok": False, "message": "السجل غير موجود"}, status_code=404)
    db.delete(r); db.commit()
    return JSONResponse({"ok": True, "message": "تم الحذف بنجاح"})
