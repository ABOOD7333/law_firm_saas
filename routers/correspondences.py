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
from database.models import AccessProfiles, LawCases, LawCorrespondences, LawClients, LawParties, LawTasks
from dependencies import get_current_user, templates, require_user_permission, user_can_access_case
from core.upload_security import save_upload

router = APIRouter()

async def _download_correspondence_file(corr_id: int, field_name: str, db: Session, user: AccessProfiles):
    if not user or not user.office_id or user.role == "موكل":
        raise HTTPException(status_code=403, detail="غير مصرح بتنزيل هذا الملف")
    require_user_permission(user, "correspondences", "view")
    corr = db.query(LawCorrespondences).filter(
        LawCorrespondences.id == corr_id,
        LawCorrespondences.office_id == user.office_id,
        LawCorrespondences.is_deleted == 0,
    ).first()
    if not corr:
        raise HTTPException(status_code=404, detail="المراسلة غير موجودة")
    if corr.case_id and not user_can_access_case(db, user, corr.case_id):
        raise HTTPException(status_code=403, detail="غير مصرح بهذه القضية")
    stored_path = getattr(corr, field_name, None)
    if not stored_path:
        raise HTTPException(status_code=404, detail="لا يوجد ملف مرفق")
    root = os.path.realpath(UPLOAD_DIR)
    path = os.path.realpath(stored_path.lstrip("/"))
    if os.path.commonpath([root, path]) != root or not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="الملف غير موجود")
    return FileResponse(path, filename=os.path.basename(path), headers={"Cache-Control": "private, no-store"})

@router.get("/correspondences/{corr_id}/attachment")
async def download_correspondence_attachment(corr_id: int, db: Session = Depends(get_db), user: AccessProfiles = Depends(get_current_user)):
    return await _download_correspondence_file(corr_id, "attachment_path", db, user)

@router.get("/correspondences/{corr_id}/proof")
async def download_correspondence_proof(corr_id: int, db: Session = Depends(get_db), user: AccessProfiles = Depends(get_current_user)):
    return await _download_correspondence_file(corr_id, "proof_of_delivery_path", db, user)

UPLOAD_DIR = os.path.join("static", "uploads", "correspondences")
os.makedirs(UPLOAD_DIR, exist_ok=True)


def generate_registry_number(db: Session, office_id: int, direction_key: str) -> str:
    year = datetime.now().year
    prefix = "ص" if direction_key == "صادر" else "و"
    pattern = f"{prefix}-{year}-%"
    existing_count = db.query(LawCorrespondences).filter(
        LawCorrespondences.office_id == office_id,
        LawCorrespondences.direction_key == direction_key,
        LawCorrespondences.registry_number.like(pattern)
    ).count()
    seq = existing_count + 1
    return f"{prefix}-{year}-{seq:04d}"


