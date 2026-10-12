import asyncio
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from httpx import AsyncClient, ASGITransport
from main import app
from database.database import SessionLocal
from database.models import AccessProfiles, LawOffices, LawCases, LawHearings

async def test_timeline_flow():
    db = SessionLocal()
    try:
        user1 = db.query(AccessProfiles).filter(AccessProfiles.username == "R1990").first()
        assert user1 is not None, "R1990 user must exist"
        case1 = db.query(LawCases).filter(LawCases.office_id == user1.office_id, LawCases.is_deleted == 0).first()
        if not case1:
            case1 = LawCases(office_id=user1.office_id, case_number="CASE-TL-101", title="قضية اختبار الخط الزمني", status_key="active")
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

        # 1. Test GET /timeline
        print("\n--- 1. Testing GET /timeline ---")
        res = await client.get("/timeline", cookies=cookies)
        assert res.status_code == 200
        assert "الخط الزمني" in res.text
        print("GET /timeline status: 200")

        # 2. Test GET /timeline with case_id filter
        print("\n--- 2. Testing GET /timeline?case_id={id} ---")
        res_case = await client.get(f"/timeline?case_id={case1.id}", cookies=cookies)
        assert res_case.status_code == 200
        print(f"GET /timeline?case_id={case1.id} status: 200")

        # 3. Test GET /api/timeline
        print("\n--- 3. Testing GET /api/timeline ---")
        api_res = await client.get("/api/timeline", cookies=cookies)
        assert api_res.status_code == 200
        api_json = api_res.json()
        assert api_json["ok"] is True
        print(f"Loaded {api_json['count']} timeline API events successfully!")

        # 4. Multi-tenant isolation test
        print("\n--- 4. Testing Multi-Tenant Isolation ---")
        client2 = AsyncClient(transport=transport, base_url="http://test")
        login2 = await client2.post("/", data={"email": user2.username, "password": "password123"}, follow_redirects=False)
        cookies2 = dict(login2.cookies)
        cross_res = await client2.get(f"/api/timeline?case_id={case1.id}", cookies=cookies2)
        # Should return 0 events for a case belonging to office 1
        if cross_res.status_code == 200:
            assert cross_res.json()["count"] == 0
        else:
            assert cross_res.status_code in [401, 403, 404]
        print("Multi-tenant isolation verified!")

        print("\nALL TIMELINE TESTS PASSED 100%!")

if __name__ == "__main__":
    asyncio.run(test_timeline_flow())
