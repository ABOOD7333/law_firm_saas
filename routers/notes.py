from fastapi import APIRouter, Request, Depends, HTTPException, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from sqlalchemy.orm import Session
import traceback

from database.database import get_db
from database.models import AccessProfiles, LawCases, LawNotes
from dependencies import get_current_user, templates

router = APIRouter()


@router.get("/notes", response_class=HTMLResponse)
async def notes_page(request: Request, db: Session = Depends(get_db), user: AccessProfiles = Depends(get_current_user)):
    if not user: return RedirectResponse(url="/", status_code=303)
    try:
        notes = db.query(LawNotes).filter(LawNotes.office_id == (user.office_id or 1)).order_by(LawNotes.id.desc()).all()
        cases = db.query(LawCases).filter(LawCases.office_id == (user.office_id or 1), LawCases.is_deleted == 0).all()
        return templates.TemplateResponse(request=request, name="notes.html",
            context={"user": user, "notes": notes, "cases": cases, "active_page": "notes"})
    except Exception:
        import traceback
        return HTMLResponse(content=f"<pre dir='ltr'>{traceback.format_exc()}</pre>", status_code=500)

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
    office_id = user.office_id or 1
    case = db.query(LawCases).filter(LawCases.id == case_id, LawCases.office_id == office_id).first()
    if not case: return HTMLResponse(content="<script>alert('غير مصرح'); window.history.back();</script>", status_code=403)
    
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
    n = db.query(LawNotes).filter(LawNotes.id == note_id, LawNotes.office_id == (user.office_id or 1)).first()
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
    n = db.query(LawNotes).filter(LawNotes.id == note_id, LawNotes.office_id == (user.office_id or 1)).first()
    if n: db.delete(n); db.commit()
    return RedirectResponse(url="/notes", status_code=303)

