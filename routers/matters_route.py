from datetime import datetime
from typing import Optional
import json

from fastapi import APIRouter, Request, Depends, HTTPException, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import or_, func

from core.error_handler import safe_error_html
from database.database import get_db
from database.models import (
    AccessProfiles, LawCases, LawClients, LawDocuments,
    LawTasks, LawTimesheets, LawTransactions, LawNotes,
    LawAuditLog, LawOffices
)
from dependencies import get_current_user, templates, check_user_permission, user_can_access_case

router = APIRouter(tags=["Legal Matters & Advisory (المسائل والاستشارات القانونية)"])


def log_matter_audit(db: Session, office_id: int, user: AccessProfiles, action: str, matter: LawCases, details: str = ""):
    try:
        audit = LawAuditLog(
            office_id=office_id,
            user_id=user.id,
            action=action,
            entity_type="LawMatters",
            entity_id=matter.id,
            details=f"[{matter.case_number}] {matter.title} - {details}"
        )
        db.add(audit)
        db.commit()
    except Exception:
        db.rollback()


@router.get("/matters", response_class=HTMLResponse)
async def matters_page(
    request: Request,
    db: Session = Depends(get_db),
    user: AccessProfiles = Depends(get_current_user),
    type_filter: Optional[str] = None,
    status_filter: Optional[str] = None,
    lawyer_filter: Optional[int] = None,
    client_filter: Optional[int] = None,
    q: Optional[str] = None
):
    if not user:
        return RedirectResponse(url="/", status_code=303)
    if not check_user_permission(user, 'cases', 'view'):
        raise HTTPException(status_code=403, detail="غير مصرح لك بعرض المسائل والاستشارات")

    office_id = user.office_id
    query = db.query(LawCases).filter(
        LawCases.office_id == office_id,
        LawCases.is_deleted == 0,
        LawCases.matter_category == "matter"
    )

    if user.role in ['محامي', 'باحث']:
        query = query.filter(LawCases.lead_lawyer_id == user.id)

    # Filters
    if type_filter and type_filter.strip():
        query = query.filter(LawCases.case_type_key == type_filter.strip())
    if status_filter and status_filter.strip():
        query = query.filter(LawCases.status_key == status_filter.strip())
    if lawyer_filter:
        query = query.filter(LawCases.lead_lawyer_id == lawyer_filter)
    if client_filter:
        # Check through law_clients
        query = query.join(LawClients, LawClients.case_id == LawCases.id).filter(LawClients.id == client_filter)
    if q and q.strip():
        search_term = f"%{q.strip()}%"
        query = query.filter(
            or_(
                LawCases.title.ilike(search_term),
                LawCases.case_number.ilike(search_term),
                LawCases.summary.ilike(search_term),
                LawCases.consultation_scope.ilike(search_term)
            )
        )

    matters = query.order_by(LawCases.created_at.desc()).all()

    # Statistics Counters
    all_matters_query = db.query(LawCases).filter(
        LawCases.office_id == office_id,
        LawCases.is_deleted == 0,
        LawCases.matter_category == "matter"
    )
    if user.role in ['محامي', 'باحث']:
        all_matters_query = all_matters_query.filter(LawCases.lead_lawyer_id == user.id)

    all_matters = all_matters_query.all()
    stats = {
        "total": len(all_matters),
        "advisory": len([m for m in all_matters if m.case_type_key in ['استشارة قانونية', 'advisory', 'consultation']]),
        "contracts": len([m for m in all_matters if m.case_type_key in ['صياغة وتدقيق عقود', 'contracts', 'contract_drafting']]),
        "corporate": len([m for m in all_matters if m.case_type_key in ['تأسيس شركات', 'corporate', 'incorporation']]),
        "completed": len([m for m in all_matters if m.status_key in ['closed', 'completed', 'مكتملة', 'معتمدة']])
    }

    # Lawyers & Clients for Dropdowns
    lawyers = db.query(AccessProfiles).filter(
        AccessProfiles.office_id == office_id,
        AccessProfiles.is_active == 1
    ).all()

    clients = db.query(LawClients).filter(
        LawClients.office_id == office_id,
        LawClients.is_deleted == 0
    ).all()

    # Unique matter types
    matter_types = [
        "استشارة قانونية",
        "صياغة وتدقيق عقود",
        "تأسيس شركات وترخيص",
        "وساطة وحلول ودية",
        "تسجيل علامات وملكية فكرية",
        "تدقيق وامتثال تنظيمي",
        "أخرى"
    ]

    return templates.TemplateResponse(
        request=request,
        name="matters.html",
        context={
            "user": user,
            "active_page": "matters",
            "matters": matters,
            "stats": stats,
            "lawyers": lawyers,
            "clients": clients,
            "matter_types": matter_types,
            "type_filter": type_filter,
            "status_filter": status_filter,
            "lawyer_filter": lawyer_filter,
            "client_filter": client_filter,
            "q": q
        }
    )


