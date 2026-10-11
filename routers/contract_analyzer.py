# -*- coding: utf-8 -*-
"""
Contract Analyzer Router — صفحة محلل العقود الذكي ومراجعة المخاطر والصياغة
"""
from fastapi import APIRouter, Request, Depends, HTTPException, Form
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from datetime import datetime

from database.database import get_db
from dependencies import get_current_user, check_user_permission
from database.models import AccessProfiles, LawCases, LawDocuments, LawAuditLog

router = APIRouter(tags=["Contract Analyzer"])
templates = Jinja2Templates(directory="templates")


@router.get("/contract-analyzer", response_class=HTMLResponse)
async def contract_analyzer_page(
    request: Request,
    case_id: int = None,
    doc_id: int = None,
    db: Session = Depends(get_db),
    current_user: AccessProfiles = Depends(get_current_user)
):
    """صفحة محلل العقود الذكي مع ربط بالقضايا ومستندات المكتب"""
    if not current_user:
        return RedirectResponse(url="/login")

    office_id = current_user.office_id
    cases_query = db.query(LawCases).filter(LawCases.office_id == office_id, LawCases.is_deleted == 0)
    
    if current_user.role in ['محامي', 'محامٍ'] and getattr(current_user, 'can_view_all_cases', 1) == 0:
        cases_query = cases_query.filter(LawCases.lead_lawyer_id == current_user.id)
        
    cases = cases_query.order_by(LawCases.case_number.asc()).all()
    
    # Contract documents in the office that can be directly analyzed
    contracts = db.query(LawDocuments).filter(
        LawDocuments.office_id == office_id,
        LawDocuments.is_deleted == 0,
        LawDocuments.document_type_key.in_(['عقد', 'اتفاقية', 'مذكرة'])
    ).order_by(LawDocuments.id.desc()).limit(30).all()

    return templates.TemplateResponse("contract_analyzer.html", {
        "request": request,
        "current_user": current_user,
        "cases": cases,
        "contracts": contracts,
        "selected_case_id": case_id,
        "selected_doc_id": doc_id,
        "page_title": "محلل العقود الذكي"
    })


@router.post("/api/contract-analyzer/save-report")
async def save_contract_report(
    request: Request,
    case_id: int = Form(...),
    contract_title: str = Form(...),
    report_content: str = Form(...),
    risk_level: str = Form("متوسط"),
    db: Session = Depends(get_db),
    current_user: AccessProfiles = Depends(get_current_user)
):
    """حفظ تقرير تحليل العقد وتوصيات الذكاء الاصطناعي مباشرة في مستندات القضية"""
    if not current_user:
        raise HTTPException(status_code=401, detail="غير مصرح")
    office_id = current_user.office_id

    case = db.query(LawCases).filter(LawCases.id == case_id, LawCases.office_id == office_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="القضية غير موجودة")

    # Generate document code
    today_str = datetime.now().strftime("%Y-%m-%d")
    doc_code = f"DOC-{datetime.now().year}-RPT{case_id}"

    # Create new document record in law_documents
    doc_name = f"تقرير فحص وتحليل عقد: {contract_title}"
    client_id = case.law_clients[0].id if case.law_clients else None

    new_doc = LawDocuments(
        office_id=office_id,
        case_id=case_id,
        client_id=client_id,
        name=doc_name[:200],
        document_type_key="تقرير",
        doc_code=doc_code,
        doc_date=today_str,
        received_date=today_str,
        description=f"تقرير مراجعة وتحليل قانوني بالذكاء الاصطناعي — مستوى المخاطر: {risk_level}",
        notes=report_content,
        internal_notes=f"تم التوليد آلياً عبر محلل العقود الذكي بواسطة {current_user.name}",
        is_archived=0,
        created_by_user_id=current_user.id
    )
    db.add(new_doc)

    # Audit log
    audit = LawAuditLog(
        table_name="law_documents",
        action_name="حفظ تقرير تحليل عقد",
        record_key=str(case_id),
        actor_name=current_user.name,
        actor_user_id=current_user.id,
        office_id=office_id,
        details=f"تم إنشاء تقرير تحليل عقد للقضية: {case.case_number} ({doc_name})"
    )
    db.add(audit)
    db.commit()

    return JSONResponse({
        "success": True,
        "message": "تم حفظ تقرير التحليل بنجاح في مستندات القضية والأرشيف",
        "doc_id": new_doc.id
    })
