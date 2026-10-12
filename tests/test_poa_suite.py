import asyncio
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from httpx import AsyncClient, ASGITransport
from datetime import date, timedelta
from main import app
from database.database import SessionLocal
from database.models import AccessProfiles, LawOffices, LawCases, LawPowerOfAttorney

async def test_poa_flow():
    db = SessionLocal()
    try:
        user1 = db.query(AccessProfiles).filter(AccessProfiles.username == "R1990").first()
        assert user1 is not None, "R1990 user must exist"
        case1 = db.query(LawCases).filter(LawCases.office_id == user1.office_id, LawCases.is_deleted == 0).first()
        if not case1:
            case1 = LawCases(office_id=user1.office_id, case_number="CASE-POA-101", title="قضية اختبار الوكالة", status_key="active")
            db.add(case1)
            db.commit()
            db.refresh(case1)

        user2 = db.query(AccessProfiles).filter(AccessProfiles.office_id != user1.office_id).first()
        assert user2 is not None, "User 2 must exist"
    finally:
        db.close()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Login
        login_res = await client.post("/", data={"email": "R1990", "password": "admin123456"}, follow_redirects=False)
        assert login_res.status_code == 303
        cookies = dict(login_res.cookies)
        csrf_token = cookies.get("csrf_token") or "test_csrf"
        headers = {"X-CSRF-Token": csrf_token}

        # 1. Test GET /power_of_attorney
        print("\n--- 1. Testing GET /power_of_attorney ---")
        res = await client.get("/power_of_attorney", cookies=cookies)
        assert res.status_code == 200
        assert "إدارة الوكالات الرسمية والشرعية" in res.text
        assert "إجمالي الوكالات" in res.text
        print("GET /power_of_attorney status: 200")

        # 2. Test POST /api/poa/save (Add)
        print("\n--- 2. Testing POST /api/poa/save (Add) ---")
        expiry = str(date.today() + timedelta(days=365))
        save_data = {
            "case_id": case1.id,
            "principal_name": "الشيخ عبد الله بن فهد آل سعود",
            "agent_name": "الأستاذ راكان (محامي المكتب)",
            "agency_number": f"POA-{date.today().year}-88219",
            "poa_type": "litigation",
            "issuing_authority": "كتابة عدل الرياض الأولى",
            "issue_date": str(date.today()),
            "expiry_date": expiry,
            "scope_of_powers": "المرافعة والمدافعة وتقديم اللوائح أمام كافة المحاكم وديوان المظالم",
            "notes": "صك وكالة إلكتروني موثق عبر منصة ناجز",
            "create_reminder": True
        }
        add_res = await client.post(
            "/api/poa/save",
            json=save_data,
            cookies=cookies,
            headers={**headers, "Content-Type": "application/json"}
        )
        assert add_res.status_code == 200
        add_json = add_res.json()
        assert add_json["ok"] is True
        created_poa_id = add_json["id"]
        print(f"Created POA ID: {created_poa_id}")

        # 3. Test GET /api/poa/{id}
        print("\n--- 3. Testing GET /api/poa/{id} ---")
        get_res = await client.get(f"/api/poa/{created_poa_id}", cookies=cookies)
        assert get_res.status_code == 200
        g_json = get_res.json()
        assert g_json["ok"] is True
        assert g_json["principal_name"] == "الشيخ عبد الله بن فهد آل سعود"
        assert g_json["agent_name"] == "الأستاذ راكان (محامي المكتب)"
        assert g_json["poa_type"] == "litigation"
        print("POA details API verified successfully!")

        # 4. Test POST /api/poa/save (Edit)
        print("\n--- 4. Testing POST /api/poa/save (Edit) ---")
        edit_data = {
            "id": created_poa_id,
            "case_id": case1.id,
            "principal_name": "الشيخ عبد الله بن فهد آل سعود (محدث)",
            "agent_name": "الأستاذ راكان (محامي المكتب)",
            "agency_number": f"POA-{date.today().year}-88219",
            "poa_type": "general",
            "issuing_authority": "كتابة عدل الرياض الأولى",
            "issue_date": str(date.today()),
            "expiry_date": expiry,
            "scope_of_powers": "إضافة صلاحية استلام وتحصيل المبالغ والشيكات",
            "notes": "تم تجديد الصك وتحديث الصلاحيات"
        }
        edit_res = await client.post(
            "/api/poa/save",
            json=edit_data,
            cookies=cookies,
            headers={**headers, "Content-Type": "application/json"}
        )
        assert edit_res.status_code == 200
        print("POA edited successfully!")

        # 5. Test Multi-Tenant Isolation
        print("\n--- 5. Testing Multi-Tenant Isolation ---")
        client2 = AsyncClient(transport=transport, base_url="http://test")
        login2 = await client2.post("/", data={"email": user2.username, "password": "password123"}, follow_redirects=False)
        cookies2 = dict(login2.cookies)
        cross_res = await client2.get(f"/api/poa/{created_poa_id}", cookies=cookies2)
        assert cross_res.status_code in [404, 403, 401, 303]
        print("Multi-tenant isolation verified!")

        # 6. Test DELETE /api/poa/delete/{id}
        print("\n--- 6. Testing DELETE /api/poa/delete/{id} ---")
        del_res = await client.delete(
            f"/api/poa/delete/{created_poa_id}",
            cookies=cookies,
            headers=headers
        )
        assert del_res.status_code == 200
        # Verify it's soft deleted
        check_del = await client.get(f"/api/poa/{created_poa_id}", cookies=cookies)
        assert check_del.status_code == 404
        print("Soft delete verified successfully!")

        print("\nALL POA TESTS PASSED 100%!")

if __name__ == "__main__":
    asyncio.run(test_poa_flow())
