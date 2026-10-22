from fastapi import APIRouter, Request, Depends, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timezone, timedelta
import json
import html
import uuid

from database.database import get_db
from database.models import AccessProfiles, LawOffices, PaymentRequest, LawCases, LawDocuments, AuthSessions
from dependencies import get_current_user, templates
from core.security import hash_session_token
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
        
        # Calculate SaaS KPI metrics
        total_offices = len(offices)
        active_offices = sum(1 for o in offices if o.is_active == 1)
        trial_offices = sum(1 for o in offices if getattr(o, 'subscription_plan', 'trial') == 'trial')
        paid_offices = sum(1 for o in offices if getattr(o, 'subscription_plan', 'trial') in ['monthly', 'yearly'])
        
        # Calculate Estimated MRR ($49.99/mo or $499.99/yr -> ~$41.67/mo)
        mrr = 0.0
        for o in offices:
            if o.is_active == 1:
                plan = getattr(o, 'subscription_plan', 'trial')
                if plan == 'monthly':
                    mrr += 49.99
                elif plan == 'yearly':
                    mrr += (499.99 / 12.0)
        
        # Payment requests
        payment_requests = db.query(PaymentRequest).order_by(PaymentRequest.id.desc()).all()
        total_revenue = sum(float(pr.amount or 0) for pr in payment_requests if pr.status == 'approved')
        pending_payments_count = sum(1 for pr in payment_requests if pr.status == 'pending')
        
        # Fetch details for each office
        office_data = []
        for office in offices:
            owner = db.query(AccessProfiles).filter(AccessProfiles.id == office.owner_user_id).first() if office.owner_user_id else None
            user_count = db.query(AccessProfiles).filter(AccessProfiles.office_id == office.id).count()
            case_count = db.query(LawCases).filter(LawCases.office_id == office.id, LawCases.is_deleted == 0).count()
            doc_count = db.query(LawDocuments).filter(LawDocuments.office_id == office.id).count()
            
            # Approximate storage quota usage (estimated average 2MB per document)
            est_storage_mb = doc_count * 2.5
            
            office_data.append({
                "id": office.id,
                "name": office.name,
                "status_key": office.status_key,
                "is_active": office.is_active,
                "created_at": office.created_at,
                "user_count": user_count,
                "case_count": case_count,
                "doc_count": doc_count,
                "storage_mb": round(est_storage_mb, 1),
                "owner_id": owner.id if owner else None,
                "owner_name": owner.name if owner else "غير محدد",
                "owner_email": owner.email if owner else "غير محدد",
                "owner_phone": owner.phone if owner else "غير محدد",
                "subscription_plan": getattr(office, 'subscription_plan', 'trial'),
                "subscription_end": getattr(office, 'subscription_end', None),
                "receipt_status": getattr(office, 'receipt_status', None),
                "receipt_base64": getattr(office, 'receipt_base64', None),
                "disabled_modules": json.loads(getattr(office, 'disabled_modules_json', '[]') or '[]')
            })
            
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
            
        metrics = {
            "total_offices": total_offices,
            "active_offices": active_offices,
            "trial_offices": trial_offices,
            "paid_offices": paid_offices,
            "mrr": round(mrr, 2),
            "arr": round(mrr * 12, 2),
            "total_revenue": round(total_revenue, 2),
            "pending_payments": pending_payments_count,
            "total_users": db.query(AccessProfiles).count(),
            "total_cases": db.query(LawCases).filter(LawCases.is_deleted == 0).count()
        }
            
        return templates.TemplateResponse(request=request, name="superadmin.html", context={
            "user": user,
            "active_page": "superadmin",
            "offices": office_data,
            "payment_requests": pr_data,
            "metrics": metrics
        })
    except Exception as e:
        import traceback
        app_logger.error(f"Superadmin page error: {e}\n{traceback.format_exc()}")
        return HTMLResponse(content="حدث خطأ داخلي", status_code=500)

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
        
        status_text = "تفعيل" if office.is_active == 1 else "إيقاف / تجميد"
        app_logger.info(f"SUPERADMIN | Office {office.id} toggled to {office.is_active} by user {user.id}")
        
        return JSONResponse({"success": True, "message": f"تم {status_text} المكتب بنجاح", "is_active": office.is_active})
    except Exception as e:
        db.rollback()
        app_logger.error(f"Superadmin toggle error: {e}")
        return JSONResponse({"success": False, "error": "حدث خطأ داخلي"}, status_code=500)

