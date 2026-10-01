from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from sqlalchemy.orm import Session
from datetime import datetime, timezone
import uuid
import json
import math

from database.database import get_db
from database.models import AccessProfiles, LawOffices, LawClients, LawCases, Invoices, InvoiceItems
from dependencies import templates, get_current_user, check_user_permission
from utils.zatca_qr import generate_zatca_qr

router = APIRouter(prefix="/accounting", tags=["Accounting & ZATCA"])

def get_admin_user(user: AccessProfiles = Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=303, headers={"Location": "/"})
    if user.role == "موكل":
        raise HTTPException(status_code=303, headers={"Location": "/client-portal"})
    return user

@router.get("/invoices", response_class=HTMLResponse)
async def list_invoices(request: Request, db: Session = Depends(get_db), user: AccessProfiles = Depends(get_admin_user)):
    if not check_user_permission(user, 'accounting', 'view'):
        return HTMLResponse("<script>alert('غير مصرح لك'); window.location.href='/dashboard';</script>")
    
    invoices = db.query(Invoices).filter(Invoices.office_id == user.office_id).order_by(Invoices.id.desc()).all()
    
    # Build a client name lookup dict
    client_ids = [inv.client_id for inv in invoices if inv.client_id]
    clients_map = {}
    if client_ids:
        clients_list = db.query(LawClients).filter(LawClients.id.in_(client_ids)).all()
        clients_map = {c.id: c.name for c in clients_list}
    
    # Attach client_name to each invoice (as dynamic attribute)
    for inv in invoices:
        inv.client_name = clients_map.get(inv.client_id, None) if inv.client_id else None
    
    total_revenue = sum(inv.grand_total for inv in invoices if inv.status in ['Paid', 'Partial'])
    total_due = sum((inv.grand_total - inv.amount_paid) for inv in invoices if inv.status in ['Unpaid', 'Partial', 'Draft'])
    
    return templates.TemplateResponse("accounting/invoices.html", {
        "request": request,
        "user": user,
        "invoices": invoices,
        "total_revenue": total_revenue,
        "total_due": total_due,
        "active_page": "accounting"
    })

@router.get("/invoices/new", response_class=HTMLResponse)
async def new_invoice_page(request: Request, db: Session = Depends(get_db), user: AccessProfiles = Depends(get_admin_user)):
    if not check_user_permission(user, 'accounting', 'add'):
        return HTMLResponse("<script>alert('غير مصرح لك'); window.location.href='/accounting/invoices';</script>")
    
    clients = db.query(LawClients).filter(LawClients.office_id == user.office_id).all()
    cases = db.query(LawCases).filter(LawCases.office_id == user.office_id).all()
    
    # Generate a draft invoice number
    count = db.query(Invoices).filter(Invoices.office_id == user.office_id).count()
    draft_number = f"INV-{datetime.now().strftime('%Y%m')}-{(count + 1):04d}"
    
    return templates.TemplateResponse("accounting/invoice_form.html", {
        "request": request,
        "user": user,
        "clients": clients,
        "cases": cases,
        "draft_number": draft_number,
        "active_page": "accounting"
    })

