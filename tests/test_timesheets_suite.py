import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from httpx import AsyncClient, ASGITransport
from main import app
from database.database import SessionLocal, engine
from database.models import AccessProfiles, LawCases, LawTimesheets
from sqlalchemy import text

async def test_timesheets_full_suite():
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM rate_limit_attempts"))

    db = SessionLocal()
    try:
        user1 = db.query(AccessProfiles).filter(AccessProfiles.username == "R1990").first()
        assert user1 is not None, "R1990 user must exist"
        case1 = db.query(LawCases).filter(LawCases.office_id == user1.office_id, LawCases.is_deleted == 0).first()
        if not case1:
            case1 = LawCases(office_id=user1.office_id, case_number="CASE-TS-101", title="قضية اختبار الساعات", status_key="active")
            db.add(case1)
            db.commit()
            db.refresh(case1)

        user2 = db.query(AccessProfiles).filter(AccessProfiles.office_id != user1.office_id).first()
        assert user2 is not None, "User 2 must exist"
        case_id = case1.id
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

        # 2. Get Timesheet page
        page_res = await client.get("/timesheet", cookies=cookies)
        assert page_res.status_code == 200
        assert "سجل الساعات" in page_res.text
        assert "إجمالي الساعات" in page_res.text

        # 3. Create a Timesheet record
        payload = {
            "case_id": case_id,
            "title": "دراسة ملف القضية وإعداد التقرير المالي والقانوني",
            "user_id": user1.id,
            "duration_hours": 3.5,
            "billable_rate": 600.0,
            "work_date": "2026-10-12",
            "is_billed": 0,
            "notes": "جلسة عمل مشتركة مع المستشار القانوني"
        }
        create_res = await client.post("/api/timesheets/save", json=payload, cookies=cookies, headers=headers)
        assert create_res.status_code == 200
        create_data = create_res.json()
        assert create_data["ok"] is True
        ts_id = create_data["id"]

        # 4. Get Timesheet details
        get_res = await client.get(f"/api/timesheets/{ts_id}", cookies=cookies)
        assert get_res.status_code == 200
        get_data = get_res.json()
        assert get_data["ok"] is True
        assert get_data["data"]["title"] == "دراسة ملف القضية وإعداد التقرير المالي والقانوني"
        assert get_data["data"]["duration_hours"] == 3.5
        assert get_data["data"]["billable_rate"] == 600.0

        # 5. Toggle Billed status
        toggle_res = await client.post(f"/api/timesheets/{ts_id}/toggle-billed", cookies=cookies, headers=headers)
        assert toggle_res.status_code == 200
        toggle_data = toggle_res.json()
        assert toggle_data["ok"] is True
        assert toggle_data["is_billed"] == 1

        # 6. Edit Timesheet
        payload["id"] = ts_id
        payload["duration_hours"] = 4.0
        edit_res = await client.post("/api/timesheets/save", json=payload, cookies=cookies, headers=headers)
        assert edit_res.status_code == 200
        assert edit_res.json()["ok"] is True

        # 7. Test Multi-Tenant Isolation (User 2 cannot access user 1's timesheet)
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM rate_limit_attempts"))
        client2 = AsyncClient(transport=transport, base_url="http://test")
        login2 = await client2.post("/", data={"email": user2.username, "password": "password123"}, follow_redirects=False)
        cookies2 = dict(login2.cookies)
        cross_res = await client2.get(f"/api/timesheets/{ts_id}", cookies=cookies2)
        assert cross_res.status_code in [404, 403, 401, 303]

        # 8. Delete Timesheet (Soft delete)
        del_res = await client.delete(f"/api/timesheets/delete/{ts_id}", cookies=cookies, headers=headers)
        assert del_res.status_code == 200
        assert del_res.json()["ok"] is True

        # Verify soft deleted in DB
        db = SessionLocal()
        try:
            del_ts = db.query(LawTimesheets).filter(LawTimesheets.id == ts_id).first()
            assert del_ts.is_deleted == 1
        finally:
            db.close()

        print("\nAll Timesheets Tests (including Multi-Tenant Isolation) PASSED 100%!")

if __name__ == "__main__":
    asyncio.run(test_timesheets_full_suite())