@router.post("/matters/add")
async def add_matter(
    request: Request,
    title: str = Form(...),
    matter_type_key: str = Form("استشارة قانونية"),
    client_id: int = Form(...),
    matter_number: Optional[str] = Form(None),
    lead_lawyer_id: Optional[int] = Form(None),
    consultation_scope: Optional[str] = Form(None),
    summary: Optional[str] = Form(None),
    estimated_fee: Optional[float] = Form(0.0),
    open_date: Optional[str] = Form(None),
    close_date: Optional[str] = Form(None),
    status_key: str = Form("in_progress"),
    visibility_mode: str = Form("office"),
    db: Session = Depends(get_db),
    user: AccessProfiles = Depends(get_current_user)
):
    if not user:
        return RedirectResponse(url="/", status_code=303)
    if not check_user_permission(user, 'cases', 'add'):
        raise HTTPException(status_code=403, detail="غير مصرح لك بإضافة مسائل واستشارات")

    office_id = user.office_id

    # Auto-generate matter number if not provided
    if not matter_number or not matter_number.strip():
        now_year = datetime.now().year
        count_matters = db.query(LawCases).filter(
            LawCases.office_id == office_id,
            LawCases.matter_category == "matter"
        ).count()
        matter_number = f"MAT-{now_year}-{count_matters + 1:04d}"
    else:
        matter_number = matter_number.strip()
        # Verify uniqueness
        exists = db.query(LawCases).filter(
            LawCases.case_number == matter_number,
            LawCases.office_id == office_id
        ).first()
        if exists:
            matter_number = f"{matter_number}-{int(datetime.now().timestamp()) % 1000}"

    new_matter = LawCases(
        office_id=office_id,
        case_number=matter_number,
        title=title.strip(),
        matter_category="matter",
        case_type_key=matter_type_key,
        status_key=status_key,
        visibility_mode=visibility_mode,
        consultation_scope=consultation_scope.strip() if consultation_scope else None,
        summary=summary.strip() if summary else None,
        estimated_fee=estimated_fee or 0.0,
        open_date=open_date or datetime.now().strftime("%Y-%m-%d"),
        close_date=close_date or None,
        lead_lawyer_id=lead_lawyer_id if lead_lawyer_id and lead_lawyer_id > 0 else user.id,
        created_by_user_id=user.id,
        is_active=1,
        is_deleted=0
    )
    db.add(new_matter)
    db.commit()
    db.refresh(new_matter)

    # Link client
    if client_id and client_id > 0:
        client = db.query(LawClients).filter(
            LawClients.id == client_id,
            LawClients.office_id == office_id
        ).first()
        if client:
            client.case_id = new_matter.id
            db.commit()

    log_matter_audit(db, office_id, user, "إضافة مسألة/استشارة جديدة", new_matter, f"النوع: {matter_type_key}")
    return RedirectResponse(url=f"/matters/{new_matter.id}?msg=added", status_code=303)


