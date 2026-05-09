import sys
sys.path.append(r'C:\Users\Roots\Desktop\law_firm1')

from database.database import SessionLocal
from database.models import AccessProfiles
import hashlib, base64, hmac

def verify_pin(pin: str, stored_hash: str) -> bool:
    if not stored_hash or not pin:
        return False
    # Normalize Arabic/Persian digits
    normalized = pin.translate(str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")).strip()
    try:
        parts = stored_hash.split('$')
        if len(parts) != 3:
            return False
        algo_iters, salt_b64, hash_b64 = parts
        _, algo, iters = algo_iters.split(':')
        salt = base64.b64decode(salt_b64 + '==')
        expected = base64.b64decode(hash_b64 + '==')
        computed = hashlib.pbkdf2_hmac(algo, normalized.encode(), salt, int(iters))
        return hmac.compare_digest(computed, expected)
    except Exception as e:
        print(f"Error verifying: {e}")
        return False

db = SessionLocal()

# البحث عن المستخدم
user = db.query(AccessProfiles).filter(
    (AccessProfiles.username == 'admin123') |
    (AccessProfiles.email == 'admin123')
).first()

if user:
    print(f"✅ وُجد المستخدم!")
    print(f"   الاسم: {user.name}")
    print(f"   اسم المستخدم: {user.username}")
    print(f"   الإيميل: {user.email}")
    print(f"   الدور: {user.role}")
    print(f"   الحالة: {'نشط' if user.is_active else 'موقوف'}")
    
    # التحقق من كلمة المرور
    pin_ok = verify_pin("464646", user.access_pin_hash)
    print(f"   كلمة المرور 464646: {'✅ صحيحة' if pin_ok else '❌ خاطئة'}")
else:
    print("❌ لم يُعثر على مستخدم باسم 'admin123'")
    print("\nالمستخدمون الموجودون في قاعدة البيانات:")
    all_users = db.query(AccessProfiles).all()
    for u in all_users:
        print(f"  - [{u.id}] username={u.username} | email={u.email} | role={u.role} | active={u.is_active}")

db.close()
