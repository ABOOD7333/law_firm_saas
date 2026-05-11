import os

# نضع رابط قاعدة البيانات السحابية
os.environ['DATABASE_URL'] = 'postgresql://postgres:CpgDcHxPvpbGJtHOcfFGvQjjivCvJGYc@viaduct.proxy.rlwy.net:38311/railway'

from database.database import SessionLocal
from database.models import AccessProfiles, LawOffices

def check_stats():
    db = SessionLocal()
    try:
        accounts = db.query(AccessProfiles).count()
        offices = db.query(LawOffices).count()
        
        pending_users = db.query(AccessProfiles).filter(AccessProfiles.email_verified == 0).all()
        pending_accounts = len(pending_users)
        active_accounts = accounts - pending_accounts
        
        print("\n" + "="*50)
        print("☁️  إحصائيات قاعدة البيانات السحابية  ☁️")
        print("="*50)
        print(f"👥 إجمالي الحسابات المسجلة : {accounts}")
        print(f"✅ الحسابات المفعلة (مؤكدة) : {active_accounts}")
        print(f"⏳ الحسابات المعلقة (لم تؤكد): {pending_accounts}")
        print("-" * 50)
        print(f"🏢 إجمالي المكاتب المسجلة : {offices}")
        print("="*50)
        
        if pending_accounts > 0:
            print("\n📌 تفاصيل الحسابات المعلقة:")
            print("-" * 50)
            for user in pending_users:
                print(f"👤 الاسم: {user.name}")
                print(f"📧 الإيميل: {user.email}")
                print(f"📱 الهاتف: {user.phone}")
                print(f"🔑 اسم المستخدم: {user.username}")
                print("-" * 50)
        print("\n")
    except Exception as e:
        print(f"\n❌ حدث خطأ أثناء الاتصال: {e}\n")
    finally:
        db.close()

if __name__ == "__main__":
    check_stats()
