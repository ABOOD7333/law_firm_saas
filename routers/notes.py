import os
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Request, Depends, HTTPException, Form, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse, FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
import traceback
from core.error_handler import safe_error_html

from database.database import get_db
from database.models import AccessProfiles, LawCases, LawNotes, LawTasks
from dependencies import get_current_user, templates, require_user_permission, user_can_access_case
from core.upload_security import save_upload

router = APIRouter()

@router.get("/notes/{note_id}/attachment")
async def download_note_attachment(note_id: int, db: Session = Depends(get_db), user: AccessProfiles = Depends(get_current_user)):
    if not user or not user.office_id:
        raise HTTPException(status_code=401, detail="غير مصرح")
    if user.role == "موكل":
        raise HTTPException(status_code=403, detail="غير مصرح بتنزيل هذا الملف")
    require_user_permission(user, "notes", "view")
    note = db.query(LawNotes).filter(
        LawNotes.id == note_id,
        LawNotes.office_id == user.office_id,
        LawNotes.is_deleted == 0,
    ).first()
    if not note:
        raise HTTPException(status_code=404, detail="الملاحظة غير موجودة")
    if note.case_id and not user_can_access_case(db, user, note.case_id):
        raise HTTPException(status_code=403, detail="غير مصرح بهذه القضية")
    if not note.attachment_path:
        raise HTTPException(status_code=404, detail="لا يوجد ملف مرفق")
    root = os.path.realpath(UPLOAD_DIR)
    path = os.path.realpath(note.attachment_path.lstrip("/"))
    if os.path.commonpath([root, path]) != root or not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="الملف غير موجود")
    return FileResponse(path, filename=os.path.basename(path), headers={"Cache-Control": "private, no-store"})

UPLOAD_DIR = os.path.join("static", "uploads", "notes")
os.makedirs(UPLOAD_DIR, exist_ok=True)


@router.get("/notes", response_class=HTMLResponse)
async def notes_page(
    request: Request,
    case_id: Optional[int] = None,
    channel: Optional[str] = None,
    priority: Optional[str] = None,
    db: Session = Depends(get_db),
    user: AccessProfiles = Depends(get_current_user)
):
    if not user:
        return RedirectResponse(url="/", status_code=303)
    require_user_permission(user, "notes", "view")
    try:
        # Multi-tenant base query
        query = db.query(LawNotes).filter(
            LawNotes.office_id == user.office_id,
            LawNotes.is_deleted == 0
        )
        if user.role in {"محامي", "محامٍ"} and not getattr(user, "can_view_all_cases", 0):
            visible_case_ids = db.query(LawCases.id).filter(
                LawCases.office_id == user.office_id,
                LawCases.lead_lawyer_id == user.id,
                LawCases.is_deleted == 0,
            ).subquery()
            query = query.filter(LawNotes.case_id.in_(visible_case_ids))

        if case_id:
            query = query.filter(LawNotes.case_id == case_id)
        if channel:
            query = query.filter(LawNotes.communication_channel == channel)
        if priority:
            query = query.filter(LawNotes.priority_level == priority)

        # Ordering: pinned first, then newest
        notes = query.order_by(LawNotes.is_pinned.desc(), LawNotes.id.desc()).all()

        # All non-deleted notes for office KPI calculation
        all_office_notes = db.query(LawNotes).filter(
            LawNotes.office_id == user.office_id,
            LawNotes.is_deleted == 0
        ).all()
        if user.role in {"محامي", "محامٍ"} and not getattr(user, "can_view_all_cases", 0):
            all_office_notes = [n for n in all_office_notes if n.case_id and user_can_access_case(db, user, n.case_id)]

        # KPIs
        total_notes = len(all_office_notes)
        phone_calls_count = sum(1 for n in all_office_notes if n.communication_channel in ['phone_call', 'مكالمة هاتفية', 'مكالمة واردة', 'مكالمة صادرة'])
        meetings_count = sum(1 for n in all_office_notes if n.communication_channel in ['client_meeting', 'اجتماع', 'لقاء'])
        total_minutes = sum(n.call_duration_minutes or 0 for n in all_office_notes)
        pinned_count = sum(1 for n in all_office_notes if n.is_pinned == 1)
        billable_count = sum(1 for n in all_office_notes if n.is_billable == 1)

        kpis = {
            "total_notes": total_notes,
            "phone_calls": phone_calls_count,
            "meetings": meetings_count,
            "total_minutes": total_minutes,
            "pinned_count": pinned_count,
            "billable_count": billable_count
        }

        # Available cases for dropdown
        cases_query = db.query(LawCases).filter(
            LawCases.office_id == user.office_id,
            LawCases.is_deleted == 0
        )
        if user.role in {"محامي", "محامٍ"} and not getattr(user, "can_view_all_cases", 0):
            cases_query = cases_query.filter(LawCases.lead_lawyer_id == user.id)
        cases = cases_query.order_by(LawCases.id.desc()).all()

        # Office team members
        team_members = db.query(AccessProfiles).filter(
            AccessProfiles.office_id == user.office_id,
            AccessProfiles.is_active == 1
        ).all()

        return templates.TemplateResponse(
            request=request,
            name="notes.html",
            context={
                "user": user,
                "notes": notes,
                "cases": cases,
                "team_members": team_members,
                "kpis": kpis,
                "selected_case_id": case_id,
                "selected_channel": channel,
                "selected_priority": priority,
                "active_page": "notes"
            }
        )
    except Exception as exc:
        return safe_error_html(exc, context="notes.py")


