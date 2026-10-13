from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from sqlalchemy.orm import Session
import traceback
from core.error_handler import safe_error_html

from database.database import get_db
from database.models import AccessProfiles, LawReferenceData
from dependencies import get_current_user, templates, check_user_permission

router = APIRouter()


@router.get("/reference_data", response_class=HTMLResponse)
async def reference_data_page(request: Request, db: Session = Depends(get_db), user: AccessProfiles = Depends(get_current_user)):
    if not user: return RedirectResponse(url="/", status_code=303)
    if not check_user_permission(user, "reference_data", "view"):
        raise HTTPException(status_code=403, detail="غير مصرح بعرض البيانات المرجعية")
    try:
        import json
        office_id = user.office_id
        records = db.query(LawReferenceData).filter(LawReferenceData.office_id == office_id).all()
        records_json = json.dumps([{
            "id": r.id, "ref_type": r.ref_type, "ref_name": r.ref_name, "notes": r.notes or ""
        } for r in records], ensure_ascii=False)
        return templates.TemplateResponse(request=request, name="reference_data.html", context={
            "user": user, "active_page": "reference_data", "records": records, "records_json": records_json
        })
    except Exception as exc:
        return safe_error_html(exc, context="reference_data.py")

@router.post("/api/refdata/save")
async def refdata_save(request: Request, db: Session = Depends(get_db), user: AccessProfiles = Depends(get_current_user)):
    from fastapi.responses import JSONResponse
    if not user: return JSONResponse({"ok": False, "message": "غير مصرح"}, status_code=401)
    try:
        data = await request.json()
        action = "edit" if data.get("id") else "add"
        if not user.office_id or not check_user_permission(user, "reference_data", action):
            return JSONResponse({"ok": False, "message": "غير مصرح بهذا الإجراء"}, status_code=403)
        office_id = user.office_id
        rec_id = data.get("id")
        if rec_id:
            r = db.query(LawReferenceData).filter(LawReferenceData.id == int(rec_id), LawReferenceData.office_id == office_id).first()
            if not r: return JSONResponse({"ok": False, "message": "السجل غير موجود أو غير مصرح"})
            r.ref_type = data.get("ref_type")
            r.ref_name = data.get("ref_name")
            r.notes = data.get("notes")
            db.commit()
            return JSONResponse({"ok": True, "message": "تم التعديل بنجاح"})
        else:
            new_r = LawReferenceData(
                office_id=office_id,
                ref_type=data.get("ref_type"),
                ref_name=data.get("ref_name"),
                notes=data.get("notes")
            )
            db.add(new_r); db.commit()
            return JSONResponse({"ok": True, "message": "تمت الإضافة بنجاح"})
    except Exception as e:
        db.rollback()
        return JSONResponse({"ok": False, "message": "حدث خطأ داخلي"}, status_code=500)

@router.delete("/api/refdata/delete/{rec_id}")
async def refdata_delete(rec_id: int, db: Session = Depends(get_db), user: AccessProfiles = Depends(get_current_user)):
    from fastapi.responses import JSONResponse
    if not user: return JSONResponse({"ok": False, "message": "غير مصرح"}, status_code=401)
    if not check_user_permission(user, "reference_data", "delete"):
        return JSONResponse({"ok": False, "message": "غير مصرح بالحذف"}, status_code=403)
    r = db.query(LawReferenceData).filter(LawReferenceData.id == rec_id, LawReferenceData.office_id == user.office_id).first()
    if not r: return JSONResponse({"ok": False, "message": "السجل غير موجود أو غير مصرح"})
    db.delete(r); db.commit()
    return JSONResponse({"ok": True, "message": "تم الحذف بنجاح"})

@router.get("/api/refdata/list/{ref_type}")
async def refdata_list(ref_type: str, db: Session = Depends(get_db), user: AccessProfiles = Depends(get_current_user)):
    from fastapi.responses import JSONResponse
    if not user: return JSONResponse([], status_code=401)
    if not check_user_permission(user, "reference_data", "view"):
        return JSONResponse({"ok": False, "message": "غير مصرح"}, status_code=403)
    office_id = user.office_id
    records = db.query(LawReferenceData).filter(LawReferenceData.office_id == office_id, LawReferenceData.ref_type == ref_type).all()
    return JSONResponse([r.ref_name for r in records])


