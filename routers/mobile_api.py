import uuid
import hashlib
from datetime import datetime, timedelta, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel

from database.database import get_db
from database.models import AccessProfiles, AuthSessions, LawCases, LawDocuments, LawOffices
from dependencies import get_current_user

router = APIRouter(prefix="/api/mobile", tags=["Mobile API"])

# Store temporary mobile 2FA sessions in RAM (valid for 5 minutes)
_mobile_temp_2fa_sessions = {}

class LoginRequest(BaseModel):
    email: str
    password: str
    case_number: Optional[str] = None

class Verify2faRequest(BaseModel):
    temp_token: str
    code: str

def _verify_pin(pin: str, stored_hash: str) -> bool:
    import hmac, base64
    if not stored_hash or not pin:
        return False
    normalized = pin.translate(str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")).strip()
    try:
        if stored_hash.startswith('pbkdf2:sha256:'):
            parts = stored_hash.split('$')
            if len(parts) != 3:
                return False
            iterations = int(parts[0].split(':')[2])
            salt_b64 = parts[1] + '=' * (-len(parts[1]) % 4)
            key_b64 = parts[2] + '=' * (-len(parts[2]) % 4)
            salt = base64.b64decode(salt_b64)
            expected = base64.b64decode(key_b64)
            actual = hashlib.pbkdf2_hmac('sha256', normalized.encode('utf-8'), salt, iterations)
            return hmac.compare_digest(actual, expected)
        if len(stored_hash) == 64 and all(c in '0123456789abcdef' for c in stored_hash.lower()):
            expected_bytes = bytes.fromhex(stored_hash)
            actual_bytes = hashlib.sha256(normalized.encode('utf-8')).digest()
            return hmac.compare_digest(actual_bytes, expected_bytes)
    except:
        pass
    return False

@router.post("/login")
async def login(req: LoginRequest, db: Session = Depends(get_db)):
    from email_service import generate_otp, store_otp, send_otp_email
    
    # Try finding user by username or email
    user = db.query(AccessProfiles).filter(
        (AccessProfiles.email == req.email.strip()) | (AccessProfiles.username == req.email.strip())
    ).first()
    
    if not user or user.is_active == 0:
        raise HTTPException(status_code=400, detail="البريد الإلكتروني أو كلمة المرور غير صحيحة.")
        
    # Client login case verification
    if user.role == "موكل" and req.case_number:
        case_num = req.case_number.strip()
        case_exists = db.query(LawCases).filter(
            LawCases.client_id == user.id,
            LawCases.case_number == case_num
        ).first()
        if not case_exists:
            raise HTTPException(status_code=400, detail="رقم القضية غير مطابق للبيانات.")
            
    if _verify_pin(req.password, user.access_pin_hash):
        user.failed_attempts = 0
        db.commit()
        
        # Check 2FA
        if getattr(user, "is_2fa_enabled", 0) == 1:
            temp_token = str(uuid.uuid4())
            _mobile_temp_2fa_sessions[temp_token] = user.id
            
            otp_code = generate_otp(6)
            store_otp(user.email, otp_code)
            send_otp_email(user.email, otp_code, purpose="2fa")
            
            return {
                "success": True,
                "two_factor_required": True,
                "temp_token": temp_token,
                "message": "تم إرسال رمز التحقق الثنائي إلى بريدك الإلكتروني."
            }
            
        # Standard login session creation
        token = str(uuid.uuid4())
        expires = datetime.now(timezone.utc) + timedelta(days=7)
        new_session = AuthSessions(
            session_token=token,
            user_id=user.id,
            is_active=1,
            expires_at=expires.strftime("%Y-%m-%d %H:%M:%S")
        )
        db.add(new_session)
        db.commit()
        
        return {
            "success": True,
            "two_factor_required": False,
            "session_token": token,
            "user": {
                "id": user.id,
                "name": user.name,
                "username": user.username,
                "email": user.email,
                "role": user.role,
                "office_id": user.office_id,
                "is_2fa_enabled": getattr(user, "is_2fa_enabled", 0)
            }
        }
    else:
        user.failed_attempts += 1
        db.commit()
        raise HTTPException(status_code=400, detail="البريد الإلكتروني أو كلمة المرور غير صحيحة.")

@router.post("/login-2fa")
async def verify_2fa(req: Verify2faRequest, db: Session = Depends(get_db)):
    from email_service import verify_otp
    
    temp_token = req.temp_token
    if temp_token not in _mobile_temp_2fa_sessions:
        raise HTTPException(status_code=400, detail="انتهت صلاحية جلسة التحقق، يرجى المحاولة مجدداً.")
        
    user_id = _mobile_temp_2fa_sessions[temp_token]
    user = db.query(AccessProfiles).filter(AccessProfiles.id == user_id).first()
    if not user:
        raise HTTPException(status_code=400, detail="المستخدم غير موجود.")
        
    if verify_otp(user.email, req.code.strip()):
        # OTP Valid! Clean temp session
        del _mobile_temp_2fa_sessions[temp_token]
        
        # Issue real session token
        token = str(uuid.uuid4())
        expires = datetime.now(timezone.utc) + timedelta(days=7)
        new_session = AuthSessions(
            session_token=token,
            user_id=user.id,
            is_active=1,
            expires_at=expires.strftime("%Y-%m-%d %H:%M:%S")
        )
        db.add(new_session)
        db.commit()
        
        return {
            "success": True,
            "session_token": token,
            "user": {
                "id": user.id,
                "name": user.name,
                "username": user.username,
                "email": user.email,
                "role": user.role,
                "office_id": user.office_id,
                "is_2fa_enabled": getattr(user, "is_2fa_enabled", 0)
            }
        }
    else:
        raise HTTPException(status_code=400, detail="رمز التحقق غير صحيح أو منتهي الصلاحية.")

@router.get("/profile")
async def get_profile(user: AccessProfiles = Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=401, detail="غير مصرح")
    return {
        "id": user.id,
        "name": user.name,
        "username": user.username,
        "email": user.email,
        "role": user.role,
        "office_id": user.office_id,
        "is_2fa_enabled": getattr(user, "is_2fa_enabled", 0)
    }

@router.get("/dashboard")
async def get_dashboard_stats(db: Session = Depends(get_db), user: AccessProfiles = Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=401, detail="غير مصرح")
        
    office_id = user.office_id or 1
    
    # Query case statistics
    total_cases = db.query(LawCases).filter(LawCases.office_id == office_id).count()
    open_cases = db.query(LawCases).filter(LawCases.office_id == office_id, LawCases.status_key == 'نشط').count()
    closed_cases = total_cases - open_cases
    
    return {
        "total_cases": total_cases,
        "open_cases": open_cases,
        "closed_cases": closed_cases,
        "user_role": user.role
    }

@router.get("/cases")
async def get_cases(db: Session = Depends(get_db), user: AccessProfiles = Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=401, detail="غير مصرح")
        
    office_id = user.office_id or 1
    
    # Enforce lawyer visibility constraints
    query = db.query(LawCases).filter(LawCases.office_id == office_id)
    if user.role in ['محامي', 'محامٍ'] and getattr(user, "can_view_all_cases", 0) == 0:
        query = query.filter(LawCases.assigned_lawyer_id == user.id)
    elif user.role == 'موكل':
        query = query.filter(LawCases.client_id == user.id)
        
    cases = query.order_by(LawCases.created_at.desc()).all()
    
    return [{
        "id": c.id,
        "case_number": c.case_number,
        "title": c.title,
        "court_name": c.court_name,
        "status_key": c.status_key,
        "case_type_key": c.case_type_key,
        "created_at": c.created_at[:10] if c.created_at else None
    } for c in cases]

@router.get("/documents")
async def get_documents(db: Session = Depends(get_db), user: AccessProfiles = Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=401, detail="غير مصرح")
        
    office_id = user.office_id or 1
    
    # Fetch cases accessible by this user to filter documents
    cases_query = db.query(LawCases).filter(LawCases.office_id == office_id)
    if user.role in ['محامي', 'محامٍ'] and getattr(user, "can_view_all_cases", 0) == 0:
        cases_query = cases_query.filter(LawCases.assigned_lawyer_id == user.id)
    elif user.role == 'موكل':
        cases_query = cases_query.filter(LawCases.client_id == user.id)
        
    accessible_case_ids = [c.id for c in cases_query.all()]
    
    documents = db.query(LawDocuments).filter(
        LawDocuments.office_id == office_id,
        LawDocuments.case_id.in_(accessible_case_ids)
    ).order_by(LawDocuments.created_at.desc()).all()
    
    return [{
        "id": doc.id,
        "name": doc.name,
        "case_id": doc.case_id,
        "document_type_key": doc.document_type_key,
        "file_path": doc.file_path,
        "doc_date": doc.doc_date,
        "notes": doc.notes
    } for doc in documents]

@router.post("/settings/toggle-2fa")
async def toggle_2fa(db: Session = Depends(get_db), user: AccessProfiles = Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=401, detail="غير مصرح")
        
    # Toggle 2FA flag
    user.is_2fa_enabled = 0 if getattr(user, "is_2fa_enabled", 0) == 1 else 1
    db.commit()
    
    return {
        "success": True,
        "is_2fa_enabled": user.is_2fa_enabled,
        "message": "تم تحديث إعدادات التحقق الثنائي بنجاح."
    }

@router.post("/logout")
async def logout(user: AccessProfiles = Depends(get_current_user), db: Session = Depends(get_db)):
    if user:
        # Deactivate all active sessions for this user
        sessions = db.query(AuthSessions).filter(AuthSessions.user_id == user.id, AuthSessions.is_active == 1).all()
        for s in sessions:
            s.is_active = 0
        db.commit()
    return {"success": True}
