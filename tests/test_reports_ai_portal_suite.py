import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from httpx import AsyncClient, ASGITransport
from main import app
from database.database import SessionLocal, engine
from database.models import AccessProfiles, LawCases, LawClients
from sqlalchemy import text

async def test_reports_portal_suite():
    # 0. Clear rate limit attempts
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM rate_limit_attempts"))

    db = SessionLocal()
    try:
        user1 = db.query(AccessProfiles).filter(AccessProfiles.username == "R1990").first()
        assert user1 is not None, "R1990 must exist"

        user2 = db.query(AccessProfiles).filter(AccessProfiles.office_id != user1.office_id).first()
        assert user2 is not None, "User 2 from different office must exist"

        office1_id = user1.office_id
        office2_id = user2.office_id
    finally:
        db.close()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Login user 1
        login1 = await client.post("/", data={"email": "R1990", "password": "admin123456"}, follow_redirects=False)
        assert login1.status_code == 303, f"Login 1 failed: {login1.status_code}"
        cookies1 = dict(login1.cookies)
        csrf1 = cookies1.get("csrf_token") or "test_csrf1"
        headers1 = {"X-CSRF-Token": csrf1}

        # -------------------------------------------------------------
        # Part 1: التقارير (/reports & /api/reports/summary)
        # -------------------------------------------------------------
        for period in ["all", "month", "quarter", "year"]:
            r_rep = await client.get(f"/reports?period={period}", cookies=cookies1)
            assert r_rep.status_code == 200, f"Reports failed for period {period}"
            assert "التقارير والإحصائيات الشاملة" in r_rep.text

        r_summary = await client.get("/api/reports/summary?period=month", cookies=cookies1)
        assert r_summary.status_code == 200
        sum_data = r_summary.json()
        assert sum_data.get("success") is True
        assert sum_data.get("office_id") == office1_id

        # -------------------------------------------------------------
        # Part 2: بوابة الموكل (/client-portal/*)
        # -------------------------------------------------------------
        routes = [
            "/client-portal",
            "/client-portal/cases",
            "/client-portal/hearings",
            "/client-portal/finance",
            "/client-portal/documents"
        ]
        for route in routes:
            r_cp = await client.get(route, cookies=cookies1)
            assert r_cp.status_code == 200, f"Client portal route {route} failed: {r_cp.status_code}"
            assert "بوابة الموكلين" in r_cp.text or "LawSaaS VIP" in r_cp.text

        # -------------------------------------------------------------
        # Part 3: Multi-Tenant Cross-Office Isolation
        # -------------------------------------------------------------
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM rate_limit_attempts"))

        login2 = await client.post("/", data={"email": user2.username, "password": "admin123456"}, follow_redirects=False)
        assert login2.status_code == 303, f"Login 2 failed: {login2.status_code}"
        cookies2 = dict(login2.cookies)

        # User 2 reports summary must only reflect office 2
        r_summary2 = await client.get("/api/reports/summary", cookies=cookies2)
        assert r_summary2.status_code == 200
        assert r_summary2.json().get("office_id") == office2_id

        # User 2 client portal must only reflect office 2
        r_cp2 = await client.get("/client-portal", cookies=cookies2)
        assert r_cp2.status_code == 200

    print("ALL REPORTS AND CLIENT-PORTAL CHECKS PASSED!")

if __name__ == "__main__":
    asyncio.run(test_reports_portal_suite())
