from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from sqlalchemy.orm import Session
import json
import traceback

from database.database import get_db
from database.models import AccessProfiles, LawOffices, LawCases
from dependencies import get_current_user, templates
from core.logger import app_logger
from core.audit import write_audit

_ADMIN_ROLES = {'مدير', 'مدير المكتب', 'صاحب المكتب'}

router = APIRouter()


@router.get("/team", response_class=HTMLResponse)
async def team_page(request: Request, db: Session = Depends(get_db), user: AccessProfiles = Depends(get_current_user)):
    if not user: return RedirectResponse(url="/", status_code=303)
    try:
        import json
        office_id = user.office_id or 1
        office = db.query(LawOffices).filter(LawOffices.id == office_id).first()
        owner = None
        if office and office.owner_user_id:
            owner = db.query(AccessProfiles).filter(AccessProfiles.id == office.owner_user_id).first()
        members = db.query(AccessProfiles).filter(AccessProfiles.office_id == office_id).all()
        cases = db.query(LawCases).filter(LawCases.office_id == office_id, LawCases.is_deleted == 0).all()
        members_json = json.dumps([{
            "id": m.id, "name": m.name, "username": m.username or "",
            "phone": m.phone or "", "email": m.email or "",
            "birth_date": m.birth_date or "", "role": m.role or "محامٍ",
            "job_title": m.job_title or "", "is_active": m.is_active,
            "can_view_all_cases": m.can_view_all_cases,
            "last_login_at": m.last_login_at or "",
            "specializations": "", "permissions": []
        } for m in members], ensure_ascii=False)
        return templates.TemplateResponse(request=request, name="team.html", context={
            "user": user, "active_page": "team", "office": office, "owner": owner,
            "members": members, "cases": cases, "members_json": members_json,
        })
    except Exception:
        import traceback
        return HTMLResponse(content=f"<pre dir='ltr'>{traceback.format_exc()}</pre>", status_code=500)


@router.post("/api/team/save")
async def team_save(request: Request, db: Session = Depends(get_db), user: AccessProfiles = Depends(get_current_user)):
    from fastapi.responses import JSONResponse
    if not user: return JSONResponse({"ok": False, "message": "غير مصرح"}, status_code=401)
    if user.role not in _ADMIN_ROLES:
        app_logger.warning(f"SECURITY | team_save blocked | actor={user.id}")
        return JSONResponse({"ok": False, "message": "ليس لديك صلاحية لإضافة أو تعديل الأعضاء"}, status_code=403)
    try:
        import hashlib, json as _json
        data = await request.json()
        office_id = user.office_id or 1
        name     = (data.get("name") or "").strip()
        username = (data.get("username") or "").strip()
        phone    = (data.get("phone") or "").strip()
        email    = (data.get("email") or "").strip()
        birth_date = data.get("birth_date") or None
        pin      = (data.get("access_pin") or "").strip()
        role     = data.get("role") or "محامٍ"
        job_title = data.get("job_title") or ""
        is_active = int(data.get("is_active", 1))
        can_view  = int(data.get("can_view_all_cases", 0))
        record_id = data.get("id")

        if not all([name, username, phone, email]):
            return JSONResponse({"ok": False, "message": "يرجى تعبئة جميع الحقول الإلزامية"})

        # Check duplicate username
        dup = db.query(AccessProfiles).filter(
            AccessProfiles.username == username,
            AccessProfiles.id != (int(record_id) if record_id else -1)
        ).first()
        if dup:
            return JSONResponse({"ok": False, "message": f"اسم الدخول '{username}' مستخدم مسبقاً"})

        if record_id:
            m = db.query(AccessProfiles).filter(AccessProfiles.id == int(record_id), AccessProfiles.office_id == office_id).first()
            if not m: return JSONResponse({"ok": False, "message": "المستخدم غير موجود أو غير مصرح"})
            m.name = name; m.username = username; m.phone = phone; m.email = email
            m.birth_date = birth_date; m.role = role; m.job_title = job_title
            m.is_active = is_active; m.can_view_all_cases = can_view
            if pin and len(pin) >= 6:
                import os as _os, base64 as _b64
                _salt = _os.urandom(16)
                _raw  = hashlib.pbkdf2_hmac('sha256', pin.encode(), _salt, 260000)
                m.access_pin_hash = f"pbkdf2:sha256:260000${_b64.b64encode(_salt).decode().rstrip('=')}${_b64.b64encode(_raw).decode().rstrip('=')}"
            db.commit()
            return JSONResponse({"ok": True, "message": "تم تحديث بيانات العضو بنجاح"})
        else:
            if not pin or len(pin) < 6:
                return JSONResponse({"ok": False, "message": "رمز الدخول مطلوب (6 أحرف على الأقل) للحساب الجديد"})
            import os as _os, base64 as _b64
            _salt    = _os.urandom(16)
            _raw     = hashlib.pbkdf2_hmac('sha256', pin.encode(), _salt, 260000)
            pin_hash = f"pbkdf2:sha256:260000${_b64.b64encode(_salt).decode().rstrip('=')}${_b64.b64encode(_raw).decode().rstrip('=')}"
            new_m = AccessProfiles(
                name=name, username=username, phone=phone, email=email,
                birth_date=birth_date, role=role, job_title=job_title,
                is_active=is_active, can_view_all_cases=can_view,
                office_id=office_id, email_verified=1, reset_verified=0,
                state="verified", access_pin_hash=pin_hash,
                protection_type="ربط الجهاز الحالي", preferred_theme="light",
                failed_attempts=0,
            )
            db.add(new_m); db.commit()
            return JSONResponse({"ok": True, "message": f"تم إنشاء العضو بنجاح. رمز الدخول: {pin}"})
    except Exception as e:
        db.rollback()
        return JSONResponse({"ok": False, "message": str(e)})


