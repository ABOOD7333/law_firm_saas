from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Request, Depends, HTTPException, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import or_

from core.error_handler import safe_error_html
from database.database import get_db
from database.models import (
    AccessProfiles, LawOffices, LawClients, LawCases,
    LawClientRepresentatives, LawTrustAccounts, Invoices, LawDocuments,
    LawAuditLog
)
from dependencies import get_current_user, templates, check_user_permission

router = APIRouter(tags=["Client Profiles & Corporate Relationships (ملفات العملاء والشركات)"])


def log_client_audit(db: Session, office_id: int, user: AccessProfiles, action: str, client: LawClients, details: str = ""):
    try:
        audit = LawAuditLog(
            office_id=office_id,
            user_id=user.id,
            action=action,
            entity_type="LawClients",
            entity_id=client.id,
            details=f"[{client.name}] - {details}"
        )
        db.add(audit)
        db.commit()
    except Exception:
        db.rollback()


@router.get("/clients/{client_id}", response_class=HTMLResponse)
async def client_profile_page(
    client_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: AccessProfiles = Depends(get_current_user)
):
    if not user:
        return RedirectResponse(url="/", status_code=303)
    if not check_user_permission(user, 'clients', 'view'):
        raise HTTPException(status_code=403, detail="غير مصرح لك بعرض ملف العميل")

    client = db.query(LawClients).filter(
        LawClients.id == client_id,
        LawClients.office_id == user.office_id,
        LawClients.is_deleted == 0
    ).first()
    if not client:
        raise HTTPException(status_code=404, detail="العميل غير موجود")

    # Subsidiaries / Sister Companies
    subsidiaries = db.query(LawClients).filter(
        LawClients.parent_company_id == client.id,
        LawClients.office_id == user.office_id,
        LawClients.is_deleted == 0
    ).all()

    # Potential Parent Companies (for linking)
    parent_candidates = db.query(LawClients).filter(
        LawClients.office_id == user.office_id,
        LawClients.client_type.in_(['company', 'شركة', 'مؤسسة']),
        LawClients.id != client.id,
        LawClients.is_deleted == 0
    ).all()

    # Representatives / Authorized Contacts
    representatives = db.query(LawClientRepresentatives).filter(
        LawClientRepresentatives.client_id == client.id,
        LawClientRepresentatives.office_id == user.office_id
    ).order_by(LawClientRepresentatives.is_primary.desc(), LawClientRepresentatives.id.asc()).all()

    # Cases & Matters
    cases = db.query(LawCases).filter(
        LawCases.office_id == user.office_id,
        LawCases.is_deleted == 0,
        LawCases.id == client.case_id
    ).all() if client.case_id else []

    # Trust Accounts
    trust_accounts = db.query(LawTrustAccounts).filter(
        LawTrustAccounts.client_id == client.id,
        LawTrustAccounts.office_id == user.office_id,
        LawTrustAccounts.is_deleted == 0
    ).all()
    trust_total_balance = sum(acc.current_balance for acc in trust_accounts)

    # Invoices
    invoices = db.query(Invoices).filter(
        Invoices.client_id == client.id,
        Invoices.office_id == user.office_id,
        Invoices.is_deleted == 0
    ).order_by(Invoices.id.desc()).all()
    total_invoiced = sum(inv.total_amount for inv in invoices if inv.total_amount)
    total_paid = sum(inv.paid_amount for inv in invoices if inv.paid_amount)

    # Documents
    documents = db.query(LawDocuments).filter(
        LawDocuments.client_id == client.id,
        LawDocuments.office_id == user.office_id,
        LawDocuments.is_deleted == 0
    ).order_by(LawDocuments.id.desc()).all()

    return templates.TemplateResponse(
        request=request,
        name="client_profile.html",
        context={
            "user": user,
            "active_page": "clients",
            "client": client,
            "representatives": representatives,
            "subsidiaries": subsidiaries,
            "parent_candidates": parent_candidates,
            "cases": cases,
            "trust_accounts": trust_accounts,
            "trust_total_balance": trust_total_balance,
            "invoices": invoices,
            "total_invoiced": total_invoiced,
            "total_paid": total_paid,
            "documents": documents
        }
    )


