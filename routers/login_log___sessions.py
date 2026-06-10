from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from sqlalchemy.orm import Session
from datetime import datetime
import traceback

from database.database import get_db
from database.models import AccessProfiles, AuthSessions
from dependencies import get_current_user, templates

router = APIRouter()


@router.get("/login_log", response_class=HTMLResponse)
async def login_log_page(request: Request, db: Session = Depends(get_db), user: AccessProfiles = Depends(get_current_user)):
    if not user: return RedirectResponse(url="/", status_code=303)
    try:
        from datetime import datetime
        office_id = user.office_id or 1
        # Fetch sessions for all users in the office
        users = db.query(AccessProfiles).filter(AccessProfiles.office_id == office_id).all()
        user_dict = {u.id: u for u in users}
        user_ids = list(user_dict.keys())
        sessions = db.query(AuthSessions).filter(AuthSessions.user_id.in_(user_ids)).order_by(AuthSessions.created_at.desc()).all()
        
        sessions_data = []
        stats = {"total": len(sessions), "active": 0, "today": 0, "expired": 0}
        today_str = datetime.now().strftime("%Y-%m-%d")
        
        for s in sessions:
            u = user_dict.get(s.user_id)
            if s.is_active: stats["active"] += 1
            else: stats["expired"] += 1
            if s.created_at and s.created_at.startswith(today_str): stats["today"] += 1
            
            sessions_data.append({
                "id": s.id, "user_name": u.name if u else "مجهول",
                "user_email": u.email if u else "", "user_role": u.role if u else "",
                "created_at": s.created_at, "expires_at": s.expires_at,
                "device_id": s.device_id, "is_active": s.is_active
            })
            
        return templates.TemplateResponse(request=request, name="login_log.html", context={
            "user": user, "active_page": "login_log", "sessions": sessions_data,
            "stats": stats, "now": datetime.now().strftime("%Y-%m-%d %H:%M")
        })
    except Exception:
        import traceback
        return HTMLResponse(content=f"<pre dir='ltr'>{traceback.format_exc()}</pre>", status_code=500)

@router.post("/api/sessions/revoke/{session_id}")
async def session_revoke(session_id: int, db: Session = Depends(get_db), user: AccessProfiles = Depends(get_current_user)):
    from fastapi.responses import JSONResponse
    if not user: return JSONResponse({"ok": False, "message": "غير مصرح"}, status_code=401)
    s = db.query(AuthSessions).filter(AuthSessions.id == session_id).first()
    if not s: return JSONResponse({"ok": False, "message": "الجلسة غير موجودة"})
    
    # 🔴 IDOR protection: Verify the target user belongs to the same office
    target_user = db.query(AccessProfiles).filter(AccessProfiles.id == s.user_id).first()
    if not target_user or target_user.office_id != user.office_id:
        return JSONResponse({"ok": False, "message": "غير مصرح لك بإنهاء هذه الجلسة"}, status_code=403)
        
    # 🔴 Privilege restriction: Non-admins can only revoke their own sessions
    _ADMIN_ROLES = {'مدير', 'مدير المكتب', 'صاحب المكتب', 'مدير النظام'}
    if user.role not in _ADMIN_ROLES and user.id != target_user.id:
        return JSONResponse({"ok": False, "message": "غير مصرح لك بإنهاء جلسات الآخرين"}, status_code=403)
        
    s.is_active = 0
    db.commit()
    return JSONResponse({"ok": True, "message": "تم إنهاء الجلسة"})

@router.post("/api/sessions/revoke-all")
async def session_revoke_all(request: Request, db: Session = Depends(get_db), user: AccessProfiles = Depends(get_current_user)):
    from fastapi.responses import JSONResponse
    if not user: return JSONResponse({"ok": False, "message": "غير مصرح"}, status_code=401)
    token = request.cookies.get("session_token")
    office_id = user.office_id or 1
    users = db.query(AccessProfiles.id).filter(AccessProfiles.office_id == office_id).all()
    user_ids = [u[0] for u in users]
    
    # Revoke all active sessions except the current one
    sessions = db.query(AuthSessions).filter(
        AuthSessions.user_id.in_(user_ids), 
        AuthSessions.is_active == 1,
        AuthSessions.session_token != token
    ).all()
    
    count = 0
    for s in sessions:
        s.is_active = 0
        count += 1
    db.commit()
    return JSONResponse({"ok": True, "message": f"تم إنهاء {count} جلسة نشطة"})

