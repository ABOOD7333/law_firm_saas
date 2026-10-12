import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from httpx import AsyncClient, ASGITransport
from main import app
from database.database import SessionLocal, engine
from database.models import AccessProfiles, LawCases, LawExpenses
from sqlalchemy import text

async def test_expenses_full_suite():
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM rate_limit_attempts"))

    db = SessionLocal()
    try:
        user1 = db.query(AccessProfiles).filter(AccessProfiles.username == "R1990").first()
        assert user1 is not None, "R1990 user must exist"
        case1 = db.query(LawCases).filter(LawCases.office_id == user1.office_id, LawCases.is_deleted == 0).first()
        if not case1:
            case1 = LawCases(office_id=user1.office_id, case_number="CASE-EXP-101", title="قضية اختبار المصاريف", status_key="active")
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

        # 2. Get Expenses page
        page_res = await client.get("/expenses", cookies=cookies)
        assert page_res.status_code == 200
        assert "مصاريف القضية" in page_res.text
        assert "إجمالي المصروفات" in page_res.text

        # 3. Create an Expense
        payload = {
            "case_id": case_id,
            "title": "رسوم قيد دعوى لدى المحكمة العامة بالرياض",
            "expense_category": "رسوم قضائية",
            "payment_method": "سداد حكومي",
            "amount": 1250.0,
            "currency": "SAR",
            "expense_at": "2026-10-12",
            "is_billable": 1,
            "notes": "سداد عبر منصة ناجز"
        }
        create_res = await client.post("/api/expenses/save", json=payload, cookies=cookies, headers=headers)
        assert create_res.status_code == 200
        create_data = create_res.json()
        assert create_data["ok"] is True
        exp_id = create_data["id"]

        # 4. Get Expense details via API
        get_res = await client.get(f"/api/expenses/{exp_id}", cookies=cookies)
        assert get_res.status_code == 200
        get_data = get_res.json()
        assert get_data["ok"] is True
        assert get_data["data"]["title"] == "رسوم قيد دعوى لدى المحكمة العامة بالرياض"
        assert get_data["data"]["amount"] == 1250.0
        assert get_data["data"]["is_billable"] == 1

        # 5. Edit Expense
        payload["id"] = exp_id
        payload["amount"] = 1500.0
        edit_res = await client.post("/api/expenses/save", json=payload, cookies=cookies, headers=headers)
        assert edit_res.status_code == 200
        assert edit_res.json()["ok"] is True

        # 6. Test Multi-Tenant Isolation (User 2 cannot access user 1's expense)
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM rate_limit_attempts"))
        client2 = AsyncClient(transport=transport, base_url="http://test")
        login2 = await client2.post("/", data={"email": user2.username, "password": "password123"}, follow_redirects=False)
        cookies2 = dict(login2.cookies)
        cross_res = await client2.get(f"/api/expenses/{exp_id}", cookies=cookies2)
        assert cross_res.status_code in [404, 403, 401, 303]

        # 7. Delete Expense (Soft delete)
        del_res = await client.delete(f"/api/expenses/delete/{exp_id}", cookies=cookies, headers=headers)
        assert del_res.status_code == 200
        assert del_res.json()["ok"] is True

        # Verify soft deleted in DB
        db = SessionLocal()
        try:
            del_exp = db.query(LawExpenses).filter(LawExpenses.id == exp_id).first()
            assert del_exp.is_deleted == 1
        finally:
            db.close()

        print("\nAll Expenses Tests (including Multi-Tenant Isolation) PASSED 100%!")

if __name__ == "__main__":
    asyncio.run(test_expenses_full_suite())
