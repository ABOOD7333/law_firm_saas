"""
سكريبت تحديث بيانات تسجيل الدخول للشركات الثلاث
"""
import os
import sys
import hashlib
import base64

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database.database import SessionLocal
from database.models import AccessProfiles, LawOffices


def hash_pin(pin: str) -> str:
    """دالة تشفير كلمة المرور - نفس الطريقة المستخدمة في النظام"""
    salt = os.urandom(16)
    iterations = 260000
    actual = hashlib.pbkdf2_hmac('sha256', pin.encode('utf-8'), salt, iterations)
    salt_b64 = base64.b64encode(salt).decode('utf-8').rstrip('=')
    hash_b64 = base64.b64encode(actual).decode('utf-8').rstrip('=')
    return f"pbkdf2:sha256:{iterations}${salt_b64}${hash_b64}"


def update_credentials():
    db = SessionLocal()
    
    # قائمة التحديثات المطلوبة: (اسم_مستخدم_جديد, كلمة_مرور_جديدة, رقم_المكتب)
    updates = [
        {"new_username": "alalimi1", "new_password": "admin123456", "office_index": 1},
        {"new_username": "alalimi2", "new_password": "admin123456", "office_index": 2},
        {"new_username": "alalimi3", "new_password": "admin123456", "office_index": 3},
    ]
    
    try:
        # عرض جميع الشركات المسجلة (باستثناء مكتب النظام id=1)
        print("=" * 60)
        print("الشركات/المكاتب المسجلة في النظام:")
        print("=" * 60)
        
        offices = db.query(LawOffices).filter(LawOffices.id != 1).all()
        
        if not offices:
            print("❌ لا توجد شركات مسجلة في النظام (غير مكتب النظام)")
            return
        
        for i, office in enumerate(offices, 1):
            print(f"{i}. مكتب ID={office.id} | الاسم: {office.name}")
            
            # عرض المستخدمين المرتبطين بهذا المكتب
            users = db.query(AccessProfiles).filter(
                AccessProfiles.office_id == office.id,
                AccessProfiles.role != "مدير"  # استثناء المدير العام
            ).all()
            
            # إذا لم يوجد مستخدمون غير مدير، اعرض الكل
            if not users:
                users = db.query(AccessProfiles).filter(
                    AccessProfiles.office_id == office.id
                ).all()
            
            for user in users:
                print(f"   👤 المستخدم: {user.username} | الدور: {user.role} | الاسم: {user.name}")
        
        print("\n" + "=" * 60)
        print("بدء تحديث بيانات تسجيل الدخول...")
        print("=" * 60)
        
        # تحديث كل شركة
        for i, office in enumerate(offices[:3], 1):
            if i > 3:
                break
                
            update = updates[i - 1]
            new_username = update["new_username"]
            new_password = update["new_password"]
            
            # جلب المستخدمين المرتبطين بهذا المكتب
            # نبحث عن المستخدم الرئيسي (المدير أو أول مستخدم)
            users_in_office = db.query(AccessProfiles).filter(
                AccessProfiles.office_id == office.id
            ).all()
            
            if not users_in_office:
                print(f"⚠️  لا يوجد مستخدمون للمكتب: {office.name}")
                continue
            
            # اختيار المستخدم الرئيسي (المدير إن وجد، وإلا الأول)
            main_user = None
            for u in users_in_office:
                if u.username != 'ABOOD':  # استثناء السوبر أدمن
                    main_user = u
                    break
            
            if not main_user:
                print(f"⚠️  لم يتم العثور على مستخدم مناسب للمكتب: {office.name}")
                continue
            
            old_username = main_user.username
            main_user.username = new_username
            main_user.access_pin_hash = hash_pin(new_password)
            main_user.failed_attempts = 0  # إعادة تعيين المحاولات الفاشلة
            main_user.is_active = 1  # التأكد أن الحساب نشط
            
            print(f"✅ الشركة {i}: {office.name}")
            print(f"   تم تغيير: {old_username} → {new_username}")
            print(f"   كلمة المرور الجديدة: {new_password}")
            print()
        
        db.commit()
        print("=" * 60)
        print("✅ تم حفظ جميع التغييرات بنجاح!")
        print("=" * 60)
        print("\n📋 ملخص بيانات الدخول الجديدة:")
        print(f"   شركة 1 → اسم المستخدم: alalimi1 | كلمة المرور: admin123456")
        print(f"   شركة 2 → اسم المستخدم: alalimi2 | كلمة المرور: admin123456")
        print(f"   شركة 3 → اسم المستخدم: alalimi3 | كلمة المرور: admin123456")
        
    except Exception as e:
        db.rollback()
        print(f"❌ حدث خطأ: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    update_credentials()
