import sys
sys.path.append(r'C:\Users\Roots\Desktop\law_firm1')

import hashlib, base64, os
from database.database import SessionLocal
from database.models import AccessProfiles

def hash_pin(pin: str) -> str:
    salt = os.urandom(16)
    iterations = 260000
    actual = hashlib.pbkdf2_hmac('sha256', pin.encode('utf-8'), salt, iterations)
    salt_b64 = base64.b64encode(salt).decode('utf-8').rstrip('=')
    hash_b64 = base64.b64encode(actual).decode('utf-8').rstrip('=')
    return f"pbkdf2:sha256:{iterations}${salt_b64}${hash_b64}"

db = SessionLocal()

# البحث عن الحساب بأي طريقة ممكنة
user = db.query(AccessProfiles).filter(
    (AccessProfiles.username == 'admin123') |
    (AccessProfiles.email == 'admin123')
).first()

if user:
    print(f"✅ تم العثور على الحساب: {user.name} ({user.role})")
    # تحديث كلمة المرور فقط
    user.access_pin_hash = hash_pin("464646")
    user.role = "مدير المكتب"
    user.is_active = 1
    user.failed_attempts = 0
    db.commit()
    print("✅ تم تحديث كلمة المرور إلى 464646 بنجاح!")
    print(f"   اسم المستخدم: {user.username}")
    print(f"   الدور: {user.role}")
else:
    # إذا لم يوجد، نُنشئه
    print("⚠️ لم يُعثر على حساب باسم admin123، سيتم إنشاؤه...")
    
    # التحقق من وجود مكتب أولاً
    from database.models import LawOffices
    office = db.query(LawOffices).first()
    office_id = office.id if office else 1
    
    new_user = AccessProfiles(
        name="مدير المكتب",
        username="admin123",
        email="admin123@lawfirm.com",
        role="مدير المكتب",
        office_id=office_id,
        access_pin_hash=hash_pin("464646"),
        is_active=1,
        failed_attempts=0
    )
    db.add(new_user)
    db.commit()
    print("✅ تم إنشاء الحساب بنجاح!")
    print(f"   اسم المستخدم: admin123")
    print(f"   كلمة المرور: 464646")
    print(f"   الدور: مدير المكتب")

db.close()
print("\n🔐 يمكنك الآن تسجيل الدخول بـ: admin123 | 464646")
