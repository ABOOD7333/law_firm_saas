from fastapi import APIRouter, Request, Depends, HTTPException, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from sqlalchemy.orm import Session
import traceback
from core.error_handler import safe_error_html

from database.database import get_db
from database.models import AccessProfiles, LawCases, LawNotes
from dependencies import get_current_user, templates, require_user_permission, user_can_access_case

router = APIRouter()


@router.get("/notes", response_class=HTMLResponse)
async def notes_page(request: Request, db: Session = Depends(get_db), user: AccessProfiles = Depends(get_current_user)):
    if not user: return RedirectResponse(url="/", status_code=303)
    require_user_permission(user, "notes", "view")
    try:
        cases_query = db.query(LawCases).filter(LawCases.office_id == user.office_id, LawCases.is_deleted == 0)
        if user.role in {"محامي", "محامٍ"} and not user.can_view_all_cases:
            cases_query = cases_query.filter(LawCases.lead_lawyer_id == user.id)
        case_ids = [row.id for row in cases_query.with_entities(LawCases.id).all()]
        notes = db.query(LawNotes).filter(LawNotes.office_id == user.office_id, LawNotes.case_id.in_(case_ids)).order_by(LawNotes.id.desc()).all() if case_ids else []
        cases = cases_query.all()
        return templates.TemplateResponse(request=request, name="notes.html",
            context={"user": user, "notes": notes, "cases": cases, "active_page": "notes"})
    except Exception as exc:
        return safe_error_html(exc, context="notes.py")

@router.post("/notes/add")
async def add_note(
    request: Request,
    case_id: int = Form(...),
    title: str = Form(...),
    note_type_key: str = Form(None),
    content: str = Form(None),
    db: Session = Depends(get_db),
    user: AccessProfiles = Depends(get_current_user)
):
    if not user: return RedirectResponse(url="/", status_code=303)
    require_user_permission(user, "notes", "add")
    office_id = user.office_id
    if not user_can_access_case(db, user, case_id): return HTMLResponse(content="<script>alert('غير مصرح'); window.history.back();</script>", status_code=403)
    
    note = LawNotes(case_id=case_id, office_id=office_id,
        title=title, note_type_key=note_type_key, content=content)
    db.add(note); db.commit()
    return RedirectResponse(url="/notes", status_code=303)

@router.post("/notes/edit")
async def edit_note(
    request: Request,
    note_id: int = Form(...),
    title: str = Form(...),
    note_type_key: str = Form(None),
    content: str = Form(None),
    db: Session = Depends(get_db),
    user: AccessProfiles = Depends(get_current_user)
):
    if not user: return RedirectResponse(url="/", status_code=303)
    require_user_permission(user, "notes", "edit")
    n = db.query(LawNotes).filter(LawNotes.id == note_id, LawNotes.office_id == user.office_id).first()
    if not n or not user_can_access_case(db, user, n.case_id): raise HTTPException(status_code=403, detail="غير مصرح بتعديل هذه الملاحظة")
    if n:
        n.title = title; n.note_type_key = note_type_key; n.content = content
        db.commit()
    return RedirectResponse(url="/notes", status_code=303)

@router.post("/notes/delete")
async def delete_note(
    request: Request,
    note_id: int = Form(...),
    db: Session = Depends(get_db),
    user: AccessProfiles = Depends(get_current_user)
):
    if not user: return RedirectResponse(url="/", status_code=303)
    require_user_permission(user, "notes", "delete")
    n = db.query(LawNotes).filter(LawNotes.id == note_id, LawNotes.office_id == user.office_id).first()
    if not n or not user_can_access_case(db, user, n.case_id): raise HTTPException(status_code=403, detail="غير مصرح بحذف هذه الملاحظة")
    if n: db.delete(n); db.commit()
    return RedirectResponse(url="/notes", status_code=303)

