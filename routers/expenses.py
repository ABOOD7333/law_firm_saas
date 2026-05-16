from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from sqlalchemy.orm import Session
import traceback

from database.database import get_db
from database.models import AccessProfiles, LawCases, LawExpenses
from dependencies import get_current_user, templates

router = APIRouter()


@router.get("/expenses", response_class=HTMLResponse)
async def expenses_page(request: Request, db: Session = Depends(get_db), user: AccessProfiles = Depends(get_current_user)):
    if not user: return RedirectResponse(url="/", status_code=303)
    try:
        import json
        office_id = user.office_id or 1
        cases = db.query(LawCases).filter(LawCases.office_id == office_id, LawCases.is_deleted == 0).all()
        records = db.query(LawExpenses).filter(LawExpenses.office_id == office_id).all()
        records_json = json.dumps([{
            "id": r.id, "case_id": r.case_id, "title": r.title,
            "amount": r.amount, "expense_at": r.expense_at
        } for r in records], ensure_ascii=False)
        return templates.TemplateResponse(request=request, name="expenses.html", context={
            "user": user, "active_page": "expenses", "records": records, "cases": cases, "records_json": records_json
        })
    except Exception:
        import traceback
        return HTMLResponse(content=f"<pre dir='ltr'>{traceback.format_exc()}</pre>", status_code=500)

@router.post("/api/expenses/save")
async def expenses_save(request: Request, db: Session = Depends(get_db), user: AccessProfiles = Depends(get_current_user)):
    from fastapi.responses import JSONResponse
    if not user: return JSONResponse({"ok": False, "message": "غير مصرح"}, status_code=401)
    try:
        data = await request.json()
        rec_id = data.get("id")
        if rec_id:
            r = db.query(LawExpenses).filter(LawExpenses.id == int(rec_id), LawExpenses.office_id == (user.office_id or 1)).first()
            if not r: return JSONResponse({"ok": False, "message": "السجل غير موجود"})
            r.case_id = data.get("case_id")
            r.title = data.get("title")
            r.amount = data.get("amount", 0)
            r.expense_at = data.get("expense_at")
            db.commit()
            return JSONResponse({"ok": True, "message": "تم التعديل بنجاح"})
        else:
            new_r = LawExpenses(
                office_id=user.office_id or 1, case_id=data.get("case_id"),
                title=data.get("title"), amount=data.get("amount", 0),
                expense_at=data.get("expense_at")
            )
            db.add(new_r); db.commit()
            return JSONResponse({"ok": True, "message": "تمت الإضافة بنجاح"})
    except Exception as e:
        db.rollback()
        return JSONResponse({"ok": False, "message": str(e)})

@router.delete("/api/expenses/delete/{rec_id}")
async def expenses_delete(rec_id: int, db: Session = Depends(get_db), user: AccessProfiles = Depends(get_current_user)):
    from fastapi.responses import JSONResponse
    if not user: return JSONResponse({"ok": False, "message": "غير مصرح"}, status_code=401)
    r = db.query(LawExpenses).filter(LawExpenses.id == rec_id, LawExpenses.office_id == (user.office_id or 1)).first()
    if r: db.delete(r); db.commit()
    return JSONResponse({"ok": True, "message": "تم الحذف"})

