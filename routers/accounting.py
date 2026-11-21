from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from sqlalchemy.orm import Session
from datetime import datetime, timezone
import uuid
import json
import math

from database.database import get_db
from database.models import AccessProfiles, LawOffices, LawClients, LawCases, Invoices, InvoiceItems, ClientPayments
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
        raise HTTPException(status_code=403, detail="غير مصرح لك")
    
    invoices = db.query(Invoices).filter(
        Invoices.office_id == user.office_id,
        Invoices.is_deleted == 0
    ).order_by(Invoices.id.desc()).all()
    
    # Build lookups for client name and case number
    client_ids = [inv.client_id for inv in invoices if inv.client_id]
    case_ids = [inv.case_id for inv in invoices if inv.case_id]
    
    clients_map = {}
    if client_ids:
        clients_list = db.query(LawClients).filter(
            LawClients.id.in_(client_ids),
            LawClients.office_id == user.office_id,
        ).all()
        clients_map = {c.id: c.name for c in clients_list}
        
    cases_map = {}
    if case_ids:
        cases_list = db.query(LawCases).filter(
            LawCases.id.in_(case_ids),
            LawCases.office_id == user.office_id,
        ).all()
        cases_map = {c.id: c.case_number for c in cases_list}
    
    # Attach dynamic attributes
    for inv in invoices:
        inv.client_name = clients_map.get(inv.client_id, None) if inv.client_id else None
        inv.case_number = cases_map.get(inv.case_id, None) if inv.case_id else None
        inv.remaining_amount = max(0.0, (inv.grand_total or 0.0) - (inv.amount_paid or 0.0))
        paid_ratio = (inv.amount_paid / inv.grand_total * 100) if (inv.grand_total and inv.grand_total > 0) else 0.0
        inv.paid_percentage = min(100.0, round(paid_ratio, 1))
    
    # KPIs calculations
    total_invoices = len(invoices)
    total_billed = sum((inv.grand_total or 0.0) for inv in invoices)
    total_collected = sum((inv.amount_paid or 0.0) for inv in invoices)
    total_remaining = max(0.0, total_billed - total_collected)
    collection_rate = round((total_collected / total_billed * 100), 1) if total_billed > 0 else 0.0
    paid_count = sum(1 for inv in invoices if inv.status == 'Paid')
    partial_count = sum(1 for inv in invoices if inv.status == 'Partial')
    unpaid_count = sum(1 for inv in invoices if inv.status in ['Unpaid', 'Draft'])
    
    stats = {
        "total_count": total_invoices,
        "total_billed": total_billed,
        "total_collected": total_collected,
        "total_remaining": total_remaining,
        "collection_rate": collection_rate,
        "paid_count": paid_count,
        "partial_count": partial_count,
        "unpaid_count": unpaid_count
    }
    
    # For quick forms/modals
    all_clients = db.query(LawClients).filter(LawClients.office_id == user.office_id, LawClients.is_deleted == 0).all()
    all_cases = db.query(LawCases).filter(LawCases.office_id == user.office_id, LawCases.is_deleted == 0).all()
    
    return templates.TemplateResponse("accounting/invoices.html", {
        "request": request,
        "user": user,
        "invoices": invoices,
        "stats": stats,
        "total_revenue": total_collected,
        "total_due": total_remaining,
        "clients": all_clients,
        "cases": all_cases,
        "active_page": "accounting"
    })