@router.post("/api/invoices")
async def create_invoice(request: Request, db: Session = Depends(get_db), user: AccessProfiles = Depends(get_admin_user)):
    if not check_user_permission(user, 'accounting', 'add'):
        return JSONResponse({"ok": False, "message": "غير مصرح لك بإصدار فاتورة"}, status_code=403)
        
    data = await request.json()
    if not isinstance(data, dict):
        return JSONResponse({"ok": False, "message": "بيانات الفاتورة غير صالحة"}, status_code=400)

    items_data = data.get('items')
    if not isinstance(items_data, list) or not items_data or len(items_data) > 100:
        return JSONResponse({"ok": False, "message": "يجب أن تحتوي الفاتورة من بند إلى 100 بند"}, status_code=400)

    if not user.office_id:
        return JSONResponse({"ok": False, "message": "المستخدم غير مرتبط بمكتب"}, status_code=400)

    office = db.query(LawOffices).filter(LawOffices.id == user.office_id).first()
    if not office:
        return JSONResponse({"ok": False, "message": "المكتب غير موجود"}, status_code=404)

    client_id = data.get('client_id') or None
    case_id = data.get('case_id') or None
    try:
        client_id = int(client_id) if client_id is not None else None
        case_id = int(case_id) if case_id is not None else None
    except (TypeError, ValueError):
        return JSONResponse({"ok": False, "message": "العميل أو القضية غير صالحين"}, status_code=400)
    client = db.query(LawClients).filter(
        LawClients.id == client_id, LawClients.office_id == user.office_id,
        LawClients.is_deleted == 0,
    ).first() if client_id else None
    if client_id and not client:
        return JSONResponse({"ok": False, "message": "العميل غير موجود في هذا المكتب"}, status_code=400)
    case = db.query(LawCases).filter(
        LawCases.id == case_id, LawCases.office_id == user.office_id,
        LawCases.is_deleted == 0,
    ).first() if case_id else None
    if case_id and not case:
        return JSONResponse({"ok": False, "message": "القضية غير موجودة في هذا المكتب"}, status_code=400)
    if case and client_id and case.client_id not in (None, client_id):
        return JSONResponse({"ok": False, "message": "القضية لا تخص العميل المحدد"}, status_code=400)
    
    try:
        new_uuid = str(uuid.uuid4())
        issue_date = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        
        # Calculate totals securely on server side
        subtotal = 0.0
        tax_total = 0.0
        grand_total = 0.0
        
        for item in items_data:
            if not isinstance(item, dict) or len(str(item.get('description', ''))) > 500:
                raise ValueError("بند الفاتورة غير صالح")
            qty = float(item.get('quantity', 1))
            price = float(item.get('unit_price', 0))
            tax_rate = float(item.get('tax_rate', 15.0))
            if not all(math.isfinite(value) for value in (qty, price, tax_rate)) or qty <= 0 or price < 0 or not 0 <= tax_rate <= 100:
                raise ValueError("قيمة كمية أو سعر أو ضريبة غير صالحة")
            
            line_sub = qty * price
            line_tax = line_sub * (tax_rate / 100)
            
            subtotal += line_sub
            tax_total += line_tax
            grand_total += (line_sub + line_tax)
            
        # ZATCA QR Code Generation
        seller_name = office.name if office else "Law Firm"
        # Assuming office has VAT number, if not, fallback
        vat_number = ""
        
        qr_base64 = generate_zatca_qr(
            seller_name=seller_name,
            vat_number=vat_number,
            timestamp=issue_date,
            invoice_total=grand_total,
            vat_total=tax_total
        )
        
        new_invoice = Invoices(
            office_id=user.office_id,
            client_id=client_id,
            case_id=case_id,
            invoice_number=(str(data.get('invoice_number') or f"INV-{int(datetime.now().timestamp())}").strip()[:80]),
            uuid=new_uuid,
            issue_date=issue_date,
            due_date=data.get('due_date'),
            invoice_type="Simplified",
            status="Unpaid",
            subtotal=subtotal,
            tax_total=tax_total,
            grand_total=grand_total,
            amount_paid=0.0,
            zatca_qr=qr_base64,
            notes=data.get('notes'),
            created_by=user.id
        )
        db.add(new_invoice)
        db.flush()
        
        for item in items_data:
            qty = float(item.get('quantity', 1))
            price = float(item.get('unit_price', 0))
            tax_rate = float(item.get('tax_rate', 15.0))
            line_tax = (qty * price) * (tax_rate / 100)
            line_total = (qty * price) + line_tax
            
            new_item = InvoiceItems(
                invoice_id=new_invoice.id,
                description=item.get('description', 'Service'),
                quantity=qty,
                unit_price=price,
                tax_rate=tax_rate,
                tax_amount=line_tax,
                line_total=line_total
            )
            db.add(new_item)
            
        db.commit()
        
        return JSONResponse({"ok": True, "message": "تم إصدار الفاتورة بنجاح", "uuid": new_uuid})
        
    except Exception:
        db.rollback()
        return JSONResponse({"ok": False, "message": "حدث خطأ أثناء إصدار الفاتورة"}, status_code=500)

@router.get("/invoices/{uuid}/pdf", response_class=HTMLResponse)
async def view_invoice_pdf(
    uuid: str,
    request: Request,
    db: Session = Depends(get_db),
    user: AccessProfiles = Depends(get_admin_user),
):
    if not user.office_id:
        raise HTTPException(status_code=403, detail="غير مصرح")
    invoice = db.query(Invoices).filter(
        Invoices.uuid == uuid,
        Invoices.office_id == user.office_id,
    ).first()
    if not invoice:
        return HTMLResponse("فاتورة غير موجودة", status_code=404)
        
    items = db.query(InvoiceItems).filter(InvoiceItems.invoice_id == invoice.id).all()
    office = db.query(LawOffices).filter(LawOffices.id == invoice.office_id).first()
    client = db.query(LawClients).filter(LawClients.id == invoice.client_id).first() if invoice.client_id else None
    
    return templates.TemplateResponse("accounting/invoice_pdf.html", {
        "request": request,
        "invoice": invoice,
        "items": items,
        "office": office,
        "client": client
    })