@router.get("/matters/{matter_id}", response_class=HTMLResponse)
async def matter_details_page(
    matter_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: AccessProfiles = Depends(get_current_user)
):
    if not user:
        return RedirectResponse(url="/", status_code=303)
    if not check_user_permission(user, 'cases', 'view'):
        raise HTTPException(status_code=403, detail="غير مصرح لك بعرض المسألة")

    matter = db.query(LawCases).filter(
        LawCases.id == matter_id,
        LawCases.office_id == user.office_id,
        LawCases.is_deleted == 0
    ).first()
    if not matter:
        raise HTTPException(status_code=404, detail="المسألة غير موجودة")

    if not user_can_access_case(db, user, matter.id):
        raise HTTPException(status_code=403, detail="غير مصرح لك بالوصول لهذه المسألة")

    # Linked client
    client = db.query(LawClients).filter(
        LawClients.case_id == matter.id,
        LawClients.office_id == user.office_id,
        LawClients.is_deleted == 0
    ).first()

    # Documents & Contracts with version count
    documents = db.query(LawDocuments).filter(
        LawDocuments.case_id == matter.id,
        LawDocuments.office_id == user.office_id,
        LawDocuments.is_deleted == 0
    ).order_by(LawDocuments.created_at.desc()).all()

    # Tasks
    tasks = db.query(LawTasks).filter(
        LawTasks.case_id == matter.id,
        LawTasks.office_id == user.office_id
    ).order_by(LawTasks.created_at.desc()).all()

    # Timesheets
    timesheets = db.query(LawTimesheets).filter(
        LawTimesheets.case_id == matter.id,
        LawTimesheets.office_id == user.office_id
    ).order_by(LawTimesheets.created_at.desc()).all()

    # Transactions & Financials
    transactions = db.query(LawTransactions).filter(
        LawTransactions.case_id == matter.id,
        LawTransactions.office_id == user.office_id,
        LawTransactions.is_deleted == 0
    ).order_by(LawTransactions.created_at.desc()).all()

    total_paid = sum(t.amount for t in transactions if t.amount)

    # Notes
    notes = db.query(LawNotes).filter(
        LawNotes.case_id == matter.id,
        LawNotes.office_id == user.office_id
    ).order_by(LawNotes.created_at.desc()).all()

    # Lawyers & Clients list for edit modal
    lawyers = db.query(AccessProfiles).filter(
        AccessProfiles.office_id == user.office_id,
        AccessProfiles.is_active == 1
    ).all()

    all_clients = db.query(LawClients).filter(
        LawClients.office_id == user.office_id,
        LawClients.is_deleted == 0
    ).all()

    return templates.TemplateResponse(
        request=request,
        name="matter_details.html",
        context={
            "user": user,
            "active_page": "matters",
            "matter": matter,
            "client": client,
            "documents": documents,
            "tasks": tasks,
            "timesheets": timesheets,
            "transactions": transactions,
            "total_paid": total_paid,
            "notes": notes,
            "lawyers": lawyers,
            "all_clients": all_clients
        }
    )


@router.post("/matters/{matter_id}/edit")
async def edit_matter(
    matter_id: int,
    title: str = Form(...),
    case_type_key: str = Form(...),
    status_key: str = Form(...),
    lead_lawyer_id: Optional[int] = Form(None),
    client_id: Optional[int] = Form(None),
    consultation_scope: Optional[str] = Form(None),
    summary: Optional[str] = Form(None),
    estimated_fee: Optional[float] = Form(0.0),
    open_date: Optional[str] = Form(None),
    close_date: Optional[str] = Form(None),
    visibility_mode: str = Form("office"),
    db: Session = Depends(get_db),
    user: AccessProfiles = Depends(get_current_user)
):
    if not user:
        return RedirectResponse(url="/", status_code=303)
    if not check_user_permission(user, 'cases', 'edit'):
        raise HTTPException(status_code=403, detail="غير مصرح لك بتعديل المسألة")

    matter = db.query(LawCases).filter(
        LawCases.id == matter_id,
        LawCases.office_id == user.office_id,
        LawCases.is_deleted == 0
    ).first()
    if not matter:
        raise HTTPException(status_code=404, detail="المسألة غير موجودة")

    matter.title = title.strip()
    matter.case_type_key = case_type_key.strip()
    matter.status_key = status_key.strip()
    matter.lead_lawyer_id = lead_lawyer_id if lead_lawyer_id and lead_lawyer_id > 0 else matter.lead_lawyer_id
    matter.consultation_scope = consultation_scope.strip() if consultation_scope else None
    matter.summary = summary.strip() if summary else None
    matter.estimated_fee = estimated_fee or 0.0
    matter.open_date = open_date or matter.open_date
    matter.close_date = close_date or None
    matter.visibility_mode = visibility_mode
    matter.updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Update client link if changed
    if client_id and client_id > 0:
        # Detach previous client
        db.query(LawClients).filter(
            LawClients.case_id == matter.id,
            LawClients.office_id == user.office_id
        ).update({"case_id": None})
        # Attach new client
        db.query(LawClients).filter(
            LawClients.id == client_id,
            LawClients.office_id == user.office_id
        ).update({"case_id": matter.id})

    db.commit()
    log_matter_audit(db, user.office_id, user, "تعديل بيانات المسألة", matter)
    return RedirectResponse(url=f"/matters/{matter.id}?msg=updated", status_code=303)


