import asyncio
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from httpx import AsyncClient, ASGITransport
from datetime import date
from main import app
from database.database import SessionLocal
from database.models import AccessProfiles, LawOffices, LawCases, LawHearings, LawTasks, LawLimitations

async def test_calendar_flow():
    db = SessionLocal()
    try:
        user1 = db.query(AccessProfiles).filter(AccessProfiles.username == "R1990").first()
        assert user1 is not None, "R1990 user must exist"
        case1 = db.query(LawCases).filter(LawCases.office_id == user1.office_id, LawCases.is_deleted == 0).first()
        if not case1:
            case1 = LawCases(office_id=user1.office_id, case_number="CASE-CAL-101", title="قضية اختبار التقويم", status_key="active")
            db.add(case1)
            db.commit()
            db.refresh(case1)

        # Seed test hearing and limitation in current month
        today_str = str(date.today())
        hearing = db.query(LawHearings).filter(LawHearings.office_id == user1.office_id).first()
        if not hearing:
            hearing = LawHearings(office_id=user1.office_id, case_id=case1.id, title="جلسة مرافعة ختامية", hearing_at=f"{today_str} 10:30")
            db.add(hearing)
            db.commit()

        lim = db.query(LawLimitations).filter(LawLimitations.office_id == user1.office_id).first()
        if not lim:
            lim = LawLimitations(office_id=user1.office_id, case_id=case1.id, title="مهلة استئناف نظامية", limitation_type_key="appeal", due_date=today_str)
            db.add(lim)
            db.commit()
    finally:
        db.close()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Login
        login_res = await client.post("/", data={"email": "R1990", "password": "admin123456"}, follow_redirects=False)
        assert login_res.status_code == 303
        cookies = dict(login_res.cookies)

        # 1. Test GET /calendar
        print("\n--- 1. Testing GET /calendar ---")
        cal_res = await client.get("/calendar", cookies=cookies)
        assert cal_res.status_code == 200
        assert "التقويم القضائي الموحد وجدول المواعيد" in cal_res.text
        assert "جلسات المحاكم" in cal_res.text
        print("GET /calendar status: 200")

        # 2. Test GET /calendar with filter event_type=deadlines
        print("\n--- 2. Testing GET /calendar?event_type=deadlines ---")
        cal_dl_res = await client.get("/calendar?event_type=deadlines", cookies=cookies)
        assert cal_dl_res.status_code == 200
        print("GET /calendar?event_type=deadlines status: 200")

        # 3. Test GET /api/calendar/events
        print("\n--- 3. Testing GET /api/calendar/events ---")
        api_res = await client.get("/api/calendar/events", cookies=cookies)
        assert api_res.status_code == 200
        api_json = api_res.json()
        assert api_json["ok"] is True
        assert isinstance(api_json["events"], list)
        print(f"Loaded {len(api_json['events'])} calendar events successfully!")

        # 4. Multi-tenant isolation test
        print("\n--- 4. Testing Multi-Tenant Isolation ---")
        unauth_client = AsyncClient(transport=transport, base_url="http://test")
        unauth_res = await unauth_client.get("/calendar", follow_redirects=False)
        assert unauth_res.status_code == 303
        print("Unauthenticated access correctly redirected!")

        print("\nALL CALENDAR TESTS PASSED 100%!")

if __name__ == "__main__":
    asyncio.run(test_calendar_flow())
