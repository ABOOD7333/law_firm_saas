import asyncio
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from httpx import AsyncClient, ASGITransport
from datetime import date
from main import app
from database.database import SessionLocal
from database.models import AccessProfiles, LawOffices, LawCases, LawExecutions

async def test_executions_flow():
    db = SessionLocal()
    try:
        user1 = db.query(AccessProfiles).filter(AccessProfiles.username == "R1990").first()
        assert user1 is not None, "R1990 user must exist"
        case1 = db.query(LawCases).filter(LawCases.office_id == user1.office_id, LawCases.is_deleted == 0).first()
        if not case1:
            case1 = LawCases(office_id=user1.office_id, case_number="CASE-EXEC-101", title="قضية اختبار التنفيذ", status_key="active")
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

        # 1. Test GET /execution
        print("\n--- 1. Testing GET /execution ---")
        res = await client.get("/execution", cookies=cookies)
        assert res.status_code == 200
        assert "إجراءات ومحاكم التنفيذ" in res.text
        assert "المبالغ المحصلة" in res.text
        print("GET /execution status: 200")

        # 2. Test POST /api/executions/save (Add)
        print("\n--- 2. Testing POST /api/executions/save (Add) ---")
        save_data = {
            "case_id": case1.id,
            "execution_number": f"EXEC-{date.today().year}-9999",
            "execution_type": "financial",
            "debtor_name": "شركة الوفاق للاستثمار والتطوير",
            "authority_name": "محكمة التنفيذ بالرياض - الدائرة 12",
            "claimed_amount": 150000.0,
            "collected_amount": 50000.0,
            "decision_number": "قرار 46 حجز وتنفيذ",
            "decision_date": str(date.today()),
            "status_key": "جاري التنفيذ",
            "request_date": str(date.today()),
            "notes": "تم إصدار قرار 46 بحجز الحسابات البنكية للمنفذ ضده",
            "create_task": True
        }
        add_res = await client.post(
            "/api/executions/save",
            json=save_data,
            cookies=cookies,
            headers={**headers, "Content-Type": "application/json"}
        )
        assert add_res.status_code == 200
        add_json = add_res.json()
        assert add_json["ok"] is True
        created_exec_id = add_json["id"]
        print(f"Created Execution ID: {created_exec_id}")

        # 3. Test GET /api/executions/{id}
        print("\n--- 3. Testing GET /api/executions/{id} ---")
        get_res = await client.get(f"/api/executions/{created_exec_id}", cookies=cookies)
        assert get_res.status_code == 200
        g_json = get_res.json()
        assert g_json["ok"] is True
        assert g_json["debtor_name"] == "شركة الوفاق للاستثمار والتطوير"
        assert g_json["claimed_amount"] == 150000.0
        assert g_json["collected_amount"] == 50000.0
        print("Execution details API verified successfully!")

        # 4. Test POST /api/executions/save (Edit)
        print("\n--- 4. Testing POST /api/executions/save (Edit) ---")
        edit_data = {
            "id": created_exec_id,
            "case_id": case1.id,
            "execution_number": f"EXEC-{date.today().year}-9999",
            "execution_type": "financial",
            "debtor_name": "شركة الوفاق للاستثمار والتطوير",
            "authority_name": "محكمة التنفيذ بالرياض - الدائرة 12",
            "claimed_amount": 150000.0,
            "collected_amount": 150000.0,
            "decision_number": "قرار 46 منتهي بالتحصيل",
            "decision_date": str(date.today()),
            "status_key": "تم التنفيذ",
            "request_date": str(date.today()),
            "notes": "تم تحصيل كامل المبلغ وتحويله للموكل"
        }
        edit_res = await client.post(
            "/api/executions/save",
            json=edit_data,
            cookies=cookies,
            headers={**headers, "Content-Type": "application/json"}
        )
        assert edit_res.status_code == 200
        print("Execution edited successfully!")

        # 5. Test Multi-Tenant Isolation
        print("\n--- 5. Testing Multi-Tenant Isolation ---")
        client2 = AsyncClient(transport=transport, base_url="http://test")
        login2 = await client2.post("/", data={"email": user2.username, "password": "password123"}, follow_redirects=False)
        cookies2 = dict(login2.cookies)
        cross_res = await client2.get(f"/api/executions/{created_exec_id}", cookies=cookies2)
        assert cross_res.status_code in [404, 403, 401, 303]
        print("Multi-tenant isolation verified!")

        # 6. Test DELETE /api/executions/delete/{id}
        print("\n--- 6. Testing DELETE /api/executions/delete/{id} ---")
        del_res = await client.delete(
            f"/api/executions/delete/{created_exec_id}",
            cookies=cookies,
            headers=headers
        )
        assert del_res.status_code == 200
        # Verify it's soft deleted
        check_del = await client.get(f"/api/executions/{created_exec_id}", cookies=cookies)
        assert check_del.status_code == 404
        print("Soft delete verified successfully!")

        print("\nALL EXECUTIONS TESTS PASSED 100%!")

if __name__ == "__main__":
    asyncio.run(test_executions_flow())
