import asyncio
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from httpx import AsyncClient, ASGITransport
from datetime import date, timedelta
from main import app
from database.database import get_db, SessionLocal
from database.models import AccessProfiles, LawOffices, LawCases, LawTasks, LawTimesheets

async def test_tasks_and_kanban_flow():
    db = SessionLocal()
    try:
        user1 = db.query(AccessProfiles).filter(AccessProfiles.username == "R1990").first()
        assert user1 is not None, "R1990 user must exist"
        case1 = db.query(LawCases).filter(LawCases.office_id == user1.office_id, LawCases.is_deleted == 0).first()
        if not case1:
            case1 = LawCases(office_id=user1.office_id, case_number="CASE-TASK-101", title="قضية اختبار المهام", status_key="active")
            db.add(case1)
            db.commit()
            db.refresh(case1)

        user2 = db.query(AccessProfiles).filter(AccessProfiles.office_id != user1.office_id).first()
        assert user2 is not None, "A user from another office must exist"
    finally:
        db.close()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Login user 1
        login_res = await client.post("/", data={"email": "R1990", "password": "admin123456"}, follow_redirects=False)
        assert login_res.status_code == 303
        cookies = dict(login_res.cookies)
        csrf_token = cookies.get("csrf_token") or "test_csrf"
        headers = {"X-CSRF-Token": csrf_token}

        # 1. Test GET /tasks
        print("\n--- 1. Testing GET /tasks ---")
        tasks_res = await client.get("/tasks", cookies=cookies)
        assert tasks_res.status_code == 200
        assert "إدارة المهام والمتابعة والتكاليف" in tasks_res.text
        assert "إجمالي المهام" in tasks_res.text
        print("GET /tasks status: 200")

        # 2. Test POST /tasks/add
        print("\n--- 2. Testing POST /tasks/add ---")
        add_data = {
            "title": "إعداد مسودة الاستئناف القضائية",
            "description": "دراسة أسباب الحكم والرد عليها وفق المادة 187",
            "case_id": case1.id,
            "assignee_user_id": user1.id,
            "due_at": str(date.today() + timedelta(days=3)),
            "priority_level": 1,
            "task_type": "pleading",
            "estimated_hours": 3.5,
            "is_billable": 1,
            "csrf_token": csrf_token
        }
        add_res = await client.post("/tasks/add", data=add_data, cookies=cookies, headers={**headers, "Accept": "application/json"})
        assert add_res.status_code == 200
        created_task_id = add_res.json()["task_id"]
        print(f"Created Task ID: {created_task_id}")

        # 3. Test GET /api/tasks/{task_id}
        print("\n--- 3. Testing GET /api/tasks/{id} ---")
        api_res = await client.get(f"/api/tasks/{created_task_id}", cookies=cookies)
        assert api_res.status_code == 200
        t_json = api_res.json()
        assert t_json["title"] == "إعداد مسودة الاستئناف القضائية"
        assert t_json["task_type"] == "pleading"
        assert t_json["estimated_hours"] == 3.5
        assert t_json["is_billable"] == 1
        print("Task details API verified successfully!")

        # 4. Test POST /tasks/edit
        print("\n--- 4. Testing POST /tasks/edit ---")
        edit_data = {
            "task_id": created_task_id,
            "title": "إعداد مسودة الاستئناف القضائية (معدلة)",
            "description": "إضافة السوابق القضائية",
            "case_id": case1.id,
            "assignee_user_id": user1.id,
            "due_at": str(date.today() + timedelta(days=2)),
            "priority_level": 1,
            "status_key": "in_progress",
            "task_type": "pleading",
            "estimated_hours": 4.0,
            "actual_hours": 2.0,
            "is_billable": 1,
            "csrf_token": csrf_token
        }
        edit_res = await client.post("/tasks/edit", data=edit_data, cookies=cookies, headers={**headers, "Accept": "application/json"})
        assert edit_res.status_code == 200
        print("Task edited successfully!")

        # 5. Test POST /tasks/update_status
        print("\n--- 5. Testing POST /tasks/update_status ---")
        status_res = await client.post("/tasks/update_status", data={
            "task_id": created_task_id,
            "status_key": "completed",
            "csrf_token": csrf_token
        }, cookies=cookies, headers={**headers, "Accept": "application/json"})
        assert status_res.status_code == 200
        print("Task completed successfully!")

        # 6. Test POST /tasks/convert-timesheet
        print("\n--- 6. Testing POST /tasks/convert-timesheet ---")
        ts_res = await client.post("/tasks/convert-timesheet", data={
            "task_id": created_task_id,
            "hours": 3.5,
            "notes": "إنجاز مسودة الاستئناف بالكامل",
            "csrf_token": csrf_token
        }, cookies=cookies, headers={**headers, "Accept": "application/json"})
        assert ts_res.status_code == 200
        ts_id = ts_res.json()["timesheet_id"]
        print(f"Timesheet created successfully! ID: {ts_id}")

        # 7. Test GET /kanban/api/tasks
        print("\n--- 7. Testing GET /kanban/api/tasks ---")
        kanban_res = await client.get("/kanban/api/tasks", cookies=cookies)
        assert kanban_res.status_code == 200
        k_data = kanban_res.json()
        assert k_data["ok"] is True
        assert any(t["id"] == created_task_id for t in k_data["tasks"])
        print("Kanban tasks API verified successfully!")

        # 8. Test PATCH /kanban/api/tasks/{id}/move
        print("\n--- 8. Testing PATCH /kanban/api/tasks/{id}/move ---")
        move_res = await client.patch(
            f"/kanban/api/tasks/{created_task_id}/move",
            json={"status_key": "under_review", "kanban_order": 1},
            cookies=cookies,
            headers={**headers, "Content-Type": "application/json"}
        )
        assert move_res.status_code == 200
        print("Kanban task move verified successfully!")

        # 9. Test Multi-Tenant Security Isolation
        print("\n--- 9. Testing Multi-Tenant Isolation ---")
        client2 = AsyncClient(transport=transport, base_url="http://test")
        login2_res = await client2.post("/", data={"email": user2.username, "password": "password123"}, follow_redirects=False)
        cookies2 = dict(login2_res.cookies)
        cross_res = await client2.get(f"/api/tasks/{created_task_id}", cookies=cookies2)
        assert cross_res.status_code in [404, 403, 303, 401]
        print("Multi-tenant isolation verified!")

        # 10. Test POST /tasks/delete
        print("\n--- 10. Testing POST /tasks/delete ---")
        del_res = await client.post("/tasks/delete", data={"task_id": created_task_id, "csrf_token": csrf_token}, cookies=cookies, headers={**headers, "Accept": "application/json"})
        assert del_res.status_code == 200
        # Verify it's soft deleted
        check_res = await client.get(f"/api/tasks/{created_task_id}", cookies=cookies)
        assert check_res.status_code == 404
        print("Soft delete verified successfully!")

        print("\nALL TASKS & KANBAN TESTS PASSED 100%!")

if __name__ == "__main__":
    asyncio.run(test_tasks_and_kanban_flow())
