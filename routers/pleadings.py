import json
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Request, Depends, HTTPException, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from sqlalchemy.orm import Session

from core.error_handler import safe_error_html
from database.database import get_db
from database.models import AccessProfiles, LawCases, LawPleadings, LawOffices
from dependencies import get_current_user, templates, check_user_permission

router = APIRouter(tags=["Pleadings & Legal Memos"])


@router.get("/pleadings", response_class=HTMLResponse)
async def pleadings_page(
    request: Request,
    db: Session = Depends(get_db),
    user: AccessProfiles = Depends(get_current_user)
):
    if not user:
        return RedirectResponse(url="/", status_code=303)
    try:
        office_id = user.office_id

        # 1. Fetch pleadings for office
        pleadings = db.query(LawPleadings).filter(
            LawPleadings.office_id == office_id,
            LawPleadings.is_deleted == 0
        ).order_by(LawPleadings.id.desc()).all()

        # 2. Fetch active cases for office
        cases = db.query(LawCases).filter(
            LawCases.office_id == office_id,
            LawCases.is_deleted == 0
        ).order_by(LawCases.id.desc()).all()

        # 3. Fetch lawyers / team members
        lawyers = db.query(AccessProfiles).filter(
            AccessProfiles.office_id == office_id,
            AccessProfiles.is_active == 1
        ).order_by(AccessProfiles.name.asc()).all()

        # 4. Office info
        office = db.query(LawOffices).filter(LawOffices.id == office_id).first()

        # 5. Serialized cases for dynamic client-side autofill
        cases_json = []
        for c in cases:
            client_name = c.law_clients[0].name if c.law_clients else "غير محدد"
            cases_json.append({
                "id": c.id,
                "case_number": c.case_number or "",
                "title": c.title or "",
                "court_name": c.court_name or "",
                "case_type": getattr(c, 'case_type_key', '') or "",
                "client_name": client_name
            })

        # 6. Advanced stats
        total_pleadings = len(pleadings)
        drafts_count = sum(1 for p in pleadings if p.status_key in ['draft', 'مسودة'])
        in_review_count = sum(1 for p in pleadings if p.status_key in ['in_review', 'قيد المراجعة'])
        submitted_count = sum(1 for p in pleadings if p.status_key in ['submitted', 'تم التقديم للمحكمة', 'final', 'نهائية'])
        approved_count = sum(1 for p in pleadings if p.status_key in ['approved', 'معتمدة'])

        return templates.TemplateResponse(
            request=request,
            name="pleadings.html",
            context={
                "user": user,
                "office": office,
                "pleadings": pleadings,
                "cases": cases,
                "cases_json": cases_json,
                "lawyers": lawyers,
                "total_pleadings": total_pleadings,
                "drafts_count": drafts_count,
                "in_review_count": in_review_count,
                "submitted_count": submitted_count,
                "approved_count": approved_count,
                "active_page": "pleadings"
            }
        )
    except Exception as exc:
        return safe_error_html(exc, context="pleadings.py")


@router.post("/pleadings/add")
async def add_pleading(
    request: Request,
    case_id: int = Form(...),
    title: str = Form(...),
    pleading_type_key: str = Form(...),
    content_html: str = Form(None),
    issue_date: str = Form(None),
    status_key: str = Form("draft"),
    lead_lawyer_id: Optional[int] = Form(None),
    redirect_to: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    user: AccessProfiles = Depends(get_current_user)
):
    if not user:
        return RedirectResponse(url="/", status_code=303)
    if not check_user_permission(user, "pleadings", "add"):
        raise HTTPException(status_code=403, detail="غير مصرح لك بإضافة مذكرات")

    office_id = user.office_id
    case = db.query(LawCases).filter(
        LawCases.id == case_id,
        LawCases.office_id == office_id,
        LawCases.is_deleted == 0
    ).first()
    if not case:
        raise HTTPException(status_code=404, detail="القضية غير موجودة أو غير تابعة لمكتبك")

    effective_lawyer_id = lead_lawyer_id if lead_lawyer_id else user.id

    new_pleading = LawPleadings(
        case_id=case_id,
        office_id=office_id,
        title=title.strip(),
        pleading_type_key=pleading_type_key.strip(),
        content_html=content_html.strip() if content_html else "",
        issue_date=issue_date.strip() if issue_date else datetime.now().strftime("%Y-%m-%d"),
        status_key=status_key.strip() if status_key else "draft",
        lead_lawyer_id=effective_lawyer_id,
        version_no=1,
        is_deleted=0
    )
    db.add(new_pleading)
    db.commit()

    target = redirect_to if redirect_to else "/pleadings"
    return RedirectResponse(url=target, status_code=303)