@router.post("/notes/add")
async def add_note(
    request: Request,
    case_id: int = Form(...),
    title: str = Form(...),
    note_type_key: Optional[str] = Form("عام"),
    communication_channel: Optional[str] = Form("internal_note"),
    direction: Optional[str] = Form("outbound"),
    contact_person: Optional[str] = Form(None),
    call_duration_minutes: int = Form(0),
    is_billable: int = Form(0),
    hourly_rate: float = Form(0.0),
    is_pinned: int = Form(0),
    is_client_visible: int = Form(0),
    priority_level: Optional[str] = Form("عادي"),
    content: Optional[str] = Form(None),
    create_followup: int = Form(0),
    followup_due_date: Optional[str] = Form(None),
    followup_title: Optional[str] = Form(None),
    attachment: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
    user: AccessProfiles = Depends(get_current_user)
):
    if not user:
        return RedirectResponse(url="/", status_code=303)
    require_user_permission(user, "notes", "add")
    office_id = user.office_id

    case = db.query(LawCases).filter(
        LawCases.id == case_id,
        LawCases.office_id == office_id
    ).first()
    if not case:
        raise HTTPException(status_code=403, detail="القضية غير موجودة أو غير مصرح بالوصول إليها")
    if not user_can_access_case(db, user, case_id):
        raise HTTPException(status_code=403, detail="غير مصرح بالوصول إلى القضية")

    attachment_path = None
    if attachment and attachment.filename:
        safe_name = save_upload(attachment, UPLOAD_DIR)
        attachment_path = f"/static/uploads/notes/{safe_name}"

    note = LawNotes(
        case_id=case_id,
        office_id=office_id,
        title=title.strip(),
        note_type_key=note_type_key,
        communication_channel=communication_channel or "internal_note",
        direction=direction or "outbound",
        contact_person=contact_person.strip() if contact_person else None,
        call_duration_minutes=max(0, call_duration_minutes),
        is_billable=1 if is_billable else 0,
        hourly_rate=max(0.0, float(hourly_rate or 0.0)),
        is_pinned=1 if is_pinned else 0,
        is_client_visible=1 if is_client_visible else 0,
        priority_level=priority_level or "عادي",
        author_id=user.id,
        attachment_path=attachment_path,
        content=content.strip() if content else None,
        created_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    )
    db.add(note)
    db.flush()

    # Create automated follow-up task if requested
    if create_followup and followup_due_date:
        task_title = followup_title.strip() if followup_title else f"متابعة ملاحظة: {title.strip()}"
        priority_int = 3 if priority_level in ["عاجل", "هام"] else 2
        task_desc = f"مهمة متابعة تلقائية من سجل الملاحظة/الاتصال رقم #{note.id}\nالعنوان: {title}\nجهة الاتصال: {contact_person or 'غير محدد'}"
        task = LawTasks(
            office_id=office_id,
            case_id=case_id,
            assignee_user_id=user.id,
            title=task_title,
            due_at=followup_due_date,
            status_key="pending",
            priority_level=priority_int,
            description=task_desc
        )
        db.add(task)

    db.commit()
    return RedirectResponse(url="/notes", status_code=303)


