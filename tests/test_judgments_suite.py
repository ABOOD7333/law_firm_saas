import asyncio
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from datetime import datetime, timedelta
from httpx import AsyncClient, ASGITransport
from main import app
from database.database import SessionLocal
from database.models import LawJudgments, LawCases, LawTasks, LawExecutions

async def run_judgments_test():
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

        # 2. Test GET /judgments
        print("\n--- Testing GET /judgments ---")
        get_resp = await client.get("/judgments", cookies=cookies)
        print("GET /judgments status:", get_resp.status_code)
        assert get_resp.status_code == 200, f"Failed GET /judgments: {get_resp.status_code}"
        assert "سجل الأحكام والقرارات القضائية" in get_resp.text
        assert "addJudgmentModal" in get_resp.text
        assert "editJudgmentModal" in get_resp.text
        assert "viewJudgmentModal" in get_resp.text

        # 3. Get existing case id
        db = SessionLocal()
        case = db.query(LawCases).filter(LawCases.office_id == 1, LawCases.is_deleted == 0).first()
        assert case is not None, "No active case found in office 1"
        case_id = case.id
        print(f"Target Case ID: {case_id} ({case.title})")

        # 4. Test POST /judgments/add with automated appeal task generation
        print("\n--- Testing POST /judgments/add ---")
        today_str = datetime.now().strftime("%Y-%m-%d")
        add_data = {
            "case_id": str(case_id),
            "judgment_date": today_str,
            "court_name": "المحكمة التجارية بالرياض",
            "chamber_name": "الدائرة التجارية الثالثة",
            "judge_name": "الشيخ عبدالمحسن المقرن",
            "decree_number": "45109888",
            "litigation_degree": "ابتدائي",
            "judgment_type": "موضوعي",
            "status_key": "صدر لصالحنا",
            "judgment_text": "حكمت الدائرة بإلزام المدعى عليه بأن يدفع للمدعي مبلغ 250,000 ريال وأتعاب محاماة 15,000 ريال.",
            "notification_date": today_str,
            "appeal_deadline_days": "30",
            "awarded_amount": "250000.0",
            "legal_fees_awarded": "15000.0",
            "is_final": "0",
            "generate_appeal_task": "1",
            "redirect_to": "/judgments"
        }
        add_resp = await client.post("/judgments/add", data=add_data, cookies=cookies, headers=headers)
        print("POST /judgments/add status:", add_resp.status_code)
        assert add_resp.status_code == 303
        assert add_resp.headers.get("location") == "/judgments"

        created_j = db.query(LawJudgments).filter(
            LawJudgments.decree_number == "45109888",
            LawJudgments.is_deleted == 0
        ).first()
        assert created_j is not None, "Judgment was not saved in DB"
        judgment_id = created_j.id
        print(f"Created Judgment ID: {judgment_id}, Decree: {created_j.decree_number}")

        # Verify automated deadline calculation
        expected_deadline = (datetime.strptime(today_str, "%Y-%m-%d") + timedelta(days=30)).strftime("%Y-%m-%d")
        assert created_j.appeal_deadline_date == expected_deadline, f"Expected deadline {expected_deadline}, got {created_j.appeal_deadline_date}"
        print(f"Verified Calculated Appeal Deadline: {created_j.appeal_deadline_date}")

        # Verify automated appeal task was generated
        appeal_task = db.query(LawTasks).filter(
            LawTasks.case_id == case_id,
            LawTasks.title.like("%45109888%")
        ).first()
        assert appeal_task is not None, "Automated appeal task was not generated"
        print(f"Verified Automated Appeal Task: ID={appeal_task.id}, Title='{appeal_task.title}'")

        # 5. Test GET /api/judgments/{id}
        print("\n--- Testing GET /api/judgments/{id} ---")
        api_resp = await client.get(f"/api/judgments/{judgment_id}", cookies=cookies)
        print("GET /api/judgments status:", api_resp.status_code)
        assert api_resp.status_code == 200
        j_json = api_resp.json()
        assert j_json.get("decree_number") == "45109888"
        assert j_json.get("awarded_amount") == 250000.0
        print(f"API Returned Amount: {j_json.get('awarded_amount')} SAR")

        # 6. Test POST /judgments/edit
        print("\n--- Testing POST /judgments/edit ---")
        edit_data = {
            "judgment_id": str(judgment_id),
            "case_id": str(case_id),
            "judgment_date": today_str,
            "court_name": "المحكمة التجارية بالرياض",
            "chamber_name": "الدائرة التجارية الثالثة",
            "judge_name": "الشيخ عبدالمحسن المقرن",
            "decree_number": "45109888-REV",
            "litigation_degree": "ابتدائي",
            "judgment_type": "موضوعي",
            "status_key": "صدر لصالحنا",
            "judgment_text": "حكمت الدائرة بعد التعديل بمبلغ 300,000 ريال.",
            "notification_date": today_str,
            "appeal_deadline_days": "30",
            "awarded_amount": "300000.0",
            "legal_fees_awarded": "20000.0",
            "is_final": "0",
            "redirect_to": "/judgments"
        }
        edit_resp = await client.post("/judgments/edit", data=edit_data, cookies=cookies, headers=headers)
        print("POST /judgments/edit status:", edit_resp.status_code)
        assert edit_resp.status_code == 303

        # 7. Test POST /judgments/{id}/convert-to-execution
        print("\n--- Testing POST /judgments/{id}/convert-to-execution ---")
        conv_resp = await client.post(f"/judgments/{judgment_id}/convert-to-execution", cookies=cookies, headers=headers)
        print("Convert to execution status:", conv_resp.status_code)
        assert conv_resp.status_code == 200
        conv_json = conv_resp.json()
        assert conv_json.get("success") is True
        print("Execution Created:", conv_json.get("message"))

        # Verify execution record in DB
        db.close()
        db = SessionLocal()
        created_exec = db.query(LawExecutions).filter(LawExecutions.case_id == case_id).first()
        assert created_exec is not None, "Execution record was not created"
        print(f"Verified Execution Record: ID={created_exec.id}, Number={created_exec.execution_number}")

        # 8. Test POST /judgments/delete
        print("\n--- Testing POST /judgments/delete ---")
        del_data = {
            "judgment_id": str(judgment_id),
            "redirect_to": "/judgments"
        }
        del_resp = await client.post("/judgments/delete", data=del_data, cookies=cookies, headers=headers)
        print("POST /judgments/delete status:", del_resp.status_code)
        assert del_resp.status_code == 303

        # Verify soft-deleted
        db.close()
        db = SessionLocal()
        j_check = db.query(LawJudgments).filter(LawJudgments.id == judgment_id).first()
        assert j_check.is_deleted == 1, "Judgment was not soft-deleted"
        print("Judgment successfully soft-deleted (is_deleted=1)")

        db.close()
        print("\n=======================================================")
        print("ALL JUDGMENTS ENDPOINTS & WORKFLOWS PASSED WITH 100% SUCCESS!")
        print("=======================================================")

if __name__ == "__main__":
    asyncio.run(run_judgments_test())
