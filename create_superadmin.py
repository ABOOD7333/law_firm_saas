import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database.database import SessionLocal, engine, Base
from database.models import AccessProfiles, LawOffices
import hashlib
import base64

def hash_pin(pin: str) -> str:
    salt = os.urandom(16)
    iterations = 260000
    actual = hashlib.pbkdf2_hmac('sha256', pin.encode('utf-8'), salt, iterations)
    salt_b64 = base64.b64encode(salt).decode('utf-8').rstrip('=')
    hash_b64 = base64.b64encode(actual).decode('utf-8').rstrip('=')
    return f"pbkdf2:sha256:{iterations}${salt_b64}${hash_b64}"

def create_superadmin():
    username = os.getenv("SUPERADMIN_USERNAME", "").strip()
    password = os.getenv("SUPERADMIN_PASSWORD", "")
    email = os.getenv("SUPERADMIN_EMAIL", "").strip().lower()
    phone = os.getenv("SUPERADMIN_PHONE", "").strip()
    db = SessionLocal()

    # Missing bootstrap settings must never mutate or disable existing users.
    if not username or len(password) < 12 or not email or not phone:
        db.close()
        print("[SuperAdmin] Bootstrap skipped: configure SUPERADMIN_USERNAME, SUPERADMIN_EMAIL, SUPERADMIN_PHONE, and a 12+ character SUPERADMIN_PASSWORD.")
        return

    # Disable accounts created by the old shared-credential demo seed unless
    # the operator explicitly enables demo mode for a development environment.
    if os.getenv("ALLOW_DEMO_SEED") != "1":
        from database.models import AuthSessions
        legacy_users = db.query(AccessProfiles).filter(
            AccessProfiles.username.in_(["ABOOD", "alalimi1", "alalimi2", "alalimi3"])
        ).all()
        for legacy in legacy_users:
            if legacy.username == username and legacy.username == "ABOOD":
                continue
            legacy.is_active = 0
            db.query(AuthSessions).filter_by(user_id=legacy.id, is_active=1).update({"is_active": 0})
        if legacy_users:
            db.commit()

    try:
        office = db.query(LawOffices).filter(LawOffices.name == "مكتب إدارة النظام (المنصة الرئيسية)").first()
        if not office:
            office = LawOffices(
                name="مكتب إدارة النظام (المنصة الرئيسية)",
                status_key="active",
                is_active=1
            )
            db.add(office)
            db.commit()

        # إنشاء مستخدم SuperAdmin
        admin = db.query(AccessProfiles).filter(AccessProfiles.username == username).first()
        if not admin:
            if db.query(AccessProfiles).filter(AccessProfiles.email == email).first():
                raise ValueError("SUPERADMIN_EMAIL is already assigned to another account")
            if db.query(AccessProfiles).filter(AccessProfiles.phone == phone).first():
                raise ValueError("SUPERADMIN_PHONE is already assigned to another account")
            admin = AccessProfiles(
                name="المدير العام للمنصة",
                username=username,
                phone=phone,
                email=email,
                role="مدير",
                office_id=office.id,
                access_pin_hash=hash_pin(password),
                is_active=1,
                failed_attempts=0,
                is_superadmin=1
            )
            db.add(admin)
            db.commit()
            print("[SuperAdmin] Bootstrap account created.")
        else:
            if getattr(admin, "is_superadmin", 0) != 1:
                raise ValueError("Configured SUPERADMIN_USERNAME belongs to a non-superadmin account")
            if admin.email.lower() != email:
                raise ValueError("Configured SUPERADMIN_EMAIL does not match the existing administrator")
            if admin.phone != phone and db.query(AccessProfiles).filter(
                AccessProfiles.phone == phone,
                AccessProfiles.id != admin.id,
            ).first():
                raise ValueError("SUPERADMIN_PHONE is already assigned to another account")
            # The deployment secret is the only permitted source for bootstrap credential rotation.
            admin.access_pin_hash = hash_pin(password)
            admin.phone = phone
            admin.is_active = 1
            admin.failed_attempts = 0
            db.commit()
        
    except Exception as e:
        print("حدث خطأ:", e)
    finally:
        db.close()

if __name__ == "__main__":
    create_superadmin()
