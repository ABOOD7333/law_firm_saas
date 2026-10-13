import asyncio
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from httpx import AsyncClient, ASGITransport
from main import app
from database.database import SessionLocal
from database.models import LawPleadings, LawCases

async def run_pleadings_test():
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
        headers = {"X-CSRF-Token": csrf_token}

        # 2. Test GET /pleadings
        print("\n--- Testing GET /pleadings ---")
        get_resp = await client.get("/pleadings", cookies=cookies)
        print("GET /pleadings status:", get_resp.status_code)
        assert get_resp.status_code == 200, f"Failed GET /pleadings: {get_resp.status_code}"
        assert "المرافعات والمذكرات القانونية" in get_resp.text
        assert "addPleadingModal" in get_resp.text
        assert "editPleadingModal" in get_resp.text

        # 3. Get existing case id
        db = SessionLocal()
        case = db.query(LawCases).filter(LawCases.office_id == 1, LawCases.is_deleted == 0).first()
        assert case is not None, "No active case found in office 1"
        case_id = case.id
        print(f"Target Case ID: {case_id} ({case.title})")

        # 4. Test POST /pleadings/add
        print("\n--- Testing POST /pleadings/add ---")
        add_data = {
            "case_id": str(case_id),
            "title": "مذكرة دفاع جوابية اختبارية رصينة",
            "pleading_type_key": "defense",
            "content_html": "بسم الله الرحمن الرحيم\nلدى المحكمة التجارية بالرياض\nالوقائع والأسانيد والطلبات...",
            "issue_date": "2026-10-15",
            "status_key": "draft",
            "redirect_to": "/pleadings"
        }
        add_resp = await client.post("/pleadings/add", data=add_data, cookies=cookies, headers=headers)
        print("POST /pleadings/add status:", add_resp.status_code)
        assert add_resp.status_code == 303, f"Unexpected add status {add_resp.status_code}"
        assert add_resp.headers.get("location") == "/pleadings"

        created_pleading = db.query(LawPleadings).filter(
            LawPleadings.title == "مذكرة دفاع جوابية اختبارية رصينة",
            LawPleadings.is_deleted == 0
        ).first()
        assert created_pleading is not None, "Pleading was not saved in DB"
        pleading_id = created_pleading.id
        print(f"Created Pleading ID: {pleading_id}")

        # 5. Test GET /api/pleadings/{pleading_id}
        print("\n--- Testing GET /api/pleadings/{id} ---")
        api_resp = await client.get(f"/api/pleadings/{pleading_id}", cookies=cookies)
        print("GET /api/pleadings status:", api_resp.status_code)
        assert api_resp.status_code == 200
        p_json = api_resp.json()
        print("API Pleading title:", p_json.get("title"))
        assert p_json.get("title") == "مذكرة دفاع جوابية اختبارية رصينة"

        # 6. Test POST /pleadings/edit
        print("\n--- Testing POST /pleadings/edit ---")
        edit_data = {
            "pleading_id": str(pleading_id),
            "case_id": str(case_id),
            "title": "مذكرة دفاع جوابية (نسخة معدلة نهائية)",
            "pleading_type_key": "defense",
            "content_html": "نص المذكرة بعد المراجعة والاعتماد النهائي...",
            "issue_date": "2026-10-16",
            "status_key": "final",
            "redirect_to": "/pleadings"
        }
        edit_resp = await client.post("/pleadings/edit", data=edit_data, cookies=cookies, headers=headers)
        print("POST /pleadings/edit status:", edit_resp.status_code)
        assert edit_resp.status_code == 303

        # 7. Test GET /pleadings/{id}/print
        print("\n--- Testing GET /pleadings/{id}/print ---")
        print_resp = await client.get(f"/pleadings/{pleading_id}/print", cookies=cookies)
        print("Print page status:", print_resp.status_code)
        assert print_resp.status_code == 200
        assert "مذكرة دفاع جوابية (نسخة معدلة نهائية)" in print_resp.text
        assert "window.print()" in print_resp.text

        # 9. Test POST /pleadings/delete
        print("\n--- Testing POST /pleadings/delete ---")
        del_data = {
            "pleading_id": str(pleading_id),
            "redirect_to": "/pleadings"
        }
        del_resp = await client.post("/pleadings/delete", data=del_data, cookies=cookies, headers=headers)
        print("POST /pleadings/delete status:", del_resp.status_code)
        assert del_resp.status_code == 303

        # Verify soft deleted
        db.close()
        db = SessionLocal()
        p_check = db.query(LawPleadings).filter(LawPleadings.id == pleading_id).first()
        assert p_check.is_deleted == 1, "Pleading was not soft-deleted"
        print("Pleading successfully soft-deleted (is_deleted=1)")

        db.close()
        print("\n=======================================================")
        print("ALL PLEADINGS ENDPOINTS & WORKFLOWS PASSED WITH 100% SUCCESS!")
        print("=======================================================")

if __name__ == "__main__":
    asyncio.run(run_pleadings_test())