@router.get("/correspondences", response_class=HTMLResponse)
async def correspondences_page(
    request: Request,
    direction: Optional[str] = None,
    status: Optional[str] = None,
    case_id: Optional[int] = None,
    db: Session = Depends(get_db),
    user: AccessProfiles = Depends(get_current_user)
):
    if not user:
        return RedirectResponse(url="/", status_code=303)
    require_user_permission(user, "correspondences", "view")
    try:
        office_id = user.office_id
        today_str = datetime.now().strftime("%Y-%m-%d")

        query = db.query(LawCorrespondences).filter(
            LawCorrespondences.office_id == office_id,
            LawCorrespondences.is_deleted == 0
        )
        if user.role in {"محامي", "محامٍ"} and not getattr(user, "can_view_all_cases", 0):
            visible_case_ids = db.query(LawCases.id).filter(
                LawCases.office_id == office_id,
                LawCases.lead_lawyer_id == user.id,
                LawCases.is_deleted == 0,
            ).subquery()
            query = query.filter(LawCorrespondences.case_id.in_(visible_case_ids))

        if direction:
            query = query.filter(LawCorrespondences.direction_key == direction)
        if status:
            if status == "overdue":
                query = query.filter(
                    LawCorrespondences.needs_reply == "نعم",
                    LawCorrespondences.response_status != "تم الرد",
                    LawCorrespondences.reply_due_date.isnot(None),
                    LawCorrespondences.reply_due_date < today_str
                )
            else:
                query = query.filter(LawCorrespondences.response_status == status)
        if case_id:
            query = query.filter(LawCorrespondences.case_id == case_id)

        corrs = query.order_by(LawCorrespondences.id.desc()).all()

        # KPIs across all non-deleted correspondences
        all_office_corrs = db.query(LawCorrespondences).filter(
            LawCorrespondences.office_id == office_id,
            LawCorrespondences.is_deleted == 0
        ).all()
        if user.role in {"محامي", "محامٍ"} and not getattr(user, "can_view_all_cases", 0):
            all_office_corrs = [c for c in all_office_corrs if c.case_id and user_can_access_case(db, user, c.case_id)]

        total_count = len(all_office_corrs)
        outgoing_count = sum(1 for c in all_office_corrs if c.direction_key == "صادر")
        incoming_count = sum(1 for c in all_office_corrs if c.direction_key == "وارد")
        pending_reply = sum(1 for c in all_office_corrs if c.needs_reply == "نعم" and c.response_status != "تم الرد")
        overdue_count = sum(1 for c in all_office_corrs if c.needs_reply == "نعم" and c.response_status != "تم الرد" and c.reply_due_date and c.reply_due_date < today_str)

        kpis = {
            "total": total_count,
            "outgoing": outgoing_count,
            "incoming": incoming_count,
            "pending_reply": pending_reply,
            "overdue": overdue_count
        }

        cases_query = db.query(LawCases).filter(
            LawCases.office_id == office_id,
            LawCases.is_deleted == 0
        )
        if user.role in {"محامي", "محامٍ"} and not getattr(user, "can_view_all_cases", 0):
            cases_query = cases_query.filter(LawCases.lead_lawyer_id == user.id)
        cases = cases_query.order_by(LawCases.id.desc()).all()

        return templates.TemplateResponse(
            request=request,
            name="correspondences.html",
            context={
                "user": user,
                "corrs": corrs,
                "cases": cases,
                "kpis": kpis,
                "selected_direction": direction,
                "selected_status": status,
                "selected_case_id": case_id,
                "today_str": today_str,
                "active_page": "correspondences"
            }
        )
    except Exception as exc:
        return safe_error_html(exc, context="correspondences.py")


@router.post("/correspondences/add")
async def add_correspondence(
    request: Request,
    case_id: int = Form(...),
    direction_key: str = Form(...),
    letter_number: Optional[str] = Form(None),
    letter_date: Optional[str] = Form(None),
    subject: Optional[str] = Form(None),
    entity_name: Optional[str] = Form(None),
    recipient_name: Optional[str] = Form(None),
    delivery_method: Optional[str] = Form(None),
    tracking_number: Optional[str] = Form(None),
    urgency_level: Optional[str] = Form("عادي"),
    confidentiality_level: Optional[str] = Form("عادي"),
    in_reply_to_id: Optional[int] = Form(None),
    needs_reply: Optional[str] = Form("لا"),
    reply_due_date: Optional[str] = Form(None),
    create_followup_task: Optional[int] = Form(0),
    attachment: Optional[UploadFile] = File(None),
    proof_of_delivery: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
    user: AccessProfiles = Depends(get_current_user)
):
    if not user:
        return RedirectResponse(url="/", status_code=303)
    require_user_permission(user, "correspondences", "add")
    office_id = user.office_id

    case = db.query(LawCases).filter(
        LawCases.id == case_id,
        LawCases.office_id == office_id
    ).first()
    if not case:
        raise HTTPException(status_code=403, detail="القضية غير مصرح بالوصول إليها")
    if not user_can_access_case(db, user, case_id):
        raise HTTPException(status_code=403, detail="غير مصرح بالوصول إلى القضية")

    # Generate sequential registry number
    registry_number = generate_registry_number(db, office_id, direction_key)

    # File uploads
    attachment_path = None
    if attachment and attachment.filename:
        safe_att_name = save_upload(attachment, UPLOAD_DIR)
        attachment_path = f"/static/uploads/correspondences/{safe_att_name}"

    proof_path = None
    if proof_of_delivery and proof_of_delivery.filename:
        safe_proof_name = save_upload(proof_of_delivery, UPLOAD_DIR)
        proof_path = f"/static/uploads/correspondences/{safe_proof_name}"

    response_status = "بانتظار الرد" if needs_reply == "نعم" else "لا يتطلب رد"

    corr = LawCorrespondences(
        case_id=case_id,
        office_id=office_id,
        direction_key=direction_key,
        registry_number=registry_number,
        letter_number=letter_number.strip() if letter_number else None,
        letter_date=letter_date or datetime.now().strftime("%Y-%m-%d"),
        subject=subject.strip() if subject else None,
        entity_name=entity_name.strip() if entity_name else None,
        recipient_name=recipient_name.strip() if recipient_name else None,
        delivery_method=delivery_method or "عبر النظام",
        tracking_number=tracking_number.strip() if tracking_number else None,
        urgency_level=urgency_level or "عادي",
        confidentiality_level=confidentiality_level or "عادي",
        in_reply_to_id=in_reply_to_id if (in_reply_to_id and in_reply_to_id > 0) else None,
        attachment_path=attachment_path,
        proof_of_delivery_path=proof_path,
        created_by_user_id=user.id,
        needs_reply=needs_reply or "لا",
        reply_due_date=reply_due_date if needs_reply == "نعم" else None,
        response_status=response_status,
        created_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    )
    db.add(corr)
    db.flush()

    # Automated follow-up task
    if needs_reply == "نعم" and reply_due_date:
        task_title = f"متابعة رد الخطاب رقم {registry_number} ({subject or 'مراسلة قضائية'})"
        priority_int = 3 if urgency_level in ["عاجل", "فوري"] else 2
        task_desc = f"مهمة متابعة تلقائية لمعاملة {direction_key} رقم {registry_number}\nالجهة: {entity_name or 'غير محدد'}\nرقم الخطاب الخارجي: {letter_number or 'لا يوجد'}"
        followup_task = LawTasks(
            office_id=office_id,
            case_id=case_id,
            assignee_user_id=user.id,
            title=task_title,
            due_at=reply_due_date,
            status_key="pending",
            priority_level=priority_int,
            description=task_desc
        )
        db.add(followup_task)

    db.commit()
    return RedirectResponse(url="/correspondences", status_code=303)


