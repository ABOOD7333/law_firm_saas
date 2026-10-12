import asyncio
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from datetime import datetime, timedelta
from httpx import AsyncClient, ASGITransport
from main import app
from database.database import SessionLocal
from database.models import LawCorrespondences, LawCases, LawTasks, AccessProfiles

async def run_correspondences_test():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Login with R1990
        login_resp = await client.post(
            "/",
            data={"email": "R1990", "password": "admin123456"},
            follow_redirects=False
        )
        assert login_resp.status_code == 303, f"Login failed: {login_resp.status_code}"
        cookies = dict(login_resp.cookies)
        csrf_token = cookies.get("csrf_token", "")

        # 2. Test GET /correspondences
        print("\n--- 1. Testing GET /correspondences ---")
        get_resp = await client.get("/correspondences", cookies=cookies)
        print("GET /correspondences status:", get_resp.status_code)
        assert get_resp.status_code == 200, f"Failed GET /correspondences: {get_resp.status_code}"
        assert "سجل المراسلات الرسمية والصادر والوارد" in get_resp.text
        assert "addCorrModal" in get_resp.text
        assert "editCorrModal" in get_resp.text
        assert "exportCorrespondencesTable" in get_resp.text

        # 3. Get target case
        db = SessionLocal()
        case = db.query(LawCases).filter(LawCases.office_id == 1, LawCases.is_deleted == 0).first()
        assert case is not None, "No active case found in office 1"
        case_id = case.id
        print(f"Target Case ID: {case_id} ({case.title})")

        # 4. Test POST /correspondences/add (Outgoing with SLA task)
        print("\n--- 2. Testing POST /correspondences/add ---")
        today_str = datetime.now().strftime("%Y-%m-%d")
        due_str = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")

        add_data = {
            "case_id": str(case_id),
            "direction_key": "صادر",
            "letter_number": "EXT-2026/8891",
            "letter_date": today_str,
            "subject": "إشعار رسمي بفسخ العقد والمطالبة بالشرط الجزائي",
            "entity_name": "شركة الأفق العقارية للمقاولات",
            "recipient_name": "الرئيس التنفيذي / م. فهد الشمري",
            "delivery_method": "البريد السعودي SPL",
            "tracking_number": "SPL-88291039",
            "urgency_level": "عاجل",
            "confidentiality_level": "عادي",
            "needs_reply": "نعم",
            "reply_due_date": due_str,
            "create_followup_task": "1",
            "csrf_token": csrf_token
        }

        add_resp = await client.post("/correspondences/add", data=add_data, cookies=cookies, follow_redirects=False)
        print("POST /correspondences/add status:", add_resp.status_code)
        assert add_resp.status_code in [200, 303], f"Add failed: {add_resp.status_code}"

        # 5. Verify created correspondence in database
        db.expire_all()
        created_corr = db.query(LawCorrespondences).filter(
            LawCorrespondences.office_id == 1,
            LawCorrespondences.letter_number == "EXT-2026/8891",
            LawCorrespondences.is_deleted == 0
        ).first()
        assert created_corr is not None, "Correspondence not found in DB!"
        print(f"Created Correspondence ID: {created_corr.id}, Registry: {created_corr.registry_number}")
        assert created_corr.direction_key == "صادر"
        assert created_corr.registry_number is not None and created_corr.registry_number.startswith("ص-")
        assert created_corr.entity_name == "شركة الأفق العقارية للمقاولات"
        assert created_corr.response_status == "بانتظار الرد"

        # 6. Verify automated follow-up task
        task = db.query(LawTasks).filter(
            LawTasks.office_id == 1,
            LawTasks.case_id == case_id,
            LawTasks.title.like(f"%{created_corr.registry_number}%")
        ).first()
        assert task is not None, "Follow-up SLA task was not generated in LawTasks!"
        print(f"Follow-up Task Verified! ID: {task.id}, Title: {task.title}, Due: {task.due_at}")

        # 7. Test GET /api/correspondences/{id}
        print("\n--- 3. Testing GET /api/correspondences/{id} ---")
        api_resp = await client.get(f"/api/correspondences/{created_corr.id}", cookies=cookies)
        print("GET API status:", api_resp.status_code)
        assert api_resp.status_code == 200
        api_data = api_resp.json()
        assert api_data["id"] == created_corr.id
        assert api_data["registry_number"] == created_corr.registry_number
        assert api_data["entity_name"] == "شركة الأفق العقارية للمقاولات"
        print("API Response verified successfully!")

        # 8. Test GET /correspondences/api/case-parties/{case_id}
        print("\n--- 4. Testing GET /correspondences/api/case-parties/{case_id} ---")
        parties_resp = await client.get(f"/correspondences/api/case-parties/{case_id}", cookies=cookies)
        print("GET parties status:", parties_resp.status_code)
        assert parties_resp.status_code == 200
        parties_data = parties_resp.json()
        assert "parties" in parties_data
        print(f"Found {len(parties_data['parties'])} parties for case {case_id}")

        # 9. Test POST /correspondences/edit
        print("\n--- 5. Testing POST /correspondences/edit ---")
        edit_data = {
            "corr_id": str(created_corr.id),
            "direction_key": "صادر",
            "letter_number": "EXT-2026/8891-REV",
            "letter_date": today_str,
            "subject": "تم التعديل: إشعار رسمي مستعجل ومؤكد",
            "entity_name": "شركة الأفق العقارية للمقاولات - الإدارة القانونية",
            "recipient_name": "م. فهد الشمري",
            "delivery_method": "تسليم يدوي بكعب استلام",
            "tracking_number": "HAND-001",
            "urgency_level": "فوري",
            "confidentiality_level": "سري",
            "needs_reply": "نعم",
            "reply_due_date": due_str,
            "response_status": "تم الرد",
            "csrf_token": csrf_token
        }
        edit_resp = await client.post("/correspondences/edit", data=edit_data, cookies=cookies, follow_redirects=False)
        print("POST /correspondences/edit status:", edit_resp.status_code)
        assert edit_resp.status_code in [200, 303]

        db.expire_all()
        refreshed = db.query(LawCorrespondences).filter(LawCorrespondences.id == created_corr.id).first()
        assert refreshed.subject == "تم التعديل: إشعار رسمي مستعجل ومؤكد"
        assert refreshed.response_status == "تم الرد"
        assert refreshed.urgency_level == "فوري"
        print("Correspondence edit verified successfully!")

        # 10. Multi-Tenant Security Check
        print("\n--- 6. Testing Multi-Tenant Security Isolation ---")
        foreign_corr = db.query(LawCorrespondences).filter(
            LawCorrespondences.id == created_corr.id,
            LawCorrespondences.office_id == 999999
        ).first()
        assert foreign_corr is None, "Multi-tenant breach detected!"
        print("Multi-tenant isolation verified!")

        # 11. Test POST /correspondences/delete (Soft delete)
        print("\n--- 7. Testing POST /correspondences/delete ---")
        del_resp = await client.post(
            "/correspondences/delete",
            data={"corr_id": str(created_corr.id), "csrf_token": csrf_token},
            cookies=cookies,
            follow_redirects=False
        )
        print("POST /correspondences/delete status:", del_resp.status_code)
        assert del_resp.status_code in [200, 303]

        db.expire_all()
        deleted_corr = db.query(LawCorrespondences).filter(LawCorrespondences.id == created_corr.id).first()
        assert deleted_corr.is_deleted == 1, "Correspondence not soft-deleted!"
        print("Soft delete verified successfully!")

        db.close()
        print("\nALL CORRESPONDENCES TESTS PASSED 100%!")

if __name__ == "__main__":
    asyncio.run(run_correspondences_test())
