from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from sqlalchemy.orm import Session
import traceback

from database.database import get_db
from database.models import AccessProfiles, LawCases, LawExecutions
from dependencies import get_current_user, templates

router = APIRouter()


@router.get("/execution", response_class=HTMLResponse)
async def execution_page(request: Request, db: Session = Depends(get_db), user: AccessProfiles = Depends(get_current_user)):
    if not user: return RedirectResponse(url="/", status_code=303)
    try:
        import json
        office_id = user.office_id or 1
        cases = db.query(LawCases).filter(LawCases.office_id == office_id, LawCases.is_deleted == 0).all()
        records = db.query(LawExecutions).filter(LawExecutions.office_id == office_id).all()
        records_json = json.dumps([{
            "id": r.id, "case_id": r.case_id, "execution_number": r.execution_number,
            "authority_name": r.authority_name or "", "status_key": r.status_key, "request_date": r.request_date or ""
        } for r in records], ensure_ascii=False)
        return templates.TemplateResponse(request=request, name="execution.html", context={
            "user": user, "active_page": "execution", "records": records, "cases": cases, "records_json": records_json
        })
    except Exception:
        import traceback
        return HTMLResponse(content=f"<pre dir='ltr'>{traceback.format_exc()}</pre>", status_code=500)

@router.post("/api/executions/save")
async def executions_save(request: Request, db: Session = Depends(get_db), user: AccessProfiles = Depends(get_current_user)):
    from fastapi.responses import JSONResponse
    if not user: return JSONResponse({"ok": False, "message": "غير مصرح"}, status_code=401)
    try:
        data = await request.json()
        rec_id = data.get("id")
        if rec_id:
            r = db.query(LawExecutions).filter(LawExecutions.id == int(rec_id)).first()
            if not r: return JSONResponse({"ok": False, "message": "السجل غير موجود"})
            r.case_id = data.get("case_id")
            r.execution_number = data.get("execution_number")
            r.authority_name = data.get("authority_name")
            r.status_key = data.get("status_key")
            r.request_date = data.get("request_date") or None
            db.commit()
            return JSONResponse({"ok": True, "message": "تم التعديل بنجاح"})
        else:
            new_r = LawExecutions(
                office_id=user.office_id or 1, case_id=data.get("case_id"),
                execution_number=data.get("execution_number"), authority_name=data.get("authority_name"),
                status_key=data.get("status_key"), request_date=data.get("request_date") or None
            )
            db.add(new_r); db.commit()
            return JSONResponse({"ok": True, "message": "تمت الإضافة بنجاح"})
    except Exception as e:
        db.rollback()
        return JSONResponse({"ok": False, "message": str(e)})

@router.delete("/api/executions/delete/{rec_id}")
async def executions_delete(rec_id: int, db: Session = Depends(get_db), user: AccessProfiles = Depends(get_current_user)):
    from fastapi.responses import JSONResponse
    if not user: return JSONResponse({"ok": False, "message": "غير مصرح"}, status_code=401)
    r = db.query(LawExecutions).filter(LawExecutions.id == rec_id).first()
    if r: db.delete(r); db.commit()
    return JSONResponse({"ok": True, "message": "تم الحذف"})