@router.post("/correspondences/edit")
async def edit_correspondence(
    request: Request,
    corr_id: int = Form(...),
    direction_key: str = Form(...),
    letter_number: Optional[str] = Form(None),
    letter_date: Optional[str] = Form(None),
    subject: Optional[str] = Form(None),
    entity_name: Optional[str] = Form(None),
    recipient_name: Optional[str] = Form(None),
    delivery_method: Optional[str] = Form(None),
    tracking_number: Optional[str] = Form(None),
    urgency_level: Optional[str] = Form("عادي"),
    confidentiality_level: Optional[str] = Form("عادي"),
    needs_reply: Optional[str] = Form("لا"),
    reply_due_date: Optional[str] = Form(None),
    response_status: Optional[str] = Form(None),
    attachment: Optional[UploadFile] = File(None),
    proof_of_delivery: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
    user: AccessProfiles = Depends(get_current_user)
):
    if not user:
        return RedirectResponse(url="/", status_code=303)
    require_user_permission(user, "correspondences", "edit")
    c = db.query(LawCorrespondences).filter(
        LawCorrespondences.id == corr_id,
        LawCorrespondences.office_id == user.office_id,
        LawCorrespondences.is_deleted == 0
    ).first()
    if not c:
        raise HTTPException(status_code=404, detail="المراسلة غير موجودة")
    if not user_can_access_case(db, user, c.case_id):
        raise HTTPException(status_code=403, detail="غير مصرح بالوصول إلى القضية")

    c.direction_key = direction_key
    c.letter_number = letter_number.strip() if letter_number else None
    c.letter_date = letter_date or c.letter_date
    c.subject = subject.strip() if subject else None
    c.entity_name = entity_name.strip() if entity_name else None
    c.recipient_name = recipient_name.strip() if recipient_name else None
    c.delivery_method = delivery_method or c.delivery_method
    c.tracking_number = tracking_number.strip() if tracking_number else None
    c.urgency_level = urgency_level or "عادي"
    c.confidentiality_level = confidentiality_level or "عادي"
    c.needs_reply = needs_reply or "لا"
    c.reply_due_date = reply_due_date if needs_reply == "نعم" else None
    c.response_status = response_status or c.response_status
    c.updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # File uploads
    if attachment and attachment.filename:
        safe_att_name = save_upload(attachment, UPLOAD_DIR)
        c.attachment_path = f"/static/uploads/correspondences/{safe_att_name}"

    if proof_of_delivery and proof_of_delivery.filename:
        safe_proof_name = save_upload(proof_of_delivery, UPLOAD_DIR)
        c.proof_of_delivery_path = f"/static/uploads/correspondences/{safe_proof_name}"

    db.commit()
    return RedirectResponse(url="/correspondences", status_code=303)