@router.post("/notes/edit")
async def edit_note(
    request: Request,
    note_id: int = Form(...),
    title: str = Form(...),
    note_type_key: Optional[str] = Form("عام"),
    communication_channel: Optional[str] = Form("internal_note"),
    direction: Optional[str] = Form("outbound"),
    contact_person: Optional[str] = Form(None),
    call_duration_minutes: int = Form(0),
    is_billable: int = Form(0),
    hourly_rate: float = Form(0.0),
    is_pinned: int = Form(0),
    is_client_visible: int = Form(0),
    priority_level: Optional[str] = Form("عادي"),
    content: Optional[str] = Form(None),
    attachment: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
    user: AccessProfiles = Depends(get_current_user)
):
    if not user:
        return RedirectResponse(url="/", status_code=303)
    require_user_permission(user, "notes", "edit")
    n = db.query(LawNotes).filter(
        LawNotes.id == note_id,
        LawNotes.office_id == user.office_id,
        LawNotes.is_deleted == 0
    ).first()
    if not n:
        raise HTTPException(status_code=404, detail="الملاحظة غير موجودة")
    if not user_can_access_case(db, user, n.case_id):
        raise HTTPException(status_code=403, detail="غير مصرح بالوصول إلى القضية")

    n.title = title.strip()
    n.note_type_key = note_type_key
    n.communication_channel = communication_channel or "internal_note"
    n.direction = direction or "outbound"
    n.contact_person = contact_person.strip() if contact_person else None
    n.call_duration_minutes = max(0, call_duration_minutes)
    n.is_billable = 1 if is_billable else 0
    n.hourly_rate = max(0.0, float(hourly_rate or 0.0))
    n.is_pinned = 1 if is_pinned else 0
    n.is_client_visible = 1 if is_client_visible else 0
    n.priority_level = priority_level or "عادي"
    n.content = content.strip() if content else None
    n.updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if attachment and attachment.filename:
        safe_name = save_upload(attachment, UPLOAD_DIR)
        n.attachment_path = f"/static/uploads/notes/{safe_name}"

    db.commit()
    return RedirectResponse(url="/notes", status_code=303)


@router.post("/notes/toggle-pin")
async def toggle_pin_note(
    request: Request,
    note_id: int = Form(...),
    db: Session = Depends(get_db),
    user: AccessProfiles = Depends(get_current_user)
):
    if not user:
        return JSONResponse({"status": "error", "message": "غير مصرح"}, status_code=401)
    require_user_permission(user, "notes", "edit")
    n = db.query(LawNotes).filter(
        LawNotes.id == note_id,
        LawNotes.office_id == user.office_id,
        LawNotes.is_deleted == 0
    ).first()
    if not n:
        return JSONResponse({"status": "error", "message": "الملاحظة غير موجودة"}, status_code=404)
    if not user_can_access_case(db, user, n.case_id):
        raise HTTPException(status_code=403, detail="غير مصرح بالوصول إلى القضية")

    n.is_pinned = 0 if (n.is_pinned == 1) else 1
    db.commit()

    # Check if request accepts JSON (AJAX)
    accept = request.headers.get("accept", "")
    if "application/json" in accept or request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JSONResponse({
            "status": "success",
            "is_pinned": n.is_pinned,
            "message": "تم تحديث التثبيت بنجاح"
        })
    return RedirectResponse(url="/notes", status_code=303)


@router.post("/notes/delete")
async def delete_note(
    request: Request,
    note_id: int = Form(...),
    db: Session = Depends(get_db),
    user: AccessProfiles = Depends(get_current_user)
):
    if not user:
        return RedirectResponse(url="/", status_code=303)
    require_user_permission(user, "notes", "delete")
    n = db.query(LawNotes).filter(
        LawNotes.id == note_id,
        LawNotes.office_id == user.office_id
    ).first()
    if n:
        if not user_can_access_case(db, user, n.case_id):
            raise HTTPException(status_code=403, detail="غير مصرح بالوصول إلى القضية")
        n.is_deleted = 1
        db.commit()
    return RedirectResponse(url="/notes", status_code=303)


@router.get("/api/notes/{note_id}")
async def get_note_api(
    note_id: int,
    db: Session = Depends(get_db),
    user: AccessProfiles = Depends(get_current_user)
):
    if not user:
        raise HTTPException(status_code=401, detail="غير مصرح")
    require_user_permission(user, "notes", "view")
    n = db.query(LawNotes).filter(
        LawNotes.id == note_id,
        LawNotes.office_id == user.office_id,
        LawNotes.is_deleted == 0
    ).first()
    if not n:
        raise HTTPException(status_code=404, detail="الملاحظة غير موجودة")
    if not user_can_access_case(db, user, n.case_id):
        raise HTTPException(status_code=403, detail="غير مصرح بالوصول إلى القضية")

    return {
        "id": n.id,
        "case_id": n.case_id,
        "case_number": n.law_case.case_number if n.law_case else "",
        "case_title": n.law_case.title if n.law_case else "",
        "title": n.title,
        "note_type_key": n.note_type_key,
        "communication_channel": n.communication_channel,
        "direction": n.direction,
        "contact_person": n.contact_person,
        "call_duration_minutes": n.call_duration_minutes,
        "is_billable": n.is_billable,
        "hourly_rate": n.hourly_rate,
        "is_pinned": n.is_pinned,
        "is_client_visible": n.is_client_visible,
        "priority_level": n.priority_level,
        "author_name": (n.author.name or n.author.username) if n.author else "",
        "attachment_path": f"/notes/{n.id}/attachment" if n.attachment_path else "",
        "content": n.content,
        "created_at": n.created_at
    }