@router.post("/matters/{matter_id}/update-opinion")
async def update_legal_opinion(
    matter_id: int,
    legal_opinion: str = Form(...),
    db: Session = Depends(get_db),
    user: AccessProfiles = Depends(get_current_user)
):
    if not user:
        return RedirectResponse(url="/", status_code=303)
    if not check_user_permission(user, 'cases', 'edit'):
        raise HTTPException(status_code=403, detail="غير مصرح")

    matter = db.query(LawCases).filter(
        LawCases.id == matter_id,
        LawCases.office_id == user.office_id,
        LawCases.is_deleted == 0
    ).first()
    if not matter:
        raise HTTPException(status_code=404, detail="المسألة غير موجودة")

    matter.legal_opinion = legal_opinion.strip()
    matter.updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    db.commit()

    log_matter_audit(db, user.office_id, user, "تحديث الرأي والمخرج القانوني", matter)
    return RedirectResponse(url=f"/matters/{matter.id}?msg=opinion_saved#opinion_tab", status_code=303)


@router.post("/matters/{matter_id}/status")
async def update_matter_status(
    matter_id: int,
    status_key: str = Form(...),
    db: Session = Depends(get_db),
    user: AccessProfiles = Depends(get_current_user)
):
    if not user or not check_user_permission(user, 'cases', 'edit'):
        raise HTTPException(status_code=403, detail="غير مصرح")

    matter = db.query(LawCases).filter(
        LawCases.id == matter_id,
        LawCases.office_id == user.office_id,
        LawCases.is_deleted == 0
    ).first()
    if not matter:
        raise HTTPException(status_code=404, detail="المسألة غير موجودة")

    matter.status_key = status_key.strip()
    matter.updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if status_key in ['closed', 'completed', 'مكتملة', 'معتمدة'] and not matter.close_date:
        matter.close_date = datetime.now().strftime("%Y-%m-%d")

    db.commit()
    log_matter_audit(db, user.office_id, user, "تغيير حالة المسألة", matter, f"الحالة الجديدة: {status_key}")
    return JSONResponse(content={"success": True, "new_status": status_key})


@router.get("/matters/{matter_id}/print", response_class=HTMLResponse)
async def print_matter_dossier(
    matter_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: AccessProfiles = Depends(get_current_user)
):
    if not user:
        return RedirectResponse(url="/", status_code=303)

    matter = db.query(LawCases).filter(
        LawCases.id == matter_id,
        LawCases.office_id == user.office_id,
        LawCases.is_deleted == 0
    ).first()
    if not matter:
        raise HTTPException(status_code=404, detail="المسألة غير موجودة")

    office = db.query(LawOffices).filter(LawOffices.id == user.office_id).first()
    client = db.query(LawClients).filter(LawClients.case_id == matter.id, LawClients.is_deleted == 0).first()
    documents = db.query(LawDocuments).filter(LawDocuments.case_id == matter.id, LawDocuments.is_deleted == 0).all()

    lead_lawyer = db.query(AccessProfiles).filter(AccessProfiles.id == matter.lead_lawyer_id).first() if matter.lead_lawyer_id else None

    return templates.TemplateResponse(
        request=request,
        name="matter_print.html",
        context={
            "matter": matter,
            "office": office,
            "client": client,
            "documents": documents,
            "lead_lawyer": lead_lawyer,
            "user": user,
            "print_date": datetime.now().strftime("%Y-%m-%d %H:%M")
        }
    )
