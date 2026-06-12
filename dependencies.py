"""
Shared dependencies module - imported by routers to avoid circular imports.
This module provides get_current_user and templates without importing from main.
"""
from fastapi import Request, Depends
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from database.database import get_db
from database.models import AccessProfiles, AuthSessions, LawOffices

templates = Jinja2Templates(directory="templates")


def get_current_user(request: Request, db: Session = Depends(get_db)):
    token = request.cookies.get("session_token")
    if not token:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
            
    if not token:
        return None

    from datetime import datetime, timezone
    
    now_str = datetime.now(timezone.utc).replace(tzinfo=None).strftime("%Y-%m-%d %H:%M:%S")
    
    session_record = db.query(AuthSessions).filter(
        AuthSessions.session_token == token,
        AuthSessions.is_active == 1,
        AuthSessions.expires_at > now_str
    ).first()

    if not session_record:
        return None

    user = db.query(AccessProfiles).filter(
        AccessProfiles.id == session_record.user_id
    ).first()
    
    if user:
        if user.is_active == 0:
            return None
            
        # Superadmins bypass office blocks
        if getattr(user, 'is_superadmin', 0) == 1:
            return user
            
        if user.office_id:
            office = db.query(LawOffices).filter(LawOffices.id == user.office_id).first()
            if office and office.is_active == 0:
                return None
            if office:
                user.subscription_plan = getattr(office, 'subscription_plan', 'trial')
                sub_end_str = getattr(office, 'subscription_end', None)
                user.subscription_expired = False
                user.trial_days_left = 0
                if sub_end_str and user.subscription_plan != 'lifetime':
                    try:
                        sub_end = datetime.strptime(sub_end_str, "%Y-%m-%d %H:%M:%S")
                        now_dt = datetime.strptime(now_str, "%Y-%m-%d %H:%M:%S")
                        diff = (sub_end - now_dt).days
                        if diff < 0:
                            user.subscription_expired = True
                        elif user.subscription_plan == 'trial':
                            user.trial_days_left = diff
                    except:
                        pass
                
        # ── حماية أمنية وتوزيع الصلاحيات (RBAC) ──
        path = request.url.path
        
        from fastapi.exceptions import HTTPException
        from fastapi import status

        # Subscription Lock Check
        is_api = path.startswith('/api/')
        allowed_sub_paths = ['/subscription', '/logout', '/api/subscription/checkout']
        if getattr(user, 'subscription_expired', False) and not any(path == p for p in allowed_sub_paths) and not path.startswith('/static'):
            if is_api:
                raise HTTPException(status_code=403, detail="Subscription Expired")
            else:
                raise HTTPException(status_code=status.HTTP_303_SEE_OTHER, headers={"Location": "/subscription"})
        
        # 1. الموكل (Client)
        if user.role == 'موكل':
            allowed = ['/', '/dashboard', '/logout']
            if not any(path == p for p in allowed) and not path.startswith('/static') and not path.startswith('/api/ai'):
                if path.startswith('/api/'):
                    raise HTTPException(status_code=403, detail="غير مصرح للموكلين بالوصول")
                raise HTTPException(status_code=status.HTTP_303_SEE_OTHER, headers={"Location": "/dashboard"})
                
        # 2. المحاسب (Accountant)
        elif user.role == 'محاسب':
            allowed_prefixes = ('/', '/dashboard', '/finance', '/expenses', '/timesheet', '/reports', '/clients', '/logout', '/static', '/api/finance', '/api/expenses', '/api/timesheets', '/api/ai')
            if not path.startswith(allowed_prefixes):
                if path.startswith('/api/'):
                    raise HTTPException(status_code=403, detail="غير مصرح للمحاسبين بالوصول")
                raise HTTPException(status_code=status.HTTP_303_SEE_OTHER, headers={"Location": "/dashboard"})
 
        # 3. السكرتير والمحامي (Secretary & Lawyer)
        elif user.role in ['سكرتير', 'محامي', 'محامٍ']:
            forbidden_prefixes = ('/team', '/settings', '/finance', '/expenses', '/login_log', '/activity', '/api/team', '/api/settings', '/api/finance', '/api/expenses', '/advanced_operations', '/reports', '/api/advanced')
            if path.startswith(forbidden_prefixes) and not path.startswith('/api/ai'):
                if path.startswith('/api/'):
                    raise HTTPException(status_code=403, detail="غير مصرح لك بالقيام بهذا الإجراء")
                raise HTTPException(status_code=status.HTTP_303_SEE_OTHER, headers={"Location": "/dashboard"})
                
    return user
