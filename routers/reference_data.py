from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from sqlalchemy.orm import Session
import traceback

from database.database import get_db
from database.models import AccessProfiles, LawReferenceData
from dependencies import get_current_user, templates

router = APIRouter()


@router.get("/reference_data", response_class=HTMLResponse)
async def reference_data_page(request: Request, db: Session = Depends(get_db), user: AccessProfiles = Depends(get_current_user)):
    if not user: return RedirectResponse(url="/", status_code=303)
    try:
        import json
        office_id = user.office_id or 1
        records = db.query(LawReferenceData).filter(LawReferenceData.office_id == office_id).all()
        records_json = json.dumps([{
            "id": r.id, "ref_type": r.ref_type, "ref_name": r.ref_name, "notes": r.notes or ""
        } for r in records], ensure_ascii=False)
        return templates.TemplateResponse(request=request, name="reference_data.html", context={
            "user": user, "active_page": "reference_data", "records": records, "records_json": records_json
        })
    except Exception:
        import traceback
        return HTMLResponse(content=f"<pre dir='ltr'>{traceback.format_exc()}</pre>", status_code=500)

@router.post("/api/refdata/save")
async def refdata_save(request: Request, db: Session = Depends(get_db), user: AccessProfiles = Depends(get_current_user)):
    from fastapi.responses import JSONResponse
    if not user: return JSONResponse({"ok": False, "message": "غير مصرح"}, status_code=401)
    try:
        data = await request.json()
        office_id = user.office_id or 1
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
        return JSONResponse({"ok": False, "message": str(e)})

@router.delete("/api/refdata/delete/{rec_id}")
async def refdata_delete(rec_id: int, db: Session = Depends(get_db), user: AccessProfiles = Depends(get_current_user)):
    from fastapi.responses import JSONResponse
    if not user: return JSONResponse({"ok": False, "message": "غير مصرح"}, status_code=401)
    r = db.query(LawReferenceData).filter(LawReferenceData.id == rec_id, LawReferenceData.office_id == (user.office_id or 1)).first()
    if not r: return JSONResponse({"ok": False, "message": "السجل غير موجود أو غير مصرح"})
    db.delete(r); db.commit()
    return JSONResponse({"ok": True, "message": "تم الحذف بنجاح"})


