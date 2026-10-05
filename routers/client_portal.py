from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
from database.database import get_db
from database.models import AccessProfiles, LawCases, LawDocuments, LawClients, Invoices
from dependencies import templates, get_current_user
from core.security import client_records_for_user

router = APIRouter(prefix="/client-portal", tags=["Client Portal"])

def get_client_user(user: AccessProfiles = Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=303, headers={"Location": "/"})
    if user.role != "موكل":
        # Redirect non-clients to main dashboard
        raise HTTPException(status_code=303, headers={"Location": "/dashboard"})
    return user


def _client_records(db: Session, user: AccessProfiles):
    return client_records_for_user(db, user)


def _client_case_query(db: Session, user: AccessProfiles):
    client_ids = [record.id for record in _client_records(db, user)]
    case_ids = db.query(LawClients.case_id).filter(
        LawClients.id.in_(client_ids),
        LawClients.office_id == user.office_id,
        LawClients.case_id.isnot(None),
        LawClients.is_deleted == 0,
    ) if client_ids else None
    query = db.query(LawCases).filter(
        LawCases.office_id == user.office_id,
        LawCases.is_deleted == 0,
    )
    # No matching client record means no accessible cases; never fall back to all cases.
    return query.filter(LawCases.id.in_(case_ids)) if case_ids is not None else query.filter(False)

@router.get("/", response_class=HTMLResponse)
async def client_dashboard(request: Request, db: Session = Depends(get_db), user: AccessProfiles = Depends(get_client_user)):
    
    # محاولة العثور على سجل الموكل (LawClients) المرتبط بهذا المستخدم لمعرفة قضاياه الدقيقة
    # إذا لم يكن هناك حقل ربط صريح، نعتمد على رقم الهاتف أو الاسم
    client_records = _client_records(db, user)
    client_ids = [record.id for record in client_records]
    cases_query = _client_case_query(db, user)
    total_cases = cases_query.count()
    
    pending_payments = db.query(func.count(Invoices.id)).filter(
        Invoices.office_id == user.office_id,
        Invoices.client_id.in_(client_ids) if client_ids else False,
        Invoices.status.in_(["Unpaid", "Partial"]),
    ).scalar()
    
    recent_cases = cases_query.order_by(LawCases.id.desc()).limit(3).all()

    return templates.TemplateResponse("client_portal/dashboard.html", {
        "request": request,
        "user": user,
        "total_cases": total_cases,
        "pending_payments": pending_payments,
        "recent_cases": recent_cases,
        "active_page": "dashboard"
    })

@router.get("/cases", response_class=HTMLResponse)
async def client_cases(request: Request, db: Session = Depends(get_db), user: AccessProfiles = Depends(get_client_user)):
    cases = _client_case_query(db, user).order_by(LawCases.id.desc()).all()

    return templates.TemplateResponse("client_portal/cases.html", {
        "request": request,
        "user": user,
        "cases": cases,
        "active_page": "cases"
    })

@router.get("/finance", response_class=HTMLResponse)
async def client_finance(request: Request, db: Session = Depends(get_db), user: AccessProfiles = Depends(get_client_user)):
    # جلب المطالبات المالية المتعلقة بالموكل
    # سنفترض أن المطالبات تكون باسم الموكل أو مرتبطة بـ client_id أو قضية تابعة له
    client_ids = [record.id for record in _client_records(db, user)]
    
    payments = []
    total_paid = 0
    total_due = 0

    if client_ids:
        payments = db.query(Invoices).filter(
            Invoices.office_id == user.office_id,
            Invoices.client_id.in_(client_ids),
        ).order_by(Invoices.id.desc()).all()

    for p in payments:
        total_paid += float(p.amount_paid or 0)
        total_due += max(0.0, float(p.grand_total or 0) - float(p.amount_paid or 0))

    return templates.TemplateResponse("client_portal/finance.html", {
        "request": request,
        "user": user,
        "payments": payments,
        "total_paid": total_paid,
        "total_due": total_due,
        "active_page": "finance"
    })

@router.get("/documents", response_class=HTMLResponse)
async def client_documents(request: Request, db: Session = Depends(get_db), user: AccessProfiles = Depends(get_client_user)):
    # جلب المستندات المرتبطة بقضايا الموكل
    client_ids = [record.id for record in _client_records(db, user)]
    
    documents = []
    if client_ids:
        # جلب القضايا الخاصة بالموكل أولاً
        case_ids = [case.id for case in _client_case_query(db, user).with_entities(LawCases.id).all()]
        
        if case_ids:
            documents = db.query(LawDocuments).filter(
                LawDocuments.office_id == user.office_id,
                LawDocuments.case_id.in_(case_ids)
            ).order_by(LawDocuments.id.desc()).all()
    
    return templates.TemplateResponse("client_portal/documents.html", {
        "request": request,
        "user": user,
        "documents": documents,
        "active_page": "documents"
    })
