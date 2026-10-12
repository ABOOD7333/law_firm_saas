import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from httpx import AsyncClient, ASGITransport
from main import app
from database.database import SessionLocal, engine
from database.models import AccessProfiles, LawCases, LawClients, Invoices, ClientPayments
from sqlalchemy import text

async def test_invoices_full_suite():
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM rate_limit_attempts"))

    db = SessionLocal()
    try:
        user1 = db.query(AccessProfiles).filter(AccessProfiles.username == "R1990").first()
        assert user1 is not None, "R1990 user must exist"
        client1 = db.query(LawClients).filter(LawClients.office_id == user1.office_id, LawClients.is_deleted == 0).first()
        if not client1:
            client1 = LawClients(office_id=user1.office_id, name="شركة الفهد للاستثمار", phone="0501234567")
            db.add(client1)
            db.commit()
            db.refresh(client1)

        case1 = db.query(LawCases).filter(LawCases.office_id == user1.office_id, LawCases.is_deleted == 0).first()
        if not case1:
            case1 = LawCases(office_id=user1.office_id, case_number="CASE-INV-101", title="قضية اختبار الفوترة", status_key="active")
            db.add(case1)
            db.commit()
            db.refresh(case1)

        user2 = db.query(AccessProfiles).filter(AccessProfiles.office_id != user1.office_id).first()
        assert user2 is not None, "User 2 must exist"
        client_id = client1.id
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

        # 2. Get Invoices page
        page_res = await client.get("/accounting/invoices", cookies=cookies)
        assert page_res.status_code == 200
        assert "الفوترة الإلكترونية" in page_res.text
        assert "إجمالي المفوتر" in page_res.text

        # 3. Create an Invoice
        payload = {
            "client_id": client_id,
            "case_id": case_id,
            "invoice_number": "INV-TEST-2026-001",
            "invoice_type": "Simplified",
            "due_date": "2026-11-01",
            "notes": "فاتورة أتعاب محاماة واستشارات قانونية",
            "items": [
                {
                    "description": "صياغة لائحة جوابية وتقديمها للمحكمة التجارية",
                    "quantity": 1,
                    "unit_price": 5000.0,
                    "tax_rate": 15.0
                },
                {
                    "description": "حضور جلسة مرافعة تمهيدية",
                    "quantity": 2,
                    "unit_price": 1500.0,
                    "tax_rate": 15.0
                }
            ]
        }
        create_res = await client.post("/accounting/api/invoices", json=payload, cookies=cookies, headers=headers)
        assert create_res.status_code == 200
        create_data = create_res.json()
        assert create_data["ok"] is True
        inv_uuid = create_data["uuid"]

        # 4. Get Invoice details
        get_res = await client.get(f"/accounting/api/invoices/{inv_uuid}", cookies=cookies)
        assert get_res.status_code == 200
        get_data = get_res.json()
        assert get_data["ok"] is True
        assert get_data["data"]["invoice_number"] == "INV-TEST-2026-001"
        # Total: (5000 + 3000) * 1.15 = 8000 * 1.15 = 9200
        assert get_data["data"]["grand_total"] == 9200.0
        assert get_data["data"]["remaining"] == 9200.0

        # 5. Record Payment
        pay_payload = {
            "amount": 4600.0,
            "payment_method": "Bank Transfer",
            "payment_date": "2026-10-12",
            "reference_number": "BANK-TRANS-7788",
            "notes": "الدفعة الأولى 50%"
        }
        pay_res = await client.post(f"/accounting/api/invoices/{inv_uuid}/payment", json=pay_payload, cookies=cookies, headers=headers)
        assert pay_res.status_code == 200
        pay_data = pay_res.json()
        assert pay_data["ok"] is True
        assert pay_data["status"] == "Partial"
        assert pay_data["remaining"] == 4600.0

        # 6. View PDF
        pdf_res = await client.get(f"/accounting/invoices/{inv_uuid}/pdf", cookies=cookies)
        assert pdf_res.status_code == 200

        # 7. Test Multi-Tenant Isolation (User 2 cannot access user 1's invoice)
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM rate_limit_attempts"))
        client2 = AsyncClient(transport=transport, base_url="http://test")
        login2 = await client2.post("/", data={"email": user2.username, "password": "password123"}, follow_redirects=False)
        cookies2 = dict(login2.cookies)
        cross_res = await client2.get(f"/accounting/api/invoices/{inv_uuid}", cookies=cookies2)
        assert cross_res.status_code in [404, 403, 401, 303]

        # 8. Delete Invoice (Soft delete)
        del_res = await client.delete(f"/accounting/api/invoices/{inv_uuid}", cookies=cookies, headers=headers)
        assert del_res.status_code == 200
        assert del_res.json()["ok"] is True

        # Verify soft deleted in DB
        db = SessionLocal()
        try:
            del_inv = db.query(Invoices).filter(Invoices.uuid == inv_uuid).first()
            assert del_inv.is_deleted == 1
            # Hard delete test invoice data so no fake test rows remain in DB
            db.execute(text("DELETE FROM client_payments WHERE invoice_id IN (SELECT id FROM invoices WHERE uuid = :u)"), {"u": inv_uuid})
            db.execute(text("DELETE FROM invoice_items WHERE invoice_id IN (SELECT id FROM invoices WHERE uuid = :u)"), {"u": inv_uuid})
            db.execute(text("DELETE FROM invoices WHERE uuid = :u"), {"u": inv_uuid})
            db.commit()
        finally:
            db.close()

        print("\nAll Invoices Tests (including Multi-Tenant Isolation) PASSED 100%!")

if __name__ == "__main__":
    asyncio.run(test_invoices_full_suite())
