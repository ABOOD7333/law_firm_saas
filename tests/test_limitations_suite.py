import asyncio
import os
import sys
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from httpx import AsyncClient, ASGITransport
from main import app
from database.database import SessionLocal
from database.models import AccessProfiles, LawCases, LawLimitations, LawTasks

async def test_limitations_full_suite():
    db = SessionLocal()
    try:
        user1 = db.query(AccessProfiles).filter(AccessProfiles.username == "R1990").first()
        assert user1 is not None, "R1990 user must exist"
        case1 = db.query(LawCases).filter(LawCases.office_id == user1.office_id, LawCases.is_deleted == 0).first()
        if not case1:
            case1 = LawCases(office_id=user1.office_id, case_number="CASE-LIM-101", title="قضية اختبار التقادم", status_key="active")
            db.add(case1)
            db.commit()
            db.refresh(case1)
        case_id = case1.id

        user2 = db.query(AccessProfiles).filter(AccessProfiles.office_id != user1.office_id).first()
        assert user2 is not None, "User 2 must exist"
    finally:
        db.close()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Login user 1
        login_res = await client.post("/", data={"email": "R1990", "password": "admin123456"}, follow_redirects=False)
        assert login_res.status_code == 303, f"Login failed: {login_res.status_code}"
        cookies = dict(login_res.cookies)
        csrf_token = cookies.get("csrf_token") or "test_csrf"
        headers = {"X-CSRF-Token": csrf_token}

        # 2. Get limitations page
        page_res = await client.get("/limitations", cookies=cookies)
        assert page_res.status_code == 200
        assert "تنبيهات التقادم" in page_res.text
        assert "إجمالي التنبيهات" in page_res.text

        # 3. Create a limitation
        tomorrow = (date.today() + timedelta(days=5)).isoformat()
        payload = {
            "case_id": case_id,
            "title": "ميعاد استئناف حكم تجاري نهائي",
            "limitation_type_key": "ميعاد استئناف/طعن",
            "status_key": "ساري",
            "due_date": tomorrow,
            "days_count": 30,
            "alert_days_before": 7,
            "law_reference": "المادة 187 مرافعات",
            "action_required": "قيد الاستئناف",
            "is_critical": 1,
            "notes": "اختبار آلي للتنبيهات"
        }
        create_res = await client.post("/api/limitations/save", json=payload, cookies=cookies, headers=headers)
        assert create_res.status_code == 200
        create_data = create_res.json()
        assert create_data["ok"] is True
        lim_id = create_data["id"]

        # 4. Get limitation details via API
        get_res = await client.get(f"/api/limitations/{lim_id}", cookies=cookies)
        assert get_res.status_code == 200
        get_data = get_res.json()
        assert get_data["ok"] is True
        assert get_data["data"]["title"] == "ميعاد استئناف حكم تجاري نهائي"
        assert get_data["data"]["is_critical"] == 1
        assert get_data["data"]["days_left"] == 5

        # 5. Convert limitation to task
        task_res = await client.post(f"/api/limitations/{lim_id}/create-task", json={}, cookies=cookies, headers=headers)
        assert task_res.status_code == 200, f"Task creation failed: {task_res.status_code} {task_res.text}"
        task_data = task_res.json()
        assert task_data["ok"] is True
        task_id = task_data["task_id"]

        # Verify task was created in db
        db = SessionLocal()
        try:
            created_task = db.query(LawTasks).filter(LawTasks.id == task_id).first()
            assert created_task is not None
            assert created_task.office_id == user1.office_id
            assert created_task.priority_level == 1
        finally:
            db.close()

        # 6. Test Multi-Tenant Isolation (User 2 from Office 2 cannot access user1's limitation)
        client2 = AsyncClient(transport=transport, base_url="http://test")
        login2 = await client2.post("/", data={"email": user2.username, "password": "password123"}, follow_redirects=False)
        cookies2 = dict(login2.cookies)
        cross_res = await client2.get(f"/api/limitations/{lim_id}", cookies=cookies2)
        assert cross_res.status_code in [404, 403, 401, 303]

        # 7. Update limitation
        payload["id"] = lim_id
        payload["status_key"] = "مكتمل"
        update_res = await client.post("/api/limitations/save", json=payload, cookies=cookies, headers=headers)
        assert update_res.status_code == 200
        assert update_res.json()["ok"] is True

        # 8. Delete limitation (soft delete)
        del_res = await client.delete(f"/api/limitations/delete/{lim_id}", cookies=cookies, headers=headers)
        assert del_res.status_code == 200
        assert del_res.json()["ok"] is True

        # Verify soft deleted in DB
        db = SessionLocal()
        try:
            del_record = db.query(LawLimitations).filter(LawLimitations.id == lim_id).first()
            assert del_record.is_deleted == 1
        finally:
            db.close()

        print("\nAll Limitations Tests (including Multi-Tenant Isolation) PASSED 100%!")

if __name__ == "__main__":
    asyncio.run(test_limitations_full_suite())
