import os
import sys
from datetime import datetime, timedelta
import random

# إعداد المسارات لضمان القدرة على استيراد الموديلات
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy.orm import Session
from database.database import engine, Base, SessionLocal
from database.models import (
    AccessProfiles, LawOffices, LawClients, LawCases, LawParties, 
    LawHearings, LawTasks, LawDocuments, LawNotes, LawTransactions, LawExpenses,
    LawCorrespondences, LawExecutions, LawPowerOfAttorney, LawTimesheets
)
import hashlib

def hash_pin(pin: str) -> str:
    salt = os.urandom(16)
    iterations = 260000
    actual = hashlib.pbkdf2_hmac('sha256', pin.encode('utf-8'), salt, iterations)
    import base64
    salt_b64 = base64.b64encode(salt).decode('utf-8').rstrip('=')
    hash_b64 = base64.b64encode(actual).decode('utf-8').rstrip('=')
    return f"pbkdf2:sha256:{iterations}${salt_b64}${hash_b64}"

def seed_data():
    # إنشاء الجداول إذا لم تكن موجودة
    Base.metadata.create_all(bind=engine)
    
    db = SessionLocal()
    try:
        print("بدأ ضخ البيانات الحقيقية والمترابطة...")
        
        # 1. إنشاء مكتب المحاماة
        office = db.query(LawOffices).first()
        if not office:
            office = LawOffices(
                name="مكتب العليمي للمحاماة والاستشارات القانونية",
                status_key="active",
                is_active=1
            )
            db.add(office)
            db.commit()

        # 2. إنشاء محامين ومستخدمين
        admin = db.query(AccessProfiles).filter(AccessProfiles.email == 'admin@lawfirm.com').first()
        lawyer1 = db.query(AccessProfiles).filter(AccessProfiles.email == 'khaled@lawfirm.com').first()
        
        if not admin:
            admin = AccessProfiles(
                name="عبدالله العليمي", username="admin", phone="966500000001",
                email="admin@lawfirm.com", role="مدير المكتب", office_id=office.id,
                access_pin_hash=hash_pin("123456"), is_active=1
            )
            db.add(admin)
        if not lawyer1:
            lawyer1 = AccessProfiles(
                name="المحامي خالد سعيد", username="khaled", phone="966500000002",
                email="khaled@lawfirm.com", role="محامٍ", office_id=office.id,
                access_pin_hash=hash_pin("123456"), is_active=1
            )
            db.add(lawyer1)
        db.commit()

        # 3. إنشاء عملاء (أفراد وشركات)
        if db.query(LawClients).count() < 3:
            client1 = LawClients(name="شركة القمة للمقاولات العامة", phone="0501111111", email="info@alqimma.com", national_id="7001234567", office_id=office.id)
            client2 = LawClients(name="محمد بن عبدالرحمن السالم", phone="0502222222", email="m.alsalem@gmail.com", national_id="1012345678", office_id=office.id)
            client3 = LawClients(name="مؤسسة التقنية الحديثة", phone="0503333333", email="tech@modern.sa", national_id="7009876543", office_id=office.id)
            db.add_all([client1, client2, client3])
            db.commit()
            print("تم إضافة العملاء...")
        else:
            clients = db.query(LawClients).all()
            client1 = clients[0]
            client2 = clients[1]

        # 4. إنشاء قضايا (Cases) مترابطة
        if db.query(LawCases).count() == 0:
            today = datetime.now()
            case1 = LawCases(
                office_id=office.id, title="مطالبة مالية بتعويض عن تأخير تنفيذ مشروع", case_number="45/3321",
                case_type_key="تجارية", status_key="قيد المتابعة",
                open_date=(today - timedelta(days=45)).strftime("%Y-%m-%d"),
                lead_lawyer_id=admin.id if admin else None,
                summary="مطالبة الشركة المدعى عليها بدفع مبلغ 5 مليون ريال تعويضاً عن الإخلال بالعقد."
            )
            case2 = LawCases(
                office_id=office.id, title="نزاع عمالي - فصل تعسفي", case_number="45/9981",
                case_type_key="عمالية", status_key="جديدة",
                open_date=(today - timedelta(days=10)).strftime("%Y-%m-%d"),
                lead_lawyer_id=lawyer1.id if lawyer1 else None,
                summary="العميل يطالب ببدل إجازات ومكافأة نهاية خدمة بعد فصله تعسفياً."
            )
            db.add_all([case1, case2])
            db.commit()
            print("تم إضافة القضايا...")
            
            # ربط العملاء بالقضايا
            client1.case_id = case1.id
            client2.case_id = case2.id
            db.commit()
        else:
            cases = db.query(LawCases).all()
            case1 = cases[0]
            case2 = cases[1]
            today = datetime.now()

        # 5. الأطراف والخصوم
        if db.query(LawParties).count() == 0:
            party1 = LawParties(office_id=office.id, case_id=case1.id, name="شركة الإعمار العربية", role_key="مدعى عليه", phone="0114444444")
            party2 = LawParties(office_id=office.id, case_id=case2.id, name="شركة التجزئة المحدودة", role_key="المدعى عليه", phone="0115555555")
            db.add_all([party1, party2])
            db.commit()

        # 6. الجلسات وما بعدها
        if db.query(LawHearings).count() == 0:
            hearing1 = LawHearings(
                office_id=office.id, case_id=case1.id, title="الجلسة الأولى - تقديم المذكرات",
                hearing_at=(today + timedelta(days=15)).strftime("%Y-%m-%d %H:%M"),
                status_key="pending"
            )
            hearing2 = LawHearings(
                office_id=office.id, case_id=case2.id, title="جلسة التسوية الودية",
                hearing_at=(today - timedelta(days=2)).strftime("%Y-%m-%d %H:%M"),
                status_key="completed",
                result_summary="لم يحضر ممثل المدعى عليها وتم تحويل الدعوى للمحكمة العمالية."
            )
            db.add_all([hearing1, hearing2])
            
            task1 = LawTasks(
                office_id=office.id, case_id=case1.id, title="صياغة لائحة الدعوى التجارية",
                description="الرجاء مراجعة العقد المرفق وصياغة اللائحة قبل موعد الجلسة.",
                due_at=(today + timedelta(days=5)).strftime("%Y-%m-%d"),
                priority_level=1, status_key="in_progress", assignee_user_id=lawyer1.id if lawyer1 else None
            )
            task2 = LawTasks(
                office_id=office.id, case_id=case2.id, title="التواصل مع العميل لطلب كشف الحساب",
                due_at=(today + timedelta(days=1)).strftime("%Y-%m-%d"),
                priority_level=2, status_key="pending", assignee_user_id=admin.id if admin else None
            )
            db.add_all([task1, task2])
            
            doc1 = LawDocuments(office_id=office.id, case_id=case1.id, name="عقد المقاولة الأساسي", document_type_key="عقد", doc_date=(today - timedelta(days=40)).strftime("%Y-%m-%d"))
            doc2 = LawDocuments(office_id=office.id, case_id=case2.id, name="خطاب إنهاء الخدمات", document_type_key="خطاب", doc_date=(today - timedelta(days=15)).strftime("%Y-%m-%d"))
            db.add_all([doc1, doc2])
            
            poa1 = LawPowerOfAttorney(office_id=office.id, case_id=case1.id, principal_name=client1.name, agency_number="45000112233", issue_date=(today - timedelta(days=100)).strftime("%Y-%m-%d"), expiry_date=(today + timedelta(days=300)).strftime("%Y-%m-%d"))
            db.add(poa1)

            trans1 = LawTransactions(office_id=office.id, case_id=case1.id, title="الدفعة المقدمة من أتعاب المحاماة", amount=50000.0, transaction_at=(today - timedelta(days=40)).strftime("%Y-%m-%d"))
            exp1 = LawExpenses(office_id=office.id, case_id=case1.id, title="رسوم قيد الدعوى التجارية", amount=10000.0, expense_at=(today - timedelta(days=35)).strftime("%Y-%m-%d"))
            db.add_all([trans1, exp1])

            corr1 = LawCorrespondences(office_id=office.id, case_id=case1.id, direction_key="صادر", subject="إنذار أخير قبل اللجوء للقضاء", letter_number="2024/001", letter_date=(today - timedelta(days=50)).strftime("%Y-%m-%d"), needs_reply="نعم", response_status="لم يتم الرد")
            db.add(corr1)
            
            time1 = LawTimesheets(office_id=office.id, case_id=case1.id, user_id=lawyer1.id if lawyer1 else None, title="دراسة مستندات وعقود القضية", duration_hours=4.5, billable_rate=500.0)
            db.add(time1)
            
            note1 = LawNotes(office_id=office.id, case_id=case1.id, title="ملاحظة هامة", content="يجب التأكد من تجديد الوكالة قبل الجلسة القادمة.")
            db.add(note1)

        db.commit()
        print("✅ تم إنشاء وتعبئة جميع البيانات بنجاح وبشكل مترابط 100%!")
    except Exception as e:
        print("حدث خطأ:", e)
    finally:
        db.close()

if __name__ == "__main__":
    seed_data()
