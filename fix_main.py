import sys

with open('main.py', 'rb') as f:
    content = f.read().decode('utf-8')

# Find the start of the subscription routes
start_idx = content.find('@app.get("/subscription")')
if start_idx == -1:
    print('Could not find subscription route')
    sys.exit(1)

# Find where the ai-assistant route starts, so we don't delete it
end_idx = content.find('@app.get("/ai-assistant")', start_idx)
if end_idx == -1:
    print('Could not find ai-assistant route')
    sys.exit(1)

new_code = """@app.get("/subscription")
async def view_subscription(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/", status_code=303)
    office = db.query(LawOffices).filter(LawOffices.id == user.office_id).first() if user.office_id else None
    
    payment_requests = []
    pending_request = False
    if office:
        payment_requests = db.query(PaymentRequest).filter(PaymentRequest.office_id == office.id).order_by(PaymentRequest.id.desc()).all()
        if any(r.status == "pending" for r in payment_requests):
            pending_request = True
            
    return templates.TemplateResponse("subscription.html", {
        "request": request, 
        "user": user, 
        "office": office,
        "payment_requests": payment_requests,
        "pending_request": pending_request
    })

@app.post("/api/subscription/checkout")
async def api_subscription_checkout(request: Request, db: Session = Depends(get_db)):
    from fastapi.responses import JSONResponse as _J
    user = get_current_user(request, db)
    if not user:
        return _J({"success": False, "error": "غير مصرح"}, status_code=403)
        
    if user.role not in ['مدير النظام', 'مدير', 'مدير المكتب', 'صاحب مكتب']:
        return _J({"success": False, "error": "غير مصرح لك بتجديد الاشتراك"}, status_code=403)
        
    data = await request.json()
    plan = data.get("plan")
    amount = data.get("amount")
    transfer_ref = data.get("transfer_ref")
    receipt_base64 = data.get("receipt_base64", "")
    
    if plan not in ['monthly', 'yearly']:
        return _J({"success": False, "error": "خطة غير صالحة"}, status_code=400)
        
    office = db.query(LawOffices).filter(LawOffices.id == user.office_id).first()
    if not office:
        return _J({"success": False, "error": "المكتب غير موجود"}, status_code=404)
        
    if not receipt_base64 or not transfer_ref:
        return _J({"success": False, "error": "يرجى إرفاق صورة السند ورقم المرجع"}, status_code=400)
        
    allowed_prefixes = ('data:image/jpeg', 'data:image/jpg', 'data:image/png', 'data:image/gif', 'data:image/webp')
    if not any(receipt_base64.startswith(p) for p in allowed_prefixes):
        return _J({"success": False, "error": "يرجى رفع صورة فقط (JPG, PNG, WEBP)"}, status_code=400)
        
    if len(receipt_base64) > 7_000_000:
        return _J({"success": False, "error": "حجم الصورة كبير جداً. يرجى ضغطها قبل الرفع"}, status_code=400)
        
    existing_pending = db.query(PaymentRequest).filter(
        PaymentRequest.office_id == office.id,
        PaymentRequest.status == 'pending'
    ).first()
    
    if existing_pending:
        return _J({"success": False, "error": "يوجد لديك طلب دفع قيد المراجعة بالفعل."})
        
    new_req = PaymentRequest(
        office_id=office.id,
        user_id=user.id,
        plan=plan,
        amount=amount,
        transfer_ref=transfer_ref,
        receipt_base64=receipt_base64,
        status='pending'
    )
    db.add(new_req)
    db.commit()
    
    try:
        from email_service import send_email_async
        import asyncio
        html_content = f\"\"\"
        <div dir="rtl" style="font-family: Arial, sans-serif;">
            <h2 style="color: #5c2d91;">طلب دفع جديد 💰</h2>
            <p><strong>المكتب:</strong> {office.name}</p>
            <p><strong>المبلغ:</strong> ${amount} ({plan})</p>
            <p><strong>المرجع:</strong> {transfer_ref}</p>
            <p>يرجى الدخول إلى لوحة تحكم SuperAdmin لمراجعة الإيصال وتفعيل الحساب.</p>
        </div>
        \"\"\"
        asyncio.create_task(send_email_async("aboodalalimi@icloud.com", f"💰 طلب دفع جديد - {office.name}", html_content))
    except Exception as e:
        pass

    write_audit(db, "payment_requests", "submit_payment", user.id, user.name, new_req.id, "office", office.id, f"Submitted payment request for {plan}")
    
    return _J({"success": True, "message": "تم إرسال السند بنجاح"})

"""

final_content = content[:start_idx] + new_code + content[end_idx:]

with open('main.py', 'wb') as f:
    f.write(final_content.encode('utf-8'))

print('Successfully replaced subscription routes.')