@router.post("/api/superadmin/impersonate/{office_id}")
async def impersonate_office(office_id: int, request: Request, db: Session = Depends(get_db), user: AccessProfiles = Depends(get_current_user)):
    """الدخول بالنيابة (Login as Tenant) لتقديم الدعم الفني لمكتب محدد"""
    if not user or not is_superadmin(user):
        return JSONResponse({"success": False, "error": "غير مصرح لك بالقيام بهذا الإجراء"}, status_code=403)
    
    try:
        office = db.query(LawOffices).filter(LawOffices.id == office_id).first()
        if not office:
            return JSONResponse({"success": False, "error": "المكتب غير موجود"}, status_code=404)
        
        # 1. البحث عن صاحب المكتب أو مدير المكتب أو المحامين أولاً (يمنع قطعياً اختيار حسابات الموكلين)
        ADMIN_AND_LAWYER_ROLES = [
            'صاحب المكتب', 'صاحب مكتب', 'مدير المكتب', 'مدير مكتب',
            'مدير', 'مدير النظام', 'محامٍ', 'محامي', 'شريك', 'مستشار',
            'admin', 'owner'
        ]

        target_user = None
        if office.owner_user_id:
            target_user = db.query(AccessProfiles).filter(
                AccessProfiles.id == office.owner_user_id,
                AccessProfiles.office_id == office.id
            ).first()

        # إذا لم يكن هناك مالك محدد أو كان الحساب المعين موكلاً، نبحث عن صاحب المكتب أو المحامي
        if not target_user or target_user.role == 'موكل':
            target_user = db.query(AccessProfiles).filter(
                AccessProfiles.office_id == office.id,
                AccessProfiles.role.in_(ADMIN_AND_LAWYER_ROLES)
            ).order_by(AccessProfiles.is_active.desc(), AccessProfiles.id.asc()).first()

        # إذا لم نجد، نبحث عن أي مستخدم في المكتب ليس موكلاً
        if not target_user:
            target_user = db.query(AccessProfiles).filter(
                AccessProfiles.office_id == office.id,
                AccessProfiles.role != 'موكل'
            ).order_by(AccessProfiles.is_active.desc(), AccessProfiles.id.asc()).first()

        # إذا كان المكتب جديداً أو لا يملك أي حساب محامٍ/إدارة، ننشئ له حساب صاحب مكتب تلقائياً
        if not target_user:
            target_user = AccessProfiles(
                office_id=office.id,
                name=f"صاحب مكتب {office.name}",
                username=f"owner_office_{office.id}",
                role="صاحب المكتب",
                is_active=1,
                can_view_all_cases=1,
                permissions_json="{}"
            )
            db.add(target_user)
            db.commit()
            db.refresh(target_user)

        # تفعيل حساب المستخدم المستهدف وضمان صلاحيات الإدارة الكاملة للدعم الفني
        target_user.is_active = 1
        if target_user.role == 'موكل':
            target_user.role = "صاحب المكتب"
        target_user.can_view_all_cases = 1
        
        # ربط مالك المكتب بالحساب الفعلي
        if not office.owner_user_id or office.owner_user_id != target_user.id:
            office.owner_user_id = target_user.id
            
        db.commit()
            
        # Activate and extend office subscription automatically during support
        office.is_active = 1
        now_utc = datetime.now(timezone.utc)
        office.subscription_end = (now_utc + timedelta(days=365)).strftime("%Y-%m-%d %H:%M:%S")
        if getattr(office, 'subscription_plan', 'trial') == 'trial':
            office.subscription_plan = 'yearly'

        # Preserve current superadmin session token
        existing_admin_token = request.cookies.get("session_token")
            
        # Create a new active session for the target user with impersonation device_id
        token = str(uuid.uuid4())
        expires = datetime.now(timezone.utc) + timedelta(hours=4)  # 4 hours support session
        new_session = AuthSessions(
            session_token=hash_session_token(token),
            user_id=target_user.id,
            device_id=f"impersonated_by_admin_{user.id}",
            is_active=1,
            expires_at=expires.strftime("%Y-%m-%d %H:%M:%S")
        )
        db.add(new_session)
        db.commit()
        
        app_logger.info(f"SUPERADMIN_IMPERSONATE | SuperAdmin {user.id} logged in as User {target_user.id} (Office {office.id})")
        
        response = JSONResponse({
            "success": True, 
            "message": f"تم تجهيز جلسة الدعم الفني للمكتب: {office.name}",
            "redirect_url": "/dashboard"
        })
        is_secure = not (request.url.hostname in ["127.0.0.1", "localhost"])
        
        # Save original superadmin session token so it can be restored on exit
        if existing_admin_token:
            response.set_cookie(
                key="superadmin_session_token",
                value=existing_admin_token,
                httponly=True,
                secure=is_secure,
                samesite="Lax",
                max_age=14400
            )

        response.set_cookie(
            key="is_support_session",
            value="1",
            httponly=False,
            secure=is_secure,
            samesite="Lax",
            max_age=14400
        )
        response.set_cookie(
            key="session_token",
            value=token,
            httponly=True,
            secure=is_secure,
            samesite="Lax",
            max_age=14400
        )
        return response
    except Exception as e:
        db.rollback()
        app_logger.error(f"Superadmin impersonate error: {e}")
        return JSONResponse({"success": False, "error": "حدث خطأ أثناء إنشاء جلسة الدخول"}, status_code=500)

