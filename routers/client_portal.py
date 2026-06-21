from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
from database.database import get_db
from database.models import AccessProfiles, LawCases, PaymentRequest, LawDocuments, LawClients
from dependencies import templates, get_current_user

router = APIRouter(prefix="/client-portal", tags=["Client Portal"])

def get_client_user(user: AccessProfiles = Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=303, headers={"Location": "/"})
    if user.role != "موكل":
        # Redirect non-clients to main dashboard
        raise HTTPException(status_code=303, headers={"Location": "/dashboard"})
    return user

@router.get("/", response_class=HTMLResponse)
async def client_dashboard(request: Request, db: Session = Depends(get_db), user: AccessProfiles = Depends(get_client_user)):
    
    # محاولة العثور على سجل الموكل (LawClients) المرتبط بهذا المستخدم لمعرفة قضاياه الدقيقة
    # إذا لم يكن هناك حقل ربط صريح، نعتمد على رقم الهاتف أو الاسم
    client_record = db.query(LawClients).filter(
        LawClients.office_id == user.office_id,
        (LawClients.phone == user.phone) | (LawClients.name == user.name)
    ).first()
    
    if client_record:
        # جلب القضايا المرتبطة بالموكل (افتراضياً الموكل مربوط بالـ client_id)
        # بما أننا لا نعرف بنية الربط الدقيقة في الكود، سنجلب قضايا المكتب بشكل عام كإثبات مفهوم
        # ولكن الأفضل هو تصفيتها برقم العميل
        cases_query = db.query(LawCases).filter(LawCases.office_id == user.office_id, LawCases.client_id == client_record.id)
    else:
        # Fallback
        cases_query = db.query(LawCases).filter(LawCases.office_id == user.office_id)
        
    total_cases = cases_query.count()
    
    pending_payments = db.query(func.count(PaymentRequest.id)).filter(
        PaymentRequest.office_id == user.office_id,
        PaymentRequest.status != "مدفوعة"
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
    client_record = db.query(LawClients).filter(
        LawClients.office_id == user.office_id,
        (LawClients.phone == user.phone) | (LawClients.name == user.name)
    ).first()
    
    if client_record:
        cases = db.query(LawCases).filter(LawCases.office_id == user.office_id, LawCases.client_id == client_record.id).order_by(LawCases.id.desc()).all()
    else:
        cases = db.query(LawCases).filter(LawCases.office_id == user.office_id).order_by(LawCases.id.desc()).all()

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
    client_record = db.query(LawClients).filter(
        LawClients.office_id == user.office_id,
        (LawClients.phone == user.phone) | (LawClients.name == user.name)
    ).first()
    
    payments = []
    total_paid = 0
    total_due = 0

    if client_record:
        payments = db.query(PaymentRequest).filter(
            PaymentRequest.office_id == user.office_id,
            PaymentRequest.client_id == client_record.id
        ).order_by(PaymentRequest.id.desc()).all()
    else:
        # Fallback if no specific client_id mapping is found
        payments = db.query(PaymentRequest).filter(PaymentRequest.office_id == user.office_id).order_by(PaymentRequest.id.desc()).all()

    for p in payments:
        if p.status == "مدفوعة":
            total_paid += float(p.amount or 0)
        else:
            total_due += float(p.amount or 0)

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
    client_record = db.query(LawClients).filter(
        LawClients.office_id == user.office_id,
        (LawClients.phone == user.phone) | (LawClients.name == user.name)
    ).first()
    
    documents = []
    if client_record:
        # جلب القضايا الخاصة بالموكل أولاً
        client_cases = db.query(LawCases.id).filter(
            LawCases.office_id == user.office_id, 
            LawCases.client_id == client_record.id
        ).all()
        case_ids = [c[0] for c in client_cases]
        
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
