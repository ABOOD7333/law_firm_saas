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
    db = SessionLocal()
    try:
        # تأكد من وجود مكتب افتراضي (SuperAdmin Office)
        office = db.query(LawOffices).filter(LawOffices.id == 1).first()
        if not office:
            office = LawOffices(
                id=1,
                name="مكتب إدارة النظام (المنصة الرئيسية)",
                status_key="active",
                is_active=1
            )
            db.add(office)
            db.commit()

        # إنشاء مستخدم SuperAdmin
        admin = db.query(AccessProfiles).filter(AccessProfiles.username == 'ABOOD').first()
        if not admin:
            admin = AccessProfiles(
                name="المدير العام للمنصة",
                username="ABOOD",
                phone="0000000000",
                email="superadmin@lawsaas.com",
                role="مدير",
                office_id=office.id,
                access_pin_hash=hash_pin("admin123456"),
                is_active=1,
                failed_attempts=0
            )
            db.add(admin)
            db.commit()
            print("✅ تم إنشاء حساب الإدارة العليا (SuperAdmin) بنجاح!")
        else:
            admin.role = "مدير"
            admin.access_pin_hash = hash_pin("admin123456")
            admin.is_active = 1
            admin.failed_attempts = 0
            if office:
                admin.office_id = office.id
            db.commit()
            print("✅ تم تحديث وتفعيل حساب الإدارة العليا بنجاح!")

        print("\n=== بيانات الدخول (SuperAdmin) ===")
        print("البريد الإلكتروني / اسم المستخدم: ABOOD")
        print("كلمة المرور: admin123456")
        print("الرابط: http://127.0.0.1:8000/superadmin")
        print("===================================")
        
    except Exception as e:
        print("حدث خطأ:", e)
    finally:
        db.close()

if __name__ == "__main__":
    create_superadmin()
