from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from sqlalchemy.orm import Session
import json

from database.database import get_db
from database.models import AccessProfiles, LawOffices, PaymentRequest
from dependencies import get_current_user, templates
from core.logger import app_logger

router = APIRouter()

def is_superadmin(user: AccessProfiles):
    if not user:
        return False
    return getattr(user, 'is_superadmin', 0) == 1

@router.get("/superadmin", response_class=HTMLResponse)
async def superadmin_page(request: Request, db: Session = Depends(get_db), user: AccessProfiles = Depends(get_current_user)):
    if not user or not is_superadmin(user):
        return RedirectResponse(url="/dashboard", status_code=303)
    
    try:
        # Fetch all offices
        offices = db.query(LawOffices).all()
        
        # Fetch the owner details for each office
        office_data = []
        for office in offices:
            owner = db.query(AccessProfiles).filter(AccessProfiles.id == office.owner_user_id).first() if office.owner_user_id else None
            # Count users in this office
            user_count = db.query(AccessProfiles).filter(AccessProfiles.office_id == office.id).count()
            
            office_data.append({
                "id": office.id,
                "name": office.name,
                "status_key": office.status_key,
                "is_active": office.is_active,
                "created_at": office.created_at,
                "user_count": user_count,
                "owner_name": owner.name if owner else "غير محدد",
                "owner_email": owner.email if owner else "غير محدد",
                "owner_phone": owner.phone if owner else "غير محدد",
                "subscription_plan": getattr(office, 'subscription_plan', 'trial'),
                "subscription_end": getattr(office, 'subscription_end', None),
                "receipt_status": getattr(office, 'receipt_status', None),
                "receipt_base64": getattr(office, 'receipt_base64', None)
            })
            
        payment_requests = db.query(PaymentRequest).order_by(PaymentRequest.id.desc()).all()
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
        })
    except Exception as e:
        import traceback
        app_logger.error(f"Superadmin page error: {e}\n{traceback.format_exc()}")
        return HTMLResponse(content=f"An error occurred: {e}", status_code=500)

@router.post("/api/superadmin/toggle-office/{office_id}")
async def toggle_office(office_id: int, request: Request, db: Session = Depends(get_db), user: AccessProfiles = Depends(get_current_user)):
    if not user or not is_superadmin(user):
        return JSONResponse({"success": False, "error": "غير مصرح لك بالقيام بهذا الإجراء"}, status_code=403)
        
    try:
        office = db.query(LawOffices).filter(LawOffices.id == office_id).first()
        if not office:
            return JSONResponse({"success": False, "error": "المكتب غير موجود"}, status_code=404)
            
        # Toggle status
        office.is_active = 1 if office.is_active == 0 else 0
        db.commit()
        
        status_text = "تفعيل" if office.is_active == 1 else "إيقاف"
        app_logger.info(f"SUPERADMIN | Office {office.id} toggled to {office.is_active} by user {user.id}")
        
        return JSONResponse({"success": True, "message": f"تم {status_text} المكتب بنجاح", "is_active": office.is_active})
    except Exception as e:
        db.rollback()
        app_logger.error(f"Superadmin toggle error: {e}")
        return JSONResponse({"success": False, "error": "حدث خطأ داخلي"}, status_code=500)

@router.post("/api/superadmin/approve-payment/{payment_id}")
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
                    html_content = f"""
                    <div dir="rtl">
                        <h2 style="color: #10b981;">✅ تم تفعيل اشتراكك بنجاح</h2>
                        <p>شكراً لثقتك بنا في LawSaaS.</p>
                        <p>لقد تم تأكيد دفعتك وتفعيل باقتك ({payment.plan}).</p>
                    </div>
                    """
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
                    html_content = f"""
                    <div dir="rtl">
                        <h2 style="color: #ef4444;">❌ لم يتم قبول طلب الدفع</h2>
                        <p>مرحباً، تم رفض إيصال الدفع الذي رفعته لسبب التالي:</p>
                        <p style="background: #f1f5f9; padding: 10px; border-radius: 5px;">{notes}</p>
                        <p>يرجى التأكد من بيانات التحويل والمحاولة مرة أخرى.</p>
                    </div>
                    """
                    asyncio.create_task(send_email_async(office_owner.email, "❌ تنبيه بشأن طلب الدفع - LawSaaS", html_content))
                except Exception:
                    pass
                    
            db.commit()
            return JSONResponse({"success": True, "message": "تم رفض السند"})
            
        return JSONResponse({"success": False, "error": "إجراء غير صالح"}, status_code=400)
    except Exception as e:
        db.rollback()
        app_logger.error(f"Superadmin payment approval error: {e}")
        return JSONResponse({"success": False, "error": "حدث خطأ داخلي"}, status_code=500)

@router.get("/api/superadmin/fix-subscriptions")
async def fix_legacy_subscriptions(request: Request, db: Session = Depends(get_db), user: AccessProfiles = Depends(get_current_user)):
    if not user or not is_superadmin(user):
        return JSONResponse({"success": False, "error": "غير مصرح"}, status_code=403)
        
    try:
        from datetime import datetime, timezone, timedelta
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        trial_end = now + timedelta(days=14)
        trial_end_str = trial_end.strftime("%Y-%m-%d %H:%M:%S")
        
        offices = db.query(LawOffices).all()
        updated_count = 0
        for off in offices:
            owner = db.query(AccessProfiles).filter(AccessProfiles.id == off.owner_user_id).first() if off.owner_user_id else None
            is_main = off.id == 1 or off.name == 'المكتب الرئيسي' or (owner and getattr(owner, 'is_superadmin', 0) == 1)
            
            if is_main:
                off.subscription_plan = 'lifetime'
                off.subscription_end = None
                off.receipt_status = 'approved'
            else:
                off.subscription_plan = 'trial'
                off.subscription_end = trial_end_str
                off.receipt_status = None
            
            updated_count += 1
            
        db.commit()
        return JSONResponse({"success": True, "message": f"تم تحديث اشتراكات {updated_count} مكتب بنجاح. المكتب الرئيسي أصبح مجاني دائماً والبقية تم إعطاؤهم 14 يوم من اليوم."})
    except Exception as e:
        db.rollback()
        app_logger.error(f"Superadmin fix subscriptions error: {e}")
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)