@router.post("/pleadings/edit")
async def edit_pleading(
    request: Request,
    pleading_id: int = Form(...),
    case_id: int = Form(...),
    title: str = Form(...),
    pleading_type_key: str = Form(...),
    content_html: str = Form(None),
    issue_date: str = Form(None),
    status_key: str = Form("draft"),
    lead_lawyer_id: Optional[int] = Form(None),
    redirect_to: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    user: AccessProfiles = Depends(get_current_user)
):
    if not user:
        return RedirectResponse(url="/", status_code=303)
    if not check_user_permission(user, "pleadings", "edit"):
        raise HTTPException(status_code=403, detail="غير مصرح لك بتعديل المذكرات")

    office_id = user.office_id
    pleading = db.query(LawPleadings).filter(
        LawPleadings.id == pleading_id,
        LawPleadings.office_id == office_id,
        LawPleadings.is_deleted == 0
    ).first()
    if not pleading:
        raise HTTPException(status_code=404, detail="المذكرة غير موجودة")

    pleading.case_id = case_id
    pleading.title = title.strip()
    pleading.pleading_type_key = pleading_type_key.strip()
    pleading.content_html = content_html.strip() if content_html else ""
    pleading.issue_date = issue_date.strip() if issue_date else pleading.issue_date
    pleading.status_key = status_key.strip() if status_key else pleading.status_key
    if lead_lawyer_id:
        pleading.lead_lawyer_id = lead_lawyer_id
    pleading.version_no = (pleading.version_no or 1) + 1
    pleading.updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    db.commit()

    target = redirect_to if redirect_to else "/pleadings"
    return RedirectResponse(url=target, status_code=303)


@router.post("/pleadings/delete")
async def delete_pleading(
    request: Request,
    pleading_id: int = Form(...),
    redirect_to: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    user: AccessProfiles = Depends(get_current_user)
):
    if not user:
        return RedirectResponse(url="/", status_code=303)
    if not check_user_permission(user, "pleadings", "delete"):
        raise HTTPException(status_code=403, detail="غير مصرح لك بحذف المذكرات")

    office_id = user.office_id
    pleading = db.query(LawPleadings).filter(
        LawPleadings.id == pleading_id,
        LawPleadings.office_id == office_id,
        LawPleadings.is_deleted == 0
    ).first()
    if pleading:
        pleading.is_deleted = 1
        db.commit()

    target = redirect_to if redirect_to else "/pleadings"
    return RedirectResponse(url=target, status_code=303)


@router.get("/api/pleadings/{pleading_id}")
async def get_pleading_json(
    pleading_id: int,
    db: Session = Depends(get_db),
    user: AccessProfiles = Depends(get_current_user)
):
    if not user:
        raise HTTPException(status_code=401, detail="غير مصرح")

    pleading = db.query(LawPleadings).filter(
        LawPleadings.id == pleading_id,
        LawPleadings.office_id == user.office_id,
        LawPleadings.is_deleted == 0
    ).first()
    if not pleading:
        raise HTTPException(status_code=404, detail="المذكرة غير موجودة")

    case = pleading.law_case
    lawyer = pleading.lead_lawyer
    client_name = case.law_clients[0].name if case and case.law_clients else "غير محدد"

    return JSONResponse({
        "id": pleading.id,
        "case_id": pleading.case_id,
        "case_title": case.title if case else "",
        "case_number": case.case_number if case else "",
        "court_name": case.court_name if case else "",
        "client_name": client_name,
        "title": pleading.title,
        "pleading_type_key": pleading_type_key_label(pleading.pleading_type_key),
        "raw_type_key": pleading.pleading_type_key,
        "content_html": pleading.content_html or "",
        "issue_date": pleading.issue_date or "",
        "status_key": pleading.status_key,
        "status_label": pleading_status_label(pleading.status_key),
        "lead_lawyer_id": pleading.lead_lawyer_id,
        "lawyer_name": lawyer.name if lawyer else "غير محدد",
        "version_no": pleading.version_no or 1
    })


@router.get("/pleadings/{pleading_id}/print", response_class=HTMLResponse)
async def print_pleading(
    pleading_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: AccessProfiles = Depends(get_current_user)
):
    """صفحة الطباعة الرسمية للمذكرة القانونية بترويسة مكتب المحاماة"""
    if not user:
        return RedirectResponse(url="/", status_code=303)

    pleading = db.query(LawPleadings).filter(
        LawPleadings.id == pleading_id,
        LawPleadings.office_id == user.office_id,
        LawPleadings.is_deleted == 0
    ).first()
    if not pleading:
        raise HTTPException(status_code=404, detail="المذكرة غير موجودة")

    office = db.query(LawOffices).filter(LawOffices.id == user.office_id).first()
    case = pleading.law_case
    lawyer = pleading.lead_lawyer

    return templates.TemplateResponse(
        request=request,
        name="pleadings_print.html",
        context={
            "user": user,
            "office": office,
            "pleading": pleading,
            "case": case,
            "lawyer": lawyer
        }
    )


def pleading_type_key_label(key: str) -> str:
    labels = {
        "claim": "لائحة دعوى",
        "defense": "مذكرة دفاع",
        "reply": "مذكرة رد وتعقيب",
        "appeal": "لائحة اعتراضية / استئناف",
        "petition": "التماس إعادة نظر",
        "cassation": "طعن بالنقض",
        "counter_claim": "دعوى متقابلة",
        "urgent": "طلب عاجل / وقتي",
        "other": "مذكرة أخرى"
    }
    return labels.get(key, key)


def pleading_status_label(key: str) -> str:
    labels = {
        "draft": "مسودة",
        "in_review": "قيد المراجعة",
        "submitted": "تم التقديم للمحكمة",
        "final": "نسخة نهائية",
        "approved": "معتمدة"
    }
    return labels.get(key, key)