@router.get("/invoices/new", response_class=HTMLResponse)
async def new_invoice_page(request: Request, db: Session = Depends(get_db), user: AccessProfiles = Depends(get_admin_user)):
    if not check_user_permission(user, 'accounting', 'add'):
        raise HTTPException(status_code=403, detail="غير مصرح لك")
    
    clients = db.query(LawClients).filter(LawClients.office_id == user.office_id, LawClients.is_deleted == 0).all()
    cases = db.query(LawCases).filter(LawCases.office_id == user.office_id, LawCases.is_deleted == 0).all()
    
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
        vat_number = getattr(office, 'vat_number', '') or ""
        
        qr_base64 = generate_zatca_qr(
            seller_name=seller_name,
            vat_number=vat_number,
            timestamp=issue_date,
            invoice_total=grand_total,
            vat_total=tax_total
        )
        
        invoice_type = data.get('invoice_type') or "Simplified"
        
        new_invoice = Invoices(
            office_id=user.office_id,
            client_id=client_id,
            case_id=case_id,
            invoice_number=(str(data.get('invoice_number') or f"INV-{int(datetime.now().timestamp())}").strip()[:80]),
            uuid=new_uuid,
            issue_date=issue_date,
            due_date=data.get('due_date'),
            invoice_type=invoice_type,
            status="Unpaid",
            subtotal=subtotal,
            tax_total=tax_total,
            grand_total=grand_total,
            amount_paid=0.0,
            zatca_qr=qr_base64,
            notes=data.get('notes'),
            created_by=user.id,
            is_deleted=0
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
        
        return JSONResponse({"ok": True, "message": "تم إصدار الفاتورة بنجاح", "uuid": new_uuid, "invoice_id": new_invoice.id})
        
    except Exception as exc:
        db.rollback()
        return JSONResponse({"ok": False, "message": f"حدث خطأ أثناء إصدار الفاتورة: {str(exc)}"}, status_code=500)

@router.get("/api/invoices/{uuid}")
async def get_invoice_details(uuid: str, db: Session = Depends(get_db), user: AccessProfiles = Depends(get_admin_user)):
    invoice = db.query(Invoices).filter(
        Invoices.uuid == uuid,
        Invoices.office_id == user.office_id,
        Invoices.is_deleted == 0
    ).first()
    if not invoice:
        return JSONResponse({"ok": False, "message": "الفاتورة غير موجودة"}, status_code=404)
        
    items = db.query(InvoiceItems).filter(InvoiceItems.invoice_id == invoice.id).all()
    payments = db.query(ClientPayments).filter(ClientPayments.invoice_id == invoice.id).all()
    client = db.query(LawClients).filter(LawClients.id == invoice.client_id).first() if invoice.client_id else None
    case = db.query(LawCases).filter(LawCases.id == invoice.case_id).first() if invoice.case_id else None
    
    return JSONResponse({
        "ok": True,
        "data": {
            "id": invoice.id,
            "uuid": invoice.uuid,
            "invoice_number": invoice.invoice_number,
            "issue_date": invoice.issue_date,
            "due_date": invoice.due_date,
            "status": invoice.status,
            "invoice_type": invoice.invoice_type,
            "subtotal": invoice.subtotal,
            "tax_total": invoice.tax_total,
            "grand_total": invoice.grand_total,
            "amount_paid": invoice.amount_paid,
            "remaining": max(0.0, (invoice.grand_total or 0.0) - (invoice.amount_paid or 0.0)),
            "client_name": client.name if client else "غير محدد",
            "case_number": case.case_number if case else None,
            "case_title": case.title if case else None,
            "notes": invoice.notes,
            "items": [{
                "description": it.description,
                "quantity": it.quantity,
                "unit_price": it.unit_price,
                "tax_rate": it.tax_rate,
                "tax_amount": it.tax_amount,
                "line_total": it.line_total
            } for it in items],
            "payments": [{
                "id": p.id,
                "amount": p.amount,
                "payment_method": p.payment_method,
                "payment_date": p.payment_date,
                "reference_number": p.reference_number,
                "notes": p.notes
            } for p in payments]
        }
    })

@router.post("/api/invoices/{uuid}/payment")
async def record_invoice_payment(uuid: str, request: Request, db: Session = Depends(get_db), user: AccessProfiles = Depends(get_admin_user)):
    if not check_user_permission(user, 'accounting', 'edit'):
        return JSONResponse({"ok": False, "message": "غير مصرح لك بتسجيل دفعات"}, status_code=403)
    
    invoice = db.query(Invoices).filter(
        Invoices.uuid == uuid,
        Invoices.office_id == user.office_id,
        Invoices.is_deleted == 0
    ).first()
    if not invoice:
        return JSONResponse({"ok": False, "message": "الفاتورة غير موجودة"}, status_code=404)
        
    try:
        data = await request.json()
        amount = float(data.get("amount", 0))
        if amount <= 0:
            return JSONResponse({"ok": False, "message": "مبلغ السداد يجب أن يكون أكبر من الصفر"}, status_code=400)
            
        remaining = max(0.0, (invoice.grand_total or 0.0) - (invoice.amount_paid or 0.0))
        if amount > remaining + 0.01:
            return JSONResponse({"ok": False, "message": f"المبلغ المدخل ({amount:,.2f}) يتجاوز المتبقي المستحق ({remaining:,.2f} ر.ي)"}, status_code=400)
            
        payment_method = data.get("payment_method") or "Bank Transfer"
        reference_number = data.get("reference_number") or None
        notes = data.get("notes") or None
        payment_date = data.get("payment_date") or datetime.now().strftime("%Y-%m-%d")
        
        payment = ClientPayments(
            office_id=user.office_id,
            invoice_id=invoice.id,
            client_id=invoice.client_id,
            amount=amount,
            payment_method=payment_method,
            reference_number=reference_number,
            payment_date=payment_date,
            notes=notes,
            created_by=user.id
        )
        db.add(payment)
        
        invoice.amount_paid = (invoice.amount_paid or 0.0) + amount
        if invoice.amount_paid >= (invoice.grand_total or 0.0) - 0.01:
            invoice.status = "Paid"
        else:
            invoice.status = "Partial"
            
        db.commit()
        return JSONResponse({
            "ok": True,
            "message": "تم تسجيل دفعة السداد بنجاح",
            "new_amount_paid": invoice.amount_paid,
            "remaining": max(0.0, invoice.grand_total - invoice.amount_paid),
            "status": invoice.status
        })
    except Exception as e:
        db.rollback()
        return JSONResponse({"ok": False, "message": f"فشل تسجيل الدفعة: {str(e)}"}, status_code=500)

@router.delete("/api/invoices/{uuid}")
async def delete_invoice(uuid: str, db: Session = Depends(get_db), user: AccessProfiles = Depends(get_admin_user)):
    if not check_user_permission(user, 'accounting', 'delete'):
        return JSONResponse({"ok": False, "message": "غير مصرح لك بحذف الفواتير"}, status_code=403)
        
    invoice = db.query(Invoices).filter(
        Invoices.uuid == uuid,
        Invoices.office_id == user.office_id,
        Invoices.is_deleted == 0
    ).first()
    if not invoice:
        return JSONResponse({"ok": False, "message": "الفاتورة غير موجودة"}, status_code=404)
        
    invoice.is_deleted = 1
    invoice.status = "Cancelled"
    db.commit()
    return JSONResponse({"ok": True, "message": "تم إلغاء وحذف الفاتورة بنجاح"})

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
        Invoices.is_deleted == 0
    ).first()
    if not invoice:
        return HTMLResponse("فاتورة غير موجودة", status_code=404)
        
    items = db.query(InvoiceItems).filter(InvoiceItems.invoice_id == invoice.id).all()
    office = db.query(LawOffices).filter(LawOffices.id == invoice.office_id).first()
    client = db.query(LawClients).filter(
        LawClients.id == invoice.client_id,
        LawClients.office_id == user.office_id,
    ).first() if invoice.client_id else None
    
    return templates.TemplateResponse("accounting/invoice_pdf.html", {
        "request": request,
        "invoice": invoice,
        "items": items,
        "office": office,
        "client": client
    })
