import sys

with open('routers/superadmin.py', 'rb') as f:
    content = f.read().decode('utf-8')

# 1. Add PaymentRequest import
content = content.replace("from database.models import AccessProfiles, LawOffices", "from database.models import AccessProfiles, LawOffices, PaymentRequest")

# 2. Add payment_requests query inside /superadmin route
old_return = """        return templates.TemplateResponse(request=request, name="superadmin.html", context={
            "user": user,
            "active_page": "superadmin",
            "offices": office_data
        })"""

new_return = """        payment_requests = db.query(PaymentRequest).order_by(PaymentRequest.id.desc()).all()
        pr_data = []
        for pr in payment_requests:
            pr_office = db.query(LawOffices).filter(LawOffices.id == pr.office_id).first()
            pr_owner = db.query(AccessProfiles).filter(AccessProfiles.id == pr.user_id).first() if pr.user_id else None
            pr_data.append({
                "id": pr.id,
                "office_id": pr.office_id,
                "office_name": pr_office.name if pr_office else "مكتب محذوف",
                "owner_email": pr_owner.email if pr_owner else "غير معروف",
                "plan": pr.plan,
                "amount": pr.amount,
                "transfer_ref": pr.transfer_ref,
                "receipt_base64": pr.receipt_base64,
                "status": pr.status,
                "submitted_at": pr.submitted_at,
                "admin_notes": pr.admin_notes
            })
            
        return templates.TemplateResponse(request=request, name="superadmin.html", context={
            "user": user,
            "active_page": "superadmin",
            "offices": office_data,
            "payment_requests": pr_data
        })"""
content = content.replace(old_return, new_return)

# 3. Replace approve-receipt endpoint with approve-payment endpoint
old_approve_endpoint = """@router.post("/api/superadmin/approve-receipt/{office_id}")
async def approve_receipt(office_id: int, request: Request, db: Session = Depends(get_db), user: AccessProfiles = Depends(get_current_user)):
    if not user or not is_superadmin(user):
        return JSONResponse({"success": False, "error": "غير مصرح لك بالقيام بهذا الإجراء"}, status_code=403)
        
    try:
        data = await request.json()
        action = data.get("action") # 'approve' or 'reject'
        
        office = db.query(LawOffices).filter(LawOffices.id == office_id).first()
        if not office:
            return JSONResponse({"success": False, "error": "المكتب غير موجود"}, status_code=404)
            
        if action == 'approve':
            from datetime import datetime, timezone, timedelta
            now = datetime.now(timezone.utc).replace(tzinfo=None)
            plan = getattr(office, 'subscription_plan', 'monthly')
            if plan == 'yearly':
                end_date = now + timedelta(days=365)
            else:
                end_date = now + timedelta(days=30)
                
            office.subscription_end = end_date.strftime("%Y-%m-%d %H:%M:%S")
            office.receipt_status = 'approved'
            office.receipt_base64 = None # Clear receipt to save space
            office.is_active = 1 # Auto-activate if suspended
            db.commit()
            return JSONResponse({"success": True, "message": "تم اعتماد السند وتفعيل الاشتراك بنجاح"})
            
        elif action == 'reject':
            office.receipt_status = 'rejected'
            office.receipt_base64 = None
            db.commit()
            return JSONResponse({"success": True, "message": "تم رفض السند"})
            
        return JSONResponse({"success": False, "error": "إجراء غير صالح"}, status_code=400)
    except Exception as e:
        db.rollback()
        app_logger.error(f"Superadmin receipt approval error: {e}")
        return JSONResponse({"success": False, "error": "حدث خطأ داخلي"}, status_code=500)"""

new_approve_endpoint = """@router.post("/api/superadmin/approve-payment/{payment_id}")
async def approve_payment(payment_id: int, request: Request, db: Session = Depends(get_db), user: AccessProfiles = Depends(get_current_user)):
    if not user or not is_superadmin(user):
        return JSONResponse({"success": False, "error": "غير مصرح لك بالقيام بهذا الإجراء"}, status_code=403)
        
    try:
        data = await request.json()
        action = data.get("action") # 'approve' or 'reject'
        notes = data.get("notes", "")
        
        payment = db.query(PaymentRequest).filter(PaymentRequest.id == payment_id).first()
        if not payment:
            return JSONResponse({"success": False, "error": "طلب الدفع غير موجود"}, status_code=404)
            
        office = db.query(LawOffices).filter(LawOffices.id == payment.office_id).first()
        office_owner = db.query(AccessProfiles).filter(AccessProfiles.id == payment.user_id).first()
        
        from datetime import datetime, timezone, timedelta
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        
        if action == 'approve':
            if office:
                # Update Office Subscription
                if payment.plan == 'yearly':
                    end_date = now + timedelta(days=365)
                else:
                    end_date = now + timedelta(days=30)
                office.subscription_plan = payment.plan
                office.subscription_end = end_date.strftime("%Y-%m-%d %H:%M:%S")
                office.is_active = 1
                
            payment.status = 'approved'
            payment.reviewed_at = now.strftime("%Y-%m-%d %H:%M:%S")
            payment.reviewed_by = user.id
            
            # Send Email
            if office_owner and office_owner.email:
                try:
                    from email_service import send_email_async
                    import asyncio
                    html_content = f\"\"\"
                    <div dir="rtl">
                        <h2 style="color: #10b981;">✅ تم تفعيل اشتراكك بنجاح</h2>
                        <p>شكراً لثقتك بنا في LawSaaS.</p>
                        <p>لقد تم تأكيد دفعتك وتفعيل باقتك ({payment.plan}).</p>
                    </div>
                    \"\"\"
                    asyncio.create_task(send_email_async(office_owner.email, "✅ تم تفعيل اشتراكك - LawSaaS", html_content))
                except Exception:
                    pass
                    
            db.commit()
            return JSONResponse({"success": True, "message": "تم اعتماد السند وتفعيل الاشتراك بنجاح"})
            
        elif action == 'reject':
            payment.status = 'rejected'
            payment.admin_notes = notes
            payment.reviewed_at = now.strftime("%Y-%m-%d %H:%M:%S")
            payment.reviewed_by = user.id
            
            # Send Email
            if office_owner and office_owner.email:
                try:
                    from email_service import send_email_async
                    import asyncio
                    html_content = f\"\"\"
                    <div dir="rtl">
                        <h2 style="color: #ef4444;">❌ لم يتم قبول طلب الدفع</h2>
                        <p>مرحباً، تم رفض إيصال الدفع الذي رفعته لسبب التالي:</p>
                        <p style="background: #f1f5f9; padding: 10px; border-radius: 5px;">{notes}</p>
                        <p>يرجى التأكد من بيانات التحويل والمحاولة مرة أخرى.</p>
                    </div>
                    \"\"\"
                    asyncio.create_task(send_email_async(office_owner.email, "❌ تنبيه بشأن طلب الدفع - LawSaaS", html_content))
                except Exception:
                    pass
                    
            db.commit()
            return JSONResponse({"success": True, "message": "تم رفض السند"})
            
        return JSONResponse({"success": False, "error": "إجراء غير صالح"}, status_code=400)
    except Exception as e:
        db.rollback()
        app_logger.error(f"Superadmin payment approval error: {e}")
        return JSONResponse({"success": False, "error": "حدث خطأ داخلي"}, status_code=500)"""

content = content.replace(old_approve_endpoint, new_approve_endpoint)

with open('routers/superadmin.py', 'wb') as f:
    f.write(content.encode('utf-8'))
print("Successfully patched superadmin.py")