@router.post("/clients/{client_id}/representatives/add")
async def add_client_representative(
    client_id: int,
    name: str = Form(...),
    role_title: str = Form(...),
    national_id: Optional[str] = Form(None),
    phone: Optional[str] = Form(None),
    email: Optional[str] = Form(None),
    poa_number: Optional[str] = Form(None),
    poa_date: Optional[str] = Form(None),
    is_primary: Optional[int] = Form(0),
    notes: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    user: AccessProfiles = Depends(get_current_user)
):
    if not user:
        return RedirectResponse(url="/", status_code=303)
    if not check_user_permission(user, 'clients', 'edit'):
        raise HTTPException(status_code=403, detail="غير مصرح لك بتعديل بيانات العميل")

    client = db.query(LawClients).filter(
        LawClients.id == client_id,
        LawClients.office_id == user.office_id,
        LawClients.is_deleted == 0
    ).first()
    if not client:
        raise HTTPException(status_code=404, detail="العميل غير موجود")

    # If this is set as primary, demote others
    if is_primary:
        db.query(LawClientRepresentatives).filter(
            LawClientRepresentatives.client_id == client.id,
            LawClientRepresentatives.office_id == user.office_id
        ).update({"is_primary": 0})

    rep = LawClientRepresentatives(
        client_id=client.id,
        office_id=user.office_id,
        name=name.strip(),
        role_title=role_title.strip(),
        national_id=national_id.strip() if national_id else None,
        phone=phone.strip() if phone else None,
        email=email.strip() if email else None,
        poa_number=poa_number.strip() if poa_number else None,
        poa_date=poa_date.strip() if poa_date else None,
        is_primary=1 if is_primary else 0,
        notes=notes.strip() if notes else None
    )
    db.add(rep)

    # Sync primary legal rep name to client table for fast summary lookups
    if is_primary or not client.legal_rep_name:
        client.legal_rep_name = f"{name.strip()} ({role_title.strip()})"

    db.commit()
    log_client_audit(db, user.office_id, user, "إضافة ممثل قانوني ومفوض للشركة", client, f"{name} - {role_title}")
    return RedirectResponse(url=f"/clients/{client.id}?msg=rep_added#representatives", status_code=303)


@router.post("/clients/representatives/{rep_id}/delete")
async def delete_client_representative(
    rep_id: int,
    db: Session = Depends(get_db),
    user: AccessProfiles = Depends(get_current_user)
):
    if not user or not check_user_permission(user, 'clients', 'edit'):
        raise HTTPException(status_code=403, detail="غير مصرح")

    rep = db.query(LawClientRepresentatives).filter(
        LawClientRepresentatives.id == rep_id,
        LawClientRepresentatives.office_id == user.office_id
    ).first()
    if not rep:
        raise HTTPException(status_code=404, detail="الممثل غير موجود")

    client_id = rep.client_id
    db.delete(rep)
    db.commit()

    return RedirectResponse(url=f"/clients/{client_id}?msg=rep_deleted#representatives", status_code=303)


@router.post("/clients/{client_id}/update-corporate")
async def update_corporate_info(
    client_id: int,
    cr_number: Optional[str] = Form(None),
    tax_number: Optional[str] = Form(None),
    industry: Optional[str] = Form(None),
    parent_company_id: Optional[int] = Form(None),
    capital: Optional[float] = Form(0.0),
    website: Optional[str] = Form(None),
    legal_rep_name: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    user: AccessProfiles = Depends(get_current_user)
):
    if not user or not check_user_permission(user, 'clients', 'edit'):
        raise HTTPException(status_code=403, detail="غير مصرح")

    client = db.query(LawClients).filter(
        LawClients.id == client_id,
        LawClients.office_id == user.office_id,
        LawClients.is_deleted == 0
    ).first()
    if not client:
        raise HTTPException(status_code=404, detail="العميل غير موجود")

    client.cr_number = cr_number.strip() if cr_number else None
    client.tax_number = tax_number.strip() if tax_number else None
    client.industry = industry.strip() if industry else None
    client.parent_company_id = parent_company_id if parent_company_id and parent_company_id > 0 else None
    client.capital = capital or 0.0
    client.website = website.strip() if website else None
    if legal_rep_name and legal_rep_name.strip():
        client.legal_rep_name = legal_rep_name.strip()
    client.updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    db.commit()
    log_client_audit(db, user.office_id, user, "تحديث البيانات المؤسسية للشركة", client)
    return RedirectResponse(url=f"/clients/{client.id}?msg=corporate_updated", status_code=303)
