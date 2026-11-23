from fastapi import APIRouter, Request, Depends, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timezone, timedelta
import json
import html
import uuid

from database.database import get_db
from database.models import AccessProfiles, LawOffices, PaymentRequest, LawCases, LawDocuments, AuthSessions, AppSettings
from dependencies import get_current_user, templates
from core.security import hash_session_token
from core.logger import app_logger
from core.subscription_tiers import (
    TIERS,
    get_tier,
    get_disabled_modules_for_tier,
    get_exchange_rates,
    set_exchange_rates,
    calculate_price_in_currency,
    DEFAULT_EXCHANGE_RATES
)

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
        trial_offices = sum(1 for o in offices if getattr(o, 'subscription_plan', 'solo') == 'trial')
        
        # Count tiers
        solo_count = sum(1 for o in offices if getattr(o, 'subscription_plan', 'solo') == 'solo')
        pro_count = sum(1 for o in offices if getattr(o, 'subscription_plan', '') in ['pro', 'monthly', 'yearly'])
        enterprise_count = sum(1 for o in offices if getattr(o, 'subscription_plan', '') == 'enterprise')
        lifetime_count = sum(1 for o in offices if getattr(o, 'subscription_plan', '') == 'lifetime')
        
        # Calculate Estimated MRR ($19.99 solo, $49.99 pro, $100.00 enterprise + $19 extra seats)
        mrr = 0.0
        for o in offices:
            if o.is_active == 1:
                plan = getattr(o, 'subscription_plan', 'solo')
                if plan == 'solo':
                    mrr += 19.99
                elif plan in ['pro', 'monthly']:
                    mrr += 49.99
                elif plan == 'yearly':
                    mrr += (480.0 / 12.0)
                elif plan == 'enterprise':
                    mrr += 100.00
                if getattr(o, 'extra_seats', 0) and getattr(o, 'extra_seats', 0) >= 1:
                    mrr += 19.00
        
        # Payment requests
        payment_requests = db.query(PaymentRequest).order_by(PaymentRequest.id.desc()).all()
        total_revenue = sum(float(pr.amount or 0) for pr in payment_requests if pr.status == 'approved')
        pending_payments_count = sum(1 for pr in payment_requests if pr.status == 'pending')
        
        # Get live exchange rates from AppSettings
        rates = get_exchange_rates(db)
        
        # Fetch details for each office
        office_data = []
        for office in offices:
            owner = db.query(AccessProfiles).filter(AccessProfiles.id == office.owner_user_id).first() if office.owner_user_id else None
            user_count = db.query(AccessProfiles).filter(AccessProfiles.office_id == office.id).count()
            case_count = db.query(LawCases).filter(LawCases.office_id == office.id, LawCases.is_deleted == 0).count()
            doc_count = db.query(LawDocuments).filter(LawDocuments.office_id == office.id).count()
            
            # Approximate storage quota usage (estimated average 2.5MB per document)
            est_storage_mb = doc_count * 2.5
            current_plan = getattr(office, 'subscription_plan', 'solo')
            tier_info = get_tier(current_plan)
            
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
                "subscription_plan": current_plan,
                "tier_name_ar": tier_info.get("name_ar", current_plan),
                "tier_color": tier_info.get("color", "#64748b"),
                "tier_badge": tier_info.get("badge", ""),
                "subscription_end": getattr(office, 'subscription_end', None),
                "receipt_status": getattr(office, 'receipt_status', None),
                "receipt_base64": getattr(office, 'receipt_base64', None),
                "disabled_modules": json.loads(getattr(office, 'disabled_modules_json', '[]') or '[]')
            })
            
        pr_data = []
        for pr in payment_requests:
            pr_office = db.query(LawOffices).filter(LawOffices.id == pr.office_id).first()
            pr_owner = db.query(AccessProfiles).filter(AccessProfiles.id == pr.user_id).first() if pr.user_id else None
            
            # Plan display
            plan_str = pr.plan or "solo"
            tier_pr = get_tier(plan_str)
            
            pr_data.append({
                "id": pr.id,
                "office_id": pr.office_id,
                "office_name": pr_office.name if pr_office else "مكتب محذوف",
                "owner_email": pr_owner.email if pr_owner else "غير معروف",
                "plan": pr.plan,
                "plan_ar": tier_pr.get("name_ar", pr.plan),
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
            "solo_offices": solo_count,
            "pro_offices": pro_count,
            "enterprise_offices": enterprise_count,
            "lifetime_offices": lifetime_count,
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
            "metrics": metrics,
            "exchange_rates": rates,
            "tiers": TIERS,
            "haseb_pos": {
                "code": "2709660",
                "merchant": "LawSaaS",
                "currency": "USD"
            }
        })
    except Exception as e:
        import traceback
        app_logger.error(f"Superadmin page error: {e}\n{traceback.format_exc()}")
        return HTMLResponse(content="حدث خطأ داخلي", status_code=500)

