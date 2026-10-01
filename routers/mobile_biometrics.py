import uuid
import base64
import hashlib
import secrets
from datetime import datetime, timezone, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database.database import get_db
from database.models import AccessProfiles, AuthSessions, AuthVerificationTokens, LawOffices, LawUserDevices
from dependencies import get_current_user
from core.security import hash_session_token

router = APIRouter(prefix="/api/mobile/biometrics", tags=["Mobile Biometrics"])

class RegisterDeviceRequest(BaseModel):
    device_id: str
    device_name: str
    fcm_token: Optional[str] = None
    biometric_public_key: Optional[str] = None

class BiometricLoginRequest(BaseModel):
    device_id: str
    signature: str
    payload: str

class BiometricChallengeRequest(BaseModel):
    device_id: str


def _load_public_key(pem: str):
    from cryptography.hazmat.primitives.serialization import load_pem_public_key
    return load_pem_public_key(pem.encode("utf-8"))


def _verify_signature(public_key, payload: bytes, signature: bytes) -> bool:
    from cryptography.hazmat.primitives.asymmetric import ec, ed25519, padding, rsa
    from cryptography.hazmat.primitives import hashes
    try:
        if isinstance(public_key, ed25519.Ed25519PublicKey):
            public_key.verify(signature, payload)
        elif isinstance(public_key, rsa.RSAPublicKey):
            if public_key.key_size < 2048:
                return False
            public_key.verify(signature, payload, padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH), hashes.SHA256())
        elif isinstance(public_key, ec.EllipticCurvePublicKey):
            public_key.verify(signature, payload, ec.ECDSA(hashes.SHA256()))
        else:
            return False
        return True
    except Exception:
        return False

@router.post("/register-device")
async def register_device(req: RegisterDeviceRequest, db: Session = Depends(get_db), user: AccessProfiles = Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=401, detail="غير مصرح")
        
    if len(req.device_id) > 200 or not req.device_id or not req.biometric_public_key:
        raise HTTPException(status_code=400, detail="معرّف الجهاز والمفتاح العام مطلوبان")
    try:
        _load_public_key(req.biometric_public_key)
    except Exception:
        raise HTTPException(status_code=400, detail="المفتاح العام غير صالح")

    device = db.query(LawUserDevices).filter(LawUserDevices.device_id == req.device_id).first()
    
    if device:
        if device.user_id != user.id:
            raise HTTPException(status_code=403, detail="الجهاز مرتبط بحساب آخر")
        # Update existing device
        device.user_id = user.id
        device.fcm_token = req.fcm_token
        device.biometric_public_key = req.biometric_public_key
        device.device_name = req.device_name
        device.last_active = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        device.is_active = 1
    else:
        # Create new device
        device = LawUserDevices(
            user_id=user.id,
            device_id=req.device_id,
            fcm_token=req.fcm_token,
            biometric_public_key=req.biometric_public_key,
            device_name=req.device_name,
            last_active=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        )
        db.add(device)
        
    db.commit()
    return {"success": True, "message": "تم تسجيل الجهاز بنجاح"}

@router.post("/challenge")
async def create_biometric_challenge(req: BiometricChallengeRequest, db: Session = Depends(get_db)):
    device = db.query(LawUserDevices).filter(
        LawUserDevices.device_id == req.device_id,
        LawUserDevices.is_active == 1,
        LawUserDevices.is_deleted == 0,
    ).first()
    user = db.query(AccessProfiles).filter(
        AccessProfiles.id == device.user_id,
        AccessProfiles.is_active == 1,
    ).first() if device else None
    if not device or not user or not device.biometric_public_key:
        raise HTTPException(status_code=404, detail="الجهاز غير مسجل")
    challenge = secrets.token_urlsafe(32)
    expires = datetime.now(timezone.utc) + timedelta(minutes=2)
    db.add(AuthVerificationTokens(
        user_id=user.id,
        token_hash=hashlib.sha256(challenge.encode()).hexdigest(),
        token_type=f"biometric:{device.device_id}",
        expires_at=expires.strftime("%Y-%m-%d %H:%M:%S"),
    ))
    db.commit()
    return {"challenge": challenge, "expires_in": 120}


@router.post("/login")
async def biometric_login(req: BiometricLoginRequest, db: Session = Depends(get_db)):
    if len(req.device_id) > 200 or len(req.payload) > 512 or len(req.signature) > 4096:
        raise HTTPException(status_code=400, detail="طلب غير صالح")
    device = db.query(LawUserDevices).filter(
        LawUserDevices.device_id == req.device_id,
        LawUserDevices.is_active == 1,
        LawUserDevices.is_deleted == 0,
    ).first()
    
    if not device:
        raise HTTPException(status_code=401, detail="الجهاز غير مسجل أو موقوف")
        
    user = db.query(AccessProfiles).filter(AccessProfiles.id == device.user_id, AccessProfiles.is_active == 1).first()
    
    if not user:
        raise HTTPException(status_code=401, detail="المستخدم غير متاح")
    office = db.query(LawOffices).filter(
        LawOffices.id == user.office_id,
        LawOffices.is_active == 1,
    ).first() if user.office_id else None
    if not office:
        raise HTTPException(status_code=401, detail="المكتب غير متاح")
    if office.subscription_end and office.subscription_plan != "lifetime":
        try:
            expiration = datetime.strptime(office.subscription_end, "%Y-%m-%d %H:%M:%S")
            if expiration < datetime.utcnow():
                raise HTTPException(status_code=403, detail="الاشتراك منتهي")
        except ValueError:
            raise HTTPException(status_code=403, detail="حالة الاشتراك غير صالحة")

    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    challenge_hash = hashlib.sha256(req.payload.encode()).hexdigest()
    challenge_record = db.query(AuthVerificationTokens).filter(
        AuthVerificationTokens.user_id == user.id,
        AuthVerificationTokens.token_hash == challenge_hash,
        AuthVerificationTokens.token_type == f"biometric:{device.device_id}",
        AuthVerificationTokens.expires_at > now_str,
        AuthVerificationTokens.consumed_at.is_(None),
    ).first()
    if not challenge_record:
        raise HTTPException(status_code=401, detail="التحدي غير صالح أو منتهي")
    try:
        signature_bytes = base64.b64decode(req.signature, validate=True)
        public_key = _load_public_key(device.biometric_public_key or "")
    except Exception:
        raise HTTPException(status_code=401, detail="تعذر التحقق من التوقيع")
    if not _verify_signature(public_key, req.payload.encode(), signature_bytes):
        challenge_record.attempts += 1
        if challenge_record.attempts >= 3:
            challenge_record.consumed_at = now_str
        db.commit()
        raise HTTPException(status_code=401, detail="التوقيع غير صالح")

    challenge_record.consumed_at = now_str
    token = str(uuid.uuid4())
    refresh_token = str(uuid.uuid4())
    expires = datetime.now(timezone.utc) + timedelta(days=7)
    new_session = AuthSessions(
        session_token=hash_session_token(token),
        refresh_token=refresh_token,
        user_id=user.id,
        device_id=req.device_id,
        is_active=1,
        expires_at=expires.strftime("%Y-%m-%d %H:%M:%S")
    )
    db.add(new_session)
    
    # Update last active
    device.last_active = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    db.commit()
    
    return {
        "success": True,
        "session_token": token,
        "refresh_token": refresh_token,
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
