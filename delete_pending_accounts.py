import os

# نضع رابط قاعدة البيانات السحابية
os.environ['DATABASE_URL'] = 'postgresql://postgres:CpgDcHxPvpbGJtHOcfFGvQjjivCvJGYc@viaduct.proxy.rlwy.net:38311/railway'

from database.database import SessionLocal
from database.models import AccessProfiles

def delete_pending():
    db = SessionLocal()
    try:
        # البحث عن جميع الحسابات المعلقة (غير المفعلة)
        pending_users = db.query(AccessProfiles).filter(AccessProfiles.email_verified == 0).all()
        count = len(pending_users)
        
        if count == 0:
            print("\n✅ لا يوجد أي حسابات معلقة للحذف.\n")
            return
            
        print(f"\n🗑️ جاري حذف {count} حساب معلق...")
        
        # حذف كل حساب معلق
        for user in pending_users:
            print(f"- تم حذف: {user.name} ({user.email})")
            db.delete(user)
            
        # تأكيد الحذف في قاعدة البيانات
        db.commit()
        
        print("\n✅ تم حذف جميع الحسابات المعلقة بنجاح! قاعدة بياناتك الآن نظيفة.\n")
    except Exception as e:
        db.rollback()
        print(f"\n❌ حدث خطأ أثناء الحذف: {e}\n")
    finally:
        db.close()

if __name__ == "__main__":
    delete_pending()