@router.api_route("/api/superadmin/exit-impersonate", methods=["GET", "POST"])
async def exit_impersonate(request: Request, db: Session = Depends(get_db)):
    """إنهاء جلسة الدعم الفني واستعادة جلسة المدير العام (SuperAdmin) فوراً"""
    superadmin_token = request.cookies.get("superadmin_session_token")
    redirect_url = "/superadmin"
    response = RedirectResponse(url=redirect_url, status_code=status.HTTP_303_SEE_OTHER)
    
    is_secure = not (request.url.hostname in ["127.0.0.1", "localhost"])
    
    if superadmin_token:
        token_hash = hash_session_token(superadmin_token)
        now_str = datetime.now(timezone.utc).replace(tzinfo=None).strftime("%Y-%m-%d %H:%M:%S")
        admin_session = db.query(AuthSessions).filter(
            AuthSessions.session_token.in_([superadmin_token, token_hash]),
            AuthSessions.is_active == 1,
            AuthSessions.expires_at > now_str
        ).first()
        
        if admin_session:
            response.set_cookie(
                key="session_token",
                value=superadmin_token,
                httponly=True,
                secure=is_secure,
                samesite="Lax",
                max_age=86400 * 7
            )
        else:
            response = RedirectResponse(url="/login?msg=session_expired", status_code=status.HTTP_303_SEE_OTHER)
            response.delete_cookie("session_token")
    else:
        response = RedirectResponse(url="/login?msg=support_ended", status_code=status.HTTP_303_SEE_OTHER)
        response.delete_cookie("session_token")
        
    response.delete_cookie("superadmin_session_token")
    response.delete_cookie("is_support_session")
    
    app_logger.info("SUPERADMIN_EXIT_IMPERSONATE | Support session ended, returning to superadmin.")
    return response

@router.post("/api/superadmin/update-plan/{office_id}")
async def update_office_plan(office_id: int, request: Request, db: Session = Depends(get_db), user: AccessProfiles = Depends(get_current_user)):
    """ترقية أو تمديد خطة المكتب يدوياً"""
    if not user or not is_superadmin(user):
        return JSONResponse({"success": False, "error": "غير مصرح"}, status_code=403)
        
    try:
        data = await request.json()
        new_plan = data.get("plan") # 'trial', 'monthly', 'yearly', 'enterprise'
        extend_days = int(data.get("days", 30))
        
        office = db.query(LawOffices).filter(LawOffices.id == office_id).first()
        if not office:
            return JSONResponse({"success": False, "error": "المكتب غير موجود"}, status_code=404)
            
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        end_date = now + timedelta(days=extend_days)
        
        office.subscription_plan = new_plan
        office.subscription_end = end_date.strftime("%Y-%m-%d %H:%M:%S")
        office.is_active = 1
        db.commit()
        
        app_logger.info(f"SUPERADMIN | Office {office.id} plan updated to {new_plan} (+{extend_days}d) by user {user.id}")
        return JSONResponse({"success": True, "message": f"تم تحديث باقة المكتب إلى {new_plan} بنجاح حتى {office.subscription_end[:10]}"})
    except Exception as e:
        db.rollback()
        app_logger.error(f"Superadmin plan update error: {e}")
        return JSONResponse({"success": False, "error": "فشل تحديث الخطة"}, status_code=500)