@router.post("/correspondences/delete")
async def delete_correspondence(
    request: Request,
    corr_id: int = Form(...),
    db: Session = Depends(get_db),
    user: AccessProfiles = Depends(get_current_user)
):
    if not user:
        return RedirectResponse(url="/", status_code=303)
    require_user_permission(user, "correspondences", "delete")
    c = db.query(LawCorrespondences).filter(
        LawCorrespondences.id == corr_id,
        LawCorrespondences.office_id == user.office_id
    ).first()
    if c:
        if not user_can_access_case(db, user, c.case_id):
            raise HTTPException(status_code=403, detail="غير مصرح بالوصول إلى القضية")
        c.is_deleted = 1
        db.commit()
    return RedirectResponse(url="/correspondences", status_code=303)


@router.get("/api/correspondences/{corr_id}")
async def get_correspondence_api(
    corr_id: int,
    db: Session = Depends(get_db),
    user: AccessProfiles = Depends(get_current_user)
):
    if not user:
        raise HTTPException(status_code=401, detail="غير مصرح")
    require_user_permission(user, "correspondences", "view")
    c = db.query(LawCorrespondences).filter(
        LawCorrespondences.id == corr_id,
        LawCorrespondences.office_id == user.office_id,
        LawCorrespondences.is_deleted == 0
    ).first()
    if not c:
        raise HTTPException(status_code=404, detail="المراسلة غير موجودة")
    if not user_can_access_case(db, user, c.case_id):
        raise HTTPException(status_code=403, detail="غير مصرح بالوصول إلى القضية")

    return {
        "id": c.id,
        "case_id": c.case_id,
        "case_number": c.law_case.case_number if c.law_case else "",
        "case_title": c.law_case.title if c.law_case else "",
        "direction_key": c.direction_key,
        "registry_number": c.registry_number,
        "letter_number": c.letter_number,
        "letter_date": c.letter_date,
        "subject": c.subject,
        "entity_name": c.entity_name,
        "recipient_name": c.recipient_name,
        "delivery_method": c.delivery_method,
        "tracking_number": c.tracking_number,
        "urgency_level": c.urgency_level,
        "confidentiality_level": c.confidentiality_level,
        "needs_reply": c.needs_reply,
        "reply_due_date": c.reply_due_date,
        "response_status": c.response_status,
        "attachment_path": f"/correspondences/{c.id}/attachment" if c.attachment_path else "",
        "proof_of_delivery_path": f"/correspondences/{c.id}/proof" if c.proof_of_delivery_path else "",
        "created_at": c.created_at,
        "created_by": (c.created_by.name or c.created_by.username) if c.created_by else ""
    }


@router.get("/correspondences/api/case-parties/{case_id}")
async def get_case_parties_api(
    case_id: int,
    db: Session = Depends(get_db),
    user: AccessProfiles = Depends(get_current_user)
):
    if not user:
        raise HTTPException(status_code=401, detail="غير مصرح")
    case = db.query(LawCases).filter(
        LawCases.id == case_id,
        LawCases.office_id == user.office_id,
        LawCases.is_deleted == 0
    ).first()
    if not case:
        return {"parties": []}

    parties = []
    # Litigant parties
    lit_parties = db.query(LawParties).filter(
        LawParties.case_id == case_id,
        LawParties.office_id == user.office_id,
        LawParties.is_deleted == 0
    ).all()
    for p in lit_parties:
        parties.append({
            "name": p.name,
            "type": p.party_role or "طرف في الدعوى",
            "phone": p.phone or p.alt_phone or "",
            "email": p.email or ""
        })

    # Clients
    if case.law_clients:
        for cl in case.law_clients:
            if cl.is_deleted == 0:
                parties.append({
                    "name": cl.name,
                    "type": "الموكل الرئيسي",
                    "phone": cl.phone or "",
                    "email": cl.email or ""
                })

    return {"parties": parties}
