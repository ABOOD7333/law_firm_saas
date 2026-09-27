"""
تجهيز وإنشاء المكاتب والمستخدمين الحقيقيين تلقائياً في قاعدة البيانات
"""
import os
import sys
import hashlib
import base64
from sqlalchemy.orm import Session

def hash_pin(pin: str) -> str:
    salt = os.urandom(16)
    iterations = 260000
    actual = hashlib.pbkdf2_hmac('sha256', pin.encode('utf-8'), salt, iterations)
    salt_b64 = base64.b64encode(salt).decode('utf-8').rstrip('=')
    hash_b64 = base64.b64encode(actual).decode('utf-8').rstrip('=')
    return f"pbkdf2:sha256:{iterations}${salt_b64}${hash_b64}"

def seed_real_offices(db: Session):
    try:
        from database.models import LawOffices, AccessProfiles, LawClients, LawCases
        
        # 1. مكتب إدارة النظام (SuperAdmin)
        main_office = db.query(LawOffices).filter(LawOffices.id == 1).first()
        if not main_office:
            main_office = LawOffices(
                id=1,
                name="مكتب إدارة النظام (المنصة الرئيسية)",
                status_key="active",
                is_active=1
            )
            db.add(main_office)
            db.commit()

        # حساب المدير العام ABOOD
        admin = db.query(AccessProfiles).filter(AccessProfiles.username == 'ABOOD').first()
        if not admin:
            admin = AccessProfiles(
                name="المدير العام للمنصة",
                username="ABOOD",
                phone="0000000000",
                email="superadmin@lawsaas.com",
                role="مدير",
                office_id=1,
                access_pin_hash=hash_pin("admin123456"),
                is_active=1,
                failed_attempts=0,
                is_superadmin=1
            )
            db.add(admin)
            db.commit()

        # 2. قائمة المكاتب والشركات المسجلة
        offices_data = [
            {
                "id": 2,
                "name": "مكتب العليمي للمحاماة والاستشارات القانونية",
                "username": "alalimi1",
                "lawyer_name": "المحامي محمد العليمي",
                "phone": "777111222",
                "email": "office1@alalimi-law.com",
                "plan": "premium"
            },
            {
                "id": 3,
                "name": "مكتب العدالة للمحاماة والتحكيم التجاري",
                "username": "alalimi2",
                "lawyer_name": "المحامي أحمد العليمي",
                "phone": "777333444",
                "email": "office2@alalimi-law.com",
                "plan": "standard"
            },
            {
                "id": 4,
                "name": "شركة الميزان الدولية للاستشارات القانونية",
                "username": "alalimi3",
                "lawyer_name": "المستشار خالد العليمي",
                "phone": "777555666",
                "email": "office3@alalimi-law.com",
                "plan": "lifetime"
            }
        ]

        for off in offices_data:
            office_rec = db.query(LawOffices).filter(LawOffices.id == off["id"]).first()
            if not office_rec:
                office_rec = LawOffices(
                    id=off["id"],
                    name=off["name"],
                    status_key="active",
                    is_active=1,
                    subscription_plan=off["plan"]
                )
                db.add(office_rec)
                db.commit()
            
            # المستخدم المسؤول عن المكتب
            user_rec = db.query(AccessProfiles).filter(AccessProfiles.username == off["username"]).first()
            if not user_rec:
                user_rec = AccessProfiles(
                    name=off["lawyer_name"],
                    username=off["username"],
                    phone=off["phone"],
                    email=off["email"],
                    role="صاحب المكتب",
                    office_id=off["id"],
                    access_pin_hash=hash_pin("admin123456"),
                    is_active=1,
                    failed_attempts=0,
                    is_superadmin=0
                )
                db.add(user_rec)
                db.commit()

        # 3. الموكل الحقيقي (سحر الهطامي)
        client_rec = db.query(LawClients).filter(LawClients.name == "سحر الهطامي").first()
        if not client_rec:
            client_rec = LawClients(
                name="سحر الهطامي",
                phone="771234567",
                email="sahar@example.com",
                national_id="1001001",
                office_id=2
            )
            db.add(client_rec)
            db.commit()

        # 4. القضية الحقيقية (TEST-101)
        case_rec = db.query(LawCases).filter(LawCases.case_number == "TEST-101").first()
        if not case_rec:
            case_rec = LawCases(
                case_number="TEST-101",
                title="دعوى مطالبة بحقوق عمالية وتعويض",
                status_key="active",
                visibility_mode="private",
                office_id=2,
                estimated_fee=150000.0,
                claim_amount=500000.0
            )
            db.add(case_rec)
            db.commit()

        print("[Seed] Real offices, users, clients and cases verified/created successfully.")
    except Exception as e:
        print(f"[Seed Warning] {e}")