@router.post("/api/superadmin/approve-payment/{payment_id}")
async def approve_payment(payment_id: int, request: Request, db: Session = Depends(get_db), user: AccessProfiles = Depends(get_current_user)):
    if not user or not is_superadmin(user):
        return JSONResponse({"success": False, "error": "غير مصرح لك بالقيام بهذا الإجراء"}, status_code=403)
        
    try:
        data = await request.json()
        if not isinstance(data, dict):
            return JSONResponse({"success": False, "error": "طلب غير صالح"}, status_code=400)
        action = data.get("action") # 'approve' or 'reject'
        notes = str(data.get("notes", ""))[:1000]
        
        payment = db.query(PaymentRequest).filter(PaymentRequest.id == payment_id).first()
        if not payment:
            return JSONResponse({"success": False, "error": "طلب الدفع غير موجود"}, status_code=404)
        if payment.status != "pending":
            return JSONResponse({"success": False, "error": "تمت مراجعة طلب الدفع مسبقاً"}, status_code=409)

        office = db.query(LawOffices).filter(LawOffices.id == payment.office_id).first()
        if not office:
            return JSONResponse({"success": False, "error": "المكتب المرتبط بالطلب غير موجود"}, status_code=404)
        office_owner = db.query(AccessProfiles).filter(AccessProfiles.id == payment.user_id).first()
        
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        
        if action == 'approve':
            if payment.plan not in {"monthly", "yearly"}:
                return JSONResponse({"success": False, "error": "خطة الدفع غير صالحة"}, status_code=400)
            expected_amount = 49.99 if payment.plan == "monthly" else 499.99
            if payment.amount is None or abs(float(payment.amount) - expected_amount) > 0.001:
                return JSONResponse({"success": False, "error": "مبلغ طلب الدفع غير مطابق للخطة"}, status_code=400)
            days = 365 if payment.plan == 'yearly' else 30
            end_date = now + timedelta(days=days)
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
                    asyncio.create_task(send_email_async(office_owner.email, "تم تفعيل اشتراكك - LawSaaS", html_content))
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
                        <p style="background: #f1f5f9; padding: 10px; border-radius: 5px;">{html.escape(notes)}</p>
                        <p>يرجى التأكد من بيانات التحويل والمحاولة مرة أخرى.</p>
                    </div>
                    """
                    asyncio.create_task(send_email_async(office_owner.email, "تنبيه بشأن طلب الدفع - LawSaaS", html_content))
                except Exception:
                    pass
                    
            db.commit()
            return JSONResponse({"success": True, "message": "تم رفض السند"})
            
        return JSONResponse({"success": False, "error": "إجراء غير صالح"}, status_code=400)
    except Exception as e:
        db.rollback()
        app_logger.error(f"Superadmin payment approval error: {e}")
        return JSONResponse({"success": False, "error": "حدث خطأ داخلي"}, status_code=500)

@router.post("/api/superadmin/update-modules/{office_id}")
async def update_office_modules(office_id: int, request: Request, db: Session = Depends(get_db), user: AccessProfiles = Depends(get_current_user)):
    """تحديث الواجهات والموديولات المتاحة لمكتب محدد (Feature Flagging)"""
    if not user or not is_superadmin(user):
        return JSONResponse({"success": False, "error": "غير مصرح"}, status_code=403)
        
    try:
        data = await request.json()
        disabled_modules = data.get("disabled_modules", [])
        if not isinstance(disabled_modules, list):
            return JSONResponse({"success": False, "error": "بيانات غير صالحة"}, status_code=400)
            
        office = db.query(LawOffices).filter(LawOffices.id == office_id).first()
        if not office:
            return JSONResponse({"success": False, "error": "المكتب غير موجود"}, status_code=404)
            
        office.disabled_modules_json = json.dumps(disabled_modules)
        db.commit()
        
        app_logger.info(f"SUPERADMIN_MODULES | Office {office.id} disabled modules updated to: {disabled_modules} by user {user.id}")
        return JSONResponse({
            "success": True, 
            "message": f"تم حفظ إعدادات الواجهات لمكتب {office.name} بنجاح",
            "disabled_modules": disabled_modules
        })
    except Exception as e:
        db.rollback()
        app_logger.error(f"Superadmin modules update error: {e}")
        return JSONResponse({"success": False, "error": "فشل حفظ إعدادات الواجهات"}, status_code=500)
