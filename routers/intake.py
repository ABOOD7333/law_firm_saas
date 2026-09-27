"""
مسار استقطاب الموكلين والتوقيع الإلكتروني الذكي (Smart Intake & E-Signature)
"""
import uuid
import json
import hashlib
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Request, Depends, Form, HTTPException, Body
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from sqlalchemy.orm import Session

from database.database import get_db
from database.models import (
    AccessProfiles, LawOffices, LawClients, LawCases,
    ClientIntakeForms, IntakeSubmissions, RetainerAgreements
)
from dependencies import templates, get_current_user, check_user_permission
from utils.conflict_checker import check_conflict_of_interest

router = APIRouter(tags=["Client Intake & E-Signature"])

def get_authorized_user(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        raise HTTPException(status_code=303, headers={"Location": "/"})
    if user.role == "موكل":
        raise HTTPException(status_code=303, headers={"Location": "/client-portal"})
    return user

# ============================================================================
# 1. لوحة تحكم المحامي (Lawyer Dashboard for Intake & E-Sign)
# ============================================================================

@router.get("/intake", response_class=HTMLResponse)
async def intake_dashboard(
    request: Request,
    db: Session = Depends(get_db),
    user: AccessProfiles = Depends(get_authorized_user)
):
    if not check_user_permission(user, 'cases', 'view'):
        return HTMLResponse("<script>alert('غير مصرح لك'); window.location.href='/dashboard';</script>")
    
    # 1. جلب نماذج الاستقطاب النشطة للمكتب
    forms = db.query(ClientIntakeForms).filter(
        ClientIntakeForms.office_id == user.office_id
    ).order_by(ClientIntakeForms.id.desc()).all()
    
    # إذا لم يكن هناك أي نموذج من قبل، ننشئ نموذجاً افتراضياً للمكتب
    if not forms:
        default_form = ClientIntakeForms(
            office_id=user.office_id,
            title="نموذج استشارة واستقطاب موكل جديد",
            form_token=str(uuid.uuid4())[:8],
            description="يرجى ملء تفاصيل القضية والأطراف للبدء في دراسة ملفك والتعاقد.",
            is_active=1,
            require_signature=1,
            default_retainer_text="أتعهد أنا الموقع أدناه بتوكيل المكتب لمتابعة القضية وفقاً للشروط واللوائح القانونية المعتمدة والأتعاب المتفق عليها.",
            created_by=user.id
        )
        db.add(default_form)
        db.commit()
        db.refresh(default_form)
        forms = [default_form]

    # 2. جلب جميع طلبات الاستقطاب الواردة
    submissions = db.query(IntakeSubmissions).filter(
        IntakeSubmissions.office_id == user.office_id
    ).order_by(IntakeSubmissions.id.desc()).all()

    # إحصائيات
    total_submissions = len(submissions)
    pending_count = sum(1 for s in submissions if s.status == 'pending')
    signed_count = sum(1 for s in submissions if s.status in ['signed', 'converted'])
    conflict_count = sum(1 for s in submissions if s.conflict_status == 'conflict_detected')

    return templates.TemplateResponse("intake/intake_list.html", {
        "request": request,
        "user": user,
        "forms": forms,
        "submissions": submissions,
        "total_submissions": total_submissions,
        "pending_count": pending_count,
        "signed_count": signed_count,
        "conflict_count": conflict_count,
        "active_page": "intake"
    })

@router.post("/intake/create-form")
async def create_intake_form(
    title: str = Form(...),
    description: Optional[str] = Form(None),
    require_signature: int = Form(1),
    retainer_text: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    user: AccessProfiles = Depends(get_authorized_user)
):
    new_form = ClientIntakeForms(
        office_id=user.office_id,
        title=title.strip(),
        form_token=str(uuid.uuid4())[:8],
        description=description.strip() if description else None,
        is_active=1,
        require_signature=require_signature,
        default_retainer_text=retainer_text.strip() if retainer_text else None,
        created_by=user.id
    )
    db.add(new_form)
    db.commit()
    return RedirectResponse(url="/intake", status_code=303)

@router.post("/intake/submission/{sub_id}/convert")
async def convert_submission_to_case(
    sub_id: int,
    db: Session = Depends(get_db),
    user: AccessProfiles = Depends(get_authorized_user)
):
    sub = db.query(IntakeSubmissions).filter(
        IntakeSubmissions.id == sub_id,
        IntakeSubmissions.office_id == user.office_id
    ).first()
    
    if not sub:
        raise HTTPException(status_code=404, detail="الطلب غير موجود")
        
    # 1. إنشاء الموكل إذا لم يكن موجوداً
    client = db.query(LawClients).filter(
        LawClients.office_id == user.office_id,
        LawClients.phone == sub.phone.strip()
    ).first()
    
    if not client:
        client = LawClients(
            office_id=user.office_id,
            name=sub.full_name,
            phone=sub.phone,
            email=sub.email,
            national_id=sub.national_id
        )
        db.add(client)
        db.commit()
        db.refresh(client)
        
    # 2. إنشاء القضية
    case_number = f"CASE-{datetime.now().strftime('%y%m')}-{uuid.uuid4().hex[:4].upper()}"
    new_case = LawCases(
        office_id=user.office_id,
        case_number=case_number,
        title=f"قضية: {sub.full_name} ({sub.case_type or 'عامة'})",
        summary=sub.case_summary,
        description=f"الخصم المذكور: {sub.opposing_party_name or 'غير محدد'}",
        status_key="active",
        visibility_mode="private",
        lead_lawyer_id=user.id,
        created_by_user_id=user.id
    )
    db.add(new_case)
    db.commit()
    db.refresh(new_case)
    
    # 3. تحديث حالة الطلب
    sub.status = "converted"
    sub.converted_client_id = client.id
    sub.converted_case_id = new_case.id
    sub.updated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    db.commit()
    
    return RedirectResponse(url=f"/cases", status_code=303)


# ============================================================================
# 2. الواجهات العامة للموكل (Public Prospective Client Form & E-Signature)
# ============================================================================

@router.get("/form/{form_token}", response_class=HTMLResponse)
async def public_intake_form(
    form_token: str,
    request: Request,
    db: Session = Depends(get_db)
):
    form_obj = db.query(ClientIntakeForms).filter(
        ClientIntakeForms.form_token == form_token,
        ClientIntakeForms.is_active == 1
    ).first()
    
    if not form_obj:
        return HTMLResponse("<div style='text-align:center;padding:50px;font-family:sans-serif;'><h2>عذراً، هذا الرابط غير صالح أو تم إيقافه.</h2></div>", status_code=404)
        
    office = db.query(LawOffices).filter(LawOffices.id == form_obj.office_id).first()
    
    return templates.TemplateResponse("intake/public_form.html", {
        "request": request,
        "form": form_obj,
        "office": office
    })

@router.post("/form/{form_token}/submit")
async def submit_public_intake_form(
    form_token: str,
    full_name: str = Form(...),
    phone: str = Form(...),
    email: Optional[str] = Form(None),
    national_id: Optional[str] = Form(None),
    case_type: Optional[str] = Form(None),
    case_summary: str = Form(...),
    opposing_party_name: Optional[str] = Form(None),
    opposing_party_id: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    form_obj = db.query(ClientIntakeForms).filter(
        ClientIntakeForms.form_token == form_token,
        ClientIntakeForms.is_active == 1
    ).first()
    
    if not form_obj:
        raise HTTPException(status_code=404, detail="النموذج غير موجود")
        
    # تشغيل محرك فحص تعارض المصالح الآلي
    conflict_res = check_conflict_of_interest(
        db=db,
        office_id=form_obj.office_id,
        client_name=full_name,
        client_national_id=national_id,
        client_phone=phone,
        opposing_name=opposing_party_name,
        opposing_id=opposing_party_id
    )
    
    sub_token = str(uuid.uuid4())
    
    submission = IntakeSubmissions(
        form_id=form_obj.id,
        office_id=form_obj.office_id,
        submission_token=sub_token,
        full_name=full_name.strip(),
        phone=phone.strip(),
        email=email.strip() if email else None,
        national_id=national_id.strip() if national_id else None,
        case_type=case_type.strip() if case_type else "استشارة عامة",
        case_summary=case_summary.strip(),
        opposing_party_name=opposing_party_name.strip() if opposing_party_name else None,
        opposing_party_id=opposing_party_id.strip() if opposing_party_id else None,
        conflict_status=conflict_res["status"],
        conflict_notes=json.dumps(conflict_res["conflicts"], ensure_ascii=False) if conflict_res["conflicts"] else None,
        status="pending"
    )
    db.add(submission)
    db.commit()
    db.refresh(submission)
    
    # إذا كان النموذج يتطلب توقيع عقد إلكتروني، نحوله لصفحة التوقيع
    if form_obj.require_signature:
        return RedirectResponse(url=f"/intake/sign/{sub_token}", status_code=303)
        
    return HTMLResponse(
        "<div style='text-align:center;padding:50px;font-family:sans-serif;direction:rtl;'>"
        "<h2 style='color:#059669;'>تم استلام طلبك بنجاح! ✅</h2>"
        "<p style='color:#4b5563;'>سيتواصل معك فريقنا القانوني لدراسة الطلب ومباشرة الإجراءات في أقرب وقت.</p>"
        "</div>"
    )

@router.get("/intake/sign/{submission_token}", response_class=HTMLResponse)
async def e_sign_page(
    submission_token: str,
    request: Request,
    db: Session = Depends(get_db)
):
    sub = db.query(IntakeSubmissions).filter(
        IntakeSubmissions.submission_token == submission_token
    ).first()
    
    if not sub:
        return HTMLResponse("<div style='text-align:center;padding:50px;'>عقد غير موجود</div>", status_code=404)
        
    office = db.query(LawOffices).filter(LawOffices.id == sub.office_id).first()
    form_obj = db.query(ClientIntakeForms).filter(ClientIntakeForms.id == sub.form_id).first()
    
    # التحقق هل تم التوقيع مسبقاً
    existing_agreement = db.query(RetainerAgreements).filter(
        RetainerAgreements.submission_id == sub.id,
        RetainerAgreements.is_signed == 1
    ).first()
    
    return templates.TemplateResponse("intake/e_sign.html", {
        "request": request,
        "sub": sub,
        "office": office,
        "form": form_obj,
        "already_signed": bool(existing_agreement),
        "agreement": existing_agreement
    })

@router.post("/intake/sign/{submission_token}")
async def process_e_signature(
    submission_token: str,
    request: Request,
    data: dict = Body(...),
    db: Session = Depends(get_db)
):
    sub = db.query(IntakeSubmissions).filter(
        IntakeSubmissions.submission_token == submission_token
    ).first()
    
    if not sub:
        return JSONResponse({"ok": False, "error": "الطلب غير موجود"}, status_code=404)
        
    signature_base64 = data.get("signature")
    if not signature_base64:
        return JSONResponse({"ok": False, "error": "التوقيع مطلوب"}, status_code=400)
        
    client_ip = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("user-agent", "unknown")
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    
    # إنشاء بصمة تحقق رقمية للعقد والتوقيع (Digital Verification Hash)
    hash_raw = f"{sub.id}-{sub.full_name}-{now_str}-{client_ip}"
    v_hash = hashlib.sha256(hash_raw.encode()).hexdigest()[:16].upper()
    
    agreement = db.query(RetainerAgreements).filter(
        RetainerAgreements.submission_id == sub.id
    ).first()
    
    if not agreement:
        agreement = RetainerAgreements(
            submission_id=sub.id,
            office_id=sub.office_id,
            agreement_number=f"AGR-{datetime.now().strftime('%Y%m')}-{uuid.uuid4().hex[:4].upper()}",
            agreement_title="عقد توكيل وتمثيل قانوني إلكتروني",
            agreement_body=f"تم إبرام هذا العقد بين الطرف الأول (المكتب) والطرف الثاني ({sub.full_name}) لمتابعة القضية وتفاصيلها: {sub.case_summary}.",
            signature_base64=signature_base64,
            signer_name=sub.full_name,
            signer_ip=client_ip,
            signer_user_agent=user_agent,
            is_signed=1,
            signed_at=now_str,
            verification_hash=v_hash
        )
        db.add(agreement)
    else:
        agreement.signature_base64 = signature_base64
        agreement.signer_name = sub.full_name
        agreement.signer_ip = client_ip
        agreement.signer_user_agent = user_agent
        agreement.is_signed = 1
        agreement.signed_at = now_str
        agreement.verification_hash = v_hash

    sub.status = "signed"
    sub.updated_at = now_str
    db.commit()
    
    return JSONResponse({"ok": True, "verification_hash": v_hash})

@router.get("/intake/agreement/{agreement_id}/view", response_class=HTMLResponse)
async def view_signed_agreement(
    agreement_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    agreement = db.query(RetainerAgreements).filter(RetainerAgreements.id == agreement_id).first()
    if not agreement:
        return HTMLResponse("<div style='text-align:center;'>العقد غير موجود</div>", status_code=404)
        
    sub = db.query(IntakeSubmissions).filter(IntakeSubmissions.id == agreement.submission_id).first()
    office = db.query(LawOffices).filter(LawOffices.id == agreement.office_id).first()
    
    return templates.TemplateResponse("intake/signed_contract_pdf.html", {
        "request": request,
        "agreement": agreement,
        "sub": sub,
        "office": office
    })