@router.post("/api/team/toggle/{member_id}")
async def team_toggle(member_id: int, db: Session = Depends(get_db), user: AccessProfiles = Depends(get_current_user)):
    if not user: return JSONResponse({"ok": False, "message": "غير مصرح"}, status_code=401)
    if user.role not in _ADMIN_ROLES:
        app_logger.warning(f"SECURITY | team_toggle blocked | actor={user.id} target={member_id}")
        return JSONResponse({"ok": False, "message": "ليس لديك صلاحية"}, status_code=403)
    office_id = user.office_id or 1
    m = db.query(AccessProfiles).filter(
        AccessProfiles.id == member_id,
        AccessProfiles.office_id == office_id
    ).first()
    if not m: return JSONResponse({"ok": False, "message": "المستخدم غير موجود"})
    if m.id == user.id: return JSONResponse({"ok": False, "message": "لا يمكن إيقاف حسابك الحالي"})
    m.is_active = 0 if m.is_active else 1
    write_audit(db, table_name="access_profiles", action_name="toggle_user",
                actor_user_id=user.id, actor_name=user.name, office_id=office_id,
                entity_id=m.id, details=f"is_active={m.is_active}")
    db.commit()
    status = "تفعيل" if m.is_active else "إيقاف"
    app_logger.info(f"team_toggle | actor={user.id} | target={m.id} | is_active={m.is_active}")
    return JSONResponse({"ok": True, "message": f"تم {status} العضو {m.name} بنجاح"})


@router.delete("/api/team/delete/{member_id}")
async def team_delete(member_id: int, db: Session = Depends(get_db), user: AccessProfiles = Depends(get_current_user)):
    if not user: return JSONResponse({"ok": False, "message": "غير مصرح"}, status_code=401)
    if user.role not in _ADMIN_ROLES:
        app_logger.warning(f"SECURITY | team_delete blocked | actor={user.id} target={member_id}")
        return JSONResponse({"ok": False, "message": "ليس لديك صلاحية"}, status_code=403)
    office_id = user.office_id or 1
    m = db.query(AccessProfiles).filter(
        AccessProfiles.id == member_id,
        AccessProfiles.office_id == office_id
    ).first()
    if not m: return JSONResponse({"ok": False, "message": "المستخدم غير موجود"})
    if m.id == user.id: return JSONResponse({"ok": False, "message": "لا يمكن حذف حسابك الحالي"})
    office = db.query(LawOffices).filter(LawOffices.id == office_id).first()
    if office and office.owner_user_id == member_id:
        return JSONResponse({"ok": False, "message": "لا يمكن حذف صاحب المكتب"})
    write_audit(db, table_name="access_profiles", action_name="delete_user",
                actor_user_id=user.id, actor_name=user.name, office_id=office_id,
                entity_id=m.id, details=f"حذف المستخدم: {m.name}")
    db.delete(m)
    db.commit()
    app_logger.info(f"team_delete | actor={user.id} | deleted={member_id} | office={office_id}")
    return JSONResponse({"ok": True, "message": f"تم حذف العضو {m.name} بنجاح"})


