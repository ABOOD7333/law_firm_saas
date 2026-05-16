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
        if user.id == 1 or user.username == 'ABOOD':
            return user
            
        if user.office_id:
            office = db.query(LawOffices).filter(LawOffices.id == user.office_id).first()
            if office and office.is_active == 0:
                return None
                
        # ── حماية أمنية وتوزيع الصلاحيات (RBAC) ──
        path = request.url.path
        
        from fastapi.exceptions import HTTPException
        from fastapi import status
        
        # 1. الموكل (Client)
        if user.role == 'موكل':
            allowed = ['/', '/dashboard', '/logout']
            if not any(path == p for p in allowed) and not path.startswith('/static'):
                raise HTTPException(status_code=status.HTTP_303_SEE_OTHER, headers={"Location": "/dashboard"})
                
        # 2. المحاسب (Accountant)
        elif user.role == 'محاسب':
            allowed_prefixes = ('/', '/dashboard', '/finance', '/expenses', '/timesheet', '/reports', '/clients', '/logout', '/static', '/api/finance', '/api/expenses', '/api/timesheets')
            if not path.startswith(allowed_prefixes):
                raise HTTPException(status_code=status.HTTP_303_SEE_OTHER, headers={"Location": "/dashboard"})

        # 3. السكرتير والمحامي (Secretary & Lawyer)
        elif user.role in ['سكرتير', 'محامي', 'محامٍ']:
            forbidden_prefixes = ('/team', '/settings', '/finance', '/expenses', '/login_log', '/activity', '/api/team', '/api/settings', '/api/finance', '/api/expenses')
            if path.startswith(forbidden_prefixes):
                raise HTTPException(status_code=status.HTTP_303_SEE_OTHER, headers={"Location": "/dashboard"})
                
    return user
