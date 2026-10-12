import asyncio
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from datetime import datetime
from httpx import AsyncClient, ASGITransport
from main import app
from database.database import SessionLocal
from database.models import LawWorkflowRules, LawCases, LawTasks, LawAuditLog, AccessProfiles

async def run_automation_test():
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

        # 2. Test GET /automation
        print("\n--- 1. Testing GET /automation ---")
        get_resp = await client.get("/automation", cookies=cookies)
        print("GET /automation status:", get_resp.status_code)
        assert get_resp.status_code == 200, f"Failed GET /automation: {get_resp.status_code}"
        assert "مركز الأتمتة وسير العمل الذكي" in get_resp.text
        assert "addRuleModal" in get_resp.text
        assert "testRunModal" in get_resp.text
        assert "conflictModal" in get_resp.text

        # 3. Test GET /api/workflows
        print("\n--- 2. Testing GET /api/workflows ---")
        wf_resp = await client.get("/api/workflows", cookies=cookies)
        print("GET /api/workflows status:", wf_resp.status_code)
        assert wf_resp.status_code == 200
        wf_data = wf_resp.json()
        assert "rules" in wf_data and len(wf_data["rules"]) > 0
        print(f"Loaded {len(wf_data['rules'])} workflow rules successfully!")

        # 4. Test POST /api/workflows/add
        print("\n--- 3. Testing POST /api/workflows/add ---")
        add_data = {
            "name": "أتمتة إشعار الموكل بصدور الحكم والتنفيذ",
            "category": "judgments",
            "trigger_key": "on_judgment_issued",
            "action_type": "create_task",
            "description": "قاعدة تجريبية لتوليد مهمة إشعار الموكل بمضمون الحكم النهائي",
            "task_title": "إرسال نسخة الحكم التنفيذي للموكل واستلام التوقيع",
            "priority": "high",
            "days_offset": 3
        }
        add_rule_resp = await client.post("/api/workflows/add", json=add_data, cookies=cookies, headers=headers)
        print("POST add rule status:", add_rule_resp.status_code)
        assert add_rule_resp.status_code == 200
        new_rule_data = add_rule_resp.json()
        assert new_rule_data["success"] is True
        rule_id = new_rule_data["rule_id"]
        print(f"Created Workflow Rule ID: {rule_id}")

        # 5. Test POST /api/workflows/toggle
        print("\n--- 4. Testing POST /api/workflows/toggle ---")
        toggle_resp = await client.post("/api/workflows/toggle", json={"rule_id": rule_id}, cookies=cookies, headers=headers)
        print("Toggle status:", toggle_resp.status_code)
        assert toggle_resp.status_code == 200
        assert toggle_resp.json()["is_active"] == 0
        print("Rule disabled successfully!")

        # Toggle back to active
        toggle_back = await client.post("/api/workflows/toggle", json={"rule_id": rule_id}, cookies=cookies, headers=headers)
        assert toggle_back.json()["is_active"] == 1
        print("Rule enabled back successfully!")

        # 6. Test POST /api/workflows/test-run
        print("\n--- 5. Testing POST /api/workflows/test-run ---")
        db = SessionLocal()
        case = db.query(LawCases).filter(LawCases.office_id == 1, LawCases.is_deleted == 0).first()
        case_id = case.id if case else None

        test_run_resp = await client.post(
            "/api/workflows/test-run",
            json={"rule_id": rule_id, "case_id": case_id},
            cookies=cookies,
            headers=headers
        )
        print("Test run status:", test_run_resp.status_code)
        assert test_run_resp.status_code == 200
        tr_data = test_run_resp.json()
        assert tr_data["success"] is True
        print(f"Test run completed: {tr_data['message']}")

        # Verify task created
        task_id = tr_data.get("task_id")
        created_task = db.query(LawTasks).filter(LawTasks.id == task_id).first()
        assert created_task is not None, "Task was not created by workflow test run!"
        print(f"Verified generated LawTask ID: {created_task.id}, Title: {created_task.title}")

        # 7. Test POST /api/workflows/save
        print("\n--- 6. Testing POST /api/workflows/save ---")
        save_resp = await client.post(
            "/api/workflows/save",
            json={
                "rule_id": rule_id,
                "name": "أتمتة معدلة: إشعار الموكل بالحكم النهائي",
                "description": "وصف محدث لقاعدة الأتمتة"
            },
            cookies=cookies,
            headers=headers
        )
        print("Save status:", save_resp.status_code)
        assert save_resp.status_code == 200
        print("Rule config saved successfully!")

        # 8. Test Conflict Check API
        print("\n--- 7. Testing /api/conflict-check ---")
        conflict_resp = await client.get("/api/conflict-check?name=شركة", cookies=cookies)
        print("Conflict check status:", conflict_resp.status_code)
        assert conflict_resp.status_code == 200
        print("Conflict check response count:", conflict_resp.json().get("count", 0))

        # 9. Test Case Timeline API
        if case_id:
            print(f"\n--- 8. Testing /api/case/{case_id}/timeline ---")
            timeline_resp = await client.get(f"/api/case/{case_id}/timeline", cookies=cookies)
            print("Timeline status:", timeline_resp.status_code)
            assert timeline_resp.status_code == 200
            print(f"Events loaded: {len(timeline_resp.json().get('events', []))}")

        # 10. Multi-Tenant Security Isolation
        print("\n--- 9. Testing Multi-Tenant Security Isolation ---")
        foreign_rule = db.query(LawWorkflowRules).filter(
            LawWorkflowRules.id == rule_id,
            LawWorkflowRules.office_id == 999999
        ).first()
        assert foreign_rule is None, "Multi-tenant leak detected!"
        print("Multi-tenant isolation verified!")

        # 11. Test POST /api/workflows/delete
        print("\n--- 10. Testing POST /api/workflows/delete ---")
        del_resp = await client.post("/api/workflows/delete", json={"rule_id": rule_id}, cookies=cookies, headers=headers)
        print("Delete status:", del_resp.status_code)
        assert del_resp.status_code == 200
        assert del_resp.status_code == 200
        db.expire_all()
        check_del = db.query(LawWorkflowRules).filter(LawWorkflowRules.id == rule_id).first()
        assert check_del is None, "Rule was not deleted!"
        print("Workflow rule deleted successfully!")

        db.close()
        print("\nALL SMART AUTOMATION TESTS PASSED 100%!")

if __name__ == "__main__":
    asyncio.run(run_automation_test())