@router.post("/api/superadmin/exchange-rates")
async def save_exchange_rates(request: Request, db: Session = Depends(get_db), user: AccessProfiles = Depends(get_current_user)):
    """حفظ أسعار الصرف اليومية (دولار / يمني / سعودي) في إعدادات المنصة"""
    if not user or not is_superadmin(user):
        return JSONResponse({"success": False, "error": "غير مصرح لك"}, status_code=403)
    try:
        data = await request.json()
        saved_rates = set_exchange_rates(db, data)
        app_logger.info(f"SUPERADMIN_RATES | Exchange rates updated to {saved_rates} by user {user.id}")
        return JSONResponse({
            "success": True,
            "message": "تم تحديث وحفظ أسعار الصرف بنجاح وتطبيقها في كامل المنصة",
            "rates": saved_rates
        })
    except Exception as e:
        db.rollback()
        app_logger.error(f"Superadmin rates save error: {e}")
        return JSONResponse({"success": False, "error": "فشل حفظ أسعار الصرف"}, status_code=500)

@router.post("/api/superadmin/office/{office_id}/set-tier")
async def set_office_tier(office_id: int, request: Request, db: Session = Depends(get_db), user: AccessProfiles = Depends(get_current_user)):
    """تعديل أو ترقية باقة مكتب بضغطة زر واحدة (Solo / Pro / Enterprise / Lifetime)"""
    if not user or not is_superadmin(user):
        return JSONResponse({"success": False, "error": "غير مصرح لك"}, status_code=403)
    try:
        data = await request.json()
        tier_id = str(data.get("tier", "solo")).lower().strip()
        if tier_id not in TIERS:
            return JSONResponse({"success": False, "error": f"الباقة '{tier_id}' غير معرفة"}, status_code=400)
            
        office = db.query(LawOffices).filter(LawOffices.id == office_id).first()
        if not office:
            return JSONResponse({"success": False, "error": "المكتب غير موجود"}, status_code=404)
            
        months = int(data.get("months", 12))
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        
        office.subscription_plan = tier_id
        office.disabled_modules_json = json.dumps(get_disabled_modules_for_tier(tier_id))
        office.is_active = 1
        
        if tier_id == "lifetime":
            office.subscription_end = (now + timedelta(days=3650)).strftime("%Y-%m-%d %H:%M:%S")
        elif tier_id == "trial":
            office.subscription_end = (now + timedelta(days=14)).strftime("%Y-%m-%d %H:%M:%S")
        else:
            office.subscription_end = (now + timedelta(days=months * 30)).strftime("%Y-%m-%d %H:%M:%S")
            
        db.commit()
        tier_info = get_tier(tier_id)
        app_logger.info(f"SUPERADMIN_TIER | Office {office.id} tier set to {tier_id} (+{months}m) by user {user.id}")
        return JSONResponse({
            "success": True,
            "message": f"تم تفعيل باقة '{tier_info['name_ar']}' لمكتب {office.name} بنجاح حتى {office.subscription_end[:10]}",
            "tier": tier_id,
            "tier_name": tier_info['name_ar'],
            "subscription_end": office.subscription_end[:10]
        })
    except Exception as e:
        db.rollback()
        app_logger.error(f"Superadmin tier assignment error: {e}")
        return JSONResponse({"success": False, "error": "فشل تعديل باقة المكتب"}, status_code=500)

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
            
        # Find office owner
        target_user = None
        if office.owner_user_id:
            target_user = db.query(AccessProfiles).filter(AccessProfiles.id == office.owner_user_id).first()
        if not target_user:
            target_user = db.query(AccessProfiles).filter(AccessProfiles.office_id == office.id).first()
            
        if not target_user:
            return JSONResponse({"success": False, "error": "لا يوجد مستخدم مسجل في هذا المكتب لتسجيل الدخول به"}, status_code=404)
            
        # Generate impersonation session
        token = str(uuid.uuid4())
        hashed = hash_session_token(token)
        expires = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=4)
        
        existing_admin_token = request.cookies.get("session_token")
        
        new_session = AuthSessions(
            session_token=hashed,
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
        is_secure = (request.url.scheme == "https") or (request.headers.get("x-forwarded-proto") == "https")
        
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
    
    is_secure = (request.url.scheme == "https") or (request.headers.get("x-forwarded-proto") == "https")
    
    if superadmin_token:
        token_hash = hash_session_token(superadmin_token)
        now_str = datetime.now(timezone.utc).replace(tzinfo=None).strftime("%Y-%m-%d %H:%M:%S")
        admin_session = db.query(AuthSessions).filter(
            AuthSessions.session_token.in_([superadmin_token, token_hash]),
            AuthSessions.expires_at > now_str
        ).first()
        
        if admin_session:
            response.set_cookie(
                key="session_token",
                value=superadmin_token,
                httponly=True,
                secure=is_secure,
                samesite="Lax",
                max_age=86400
            )
            
    response.delete_cookie("superadmin_session_token")
    response.delete_cookie("is_support_session")
    return response

@router.post("/api/superadmin/fix-subscriptions")
async def fix_subscriptions(request: Request, db: Session = Depends(get_db), user: AccessProfiles = Depends(get_current_user)):
    """تهيئة باقات المكاتب القديمة (باستثناء مكتب المدير العام)"""
    if not user or not is_superadmin(user):
        return JSONResponse({"success": False, "error": "غير مصرح"}, status_code=403)
        
    try:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        trial_end = (now + timedelta(days=14)).strftime("%Y-%m-%d %H:%M:%S")
        
        offices = db.query(LawOffices).all()
        updated_count = 0
        for off in offices:
            if off.id == user.office_id:
                # مكتب المدير العام يمنح ترخيص شامل دائم
                off.subscription_plan = 'lifetime'
                off.subscription_end = (now + timedelta(days=3650)).strftime("%Y-%m-%d %H:%M:%S")
                off.disabled_modules_json = '[]'
                off.is_active = 1
                continue
                
            if not off.subscription_plan or off.subscription_plan in ['trial', 'monthly', 'yearly']:
                if not off.subscription_plan:
                    off.subscription_plan = 'trial'
                    off.subscription_end = trial_end
                    off.disabled_modules_json = json.dumps(get_disabled_modules_for_tier('trial'))
                updated_count += 1
                
        db.commit()
        return JSONResponse({"success": True, "message": f"تم فحص وضبط باقات {updated_count} مكتب بنجاح وتأمين مكتبك الرئيسي"})
    except Exception as e:
        db.rollback()
        app_logger.error(f"Superadmin fix subscriptions error: {e}")
        return JSONResponse({"success": False, "error": "فشل تعديل البيانات"}, status_code=500)

@router.post("/api/superadmin/approve-payment/{payment_id}")
async def approve_payment(payment_id: int, request: Request, db: Session = Depends(get_db), user: AccessProfiles = Depends(get_current_user)):
    """اعتماد أو رفض طلب سداد حاسب بنك الكريمي"""
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
            plan_clean = (payment.plan or "pro").lower().strip()
            
            if "extra_seat" in plan_clean or "seat" in plan_clean:
                # تفعيل مقعد مستخدم إضافي واحد للمكتب
                office.extra_seats = 1
                payment.status = 'approved'
                payment.reviewed_at = now.strftime("%Y-%m-%d %H:%M:%S")
                payment.reviewed_by = user.id
                db.commit()

                if office_owner and office_owner.email:
                    try:
                        from email_service import send_email_async
                        import asyncio
                        html_content = f"""
                        <div dir="rtl" style="font-family: Arial, sans-serif;">
                            <h2 style="color: #10b981;">✅ تم تفعيل المقعد الإضافي بنجاح في LawSaaS</h2>
                            <p>عزيزنا المشترك، تم تأكيد عملية الدفع وتفعيل <strong>المقعد الإضافي (+1 مستخدم)</strong> لمكتبكم: <strong>{office.name}</strong>.</p>
                            <p>يمكنكم الآن التوجه إلى إدارة الفريق وإضافة العضو الجديد فوراً.</p>
                        </div>
                        """
                        asyncio.create_task(send_email_async(office_owner.email, "تم تفعيل المقعد الإضافي - LawSaaS", html_content))
                    except Exception:
                        pass
                return JSONResponse({"success": True, "message": "تم تفعيل المقعد الإضافي بنجاح"})

            # Map plan to tier
            tier_key = "pro"
            if "solo" in plan_clean:
                tier_key = "solo"
            elif "enterprise" in plan_clean:
                tier_key = "enterprise"
            elif "pro" in plan_clean or "month" in plan_clean or "year" in plan_clean:
                tier_key = "pro"
            else:
                tier_key = plan_clean if plan_clean in TIERS else "pro"
                
            is_yearly = "year" in plan_clean or (payment.amount and float(payment.amount) >= 150)
            days = 365 if is_yearly else 30
            end_date = now + timedelta(days=days)
            
            office.subscription_plan = tier_key
            office.subscription_end = end_date.strftime("%Y-%m-%d %H:%M:%S")
            office.disabled_modules_json = json.dumps(get_disabled_modules_for_tier(tier_key))
            office.is_active = 1
                
            payment.status = 'approved'
            payment.reviewed_at = now.strftime("%Y-%m-%d %H:%M:%S")
            payment.reviewed_by = user.id
            
            # Send Email
            if office_owner and office_owner.email:
                try:
                    from email_service import send_email_async
                    import asyncio
                    tier_info = get_tier(tier_key)
                    html_content = f"""
                    <div dir="rtl" style="font-family: Arial, sans-serif;">
                        <h2 style="color: #10b981;">✅ تم تفعيل اشتراكك بنجاح في LawSaaS</h2>
                        <p>عزيزنا المشترك، تم تأكيد عملية الدفع عبر حاسب بنك الكريمي وتفعيل باقتك: <strong>{tier_info['name_ar']}</strong>.</p>
                        <p>تاريخ انتهاء الاشتراك: <strong>{office.subscription_end[:10]}</strong></p>
                        <p>شكراً لثقتكم بنا.</p>
                    </div>
                    """
                    asyncio.create_task(send_email_async(office_owner.email, "تم تفعيل اشتراكك - LawSaaS", html_content))
                except Exception:
                    pass
                    
            db.commit()
            return JSONResponse({"success": True, "message": "تم اعتماد السند وتفعيل الباقة بنجاح"})
            
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
                    <div dir="rtl" style="font-family: Arial, sans-serif;">
                        <h2 style="color: #ef4444;">❌ إشعار بخصوص طلب الدفع في LawSaaS</h2>
                        <p>مرحباً، لم يتم قبول إيصال السداد للأسباب التالية:</p>
                        <p style="background: #f1f5f9; padding: 12px; border-radius: 6px; border-right: 4px solid #ef4444;">{html.escape(notes)}</p>
                        <p>يرجى مراجعة المبلغ أو رقم العملية في تطبيق الكريمي والمحاولة مجدداً.</p>
                    </div>
                    """
                    asyncio.create_task(send_email_async(office_owner.email, "تنبيه بشأن طلب الدفع - LawSaaS", html_content))
                except Exception:
                    pass
                    
            db.commit()
            return JSONResponse({"success": True, "message": "تم رفض السند وتسجيل السبب"})
            
        return JSONResponse({"success": False, "error": "إجراء غير صالح"}, status_code=400)
    except Exception as e:
        db.rollback()
        app_logger.error(f"Superadmin payment approval error: {e}")
        return JSONResponse({"success": False, "error": "حدث خطأ داخلي"}, status_code=500)
